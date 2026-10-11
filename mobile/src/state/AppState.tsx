/**
 * One MemoryStore for the app, plus phone-only preferences (appearance),
 * shared through React context. Screens re-render whenever either changes.
 */
import { createContext, ReactNode, useContext, useMemo, useSyncExternalStore } from 'react';
import { AppState as RNAppState } from 'react-native';

import { CloudAccount } from '../cloud/account';
import { CloudError, cloudConfigured, Session } from '../cloud/client';
import { MemoryStore } from '../core/store';
import { keyAdapter } from './storage';

export type ThemeChoice = 'system' | 'light' | 'dark';

export interface DevicePrefs {
  theme: ThemeChoice;
  haptics: boolean;
}

const DEFAULT_PREFS: DevicePrefs = { theme: 'system', haptics: true };

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

const SYNC_AFTER_CHANGE_MS = 15_000;
const SYNC_EVERY_MS = 10 * 60_000;

/** Keeps the signed-in profile in sync: on launch, after changes, on return to the app, and every 10 minutes. */
export class SyncController {
  account = new CloudAccount();
  syncing = false;
  error = '';
  version = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private applying = false;
  private listeners = new Set<() => void>();

  constructor(private store: MemoryStore) {
    store.subscribe(() => {
      if (!this.applying && this.account.signedIn) this.syncSoon(SYNC_AFTER_CHANGE_MS);
    });
    this.account.restore().then(() => {
      this.changed();
      if (this.account.signedIn) this.syncSoon(1000);
    });
    setInterval(() => this.account.signedIn && this.syncSoon(0), SYNC_EVERY_MS);
    RNAppState.addEventListener('change', (state) => {
      if (state === 'active' && this.account.signedIn) this.syncSoon(500);
    });
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
  async syncNow(): Promise<string> {
    if (this.syncing || !this.configured || !this.account.signedIn) return this.error;
    this.syncing = true;
    this.changed();
    this.applying = true;
    try {
      await this.account.sync(this.store);
      this.error = '';
    } catch (error) {
      this.error = error instanceof CloudError ? error.message : `Sync stopped: ${String(error)}`;
    } finally {
      this.applying = false;
      this.syncing = false;
      this.changed();
    }
    return this.error;
  }

  async signedIn(session: Session) {
    await this.account.remember(session);
    this.changed();
    await this.syncNow();
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
    const store = new MemoryStore(keyAdapter('memorypal-data'));
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
