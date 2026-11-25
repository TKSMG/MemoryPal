/**
 * The iPhone's audio session for read-aloud.
 *
 * iOS starts every app in the "solo ambient" category, which the Ring/Silent
 * switch (or Silent mode) mutes. The phone's voice (expo-speech) plays through
 * the app's own session, so with Silent on, read-aloud and classic Talk-back
 * made no sound at all. Before speaking, the session is set to "playback" with
 * the spoken-audio mode (what podcast and audiobook apps use): it plays with
 * Silent on and lowers other apps' sound instead of stopping it. Once nothing
 * has been said for a moment the session is handed back, so music comes back
 * up to full volume.
 *
 * The live AI tutor runs its own session (modules/live-audio); while it is on,
 * read-aloud leaves the session alone so the call isn't cut off.
 */
import { Platform } from 'react-native';

type SpeechModule = typeof import('expo-speech-recognition').ExpoSpeechRecognitionModule;

/** The native module that can set the session (it ships with the app), or null in Expo Go and tests. */
function sessionModule(): SpeechModule | null {
  if (Platform.OS !== 'ios') return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return (require('expo-speech-recognition') as typeof import('expo-speech-recognition')).ExpoSpeechRecognitionModule ?? null;
  } catch {
    return null;
  }
}

let liveHolds = 0;
let releaseTimer: ReturnType<typeof setTimeout> | null = null;

/** How long after the last words the session is handed back. */
export const RELEASE_AFTER_MS = 1500;

function cancelRelease() {
  if (releaseTimer) clearTimeout(releaseTimer);
  releaseTimer = null;
}

/**
 * Marks the live tutor's audio as on until the returned function is called.
 * Read-aloud then doesn't touch the session.
 */
export function holdForLive(): () => void {
  liveHolds += 1;
  cancelRelease();
  let released = false;
  return () => {
    if (released) return;
    released = true;
    liveHolds = Math.max(0, liveHolds - 1);
  };
}

export function liveHeld(): boolean {
  return liveHolds > 0;
}

/** Call just before the phone's voice speaks. */
export function prepareSpeech() {
  cancelRelease();
  // Set every time: Talk-back's listening and the tutor change the category.
  if (liveHolds > 0) return;
  const session = sessionModule();
  if (!session) return;
  try {
    session.setCategoryIOS({ category: 'playback', categoryOptions: ['duckOthers'], mode: 'spokenAudio' });
  } catch {
    // Leave the session as it is; speech still plays with the ringer on.
  }
}

/** Call once the voice has nothing left to say: hands the session back after a moment. */
export function releaseSpeechSoon(stillSpeaking: () => boolean) {
  cancelRelease();
  if (Platform.OS !== 'ios') return;
  releaseTimer = setTimeout(() => {
    releaseTimer = null;
    if (liveHolds > 0 || stillSpeaking()) return;
    const session = sessionModule();
    if (!session) return;
    try {
      session.setAudioSessionActiveIOS(false, { notifyOthersOnDeactivation: true });
    } catch {
      // Already inactive, or another part of the app is using it.
    }
  }, RELEASE_AFTER_MS);
}

/** For tests. */
export function resetAudioSessionForTests() {
  cancelRelease();
  liveHolds = 0;
}
