/** On phones, data lives in Expo's SQLite-backed key-value store (survives restarts and updates). */
import Storage from 'expo-sqlite/kv-store';

import { StorageAdapter } from '../core/store';

export function keyAdapter(key: string): StorageAdapter {
  return {
    load: () => Storage.getItemSync(key),
    save: (text: string) => Storage.setItemSync(key, text),
  };
}
