/**
 * The phone audio wrapper for the live tutor: speech that arrives while the
 * microphone is still starting is kept, and stopping during the start leaves
 * no microphone running.
 */
const calls: string[] = [];
let finishStart: () => void = () => undefined;

jest.mock('react-native', () => ({ Platform: { OS: 'ios' } }));
jest.mock('../modules/live-audio', () => ({
  LiveAudio: {
    start: () => new Promise<boolean>((resolve) => (finishStart = () => resolve(true))),
    setMuted: () => calls.push('muted'),
    play: (data: string) => calls.push(`play:${data}`),
    clear: () => calls.push('clear'),
    stop: () => calls.push('stop'),
    addListener: () => ({ remove: () => undefined }),
  },
}));

// eslint-disable-next-line import/first
import { makeLiveAudio } from '../src/features/liveAudio';

beforeEach(() => {
  calls.length = 0;
});

test('speech that arrives before the player is up plays once it is', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('hello');
  audio.play('there');
  expect(calls).toEqual([]);
  finishStart();
  await started;
  audio.play('next');
  expect(calls).toEqual(['play:hello', 'play:there', 'play:next']);
});

test('clear drops speech still waiting for the player', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('old');
  audio.clear();
  finishStart();
  await started;
  expect(calls).toEqual([]);
});

test('stopping while the microphone starts stops it once it has started', async () => {
  const audio = makeLiveAudio()!;
  const started = audio.start(() => undefined);
  audio.play('hello');
  audio.stop();
  expect(calls).toEqual(['stop']);
  finishStart();
  await started;
  expect(calls).toEqual(['stop', 'stop']);
  audio.play('late');
  expect(calls).toEqual(['stop', 'stop']);
});
