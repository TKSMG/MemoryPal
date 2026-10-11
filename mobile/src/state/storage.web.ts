/** In a browser, data lives in localStorage (expo-sqlite on web needs special server headers). */
import { StorageAdapter } from '../core/store';

export function keyAdapter(key: string): StorageAdapter {
  return {
    load: () => {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return null;
      }
    },
    save: (text: string) => {
      try {
        globalThis.localStorage?.setItem(key, text);
      } catch {
        // private mode or storage full: keep working in memory
      }
    },
  };
}
