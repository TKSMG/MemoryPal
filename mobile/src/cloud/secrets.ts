/** The sign-in token lives in the phone's secure storage (iOS Keychain / Android Keystore). */
import * as SecureStore from 'expo-secure-store';

import { keyAdapter } from '../state/storage';

// The iOS Keychain outlives the app: after an uninstall and reinstall, the
// old install's sign-in would quietly come back (on a phone that may have
// changed hands). The app's own storage is wiped on uninstall, so a marker
// kept there tells a new install apart. An update from a version without the
// marker already has profile data (saved on every first launch), so it keeps
// its sign-in. This runs when the module loads, before any profile is saved.
const INSTALL_MARKER = 'memorypal-installed';
const PROFILE_DATA = 'memorypal-data'; // the profile's key in AppState.tsx
const LEFT_BY_EARLIER_INSTALLS = ['memorypal-account'];

function clearEarlierInstall(): Promise<void> {
  try {
    const marker = keyAdapter(INSTALL_MARKER);
    if (marker.load()) return Promise.resolve();
    const updated = keyAdapter(PROFILE_DATA).load() !== null;
    marker.save('1');
    if (updated) return Promise.resolve();
    return Promise.all(LEFT_BY_EARLIER_INSTALLS.map((key) => SecureStore.deleteItemAsync(key)))
      .then(() => undefined)
      .catch(() => undefined);
  } catch {
    return Promise.resolve(); // storage unreadable: leave things as they are
  }
}

const earlierInstallCleared = clearEarlierInstall();

export async function readSecret(key: string): Promise<string | null> {
  await earlierInstallCleared;
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}

export async function writeSecret(key: string, value: string | null): Promise<void> {
  await earlierInstallCleared;
  if (value === null) await SecureStore.deleteItemAsync(key);
  else await SecureStore.setItemAsync(key, value);
}
