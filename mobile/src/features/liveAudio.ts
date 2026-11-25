/**
 * The phone's audio for live Talk-back, through the app's own native module
 * (modules/live-audio): an echo-cancelled microphone, so the tutor doesn't
 * hear itself on the loudspeaker and stop mid-sentence, and a speech player
 * that can drop unplayed speech the moment the learner talks over it.
 *
 * Expo Go and the browser don't include the module: there, live Talk-back
 * isn't offered and classic Talk-back is used.
 */
import { Platform } from 'react-native';

import { LiveAudio } from '../../modules/live-audio';
import { holdForLive } from './audioSession';
import { pcmMs } from './pcm';
import { MODEL_RATE, type LiveAudio as LiveAudioPort } from './liveTutor';

/**
 * On an iPhone the call's audio set-up (echo cancelling, the loudspeaker
 * route) keeps settling for a moment after it starts; the tutor's first
 * words wait this long so they aren't spoken into a player that is about to
 * restart.
 */
export const IOS_SETTLE_MS = 350;

/** True when this build can hold a live conversation. */
export function liveAudioAvailable(): boolean {
  return (Platform.OS === 'ios' || Platform.OS === 'android') && LiveAudio !== null;
}

export type MicPermission = 'granted' | 'denied' | 'unavailable';

/** Asks for the microphone (the same permission classic Talk-back uses). */
export async function prepareLiveMic(): Promise<MicPermission> {
  if (!liveAudioAvailable()) return 'unavailable';
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const speech = (require('expo-speech-recognition') as typeof import('expo-speech-recognition')).ExpoSpeechRecognitionModule;
    const permission = await speech.requestMicrophonePermissionsAsync();
    return permission.granted ? 'granted' : 'denied';
  } catch {
    return 'unavailable';
  }
}

/**
 * The microphone and player. The picture's loudness comes from the tutor
 * (liveTutor.voice()), timed to when the speech actually plays.
 */
export function makeLiveAudio(native = LiveAudio, now: () => number = () => Date.now()): LiveAudioPort | null {
  if (!native || !liveAudioAvailable()) return null;
  let subscriptions: { remove(): void }[] = [];
  let started = false;
  let stopped = false;
  // The tutor's greeting can arrive while the audio session is still starting
  // (iOS can take most of a second): keep it and play it once the player is up,
  // so the first words aren't lost.
  let waiting: string[] = [];
  // While the call is on, read-aloud keeps its hands off the audio session.
  let release: (() => void) | null = null;
  // Speech handed to the player that may not have played yet, with when it
  // should finish. If iOS restarts the player (the audio route changed, or the
  // call set-up settled), that speech is gone, so it is played again.
  let recent: { data: string; end: number }[] = [];
  let until = 0;
  const replay = () => {
    const at = now();
    recent = recent.filter((chunk) => chunk.end > at);
    until = at;
    const again = recent;
    recent = [];
    again.forEach((chunk) => {
      until += pcmMs(chunk.data, MODEL_RATE);
      recent.push({ data: chunk.data, end: until });
      native.play(chunk.data);
    });
  };
  return {
    async start(onMic) {
      release = holdForLive();
      subscriptions.push(native.addListener('onMic', (event) => onMic(event.data)));
      subscriptions.push(native.addListener('onRestart', () => {
        if (started && !stopped) replay();
      }));
      await native.start();
      if (Platform.OS === 'ios' && !stopped) await new Promise((done) => setTimeout(done, IOS_SETTLE_MS));
      if (stopped) {
        // Stopped (End, or leaving the screen) while the microphone was still
        // starting: the native stop() then had nothing to stop, so stop it now
        // instead of leaving the microphone on.
        native.stop();
        release?.();
        release = null;
        return;
      }
      started = true;
      const queued = waiting;
      waiting = [];
      queued.forEach((chunk) => native.play(chunk));
    },
    setMuted(muted) {
      if (started) native.setMuted(muted);
    },
    play(base64) {
      if (stopped) return;
      const at = now();
      until = Math.max(until, at) + pcmMs(base64, MODEL_RATE);
      recent = recent.filter((chunk) => chunk.end > at);
      recent.push({ data: base64, end: until });
      if (started) native.play(base64);
      else waiting.push(base64);
    },
    clear() {
      waiting = [];
      recent = [];
      until = now();
      if (started) native.clear();
    },
    stop() {
      stopped = true;
      waiting = [];
      recent = [];
      subscriptions.forEach((subscription) => subscription.remove());
      subscriptions = [];
      // Gives the audio session back, so read-aloud and other apps sound normal again.
      native.stop();
      started = false;
      release?.();
      release = null;
    },
  };
}
