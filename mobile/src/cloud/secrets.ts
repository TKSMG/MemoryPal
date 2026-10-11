/** The sign-in token lives in the phone's secure storage (iOS Keychain / Android Keystore). */
import * as SecureStore from 'expo-secure-store';

export async function readSecret(key: string): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}

export async function writeSecret(key: string, value: string | null): Promise<void> {
  if (value === null) await SecureStore.deleteItemAsync(key);
  else await SecureStore.setItemAsync(key, value);
}
