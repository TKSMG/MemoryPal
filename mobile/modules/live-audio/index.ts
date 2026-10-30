/**
 * The native side of live Talk-back (modules/live-audio): an echo-cancelled
 * microphone and a speech player. Audio crosses as base64 PCM: 16 kHz from
 * the microphone, 24 kHz to the player (what Gemini Live sends).
 */
import { requireOptionalNativeModule } from 'expo-modules-core';

export interface LiveAudioEvents {
  onMic: (event: { data: string }) => void;
  onLevel: (event: { who: 'you' | 'tutor'; level: number }) => void;
}

export interface LiveAudioNative {
  start(): Promise<boolean>;
  setMuted(muted: boolean): void;
  play(base64: string): void;
  clear(): void;
  stop(): void;
  addListener<K extends keyof LiveAudioEvents>(name: K, listener: LiveAudioEvents[K]): { remove(): void };
}

/** null in Expo Go, the browser and tests, where the module isn't built in. */
export const LiveAudio = requireOptionalNativeModule<LiveAudioNative>('LiveAudio');
