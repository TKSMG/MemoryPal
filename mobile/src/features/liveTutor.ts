/**
 * Live Talk-back: a spoken study conversation with Gemini Live, like a voice
 * call with a tutor. The tutor asks the cards, listens, can be interrupted
 * mid-sentence, explains, and saves a result for each card through a tool
 * call (record_answer), so ratings land in the schedule like any review.
 *
 * This is the protocol and the timing only. The WebSocket and the phone's
 * audio are passed in, so the flow can be tested without a phone. The "ai"
 * Edge Function hands out the one-use token and the set-up (see
 * supabase/functions/ai/live.ts); the audio goes straight to Google.
 */
import type { Assessment } from '../core/smartCheck';
import { pcmMs, utf8 } from './pcm';
import type { Outcome, TalkCard } from './talkback';

export const LIVE_URL = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained';
export const MIC_RATE = 16000;
export const MODEL_RATE = 24000;
const START_LINE = '(The learner pressed Start and is listening. Greet them in one short line and ask the first card.)';
const LAST_MINUTE_LINE = '(About one minute is left. After the current card, give the short summary, say goodbye and call end_session.)';

export interface LiveSocket {
  send(data: string): void;
  close(): void;
  binaryType?: string;
  onopen: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onerror: ((event: unknown) => void) | null;
  onclose: ((event: { code?: number; reason?: string }) => void) | null;
}

export interface LiveAudio {
  /** Starts the echo-cancelled microphone; `onMic` gets base64 16 kHz PCM. */
  start(onMic: (base64: string) => void): Promise<void>;
  setMuted(muted: boolean): void;
  /** Plays base64 24 kHz PCM after whatever is already playing. */
  play(base64: string): void;
  /** Drops speech that hasn't been played yet. */
  clear(): void;
  stop(): void;
}

export type LivePhase = 'connecting' | 'live' | 'done' | 'error';

export interface LiveResult {
  card: TalkCard;
  outcome: Outcome;
  said: string;
}

export interface LiveSnapshot {
  phase: LivePhase;
  /** Who is talking now, for the picture. */
  speaking: 'tutor' | 'you' | null;
  tutorLine: string;
  youLine: string;
  muted: boolean;
  results: LiveResult[];
  total: number;
  secondsLeft: number;
  error: string;
}

export interface LiveTutorOptions {
  token: string;
  setup: Record<string, unknown>;
  /** The cards by the key the tutor was given ("c1"). */
  cards: Record<string, TalkCard>;
  minutes: number;
  openSocket: (url: string) => LiveSocket;
  audio: LiveAudio;
  onRate?: (card: TalkCard, outcome: Outcome) => void;
  now?: () => number;
}

/** The schedule rating for a tutor's verdict (skipped cards aren't rated). */
export function liveAssessment(outcome: Outcome): Assessment | null {
  if (outcome === 'right') return { score: 80, quality: 4, label: 'Right (AI tutor)', bucket: 'Good', repetitions: 2, detail: 'Judged by the live AI tutor.' };
  if (outcome === 'close') return { score: 50, quality: 3, label: 'Nearly (AI tutor)', bucket: 'Review', repetitions: 3, detail: 'Judged by the live AI tutor.' };
  if (outcome === 'wrong') return { score: 10, quality: 1, label: 'Not yet (AI tutor)', bucket: 'Again', repetitions: 5, detail: 'Judged by the live AI tutor.' };
  return null;
}

/** Friendly text for a socket that closed before the conversation ended. */
export function closeText(code?: number, reason?: string): string {
  const why = (reason ?? '').toLowerCase();
  if (code === 1008 || why.includes('quota') || why.includes('resource')) return 'The AI tutor is busy right now. Try again in a minute, or use classic Talk-back.';
  if (why.includes('token') || why.includes('auth') || why.includes('expired')) return 'The conversation couldn’t be started. Try again.';
  return 'The connection to the AI tutor dropped. Your answers so far are saved.';
}

const RESULT_SET = new Set<Outcome>(['right', 'close', 'wrong', 'skipped']);

export class LiveTutor {
  private phase: LivePhase = 'connecting';
  private socket: LiveSocket | null = null;
  /** When the speech handed to the player so far will have finished. */
  private speechUntil = 0;
  private clockTimer: ReturnType<typeof setInterval> | null = null;
  private endTimer: ReturnType<typeof setTimeout> | null = null;
  private startedAt = 0;
  private warned = false;
  private ending = false;
  private tutorLine = '';
  private youLine = '';
  private tutorTurnOpen = false;
  private youFresh = true;
  private youHeardAt = 0;
  private muted = false;
  private results: LiveResult[] = [];
  private error = '';
  private listeners = new Set<() => void>();
  private snapshot: LiveSnapshot;
  private now: () => number;

  constructor(private options: LiveTutorOptions) {
    this.now = options.now ?? (() => Date.now());
    this.snapshot = this.makeSnapshot();
  }

  // ------------------------------------------------------------- reading
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): LiveSnapshot => this.snapshot;

  // ------------------------------------------------------------ controls
  start() {
    let socket: LiveSocket;
    try {
      socket = this.options.openSocket(`${LIVE_URL}?access_token=${encodeURIComponent(this.options.token)}`);
    } catch {
      return this.fail('The AI tutor couldn’t be reached. Check the internet connection.');
    }
    this.socket = socket;
    socket.binaryType = 'arraybuffer';
    socket.onopen = () => this.send({ setup: this.options.setup });
    socket.onmessage = (event) => this.receive(event.data);
    socket.onerror = () => undefined; // onclose follows with the reason
    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      this.socket = null;
      if (this.phase === 'done' || this.phase === 'error') return;
      if (this.ending) return this.finish();
      this.fail(this.phase === 'connecting' ? closeText(event.code, event.reason || 'start') : closeText(event.code, event.reason));
    };
  }

  setMuted(muted: boolean) {
    if (this.phase !== 'live' || muted === this.muted) return;
    this.muted = muted;
    this.options.audio.setMuted(muted);
    // Tells the voice detector the speaker went quiet, so a half-said answer is still heard.
    if (muted) this.send({ realtimeInput: { audioStreamEnd: true } });
    this.emit();
  }

  /** Ends now (the End button, leaving the screen). Saved ratings stay. */
  stop() {
    if (this.phase === 'done' || this.phase === 'error') return;
    this.finish();
  }

  // ------------------------------------------------------------- incoming
  private receive(data: unknown) {
    let message: Record<string, unknown>;
    try {
      const text = typeof data === 'string' ? data : data instanceof ArrayBuffer ? utf8(new Uint8Array(data)) : ArrayBuffer.isView(data) ? utf8(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)) : '';
      message = JSON.parse(text);
    } catch {
      return;
    }
    if (!message || typeof message !== 'object') return;
    if (message.setupComplete) this.begin();
    if (message.serverContent) this.content(message.serverContent as Record<string, unknown>);
    if (message.toolCall) this.toolCall(message.toolCall as { functionCalls?: { id?: string; name?: string; args?: Record<string, unknown> }[] });
    if (message.goAway) this.wrapUp(LAST_MINUTE_LINE);
  }

  private begin() {
    if (this.phase !== 'connecting') return;
    this.phase = 'live';
    this.startedAt = this.now();
    this.send({ clientContent: { turns: [{ role: 'user', parts: [{ text: START_LINE }] }], turnComplete: true } });
    this.options.audio
      .start((data) => {
        if (this.phase === 'live' && !this.muted) this.send({ realtimeInput: { audio: { data, mimeType: `audio/pcm;rate=${MIC_RATE}` } } });
      })
      .catch(() => this.fail('The microphone couldn’t be started. Check that MemoryPal may use it in Settings.'));
    this.clockTimer = setInterval(() => this.tick(), 1000);
    this.emit();
  }

  private content(content: Record<string, unknown>) {
    if (this.phase !== 'live') return;
    const input = (content.inputTranscription as { text?: unknown } | undefined)?.text;
    if (typeof input === 'string' && input) {
      // The learner's first words after the tutor spoke start a fresh line.
      if (this.youFresh) {
        this.youFresh = false;
        this.youLine = '';
      }
      this.youLine = (this.youLine + input).replace(/\s+/g, ' ').trimStart();
      this.youHeardAt = this.now();
    }
    const turn = content.modelTurn as { parts?: { inlineData?: { data?: unknown } }[] } | undefined;
    for (const part of turn?.parts ?? []) {
      const audio = part?.inlineData?.data;
      if (typeof audio === 'string' && audio) {
        this.openTutorTurn();
        this.options.audio.play(audio);
        this.speechUntil = Math.max(this.speechUntil, this.now()) + pcmMs(audio, MODEL_RATE);
      }
    }
    const output = (content.outputTranscription as { text?: unknown } | undefined)?.text;
    if (typeof output === 'string' && output) {
      this.openTutorTurn();
      this.tutorLine = (this.tutorLine + output).replace(/\s+/g, ' ').trimStart();
    }
    if (content.interrupted) {
      // The learner spoke over the tutor: drop what hasn't been played.
      this.options.audio.clear();
      this.speechUntil = Math.min(this.speechUntil, this.now());
    }
    if (content.turnComplete || content.interrupted) this.tutorTurnOpen = false;
    this.emit();
  }

  private openTutorTurn() {
    if (this.tutorTurnOpen) return;
    this.tutorTurnOpen = true;
    this.youFresh = true;
    this.tutorLine = '';
  }

  private toolCall(call: { functionCalls?: { id?: string; name?: string; args?: Record<string, unknown> }[] }) {
    const responses: Record<string, unknown>[] = [];
    for (const fn of call.functionCalls ?? []) {
      const name = String(fn?.name ?? '');
      let response: Record<string, unknown> = { result: 'unknown tool' };
      if (name === 'record_answer') response = this.record(fn.args ?? {});
      else if (name === 'end_session') {
        response = { result: 'ok' };
        this.endAfterSpeech();
      }
      responses.push({ id: fn?.id, name, response: { ...response, scheduling: 'SILENT' } });
    }
    if (responses.length) this.send({ toolResponse: { functionResponses: responses } });
  }

  private record(args: Record<string, unknown>): Record<string, unknown> {
    const card = this.options.cards[String(args.card ?? '').trim()];
    const outcome = String(args.result ?? '').trim().toLowerCase() as Outcome;
    if (!card || !RESULT_SET.has(outcome)) return { result: 'error: unknown card key or result' };
    const said = typeof args.said === 'string' ? args.said.replace(/\s+/g, ' ').trim().slice(0, 200) : '';
    const result = { card, outcome, said };
    const at = this.results.findIndex((item) => item.card.id === card.id);
    // A card the tutor comes back to keeps its latest result, and is rated once.
    if (at >= 0) this.results[at] = result;
    else {
      this.results.push(result);
      if (outcome !== 'skipped') this.options.onRate?.(card, outcome);
    }
    this.emit();
    return { result: 'saved' };
  }

  // ---------------------------------------------------------------- timing
  private speechLeftMs(): number {
    return Math.max(0, this.speechUntil - this.now());
  }

  private tick() {
    if (this.phase !== 'live') return;
    const left = this.secondsLeft();
    if (left <= 60 && !this.warned) this.wrapUp(LAST_MINUTE_LINE);
    if (left <= 0) this.finish();
    else this.emit();
  }

  private secondsLeft(): number {
    if (!this.startedAt) return this.options.minutes * 60;
    return Math.max(0, Math.round(this.options.minutes * 60 - (this.now() - this.startedAt) / 1000));
  }

  private wrapUp(line: string) {
    if (this.warned || this.phase !== 'live') return;
    this.warned = true;
    // Not a turn of its own: the tutor reads it with the learner's next words.
    this.send({ clientContent: { turns: [{ role: 'user', parts: [{ text: line }] }], turnComplete: false } });
  }

  private endAfterSpeech() {
    this.ending = true;
    if (this.endTimer) clearTimeout(this.endTimer);
    // Let the goodbye finish playing first.
    this.endTimer = setTimeout(() => this.finish(), this.speechLeftMs() + 600);
  }

  // ------------------------------------------------------------- endings
  private finish() {
    this.phase = 'done';
    this.teardown();
    this.emit();
  }

  private fail(error: string) {
    this.phase = 'error';
    this.error = error;
    this.teardown();
    this.emit();
  }

  private teardown() {
    if (this.clockTimer) clearInterval(this.clockTimer);
    if (this.endTimer) clearTimeout(this.endTimer);
    this.clockTimer = this.endTimer = null;
    try {
      this.options.audio.stop();
    } catch {
      // already stopped
    }
    const socket = this.socket;
    this.socket = null;
    try {
      socket?.close();
    } catch {
      // already closed
    }
  }

  private send(message: Record<string, unknown>) {
    try {
      this.socket?.send(JSON.stringify(message));
    } catch {
      // a closing socket; onclose reports it
    }
  }

  private makeSnapshot(): LiveSnapshot {
    const now = this.now();
    const tutorTalking = this.phase === 'live' && this.speechUntil > now;
    const youTalking = this.phase === 'live' && !tutorTalking && now - this.youHeardAt < 1200;
    return {
      phase: this.phase,
      speaking: tutorTalking ? 'tutor' : youTalking ? 'you' : null,
      tutorLine: this.tutorLine,
      youLine: this.youLine,
      muted: this.muted,
      results: [...this.results],
      total: Object.keys(this.options.cards).length,
      secondsLeft: this.secondsLeft(),
      error: this.error,
    };
  }

  private emit() {
    this.snapshot = this.makeSnapshot();
    this.listeners.forEach((listener) => listener());
  }
}
