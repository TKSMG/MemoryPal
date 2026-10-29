/**
 * The phone's audio for live Talk-back, through @speechmatics/expo-two-way-audio:
 * an echo-cancelled microphone (so the tutor doesn't hear itself on the
 * loudspeaker and stop mid-sentence) and a player, both 16 kHz PCM.
 *
 * Loaded on first use: Expo Go and the browser don't include the native
 * module, and a top-level import would crash the screen there. On Android the
 * module needs Android 10 or later.
 */
import { Platform } from 'react-native';

import type { LiveAudio } from './liveTutor';

type TwoWay = typeof import('@speechmatics/expo-two-way-audio');

function module(): TwoWay | null {
  if (Platform.OS !== 'ios' && Platform.OS !== 'android') return null;
  if (Platform.OS === 'android' && Number(Platform.Version) < 29) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const twoWay = require('@speechmatics/expo-two-way-audio') as TwoWay;
    return typeof twoWay?.playPCMData === 'function' ? twoWay : null;
  } catch {
    return null;
  }
}

/** True when this build can hold a live conversation. */
export function liveAudioAvailable(): boolean {
  return module() !== null;
}

export type MicPermission = 'granted' | 'denied' | 'unavailable';

export async function prepareLiveMic(): Promise<MicPermission> {
  const twoWay = module();
  if (!twoWay) return 'unavailable';
  try {
    const permission = await twoWay.requestMicrophonePermissionsAsync();
    return permission.granted ? 'granted' : 'denied';
  } catch {
    return 'unavailable';
  }
}

/**
 * The microphone and player. `onLevel` gets 0..1 loudness for the picture:
 * `who` is 'you' for the microphone and 'tutor' for the speaker.
 */
export function makeLiveAudio(onLevel?: (who: 'you' | 'tutor', level: number) => void): LiveAudio | null {
  const twoWay = module();
  if (!twoWay) return null;
  let subscriptions: { remove(): void }[] = [];
  let started = false;
  const listen = <K extends keyof import('@speechmatics/expo-two-way-audio').ExpoTwoWayAudioEventMap>(name: K, handler: (event: import('@speechmatics/expo-two-way-audio').ExpoTwoWayAudioEventMap[K]) => void) => {
    const subscription = twoWay.addExpoTwoWayAudioEventListener(name, handler);
    if (subscription && typeof subscription.remove === 'function') subscriptions.push(subscription);
  };
  return {
    async start(onMic) {
      await twoWay.initialize();
      started = true;
      listen('onMicrophoneData', (event) => onMic(event.data));
      if (onLevel) {
        listen('onInputVolumeLevelData', (event) => onLevel('you', event.data));
        listen('onOutputVolumeLevelData', (event) => onLevel('tutor', event.data));
      }
      twoWay.toggleRecording(true);
    },
    setMuted(muted) {
      if (started) twoWay.toggleRecording(!muted);
    },
    play(pcm) {
      if (started) twoWay.playPCMData(pcm);
    },
    stop() {
      subscriptions.forEach((subscription) => subscription.remove());
      subscriptions = [];
      if (!started) return;
      started = false;
      try {
        twoWay.toggleRecording(false);
      } finally {
        // Gives the audio session back, so read-aloud and other apps sound normal again.
        twoWay.tearDown();
      }
    },
  };
}
