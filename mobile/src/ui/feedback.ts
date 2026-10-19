/** Read aloud and gentle haptics. Read aloud uses the phone's own voice, offline. */
import * as Haptics from 'expo-haptics';
import * as Speech from 'expo-speech';
import { Alert, Platform } from 'react-native';

// Which speaker button (if any) started the voice that is talking now, so
// only that button shows "Stop" and a screen can stop its own speech.
let owner: object | null = null;
const listeners = new Set<() => void>();

function setOwner(next: object | null) {
  if (owner === next) return;
  owner = next;
  listeners.forEach((listener) => listener());
}

export function speakingOwner(): object | null {
  return owner;
}

export function onSpeakingChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function rate(slow: boolean): number {
  return slow ? 0.8 : 1.0;
}

/** Says `text`, cutting off anything already being said. `who` marks the button that asked. */
export function speak(text: string, slow = false, who: object | null = null) {
  Speech.stop();
  if (!text.trim()) {
    setOwner(null);
    return;
  }
  setOwner(who);
  const finished = () => {
    if (owner === who) setOwner(null);
  };
  Speech.speak(text, { rate: rate(slow), onDone: finished, onStopped: finished, onError: finished });
}

/** Says `text` and resolves when it has been said (or was stopped). */
export function speakAsync(text: string, slow = false): Promise<void> {
  return new Promise((resolve) => {
    Speech.stop();
    setOwner(null);
    if (!text.trim()) return resolve();
    Speech.speak(text, { rate: rate(slow), onDone: () => resolve(), onStopped: () => resolve(), onError: () => resolve() });
  });
}

export function stopSpeaking() {
  Speech.stop();
  setOwner(null);
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
