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
import { GATE, levelDb, decodeBase64, SpeechGate } from './speechGate';
import type { Outcome, TalkCard } from './talkback';
import { Voice, VoiceMeter } from './voiceMeter';

// Ephemeral (one-use) tokens only work on the v1alpha Live endpoint, as in Google's SDK.
export const LIVE_URL = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained';
export const MIC_RATE = 16000;
export const MODEL_RATE = 24000;
const START_LINE = '(The learner pressed Start and is listening. Greet them in one short line and ask the first card.)';
const LAST_MINUTE_LINE = '(About one minute is left. After the current card, give the short summary, say goodbye and call end_session.)';
/**
 * How much clear speech from the learner counts as an answer, when the
 * transcript hasn't caught up yet. Shorter is a cough or a click.
 */
export const ANSWER_SPEECH_MS = 200;
/** Cut off with at least this much of its turn unplayed, the tutor is told what the learner actually heard. */
export const CUT_OFF_MS = 500;

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
  /**
   * Starts the echo-cancelled microphone and the player; `onMic` gets base64
   * 16 kHz PCM. The tutor is only asked to speak once this has finished, so
   * its first words can't land in a player that isn't ready.
   */
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
  /** Keeps noise and echo from reaching the tutor (speechGate.ts); null sends the microphone as it is. */
  gate?: SpeechGate | null;
}

/**
 * What record_answer tells the tutor to ask next: the first card, in order,
 * without a result yet. Saying so each time keeps it from asking a card twice
 * (it lost its place after being talked over). Same as next_card() on desktop.
 */
export function nextCard(cards: Record<string, TalkCard>, results: { card: TalkCard }[]): string {
  const done = new Set(results.map((item) => item.card.id));
  for (const [key, card] of Object.entries(cards)) if (!done.has(card.id)) return key;
  return 'none: every card is done, so give the summary';
}

/** record_answer's reply: the result, the next card's key and its question. */
export function nextReply(cards: Record<string, TalkCard>, results: { card: TalkCard }[], result: string): Record<string, unknown> {
  const next = nextCard(cards, results);
  const question = cards[next]?.front;
  return question ? { result, next, question } : { result, next };
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

/** record_answer's reply when the learner hasn't said anything since the card was asked. Same text on desktop. */
export const NOT_ANSWERED = 'not saved: the learner has not answered this card yet. Say nothing more now and wait for their answer. Don\'t ask the card again, and never answer for them or reuse an earlier answer.';

/**
 * With app turns, how long the learner can stay quiet after a question before
 * the tutor offers (once) to repeat it, give a hint or skip.
 */
export const QUIET_NUDGE_MS = 15000;
export const QUIET_LINE = "(The learner has gone quiet and hasn't answered this card yet, so don't judge or record it. In one short, kind line, offer to repeat the question, give a hint, or skip it. Then wait.)";

/**
 * True when the set-up turns Google's voice detection off, so the app says
 * when the learner starts and stops talking (live.ts APP_TURNS).
 */
export function appTurns(setup: Record<string, unknown>): boolean {
  const config = setup.realtimeInputConfig as { automaticActivityDetection?: { disabled?: unknown } } | undefined;
  return config?.automaticActivityDetection?.disabled === true;
}

const NOT_SPOKEN = /<!--[\s\S]*?(?:-->|$)|<[^>]*(?:>|$)|\[[^\]]*(?:\]|$)|\([^)]*(?:\)|$)|\{[^}]*(?:\}|$)|\*[^*]*(?:\*|$)/g;

/**
 * A caption without notes that aren't words, such as the tutor's
 * "<!-- Silence, waiting for learner -->" or "(pause)", or markers like
 * "{cont}" or "<noise>" in the transcript of the learner; unclosed ones are
 * dropped too, since the rest may still be on its way. Same as spoken() on desktop.
 */
export function spoken(text: string): string {
  return text.replace(NOT_SPOKEN, ' ').replace(/\s+/g, ' ').trim();
}

/**
 * What the tutor is told when the learner talked over it. Gemini writes a
 * whole turn long before it has played, so it believed the learner had heard
 * every word: a question cut off halfway counted as asked, and it went on to
 * the next card, or judged the learner's "sorry?" (or their last answer) as
 * the answer. Same text on desktop.
 */
export function cutOffNote(heard: string): string {
  const said = heard ? `the learner only heard "${heard}…" and none of the rest` : 'the learner heard none of what you just said';
  return `(You were cut off: ${said}. Respond to what they say now. Judge it only if it is a real answer to the card you were asking; if they didn't hear the question, ask it again.)`;
}

/** The start of `line`, in proportion to how much of the turn played. */
export function heardPart(line: string, played: number): string {
  const words = line.split(' ').filter(Boolean);
  return words.slice(0, Math.floor(words.length * Math.max(0, Math.min(1, played)))).join(' ');
}

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
  private gate: SpeechGate | null;
  private meter = new VoiceMeter(MODEL_RATE);
  /**
   * What the learner has said since the last saved card: clear speech the
   * gate let through, and words in the transcript. A card is only saved once
   * the learner has said something, so the tutor can't "answer" the next card
   * with the previous answer while the learner is quiet.
   */
  private heardMs = 0;
  private heardWords = false;
  /** The current tutor turn on the playback timeline: when its first words play and how long all of it lasts. */
  private turnStart: number | null = null;
  private turnMs = 0;
  /** The last caption with words in it, shown while a new turn has none yet. */
  private lastTutorLine = '';
  /** Speech before the tutor starts asking the next card doesn't count as its answer. */
  private freshCard = false;
  /**
   * A learner turn ended after the last save: that was an answer, even if the
   * tutor asked the next card before saving the last one.
   */
  private turnSinceSave = false;
  /**
   * App turns (Google's voice detection off): the gate's opening and closing
   * are the learner's turns, sent as activityStart and activityEnd.
   */
  private appTurns: boolean;
  private learnerTalking = false;
  private learnerAt = 0;
  private nudged = false;

  constructor(private options: LiveTutorOptions) {
    this.now = options.now ?? (() => Date.now());
    this.gate = options.gate === undefined ? new SpeechGate(MIC_RATE) : options.gate;
    this.appTurns = appTurns(options.setup);
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
    this.gate?.reset();
    this.meter.micOff();
    const talking = this.learnerTalking;
    this.learnerTalking = false;
    // Tells the tutor the speaker went quiet, so a half-said answer is still heard.
    if (muted && this.appTurns) {
      if (talking) this.send({ realtimeInput: { activityEnd: {} } });
    } else if (muted) this.send({ realtimeInput: { audioStreamEnd: true } });
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
    // The microphone and player first, then the greeting: on an iPhone the
    // first call's audio set-up can take most of a second and restart the
    // player, and a greeting that arrived meanwhile was lost, so the tutor
    // sat waiting for an answer to a question nobody heard.
    this.options.audio
      .start((data) => this.mic(data))
      .then(() => {
        if (this.phase === 'live') this.send({ clientContent: { turns: [{ role: 'user', parts: [{ text: START_LINE }] }], turnComplete: true } });
      })
      .catch(() => this.fail('The microphone couldn’t be started. Check that MemoryPal may use it in Settings.'));
    this.clockTimer = setInterval(() => this.tick(), 1000);
    this.emit();
  }

  private mic(data: string) {
    if (this.phase !== 'live' || this.muted) return;
    const now = this.now();
    const wasOpen = this.gate?.isOpen ?? false;
    let chunks = this.gate ? this.gate.process(data, this.tutorAudible()) : [data];
    const open = this.gate?.isOpen ?? false;
    if (this.gate) {
      if (open && this.gate.lastLoud) this.heardMs += pcmMs(data, MIC_RATE);
      this.meter.mic(this.gate.lastDb, open, now);
    } else {
      this.meter.mic(levelDb(decodeBase64(data)), true, now);
    }
    if (open) {
      this.learnerAt = now;
      this.nudged = false;
    }
    let start = false;
    let end = false;
    if (this.appTurns && this.gate) {
      // Only the learner's own turns go to the tutor: a turn starts when the
      // gate opens (with the half second before it) and ends once they have
      // been quiet for a moment. Nothing else is sent, so noise and echo can't
      // start a turn or cut the tutor off.
      start = open && !wasOpen;
      end = wasOpen && !open;
      if (end) this.turnSinceSave = true;
      this.learnerTalking = open;
      if (!open && !end) chunks = [];
    }
    if (start) this.send({ realtimeInput: { activityStart: {} } });
    for (const chunk of chunks) this.send({ realtimeInput: { audio: { data: chunk, mimeType: `audio/pcm;rate=${MIC_RATE}` } } });
    if (end) this.send({ realtimeInput: { activityEnd: {} } });
  }

  /** True while the tutor's voice (or its echo) may still be on the microphone. */
  private tutorAudible(): boolean {
    return this.now() < this.speechUntil + GATE.echoTailMs;
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
      if (/[\p{L}\p{N}]/u.test(input)) this.heardWords = true;
    }
    const turn = content.modelTurn as { parts?: { inlineData?: { data?: unknown } }[] } | undefined;
    for (const part of turn?.parts ?? []) {
      const audio = part?.inlineData?.data;
      if (typeof audio === 'string' && audio) {
        if (this.freshCard) {
          // The tutor is starting on the next card: only what the learner says from here answers it.
          // Unless they already finished a turn since the save: then the tutor had asked the card
          // before saving the last one, and this is its verdict on their answer.
          this.freshCard = false;
          if (!this.turnSinceSave) {
            this.heardMs = 0;
            this.heardWords = false;
          }
        }
        this.openTutorTurn();
        this.options.audio.play(audio);
        const ms = pcmMs(audio, MODEL_RATE);
        this.speechUntil = this.meter.speech(audio, this.now());
        if (this.turnStart === null) this.turnStart = this.speechUntil - ms;
        this.turnMs += ms;
      }
    }
    const output = (content.outputTranscription as { text?: unknown } | undefined)?.text;
    if (typeof output === 'string' && output) {
      this.openTutorTurn();
      this.tutorLine = (this.tutorLine + output).replace(/\s+/g, ' ').trimStart();
    }
    if (content.interrupted) {
      // The learner spoke over the tutor: drop what hasn't been played, and
      // say how much they heard (read with their words, not a turn of its own).
      const played = this.turnStart === null ? this.turnMs : Math.max(0, Math.min(this.turnMs, this.now() - this.turnStart));
      if (this.tutorTurnOpen && this.turnMs - played >= CUT_OFF_MS) {
        const note = cutOffNote(heardPart(spoken(this.tutorLine), this.turnMs ? played / this.turnMs : 0));
        this.send({ clientContent: { turns: [{ role: 'user', parts: [{ text: note }] }], turnComplete: false } });
      }
      this.options.audio.clear();
      this.meter.clearSpeech(this.now());
      this.speechUntil = Math.min(this.speechUntil, this.now());
    }
    if (content.turnComplete || content.interrupted) this.tutorTurnOpen = false;
    this.emit();
  }

  private openTutorTurn() {
    if (this.tutorTurnOpen) return;
    this.tutorTurnOpen = true;
    this.youFresh = true;
    this.lastTutorLine = spoken(this.tutorLine) || this.lastTutorLine;
    this.tutorLine = '';
    this.turnStart = null;
    this.turnMs = 0;
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
    const at = this.results.findIndex((item) => item.card.id === card.id);
    if (!this.learnerAnswered()) {
      // Nothing said since the last saved card: the tutor is guessing, often
      // from the previous answer. Keep the card open and have it wait.
      if (at >= 0) return nextReply(this.options.cards, this.results, 'already saved');
      return { result: NOT_ANSWERED, next: String(args.card).trim() };
    }
    this.heardMs = 0;
    this.heardWords = false;
    this.freshCard = true;
    this.turnSinceSave = false;
    const said = typeof args.said === 'string' ? args.said.replace(/\s+/g, ' ').trim().slice(0, 200) : '';
    if (said) {
      // Show what the tutor understood rather than the raw transcript, which mishears more than the tutor does.
      this.youLine = said;
      this.youFresh = true;
    }
    const result = { card, outcome, said };
    // A card the tutor comes back to keeps its latest result, and is rated once.
    if (at >= 0) this.results[at] = result;
    else {
      this.results.push(result);
      if (outcome !== 'skipped') this.options.onRate?.(card, outcome);
    }
    this.emit();
    return nextReply(this.options.cards, this.results, 'saved');
  }

  // ---------------------------------------------------------------- timing
  /**
   * True once the learner has said something since the last saved card. With
   * the gate, only speech it let through counts: that is all the tutor heard,
   * and the transcript of the previous answer often arrives after that card
   * was saved, which made the next card look answered.
   */
  private learnerAnswered(): boolean {
    return this.gate ? this.heardMs >= ANSWER_SPEECH_MS : this.heardWords;
  }

  /** Who is talking and how loud, right now, for the picture (poll it each frame or so). */
  voice = (): Voice => {
    if (this.phase !== 'live') return { who: null, level: 0 };
    const voice = this.meter.voice(this.now());
    return this.muted && voice.who === 'you' ? { who: null, level: 0 } : voice;
  };

  private speechLeftMs(): number {
    return Math.max(0, this.speechUntil - this.now());
  }

  private tick() {
    if (this.phase !== 'live') return;
    const left = this.secondsLeft();
    if (left <= 60 && !this.warned) this.wrapUp(LAST_MINUTE_LINE);
    if (left <= 0) return this.finish();
    this.nudgeIfQuiet();
    this.emit();
  }

  /**
   * With app turns, the tutor only speaks after the learner does, so a
   * learner who is stuck would sit in silence: after a while, have it offer
   * (once) to repeat the question, give a hint or skip.
   */
  private nudgeIfQuiet() {
    if (!this.appTurns || this.nudged || this.muted || this.ending || this.learnerTalking || this.speechUntil <= 0) return;
    if (this.now() - Math.max(this.speechUntil, this.learnerAt) < QUIET_NUDGE_MS) return;
    this.nudged = true;
    this.send({ clientContent: { turns: [{ role: 'user', parts: [{ text: QUIET_LINE }] }], turnComplete: true } });
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
      tutorLine: spoken(this.tutorLine) || this.lastTutorLine,
      youLine: spoken(this.youLine),
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
