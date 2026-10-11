/** Read aloud and gentle haptics. Read aloud uses the phone's own voice, offline. */
import * as Haptics from 'expo-haptics';
import * as Speech from 'expo-speech';
import { Alert, Platform } from 'react-native';

export function speak(text: string, slow = false) {
  Speech.stop();
  if (text.trim()) Speech.speak(text, { rate: slow ? 0.8 : 1.0 });
}

export function stopSpeaking() {
  Speech.stop();
}

export function tap(enabled = true) {
  if (enabled && Platform.OS !== 'web') Haptics.selectionAsync().catch(() => undefined);
}

/** A confirmation that works on phones and in a browser. */
export function confirm(title: string, message: string, confirmLabel: string, destructive = false): Promise<boolean> {
  if (Platform.OS === 'web') {
    return Promise.resolve(globalThis.confirm?.(`${title}\n\n${message}`) ?? false);
  }
  return new Promise((resolve) => {
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: confirmLabel, style: destructive ? 'destructive' : 'default', onPress: () => resolve(true) },
    ], { cancelable: true, onDismiss: () => resolve(false) });
  });
}

export function notify(title: string, message: string) {
  if (Platform.OS === 'web') globalThis.alert?.(`${title}\n\n${message}`);
  else Alert.alert(title, message);
}
