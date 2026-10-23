/**
 * The phone's sign-in and sync, mirroring cloud.Account / sync_profile in
 * latest_app/memorypal/cloud.py. The sign-in token sits in secure storage;
 * the sync state (device id, pull position, last synced records) sits in the
 * app's key-value store.
 */
import { applyPlan, Entries, entriesOf, planSync, recordsFromPayload, Records, Remote, SyncPlan } from '../core/sync';
import { MemoryStore } from '../core/store';
import { uid } from '../core/models';
import { nowLabel } from '../core/dates';
import { keyAdapter } from '../state/storage';
import { CloudClient, cloudConfigured, CloudError, expiring, friendly, needsSecondStep, Session } from './client';
import { DriveFiles, FileStore, syncFiles } from './drive';
import { driveError } from './driveErrors';
import { connectGoogle, disconnectGoogle, googleAccessToken, googleConfigured } from './googleAuth';
import { readSecret, writeSecret } from './secrets';

const TOKEN_KEY = 'memorypal-account';
const OVERLAP_SECONDS = 120;
const SIGNED_OUT_CODES = ['refresh_token_not_found', 'refresh_token_already_used', 'session_not_found', 'unauthorized', 'invalid_grant'];

interface SavedSignIn {
  refresh_token: string;
  user_id: string;
  email: string;
}

export interface SyncState {
  device_id: string;
  user_id: string;
  cursor: string | null;
  base: Records;
  last_synced: string;
  /** Sync on its own after changes, on opening and every few minutes (on by default). */
  auto_sync: boolean;
  /** The first-launch sign-in page was answered (signed in, or chose to go on without). */
  account_prompted: boolean;
  /** Google Drive sync: the Google account, this phone's file there, and the versions of the files already read. */
  drive_user: string;
  drive_file: string;
  drive_seen: Record<string, string>;
  /** This phone's file: every record with its stamp (see core/sync.ts). */
  entries: Entries;
  /** The MemoryPal account whose records were merged into the drive... */
  moved_user: string;
  /** ... and still need removing from the MemoryPal cloud. */
  cloud_cleanup: boolean;
}

/** The Google account connected for Drive sync (the token itself stays with Google's sign-in). */
export interface DriveLink {
  user_id: string;
  email: string;
}

/** Pull from two minutes before the last position (see cloud.pull_since). */
export function pullSince(cursor: string | null): string | null {
  if (!cursor) return null;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$/.exec(cursor);
  if (!match) return null;
  // Date can't parse microseconds everywhere, so keep milliseconds only.
  const millis = (match[2] ?? '.000').slice(0, 4).padEnd(4, '0');
  const zone = !match[3] || match[3] === 'Z' ? 'Z' : match[3].length === 5 ? `${match[3].slice(0, 3)}:${match[3].slice(3)}` : match[3];
  const moment = new Date(`${match[1]}${millis}${zone}`);
  if (Number.isNaN(moment.getTime())) return null;
  return new Date(moment.getTime() - OVERLAP_SECONDS * 1000).toISOString();
}

export class CloudAccount {
  session: Session | null = null;
  saved: SavedSignIn | null = null;
  state: SyncState;
  private stateStore = keyAdapter('memorypal-sync-state');
  private driveStore = keyAdapter('memorypal-drive-link');
  drive: DriveLink | null = null;
  /** Bumped by forget(), so a refresh that finishes after Sign out can't sign the person back in. */
  private generation = 0;

  constructor(
    public client = new CloudClient(),
    private files: () => FileStore = () => new DriveFiles(googleAccessToken),
  ) {
    this.state = this.loadState();
    try {
      const link = JSON.parse(this.driveStore.load() ?? 'null');
      this.drive = link && typeof link.user_id === 'string' && link.user_id ? { user_id: link.user_id, email: String(link.email ?? '') } : null;
    } catch {
      this.drive = null;
    }
  }

  /** True once the remembered sign-in has been read, so screens can tell "signed out" from "not known yet". */
  restored = false;

  /** Read the remembered sign-in from secure storage. */
  async restore() {
    try {
      const raw = await readSecret(TOKEN_KEY);
      const data = raw ? JSON.parse(raw) : null;
      this.saved = data && data.refresh_token ? data : null;
    } catch {
      this.saved = null;
    }
    this.restored = true;
  }

  get signedIn() {
    return Boolean(this.session || this.saved);
  }

  get email() {
    return this.session?.email ?? this.saved?.email ?? '';
  }

  /** Keep a fresh session. A sign-in still waiting for its authenticator code is never saved. */
  async remember(session: Session) {
    if (needsSecondStep(session)) throw new CloudError(friendly('insufficient_aal'), 'insufficient_aal');
    this.session = session;
    this.saved = { refresh_token: session.refreshToken, user_id: session.userId, email: session.email };
    await writeSecret(TOKEN_KEY, JSON.stringify(this.saved));
    return session;
  }

  async forget() {
    this.generation += 1;
    this.session = null;
    this.saved = null;
    await writeSecret(TOKEN_KEY, null);
  }

  async activeSession(): Promise<Session> {
    if (this.session && !expiring(this.session)) return this.session;
    const refresh = this.session?.refreshToken || this.saved?.refresh_token;
    if (!refresh) throw new CloudError('Sign in to sync your cards.', 'signed_out');
    const generation = this.generation;
    let fresh: Session;
    try {
      fresh = await this.client.refresh(refresh);
    } catch (error) {
      if (error instanceof CloudError && SIGNED_OUT_CODES.includes(error.code) && generation === this.generation) await this.forget();
      throw error;
    }
    if (generation !== this.generation) throw new CloudError('Sign in to sync your cards.', 'signed_out');
    if (needsSecondStep(fresh)) {
      // Two-step sign-in was turned on from another device: this session can't
      // reach the data and has nowhere to type the code, so sign in again.
      await this.forget();
      throw new CloudError(friendly('two_step_now_on'), 'two_step_now_on');
    }
    return this.remember(fresh);
  }

  /** Sign out here and end the session on the server too, so an earlier copy of the sign-in stops working. */
  async signOut() {
    let session = this.session;
    if (!session && this.saved?.refresh_token) {
      try {
        session = await this.client.refresh(this.saved.refresh_token);
      } catch {
        session = null; // already ended, or offline: forget it here anyway
      }
    }
    try {
      if (session) await this.client.signOut(session);
    } finally {
      await this.forget();
    }
  }

  async deleteAccount() {
    await this.client.deleteAccount(await this.activeSession());
    await this.forget();
    this.useAccount('');
    this.saveState();
  }

  // ----------------------------------------------------------- sync state
  loadState(): SyncState {
    let raw: Partial<SyncState> = {};
    try {
      raw = JSON.parse(this.stateStore.load() ?? '{}') ?? {};
    } catch {
      raw = {};
    }
    return {
      device_id: String(raw.device_id || uid()),
      user_id: String(raw.user_id || ''),
      cursor: raw.cursor || null,
      base: raw.base && typeof raw.base === 'object' ? (raw.base as Records) : {},
      last_synced: String(raw.last_synced || ''),
      auto_sync: raw.auto_sync !== false,
      account_prompted: Boolean(raw.account_prompted),
      drive_user: String(raw.drive_user || ''),
      drive_file: String(raw.drive_file || ''),
      drive_seen: raw.drive_seen && typeof raw.drive_seen === 'object' ? (raw.drive_seen as Record<string, string>) : {},
      entries: entriesOf({ records: raw.entries }),
      moved_user: String(raw.moved_user || ''),
      cloud_cleanup: Boolean(raw.cloud_cleanup),
    };
  }

  /** Change a device setting kept with the sync state (auto sync, first-launch prompt). */
  setOption(changes: Partial<Pick<SyncState, 'auto_sync' | 'account_prompted'>>) {
    this.state = { ...this.state, ...changes };
    this.saveState();
  }

  saveState() {
    this.stateStore.save(JSON.stringify(this.state));
  }

  /** A different account starts its sync from scratch (a merge, never a wipe). */
  useAccount(userId: string) {
    if (userId !== this.state.user_id) {
      this.state = { ...this.state, user_id: userId, cursor: null, base: {} };
    }
  }

  /** A different Google account starts with a fresh file for this phone (a merge, never a wipe). */
  useDrive(userId: string) {
    if (userId !== this.state.drive_user) {
      this.state = { ...this.state, drive_user: userId, drive_file: '', drive_seen: {}, entries: {}, base: {} };
    }
  }

  // ------------------------------------------------------- Google Drive
  /** Sync goes through Google Drive when this build has it set up; the MemoryPal cloud then only keeps the account. */
  get usesDrive() {
    return googleConfigured();
  }

  get canSync() {
    return this.usesDrive ? Boolean(this.drive) : cloudConfigured() && this.signedIn;
  }

  /** The account the cards sync with. */
  get syncEmail() {
    return this.usesDrive ? this.drive?.email ?? '' : this.email;
  }

  async connectDrive(): Promise<DriveLink> {
    const link = await connectGoogle();
    this.drive = link;
    this.driveStore.save(JSON.stringify(link));
    return link;
  }

  async disconnectDrive() {
    this.drive = null;
    this.driveStore.save('null');
    await disconnectGoogle();
  }

  /**
   * After a backup is loaded or the phone is reset, the next sync merges with
   * the cloud as if for the first time, so cards missing here are fetched back
   * instead of being deleted on every other device.
   */
  startOver() {
    this.state = { ...this.state, cursor: null, base: {} };
    this.saveState();
  }

  /**
   * One full sync: pull, merge into the store, push, remember the new base.
   *
   * When this phone last synced with a different account, nothing is sent
   * until the person chooses (CloudError 'other_account'): 'merge' adds this
   * phone's cards to the new account, 'replace' swaps them for the account's
   * own. Without that, signing out of one account and into another quietly
   * copied the first account's cards into the second.
   */
  async sync(
    store: MemoryStore,
    applying: (apply: () => void) => void = (apply) => apply(),
    mode?: 'merge' | 'replace',
  ): Promise<{ pulled: number; pushed: number; applied: number }> {
    if (!this.usesDrive) return this.syncCloud(store, applying, mode);
    if (!this.drive) throw driveError('drive_not_linked');
    const accountUser = this.session?.userId ?? this.saved?.user_id ?? '';
    const moving = cloudConfigured() && this.signedIn && accountUser !== this.state.moved_user;
    if (moving) {
      // Moving to Google Drive: bring this phone up to date with the MemoryPal
      // cloud one last time, then merge everything into the drive as if new,
      // so nothing only the cloud had is lost.
      await this.syncCloud(store, applying, mode);
      this.state = { ...this.state, base: {} };
      mode = undefined; // an account choice above was about the MemoryPal cloud
    }
    const result = await this.syncDrive(store, applying, mode);
    if (moving || this.state.cloud_cleanup) {
      // The records are in the drive now: remove them from the MemoryPal cloud
      // (tried again after later syncs until it works).
      if (moving) this.state = { ...this.state, moved_user: accountUser, cloud_cleanup: true };
      try {
        await this.client.deleteSyncRecords(await this.activeSession());
        this.state = { ...this.state, cloud_cleanup: false };
      } catch {
        // offline or signed out: tried again next time
      }
      this.saveState();
    }
    return result;
  }

  /** Merge `remote` into the store; returns the plan. No await, so nothing the person does slips in between. */
  private mergeInto(store: MemoryStore, remote: Remote, applying: (apply: () => void) => void, mode?: 'merge' | 'replace'): SyncPlan {
    let payload = store.payload() as unknown as Record<string, unknown>;
    // Replacing starts from an empty phone (settings stay until the account's own arrive).
    if (mode === 'replace') payload = { ...payload, cards: [], captures: [], decks: [], activity: {}, practiced: 0 };
    const local = recordsFromPayload(payload, this.state.device_id, this.state.base);
    const plan = planSync(local, this.state.base, remote);
    if (Object.keys(plan.apply).length || mode === 'replace') applying(() => store.replaceWith(applyPlan(payload, local, plan)));
    return plan;
  }

  /** One sync through Google Drive (as drive.sync_files on the desktop). */
  private async syncDrive(store: MemoryStore, applying: (apply: () => void) => void, mode?: 'merge' | 'replace') {
    const link = this.drive as DriveLink;
    if (this.state.drive_user && this.state.drive_user !== link.user_id && !mode) {
      throw new CloudError(friendly('other_account'), 'other_account');
    }
    this.useDrive(link.user_id);
    const { state, plan, remote } = await syncFiles(this.files(), this.state, (remote) => this.mergeInto(store, remote, applying, mode));
    this.state = { ...this.state, ...state, base: plan.final, last_synced: nowLabel() };
    this.saveState();
    return { pulled: Object.keys(remote).length, pushed: Object.keys(plan.push).length, applied: Object.keys(plan.apply).length };
  }

  /** One sync with the MemoryPal cloud (Supabase). */
  private async syncCloud(
    store: MemoryStore,
    applying: (apply: () => void) => void,
    mode?: 'merge' | 'replace',
  ): Promise<{ pulled: number; pushed: number; applied: number }> {
    const session = await this.activeSession();
    if (this.state.user_id && this.state.user_id !== session.userId && !mode) {
      throw new CloudError(friendly('other_account'), 'other_account');
    }
    this.useAccount(session.userId);
    const rows = await this.client.pull(session, pullSince(this.state.cursor));
    const remote: Remote = Object.create(null); // a row keyed __proto__ can't touch the prototype
    let cursor = this.state.cursor;
    for (const [key, data, updatedAt] of rows) {
      remote[key] = data;
      if (updatedAt && (cursor === null || updatedAt > cursor)) cursor = updatedAt;
    }
    const plan = this.mergeInto(store, remote, applying, mode);
    if (Object.keys(plan.push).length) await this.client.push(session, plan.push);
    this.state = { ...this.state, base: plan.final, cursor, last_synced: nowLabel() };
    this.saveState();
    return { pulled: Object.keys(remote).length, pushed: Object.keys(plan.push).length, applied: Object.keys(plan.apply).length };
  }
}
