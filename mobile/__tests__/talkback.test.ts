import { answerAssessment } from '../src/core/smartCheck';
import { Ears, ListenResult, TalkbackSession, TalkCard, Voice } from '../src/features/talkback';

const CARDS: TalkCard[] = [
  { id: 'a', front: 'Capital of France?', back: 'Paris' },
  { id: 'b', front: 'Largest planet?', back: 'Jupiter' },
];

/** Lets every pending promise (voice, microphone) settle. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function mockVoice() {
  const said: string[] = [];
  let pending: (() => void) | null = null;
  const voice: Voice & { said: string[]; hold: boolean; release: () => void } = {
    said,
    hold: false,
    say: jest.fn((text: string) => {
      said.push(text);
      if (!voice.hold) return Promise.resolve();
      return new Promise<void>((resolve) => { pending = resolve; });
    }),
    stop: jest.fn(() => { pending?.(); pending = null; }),
    release: () => { pending?.(); pending = null; },
  };
  return voice;
}

function mockEars(answers: ListenResult[]) {
  const queue = [...answers];
  const ears: Ears & { hints: string[][] } = {
    hints: [],
    listen: jest.fn((hints: string[]) => {
      ears.hints.push(hints);
      return Promise.resolve(queue.shift() ?? { error: 'no-speech' });
    }),
    stop: jest.fn(),
  };
  return ears;
}

function session(answers: ListenResult[] | null, screenReader = false) {
  const voice = mockVoice();
  const ears = answers ? mockEars(answers) : null;
  const onRate = jest.fn();
  const s = new TalkbackSession(CARDS, { voice, ears, check: answerAssessment, screenReader, onRate });
  return { s, voice, ears, onRate };
}

describe('Talk-back study', () => {
  test('reads, listens, checks, says the result and moves on by itself', async () => {
    const { s, voice, ears, onRate } = session([{ transcript: 'paris' }, { transcript: 'saturn' }]);
    s.start();
    await settle();
    expect(voice.said).toEqual(['Capital of France?', 'Correct.', 'Largest planet?', 'Not quite, the answer is Jupiter.', 'All done. 1 of 2 right.']);
    expect(ears!.hints).toEqual([['Paris'], ['Jupiter']]);
    expect(onRate).toHaveBeenCalledTimes(2);
    const snap = s.getSnapshot();
    expect(snap.phase).toBe('done');
    expect(snap.results.map((r) => r.outcome)).toEqual(['right', 'wrong']);
  });

  test('shows a listening state while the microphone is on', async () => {
    const { s } = session([]);
    let release: (r: ListenResult) => void = () => undefined;
    const ears: Ears = { listen: () => new Promise((resolve) => { release = resolve; }), stop: jest.fn() };
    const live = new TalkbackSession(CARDS, { voice: mockVoice(), ears, check: answerAssessment, screenReader: false });
    live.start();
    await settle();
    expect(live.getSnapshot().phase).toBe('listening');
    release({ transcript: 'Paris' });
    await settle();
    expect(live.getSnapshot().results[0].outcome).toBe('right');
    s.stop();
  });

  test('asks again once when nothing is heard, then offers typing', async () => {
    const { s, voice } = session([{ error: 'no-speech' }, { error: 'no-speech' }]);
    s.start();
    await settle();
    expect(voice.said).toContain('I didn’t catch that. Please say it again.');
    const snap = s.getSnapshot();
    expect(snap.phase).toBe('typing');
    expect(snap.message).toMatch(/didn’t catch/);
    s.submitTyped('Paris');
    await settle();
    expect(s.getSnapshot().results[0].outcome).toBe('right');
  });

  test('without recognition it reads aloud and waits for a typed answer', async () => {
    const { s, voice } = session(null);
    s.start();
    await settle();
    expect(voice.said).toEqual(['Capital of France?']);
    expect(s.getSnapshot().phase).toBe('typing');
    expect(s.canListen).toBe(false);
  });

  test('a refused microphone falls back to typing for the rest of the session', async () => {
    const { s } = session([{ error: 'not-allowed' }]);
    s.start();
    await settle();
    expect(s.getSnapshot().phase).toBe('typing');
    expect(s.canListen).toBe(false);
  });

  test('pause stops the voice and microphone; resume asks the same question again', async () => {
    const { s, voice, ears } = session([{ transcript: 'Paris' }]);
    voice.hold = true;
    s.start();
    s.pause();
    expect(s.getSnapshot().phase).toBe('paused');
    expect(voice.stop).toHaveBeenCalled();
    expect(ears!.stop).toHaveBeenCalled();
    await settle();
    expect(ears!.listen).not.toHaveBeenCalled(); // the stopped question didn't start the mic
    voice.hold = false;
    s.resume();
    await settle();
    expect(voice.said.filter((t) => t === 'Capital of France?')).toHaveLength(2);
    expect(s.getSnapshot().results[0].outcome).toBe('right');
  });

  test('repeat reads the question again; skip moves on without rating', async () => {
    const { s, voice, onRate } = session([]);
    voice.hold = true;
    s.start();
    s.repeat();
    expect(voice.said).toEqual(['Capital of France?', 'Capital of France?']);
    s.skip();
    expect(s.getSnapshot().index).toBe(1);
    expect(s.getSnapshot().results[0].outcome).toBe('skipped');
    expect(onRate).not.toHaveBeenCalled();
  });

  test('type instead stops listening and takes a typed answer', async () => {
    const { s, voice } = session([]);
    voice.hold = true;
    s.start();
    s.typeInstead();
    expect(s.getSnapshot().phase).toBe('typing');
    voice.hold = false;
    s.submitTyped('jupiter');
    await settle();
    expect(s.getSnapshot().results[0].outcome).toBe('wrong'); // Jupiter is card two's answer
  });

  test('with a screen reader on, nothing advances or listens on its own', async () => {
    const { s, ears } = session([{ transcript: 'Paris' }], true);
    s.start();
    await settle();
    expect(s.getSnapshot().phase).toBe('ready');
    expect(ears!.listen).not.toHaveBeenCalled();
    s.listen();
    await settle();
    expect(s.getSnapshot().phase).toBe('waiting');
    expect(s.getSnapshot().message).toBe('Correct.');
    expect(s.getSnapshot().index).toBe(0);
    s.next();
    await settle();
    expect(s.getSnapshot().index).toBe(1);
    expect(s.getSnapshot().phase).toBe('ready');
  });

  test('an empty session is done at once', () => {
    const s = new TalkbackSession([], { voice: mockVoice(), ears: null, check: answerAssessment, screenReader: false });
    s.start();
    expect(s.getSnapshot().phase).toBe('done');
  });
});
