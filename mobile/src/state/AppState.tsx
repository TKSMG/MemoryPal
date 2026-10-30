/**
 * One MemoryStore for the app, plus phone-only preferences (appearance),
 * shared through React context. Screens re-render whenever either changes.
 */
import { createContext, ReactNode, useContext, useMemo, useSyncExternalStore } from 'react';
import { Alert, AppState as RNAppState } from 'react-native';

import { CloudAccount } from '../cloud/account';
import { CloudError, cloudConfigured, Session } from '../cloud/client';
import { MemoryStore } from '../core/store';
import { keyAdapter } from './storage';

export type ThemeChoice = 'system' | 'light' | 'dark';

export interface DevicePrefs {
  theme: ThemeChoice;
  haptics: boolean;
  /** Question ids ("<card id>:<type>") from the last quiz round, so the next one avoids them. */
  quiz_recent: string[];
  /**
   * AI features are on. Starts on (Kirthik's call, 2026-10-30): agreeing to
   * the Terms when creating or signing in to the account AI needs is the
   * consent. Turning it off in Settings is kept; turning it back on shows the AI screen.
   */
  ai_allowed: boolean;
  /** When they last allowed it on the AI screen (ISO time), or ''. */
  ai_allowed_at: string;
  /** A daily reminder when cards are due (asks for notification permission when turned on). */
  reminders: boolean;
  /** "HH:MM", one of REMINDER_TIMES. */
  reminder_time: string;
  /** Cards due today on the app icon. */
  badge: boolean;
}

const DEFAULT_PREFS: DevicePrefs = {
  theme: 'system', haptics: true, quiz_recent: [], ai_allowed: true, ai_allowed_at: '',
  reminders: false, reminder_time: '19:00', badge: true,
};

/** Preferences that belong to this phone, not the profile (so a backup never changes them). */
class PrefsStore {
  prefs: DevicePrefs = { ...DEFAULT_PREFS };
  version = 0;
  private listeners = new Set<() => void>();
  private adapter = keyAdapter('memorypal-device-prefs');

  constructor() {
    try {
      const raw = JSON.parse(this.adapter.load() ?? '{}');
      this.prefs = { ...DEFAULT_PREFS, ...(raw && typeof raw === 'object' ? raw : {}) };
      if (!Array.isArray(this.prefs.quiz_recent)) this.prefs.quiz_recent = [];
      this.prefs.quiz_recent = this.prefs.quiz_recent.map(String).slice(0, 60);
      this.prefs.ai_allowed = this.prefs.ai_allowed === true;
      this.prefs.reminders = this.prefs.reminders === true;
      this.prefs.badge = this.prefs.badge !== false;
      this.prefs.reminder_time = typeof this.prefs.reminder_time === 'string' ? this.prefs.reminder_time : '19:00';
    } catch {
      this.prefs = { ...DEFAULT_PREFS };
    }
  }

  set(changes: Partial<DevicePrefs>) {
    this.prefs = { ...this.prefs, ...changes };
    this.adapter.save(JSON.stringify(this.prefs));
    this.version += 1;
    this.listeners.forEach((listener) => listener());
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
}

const SYNC_AFTER_CHANGE_MS = 5_000;
const SYNC_EVERY_MS = 5 * 60_000;
const RETURN_SYNC_GAP_MS = 60_000;

/**
 * Keeps the signed-in profile in sync on its own: on launch, a few seconds
 * after a change, when the app is opened again or put away, and every five
 * minutes. "Sync now" is always there too, and automatic sync can be turned
 * off in Account & sync.
 */
export class SyncController {
  account = new CloudAccount();
  syncing = false;
  error = '';
  version = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private applying = false;
  private changedDuringSync = false;
  private lastReturnSync = 0;
  private listeners = new Set<() => void>();

  constructor(private store: MemoryStore) {
    store.subscribe(() => {
      if (this.applying || !this.autoReady) return;
      // A change made while a sync is on the network goes up right after it.
      if (this.syncing) this.changedDuringSync = true;
      else this.syncSoon(SYNC_AFTER_CHANGE_MS);
    });
    this.account.restore().then(() => {
      // Started fresh because the saved data was damaged: fetch everything back
      // from the cloud instead of syncing the empty phone as deletions.
      if (store.loadProblem) this.account.startOver();
      this.changed();
      if (this.autoReady) this.syncSoon(1000);
    });
    setInterval(() => this.autoReady && this.syncSoon(0), SYNC_EVERY_MS);
    RNAppState.addEventListener('change', (state) => {
      if (!this.autoReady) return;
      // Coming back fetches what other devices did; going away sends what
      // was done here, so the next device opened is already up to date.
      if (state === 'active') {
        // At most once a minute, like the desktop app, so flicking between
        // apps doesn't send a sync each time.
        if (Date.now() - this.lastReturnSync < RETURN_SYNC_GAP_MS) return;
        this.lastReturnSync = Date.now();
        this.syncSoon(500);
      }
      else if (state === 'background' && this.timer) this.syncSoon(0);
    });
  }

  /** Signed in (or Google Drive connected) with automatic sync on. */
  private get autoReady() {
    return this.account.canSync && this.account.state.auto_sync;
  }

  get auto() {
    return this.account.state.auto_sync;
  }

  setAuto(value: boolean) {
    this.account.setOption({ auto_sync: value });
    this.changed();
    if (value && this.account.canSync) this.syncSoon(0);
  }

  /** The first-launch sign-in page shows until someone signs in or chooses to go on without. */
  get needsSignInPrompt() {
    if (this.account.usesDrive) return this.account.restored && !this.account.drive && !this.account.state.account_prompted;
    return this.configured && this.account.restored && !this.account.signedIn && !this.account.state.account_prompted;
  }

  markPrompted() {
    if (this.account.state.account_prompted) return;
    this.account.setOption({ account_prompted: true });
    this.changed();
  }

  get configured() {
    return cloudConfigured();
  }

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private changed() {
    this.version += 1;
    this.listeners.forEach((listener) => listener());
  }

  syncSoon(delay: number) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.syncNow().catch(() => undefined);
    }, delay);
  }

  /** Sync now; resolves to an error message, or '' when everything is in step. */
  async syncNow(mode?: 'merge' | 'replace'): Promise<string> {
    if (this.syncing || !this.account.canSync) return this.error;
    if (mode === 'replace') {
      // Keep a copy of this phone's data before it's swapped for the account's.
      keyAdapter('memorypal-before-account-switch').save(JSON.stringify(this.store.payload()));
    }
    this.syncing = true;
    this.changedDuringSync = false;
    this.changed();
    try {
      await this.account.sync(
        this.store,
        (apply) => {
          this.applying = true;
          try {
            apply();
          } finally {
            this.applying = false;
          }
        },
        mode,
      );
      this.error = '';
    } catch (error) {
      this.error = error instanceof CloudError ? error.message : `Sync stopped: ${String(error)}`;
      if (error instanceof CloudError && error.code === 'other_account') this.askAboutOtherAccount();
    } finally {
      this.syncing = false;
      this.changed();
    }
    if (this.changedDuringSync && !this.error) this.syncSoon(SYNC_AFTER_CHANGE_MS);
    return this.error;
  }

  private asking = false;

  /** This phone last synced with another account: ask before mixing the two. */
  private askAboutOtherAccount() {
    if (this.asking) return;
    this.asking = true;
    const email = this.account.syncEmail || 'this account';
    const usesDrive = this.account.usesDrive;
    const done = () => {
      this.asking = false;
    };
    Alert.alert(
      'Different account',
      `The cards and progress on this phone came from a different account than ${email}.`,
      [
        { text: `Use ${email}'s cards`, onPress: () => { done(); this.syncNow('replace').catch(() => undefined); } },
        { text: `Add this phone's cards to ${email}`, onPress: () => { done(); this.syncNow('merge').catch(() => undefined); } },
        usesDrive
          ? { text: 'Disconnect', style: 'cancel', onPress: () => { done(); this.disconnectDrive().catch(() => undefined); } }
          : { text: 'Sign out', style: 'cancel', onPress: () => { done(); this.signOut().catch(() => undefined); } },
      ],
      { cancelable: false },
    );
  }

  async signedIn(session: Session) {
    await this.account.remember(session);
    this.account.setOption({ account_prompted: true });
    // syncNow marks itself as syncing before telling screens, so the
    // first-launch page waits for the account's data before moving on.
    await this.syncNow();
    this.changed();
  }

  /** Connect Google Drive (Google's own sign-in sheet), then sync straight away. */
  async connectDrive() {
    await this.account.connectDrive();
    this.account.setOption({ account_prompted: true });
    await this.syncNow();
    this.changed();
  }

  async disconnectDrive() {
    await this.account.disconnectDrive();
    this.error = '';
    this.changed();
  }

  async signOut() {
    await this.account.signOut();
    this.error = '';
    this.changed();
  }

  async deleteAccount() {
    await this.account.deleteAccount();
    this.error = '';
    this.changed();
  }
}

interface AppState {
  store: MemoryStore;
  prefs: PrefsStore;
  sync: SyncController;
}

const Context = createContext<AppState | null>(null);

let singleton: AppState | null = null;
function appState(): AppState {
  if (!singleton) {
    const store = new MemoryStore(keyAdapter('memorypal-data'), { deferWrites: true });
    // Leaving the app (home button, app switcher, a call) writes any change
    // still waiting, before the system can stop the app.
    RNAppState.addEventListener('change', (state) => {
      if (state !== 'active') store.flush();
    });
    singleton = { store, prefs: new PrefsStore(), sync: new SyncController(store) };
  }
  return singleton;
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const value = useMemo(() => appState(), []);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

function useAppState(): AppState {
  const value = useContext(Context);
  if (!value) throw new Error('useStore must be used inside AppStateProvider');
  return value;
}

/** The profile's store; the calling screen re-renders after every change. */
export function useStore(): MemoryStore {
  const { store } = useAppState();
  useSyncExternalStore(
    (listener) => store.subscribe(listener),
    () => store.version,
  );
  return store;
}

/** The account and sync status; the calling screen re-renders as they change. */
export function useSync(): SyncController {
  const { sync } = useAppState();
  useSyncExternalStore(sync.subscribe, () => sync.version);
  return sync;
}

export function usePrefs(): [DevicePrefs, (changes: Partial<DevicePrefs>) => void] {
  const { prefs } = useAppState();
  useSyncExternalStore(prefs.subscribe, () => prefs.version);
  return [prefs.prefs, (changes) => prefs.set(changes)];
}
