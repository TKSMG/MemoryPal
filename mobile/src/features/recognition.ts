/**
 * The phone's own speech recognition (expo-speech-recognition) as Talk-back's
 * "ears". Recognition runs on the device whenever the OS supports it for the
 * language, so answers don't leave the phone; otherwise the system recogniser
 * is used as is.
 */
import { Platform } from 'react-native';

import type { Ears, ListenResult } from './talkback';

export type Readiness = 'ready' | 'unavailable' | 'denied';

type SpeechModule = typeof import('expo-speech-recognition').ExpoSpeechRecognitionModule;

/**
 * The native module, loaded on first use: Expo Go doesn't include it, and a
 * top-level import would crash the Talk-back screen there. null when missing.
 */
function speech(): SpeechModule | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return (require('expo-speech-recognition') as typeof import('expo-speech-recognition')).ExpoSpeechRecognitionModule ?? null;
  } catch {
    return null;
  }
}

function locale(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().locale || 'en-US';
  } catch {
    return 'en-US';
  }
}

/** Checks recognition is there and asks for the microphone and speech permissions. */
export async function prepareRecognition(): Promise<Readiness> {
  try {
    const recognizer = speech();
    if (!recognizer || !recognizer.isRecognitionAvailable()) return 'unavailable';
    const permission = await recognizer.requestPermissionsAsync();
    return permission.granted ? 'ready' : 'denied';
  } catch {
    return 'unavailable';
  }
}

export function makeEars(): Ears {
  const recognizer = speech();
  let onDevice = (() => {
    try {
      return !!recognizer?.supportsOnDeviceRecognition();
    } catch {
      return false;
    }
  })();
  let finish: ((result: ListenResult) => void) | null = null;

  const listenOnce = (hints: string[]): Promise<ListenResult> =>
    new Promise((resolve) => {
      if (!recognizer) {
        resolve({ error: 'unavailable' });
        return;
      }
      let best = '';
      const subscriptions = [
        recognizer.addListener('result', (event) => {
          best = event.results[0]?.transcript ?? best;
          if (event.isFinal) done({ transcript: best });
        }),
        recognizer.addListener('error', (event) => done(best ? { transcript: best } : { error: event.error })),
        recognizer.addListener('end', () => done(best ? { transcript: best } : { error: 'no-speech' })),
      ];
      function done(result: ListenResult) {
        if (finish !== done) return;
        finish = null;
        subscriptions.forEach((subscription) => subscription.remove());
        resolve(result);
      }
      finish = done;
      try {
        recognizer.start({
          lang: locale(),
          interimResults: true,
          continuous: false,
          maxAlternatives: 1,
          requiresOnDeviceRecognition: onDevice,
          addsPunctuation: false,
          contextualStrings: hints.slice(0, 20),
          // Keep the spoken questions on the loudspeaker after the mic opens.
          iosCategory: { category: 'playAndRecord', categoryOptions: ['defaultToSpeaker', 'allowBluetooth'], mode: 'measurement' },
          iosTaskHint: 'confirmation',
        });
      } catch {
        done({ error: 'unavailable' });
      }
    });

  return {
    async listen(hints) {
      const result = await listenOnce(hints);
      // No on-device model for this language yet (common on Android): use
      // the system recogniser for the rest of the session.
      if ('error' in result && onDevice && (result.error === 'language-not-supported' || (Platform.OS === 'android' && result.error === 'network'))) {
        onDevice = false;
        return listenOnce(hints);
      }
      return result;
    },
    stop() {
      if (!finish) return;
      const pending = finish;
      try {
        recognizer?.abort();
      } catch {
        // already stopped
      }
      pending({ error: 'aborted' });
    },
  };
}
