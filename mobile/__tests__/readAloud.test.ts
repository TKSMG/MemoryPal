/** Read-aloud: the iPhone audio session and the stop-then-speak timing (expo-speech and the session module mocked). */
import { Platform } from 'react-native';

type Callbacks = { onDone?: () => void; onStopped?: () => void; onError?: () => void };
const spoken: { text: string; options: Callbacks }[] = [];
const calls: string[] = [];

jest.mock('expo-haptics', () => ({ selectionAsync: jest.fn(() => Promise.resolve()) }));
jest.mock('expo-speech', () => ({
  speak: (text: string, options: Callbacks) => {
    calls.push(`speak:${text}`);
    spoken.push({ text, options });
  },
  stop: () => {
    calls.push('stop');
    // Like the phone: whatever was speaking reports "stopped" a little later.
    const stopped = spoken.splice(0);
    setTimeout(() => stopped.forEach((s) => s.options.onStopped?.()), 5);
  },
}));
jest.mock('expo-speech-recognition', () => ({
  ExpoSpeechRecognitionModule: {
    setCategoryIOS: (options: { category: string; mode: string; categoryOptions: string[] }) => calls.push(`category:${options.category}/${options.mode}/${options.categoryOptions.join(',')}`),
    setAudioSessionActiveIOS: (value: boolean) => calls.push(`active:${value}`),
  },
}));

// eslint-disable-next-line import/first
import { holdForLive, RELEASE_AFTER_MS, resetAudioSessionForTests } from '../src/features/audioSession';
// eslint-disable-next-line import/first
import { RESTART_GAP_MS, speak, speakAsync, speakingOwner, stopSpeaking } from '../src/ui/feedback';

function finishSpeaking() {
  spoken.splice(0).forEach((s) => s.options.onDone?.());
}

describe('read aloud on iPhone', () => {
  const realOS = Platform.OS;
  let runs = 0;
  beforeEach(() => {
    jest.useFakeTimers();
    // Each test's fake clock starts later than the last one's ended.
    jest.setSystemTime(Date.now() + 1_000_000 * ++runs);
    (Platform as { OS: string }).OS = 'ios';
    stopSpeaking();
    jest.advanceTimersByTime(RELEASE_AFTER_MS + RESTART_GAP_MS);
    spoken.length = 0;
    calls.length = 0;
    resetAudioSessionForTests();
  });
  afterEach(() => {
    stopSpeaking();
    jest.advanceTimersByTime(RELEASE_AFTER_MS + RESTART_GAP_MS);
    jest.useRealTimers();
    (Platform as { OS: string }).OS = realOS;
  });

  test('plays with Silent mode on: the session is set to spoken-audio playback first', () => {
    speak('Capital of France?');
    expect(calls).toEqual(['category:playback/spokenAudio/duckOthers', 'speak:Capital of France?']);
  });

  test('nothing is stopped when nothing is being said (no lost first words)', () => {
    stopSpeaking();
    speak('One');
    expect(calls).not.toContain('stop');
    expect(calls[calls.length - 1]).toBe('speak:One');
  });

  test('after a real stop the next words wait a moment, then play', () => {
    speak('One');
    calls.length = 0;
    speak('Two');
    expect(calls).toEqual(['stop']);
    jest.advanceTimersByTime(RESTART_GAP_MS);
    expect(calls).toEqual(['stop', 'category:playback/spokenAudio/duckOthers', 'speak:Two']);
  });

  test('a late "stopped" from the old words does not cut the new ones short', async () => {
    const owner = {};
    speak('One', false, owner);
    speak('Two', false, owner);
    jest.advanceTimersByTime(RESTART_GAP_MS);
    expect(speakingOwner()).toBe(owner);
    jest.advanceTimersByTime(10); // the old utterance's onStopped arrives now
    expect(speakingOwner()).toBe(owner);
    finishSpeaking();
    expect(speakingOwner()).toBe(null);
  });

  test('speakAsync resolves once said, and when stopped before it started', async () => {
    const said = speakAsync('One');
    finishSpeaking();
    await said;
    speak('Two');
    const waiting = speakAsync('Three');
    stopSpeaking();
    await waiting;
    expect(calls.filter((c) => c === 'speak:Three')).toHaveLength(0);
  });

  test('the session is handed back after the last words, so music comes back up', () => {
    speak('One');
    finishSpeaking();
    jest.advanceTimersByTime(RELEASE_AFTER_MS - 10);
    expect(calls).not.toContain('active:false');
    jest.advanceTimersByTime(20);
    expect(calls).toContain('active:false');
  });

  test('while the live tutor is on, read-aloud leaves its session alone', () => {
    const release = holdForLive();
    speak('One');
    finishSpeaking();
    jest.advanceTimersByTime(RELEASE_AFTER_MS * 2);
    expect(calls).toEqual(['speak:One']);
    release();
  });
});
