/** Read aloud and gentle haptics. Read aloud uses the phone's own voice, offline. */
import * as Haptics from 'expo-haptics';
import * as Speech from 'expo-speech';
import { Alert, Platform } from 'react-native';

import { prepareSpeech, releaseSpeechSoon } from '../features/audioSession';

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

// Utterances handed to the voice that haven't finished yet. Only then does a
// new one stop the voice first: on iPhone, stopping the voice and speaking
// straight away often lost the new words too (read-aloud and Talk-back went
// quiet), so after a real stop the next words wait a moment.
const inFlight = new Set<object>();
let stoppedAt = -Infinity;
let pending: ReturnType<typeof setTimeout> | null = null;
let pendingCancel: (() => void) | null = null;
export const RESTART_GAP_MS = 150;
// Bumped by every new utterance, so a late "stopped" from older words is told apart.
let serial = 0;

function now(): number {
  return Date.now();
}

function halt() {
  if (pending) clearTimeout(pending);
  pending = null;
  const cancel = pendingCancel;
  pendingCancel = null;
  cancel?.();
  if (inFlight.size > 0) {
    inFlight.clear();
    stoppedAt = now();
    Speech.stop();
  }
}

/**
 * Says `text` after cutting off anything being said; `done` runs once it was
 * said, stopped or failed (always exactly once).
 */
function say(text: string, slow: boolean, done: () => void) {
  halt();
  serial += 1;
  if (!text.trim()) return done();
  let settled = false;
  const finish = () => {
    if (settled) return;
    settled = true;
    // A stopped utterance was already taken off the list, so it never counts against a newer one.
    inFlight.delete(token);
    if (inFlight.size === 0 && !pending) releaseSpeechSoon(() => inFlight.size > 0 || pending !== null);
    done();
  };
  const token = {};
  const go = () => {
    pending = null;
    pendingCancel = null;
    prepareSpeech();
    inFlight.add(token);
    Speech.speak(text, { rate: rate(slow), onDone: finish, onStopped: finish, onError: finish });
  };
  const wait = Platform.OS === 'ios' ? RESTART_GAP_MS - (now() - stoppedAt) : 0;
  if (wait > 0) {
    pending = setTimeout(go, wait);
    pendingCancel = finish;
  } else go();
}

/** Says `text`, cutting off anything already being said. `who` marks the button that asked. */
export function speak(text: string, slow = false, who: object | null = null) {
  if (!text.trim()) {
    halt();
    setOwner(null);
    return;
  }
  const mine = serial + 1; // what say() makes it
  say(text, slow, () => {
    if (serial === mine && owner === who) setOwner(null);
  });
  setOwner(who);
}

/** Says `text` and resolves when it has been said (or was stopped). */
export function speakAsync(text: string, slow = false): Promise<void> {
  return new Promise((resolve) => {
    setOwner(null);
    say(text, slow, resolve);
  });
}

export function stopSpeaking() {
  halt();
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
