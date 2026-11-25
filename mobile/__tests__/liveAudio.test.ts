/**
 * The phone audio wrapper for the live tutor: speech that arrives while the
 * microphone is still starting is kept, and stopping during the start leaves
 * no microphone running.
 */
const calls: string[] = [];
let finishStart: () => void = () => undefined;
const listeners: Record<string, () => void> = {};

jest.mock('react-native', () => ({ Platform: { OS: 'ios' } }));
jest.mock('../modules/live-audio', () => ({
  LiveAudio: {
    start: () => new Promise<boolean>((resolve) => (finishStart = () => resolve(true))),
    setMuted: () => calls.push('muted'),
    play: (data: string) => calls.push(`play:${data}`),
    clear: () => calls.push('clear'),
    stop: () => calls.push('stop'),
    addListener: (name: string, listener: () => void) => {
      listeners[name] = listener;
      return { remove: () => undefined };
    },
  },
}));

// eslint-disable-next-line import/first
import { IOS_SETTLE_MS, makeLiveAudio } from '../src/features/liveAudio';

beforeEach(() => {
  calls.length = 0;
  jest.useFakeTimers();
});
afterEach(() => jest.useRealTimers());

/** Lets the start finish, including the iPhone's short settling wait. */
async function settle(started: Promise<void>) {
  await Promise.resolve();
  await Promise.resolve();
  jest.advanceTimersByTime(IOS_SETTLE_MS);
  await started;
}

test('if iOS restarts the player, speech not yet played is played again', async () => {
  let now = 0;
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const audio = makeLiveAudio(require('../modules/live-audio').LiveAudio, () => now)!;
  const started = audio.start(() => undefined);
  finishStart();
  await settle(started);
  const ms100 = btoa(String.fromCharCode(...new Uint8Array(4800))); // 100 ms at 24 kHz
  audio.play(ms100);
  audio.play(ms100);
  audio.play(ms100);
  now = 150; // the first piece has played, the second is half way
  calls.length = 0;
  listeners.onRestart();
  expect(calls).toEqual([`play:${ms100}`, `play:${ms100}`]);
  audio.clear();
  calls.length = 0;
  listeners.onRestart();
  expect(calls).toEqual([]);
});

test('speech that arrives before the player is up plays once it is', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('hello');
  audio.play('there');
  expect(calls).toEqual([]);
  finishStart();
  await settle(started);
  audio.play('next');
  expect(calls).toEqual(['play:hello', 'play:there', 'play:next']);
});

test('clear drops speech still waiting for the player', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('old');
  audio.clear();
  finishStart();
  await settle(started);
  expect(calls).toEqual([]);
});

test('stopping while the microphone starts stops it once it has started', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('hello');
  audio.stop();
  expect(calls).toEqual(['stop']);
  finishStart();
  await settle(started);
  expect(calls).toEqual(['stop', 'stop']);
  audio.play('late');
  expect(calls).toEqual(['stop', 'stop']);
});
