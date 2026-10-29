/** Live Talk-back: audio helpers and the Gemini Live conversation flow, with a fake socket and fake audio. */
import { base64ToBytes, bytesToBase64, Resampler, utf8 } from '../src/features/pcm';
import { LEAD_MS, liveAssessment, LiveAudio, LiveSocket, LiveTutor } from '../src/features/liveTutor';
import type { Outcome, TalkCard } from '../src/features/talkback';
import { startLive } from '../src/cloud/ai';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { supabaseUrl: 'https://proj.supabase.co/', supabasePublishableKey: 'sb_publishable_x' } } } }));

function pcm(samples: number[]): Uint8Array {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  samples.forEach((value, i) => view.setInt16(i * 2, value, true));
  return bytes;
}

function samplesOf(bytes: Uint8Array): number[] {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return Array.from({ length: bytes.length / 2 }, (_, i) => view.getInt16(i * 2, true));
}

describe('audio helpers', () => {
  test('base64 round-trips every length and matches the standard encoding', () => {
    for (let n = 0; n < 10; n++) {
      const bytes = Uint8Array.from({ length: n }, (_, i) => (i * 97 + 13) & 0xff);
      const text = bytesToBase64(bytes);
      expect(text).toBe(btoa(String.fromCharCode(...bytes)));
      expect(Array.from(base64ToBytes(text))).toEqual(Array.from(bytes));
    }
  });

  test('UTF-8 frames decode', () => {
    expect(utf8(new TextEncoder().encode('{"a":"café ✓"}'))).toBe('{"a":"café ✓"}');
  });

  test('24 kHz becomes 16 kHz with no gaps across chunks, odd bytes kept', () => {
    const ramp = Array.from({ length: 300 }, (_, i) => i * 10);
    const whole = samplesOf(new Resampler(24000, 16000).push(pcm(ramp)));
    const streamed = new Resampler(24000, 16000);
    const bytes = pcm(ramp);
    const parts = [bytes.subarray(0, 101), bytes.subarray(101, 333), bytes.subarray(333)];
    const joined = parts.flatMap((part) => samplesOf(streamed.push(part)));
    expect(joined).toEqual(whole);
    expect(whole.length).toBe(200);
    // A ramp stays a ramp: every output step is 1.5 input samples.
    expect(whole.slice(0, 4)).toEqual([0, 15, 30, 45]);
  });
});

class FakeSocket implements LiveSocket {
  sent: Record<string, unknown>[] = [];
  closed = false;
  binaryType = '';
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;
  onclose: ((event: { code?: number; reason?: string }) => void) | null = null;
  constructor(public url: string) {}
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.closed = true;
  }
  server(message: Record<string, unknown>, binary = false) {
    const text = JSON.stringify(message);
    this.onmessage?.({ data: binary ? new TextEncoder().encode(text).buffer : text });
  }
}

function setup(minutes = 10) {
  let now = 1_000_000;
  const played: Uint8Array[] = [];
  let mic: ((pcm: Uint8Array) => void) | null = null;
  const audio: LiveAudio & { muted: boolean; stopped: boolean } = {
    muted: false,
    stopped: false,
    async start(onMic) {
      mic = onMic;
    },
    setMuted(muted) {
      this.muted = muted;
    },
    play(chunk) {
      played.push(chunk);
    },
    stop() {
      this.stopped = true;
    },
  };
  const cards: Record<string, TalkCard> = { c1: { id: 'a', front: 'Capital of France?', back: 'Paris' }, c2: { id: 'b', front: '2 + 2?', back: '4' } };
  const rated: [string, Outcome][] = [];
  let socket: FakeSocket | null = null;
  const tutor = new LiveTutor({
    token: 'auth_tokens/xyz',
    setup: { model: 'models/gemini-3.8-live' },
    cards,
    minutes,
    audio,
    openSocket: (url) => (socket = new FakeSocket(url)),
    onRate: (card, outcome) => rated.push([card.id, outcome]),
    now: () => now,
  });
  tutor.start();
  const ws = socket as unknown as FakeSocket;
  return {
    tutor,
    ws,
    audio,
    played,
    rated,
    mic: (chunk: Uint8Array) => mic?.(chunk),
    advance: (ms: number) => {
      now += ms;
      jest.advanceTimersByTime(ms);
    },
  };
}

const audioMessage = (ms: number) => ({ serverContent: { modelTurn: { parts: [{ inlineData: { data: bytesToBase64(new Uint8Array(ms * 48)), mimeType: 'audio/pcm;rate=24000' } }] } } });

describe('live tutor conversation', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('connects with the token, sends the set-up, then starts the tutor and the microphone', async () => {
    const { tutor, ws, mic } = setup();
    expect(ws.url).toContain('BidiGenerateContentConstrained?access_token=auth_tokens%2Fxyz');
    expect(ws.binaryType).toBe('arraybuffer');
    ws.onopen?.();
    expect(ws.sent[0]).toEqual({ setup: { model: 'models/gemini-3.8-live' } });
    expect(tutor.getSnapshot().phase).toBe('connecting');
    ws.server({ setupComplete: {} }, true);
    await Promise.resolve();
    expect(tutor.getSnapshot().phase).toBe('live');
    expect((ws.sent[1].clientContent as { turnComplete: boolean }).turnComplete).toBe(true);
    mic(new Uint8Array([1, 2, 3, 4]));
    expect(ws.sent[2]).toEqual({ realtimeInput: { audio: { data: bytesToBase64(new Uint8Array([1, 2, 3, 4])), mimeType: 'audio/pcm;rate=16000' } } });
  });

  test('speech is handed to the player only a little ahead, and an interruption drops the rest', () => {
    const { tutor, ws, played, advance } = setup();
    ws.server({ setupComplete: {} });
    for (let i = 0; i < 10; i++) ws.server(audioMessage(100)); // one second of speech
    const playedMs = () => played.reduce((sum, chunk) => sum + chunk.length, 0) / 32;
    expect(playedMs()).toBeLessThanOrEqual(LEAD_MS + 100);
    expect(tutor.getSnapshot().speaking).toBe('tutor');
    advance(200);
    const before = playedMs();
    expect(before).toBeGreaterThan(LEAD_MS);
    ws.server({ serverContent: { interrupted: true } });
    advance(2000);
    expect(playedMs()).toBe(before);
    expect(playedMs()).toBeLessThan(800);
  });

  test('captions follow each turn', () => {
    const { tutor, ws } = setup();
    ws.server({ setupComplete: {} });
    ws.server({ serverContent: { outputTranscription: { text: 'What is the capital ' } } });
    ws.server({ serverContent: { outputTranscription: { text: 'of France?' } } });
    ws.server({ serverContent: { turnComplete: true } });
    ws.server({ serverContent: { inputTranscription: { text: 'Paris' } } });
    expect(tutor.getSnapshot().tutorLine).toBe('What is the capital of France?');
    expect(tutor.getSnapshot().youLine).toBe('Paris');
    ws.server({ serverContent: { outputTranscription: { text: 'Yes! Next one.' } } });
    ws.server({ serverContent: { inputTranscription: { text: 'Four' } } });
    expect(tutor.getSnapshot().tutorLine).toBe('Yes! Next one.');
    expect(tutor.getSnapshot().youLine).toBe('Four');
  });

  test('record_answer rates each card once and always answers the tool call', () => {
    const { tutor, ws, rated } = setup();
    ws.server({ setupComplete: {} });
    ws.server({ toolCall: { functionCalls: [{ id: '1', name: 'record_answer', args: { card: 'c1', result: 'right', said: 'Paris' } }] } });
    ws.server({ toolCall: { functionCalls: [{ id: '2', name: 'record_answer', args: { card: 'c1', result: 'wrong' } }, { id: '3', name: 'record_answer', args: { card: 'c9', result: 'right' } }] } });
    ws.server({ toolCall: { functionCalls: [{ id: '4', name: 'record_answer', args: { card: 'c2', result: 'skipped' } }] } });
    expect(rated).toEqual([['a', 'right']]);
    const responses = ws.sent.filter((m) => m.toolResponse).flatMap((m) => (m.toolResponse as { functionResponses: { id: string; response: { result: string } }[] }).functionResponses);
    expect(responses.map((r) => [r.id, r.response.result])).toEqual([['1', 'saved'], ['2', 'saved'], ['3', 'error: unknown card key or result'], ['4', 'saved']]);
    expect(tutor.getSnapshot().results.map((r) => [r.card.id, r.outcome])).toEqual([['a', 'wrong'], ['b', 'skipped']]);
  });

  test('end_session lets the goodbye play, then hangs up', () => {
    const { tutor, ws, audio, advance } = setup();
    ws.server({ setupComplete: {} });
    ws.server(audioMessage(500));
    ws.server({ toolCall: { functionCalls: [{ id: '9', name: 'end_session', args: {} }] } });
    advance(300);
    expect(tutor.getSnapshot().phase).toBe('live');
    advance(1000);
    expect(tutor.getSnapshot().phase).toBe('done');
    expect(ws.closed && audio.stopped).toBe(true);
  });

  test('the last minute asks for a wrap-up, and time up ends it', () => {
    const { tutor, ws, advance } = setup(2);
    ws.server({ setupComplete: {} });
    advance(61_000);
    const wrap = ws.sent.find((m) => (m.clientContent as { turnComplete?: boolean } | undefined)?.turnComplete === false);
    expect(JSON.stringify(wrap)).toContain('one minute');
    advance(60_000);
    expect(tutor.getSnapshot().phase).toBe('done');
  });

  test('mute stops sending and tells the voice detector; a dropped line is an error with results kept', () => {
    const { tutor, ws, audio, mic, rated } = setup();
    ws.server({ setupComplete: {} });
    ws.server({ toolCall: { functionCalls: [{ id: '1', name: 'record_answer', args: { card: 'c2', result: 'close' } }] } });
    tutor.setMuted(true);
    expect(audio.muted).toBe(true);
    expect(ws.sent[ws.sent.length - 1]).toEqual({ realtimeInput: { audioStreamEnd: true } });
    const count = ws.sent.length;
    mic(new Uint8Array([1, 2]));
    expect(ws.sent.length).toBe(count);
    ws.onclose?.({ code: 1006 });
    expect(tutor.getSnapshot().phase).toBe('error');
    expect(tutor.getSnapshot().error).toContain('saved');
    expect(rated).toEqual([['b', 'close']]);
  });

  test('a refused start says the tutor is busy', () => {
    const { tutor, ws } = setup();
    ws.onclose?.({ code: 1008, reason: 'Quota exceeded' });
    expect(tutor.getSnapshot().error).toContain('busy');
  });

  test('verdicts map to schedule ratings', () => {
    expect(liveAssessment('right')?.quality).toBe(4);
    expect(liveAssessment('close')?.quality).toBe(3);
    expect(liveAssessment('wrong')?.quality).toBe(1);
    expect(liveAssessment('skipped')).toBeNull();
  });
});

describe('starting a live conversation', () => {
  test('sends keyed cards to the ai function and returns the token and set-up', async () => {
    let body: Record<string, unknown> = {};
    const fetcher = (async (_url: string, init: { body: string }) => {
      body = JSON.parse(init.body);
      return new Response(JSON.stringify({ ok: true, action: 'live', result: { token: 'auth_tokens/t', setup: { model: 'models/m' }, minutes: 10 }, remaining: 7 }), { status: 200 });
    }) as unknown as typeof fetch;
    const cards = Array.from({ length: 45 }, (_, i) => ({ front: ` Q${i} `, back: `A${i}` }));
    const started = await startLive('token', cards, 'Bio', { fetcher });
    expect(body.action).toBe('live');
    expect((body.cards as { key: string; front: string }[]).length).toBe(40);
    expect((body.cards as { key: string; front: string }[])[0]).toEqual({ key: 'c1', front: 'Q0', back: 'A0' });
    expect(started).toEqual({ token: 'auth_tokens/t', setup: { model: 'models/m' }, minutes: 10, remaining: 7 });
  });

  test('a used-up allowance is reported as such', async () => {
    const fetcher = (async () => new Response(JSON.stringify({ ok: false, error: 'limit_reached' }), { status: 429 })) as unknown as typeof fetch;
    await expect(startLive('token', [{ front: 'Q', back: 'A' }], '', { fetcher })).rejects.toMatchObject({ code: 'limit_reached' });
  });
});
