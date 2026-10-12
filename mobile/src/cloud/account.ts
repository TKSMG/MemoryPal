/**
 * The phone's sign-in and sync, mirroring cloud.Account / sync_profile in
 * latest_app/memorypal/cloud.py. The sign-in token sits in secure storage;
 * the sync state (device id, pull position, last synced records) sits in the
 * app's key-value store.
 */
import { applyPlan, planSync, recordsFromPayload, Records, Remote } from '../core/sync';
import { MemoryStore } from '../core/store';
import { uid } from '../core/models';
import { nowLabel } from '../core/dates';
import { keyAdapter } from '../state/storage';
import { CloudClient, CloudError, expiring, friendly, needsSecondStep, Session } from './client';
import { readSecret, writeSecret } from './secrets';

const TOKEN_KEY = 'memorypal-account';
const OVERLAP_SECONDS = 120;
const SIGNED_OUT_CODES = ['refresh_token_not_found', 'session_not_found', 'unauthorized', 'invalid_grant'];

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

  constructor(public client = new CloudClient()) {
    this.state = this.loadState();
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
    this.session = null;
    this.saved = null;
    await writeSecret(TOKEN_KEY, null);
  }

  async activeSession(): Promise<Session> {
    if (this.session && !expiring(this.session)) return this.session;
    const refresh = this.session?.refreshToken || this.saved?.refresh_token;
    if (!refresh) throw new CloudError('Sign in to sync your cards.', 'signed_out');
    try {
      return await this.remember(await this.client.refresh(refresh));
    } catch (error) {
      if (error instanceof CloudError && SIGNED_OUT_CODES.includes(error.code)) await this.forget();
      throw error;
    }
  }

  async signOut() {
    if (this.session) await this.client.signOut(this.session);
    await this.forget();
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

  /**
   * After a backup is loaded or the phone is reset, the next sync merges with
   * the cloud as if for the first time, so cards missing here are fetched back
   * instead of being deleted on every other device.
   */
  startOver() {
    this.state = { ...this.state, cursor: null, base: {} };
    this.saveState();
  }

  /** One full sync: pull, merge into the store, push, remember the new base. */
  async sync(store: MemoryStore, applying: (apply: () => void) => void = (apply) => apply()): Promise<{ pulled: number; pushed: number; applied: number }> {
    const session = await this.activeSession();
    this.useAccount(session.userId);
    const rows = await this.client.pull(session, pullSince(this.state.cursor));
    const remote: Remote = {};
    let cursor = this.state.cursor;
    for (const [key, data, updatedAt] of rows) {
      remote[key] = data;
      if (updatedAt && (cursor === null || updatedAt > cursor)) cursor = updatedAt;
    }
    // Reading, merging and writing happen with no await in between, so
    // nothing the person does can slip between them.
    const payload = store.payload() as unknown as Record<string, unknown>;
    const local = recordsFromPayload(payload, this.state.device_id, this.state.base);
    const plan = planSync(local, this.state.base, remote);
    if (Object.keys(plan.apply).length) applying(() => store.replaceWith(applyPlan(payload, local, plan)));
    if (Object.keys(plan.push).length) await this.client.push(session, plan.push);
    this.state = { ...this.state, base: plan.final, cursor, last_synced: nowLabel() };
    this.saveState();
    return { pulled: Object.keys(remote).length, pushed: Object.keys(plan.push).length, applied: Object.keys(plan.apply).length };
  }
}
