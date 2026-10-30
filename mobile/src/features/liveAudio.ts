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
import type { LiveAudio as LiveAudioPort } from './liveTutor';

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
 * The microphone and player. `onLevel` gets 0..1 loudness for the picture:
 * `who` is 'you' for the microphone and 'tutor' for the speaker.
 */
export function makeLiveAudio(onLevel?: (who: 'you' | 'tutor', level: number) => void): LiveAudioPort | null {
  const native = LiveAudio;
  if (!native || !liveAudioAvailable()) return null;
  let subscriptions: { remove(): void }[] = [];
  let started = false;
  return {
    async start(onMic) {
      subscriptions.push(native.addListener('onMic', (event) => onMic(event.data)));
      if (onLevel) subscriptions.push(native.addListener('onLevel', (event) => onLevel(event.who, event.level)));
      await native.start();
      started = true;
    },
    setMuted(muted) {
      if (started) native.setMuted(muted);
    },
    play(base64) {
      if (started) native.play(base64);
    },
    clear() {
      if (started) native.clear();
    },
    stop() {
      subscriptions.forEach((subscription) => subscription.remove());
      subscriptions = [];
      // Gives the audio session back, so read-aloud and other apps sound normal again.
      native.stop();
      started = false;
    },
  };
}
