/**
 * Talk-back study: the phone reads each question aloud, listens for the
 * spoken answer, checks it with Smart Check, says how it went, and moves on.
 *
 * This is the state machine only. The voice (text to speech), the ears
 * (speech recognition) and the answer check are passed in, so the flow can be
 * tested without a phone and the screen stays a thin view over it.
 *
 * With a screen reader on, nothing chains on its own: the question and the
 * result are announced, and the person moves on with the buttons, so the app
 * never talks over VoiceOver or TalkBack.
 */
import { BLANK, buildQuiz, Rng } from '../core/questions';
import type { QuizCard } from '../core/questions';
import type { Assessment } from '../core/smartCheck';

export interface TalkCard {
  id: string;
  front: string;
  back: string;
}

export type ListenResult = { transcript: string } | { error: string };

export interface Voice {
  /** Says the text and resolves once it has been said (or was stopped). */
  say(text: string): Promise<void>;
  stop(): void;
}

export interface Ears {
  /** Listens for one answer. `hints` are words likely to be said (the expected answer). */
  listen(hints: string[]): Promise<ListenResult>;
  stop(): void;
}

export type Phase =
  | 'idle' // not started
  | 'asking' // reading the question
  | 'ready' // waiting for the person to answer (screen reader on, or nothing was heard)
  | 'listening' // the microphone is on
  | 'feedback' // saying how it went
  | 'waiting' // result shown; the person taps Next (screen reader on)
  | 'typing' // answering with the keyboard instead
  | 'paused'
  | 'done';

export type Outcome = 'right' | 'close' | 'wrong' | 'skipped';

export interface Result {
  card: TalkCard;
  answer: string;
  outcome: Outcome;
  assessment: Assessment | null;
}

export interface TalkbackOptions {
  voice: Voice;
  /** Null when recognition isn't available or allowed: answers are typed instead. */
  ears: Ears | null;
  check: (answer: string, expected: string, question: string) => Assessment;
  /** True while a screen reader is on: announce, never auto-advance or auto-listen. */
  screenReader: boolean;
  /** Saves the rating for a card that was answered (not for a skipped one). */
  onRate?: (card: TalkCard, assessment: Assessment) => void;
}

export interface Snapshot {
  phase: Phase;
  index: number;
  total: number;
  card: TalkCard | null;
  heard: string;
  message: string;
  last: Result | null;
  results: Result[];
}

const MISSES_BEFORE_TYPING = 2;

export function outcomeOf(assessment: Assessment): Outcome {
  if (assessment.bucket === 'Good' || assessment.bucket === 'Easy') return 'right';
  return assessment.bucket === 'Review' ? 'close' : 'wrong';
}

export function feedbackText(result: Result): string {
  const answer = result.card.back.trim();
  if (result.outcome === 'right') return 'Correct.';
  if (result.outcome === 'skipped') return answer ? `Skipped. The answer is ${answer}.` : 'Skipped.';
  if (result.outcome === 'close') return answer ? `Nearly. The answer is ${answer}.` : 'Nearly.';
  return answer ? `Not quite, the answer is ${answer}.` : 'Not quite.';
}

export function summaryText(results: Result[]): string {
  const right = results.filter((r) => r.outcome === 'right').length;
  return `All done. ${right} of ${results.length} right.`;
}

export class TalkbackSession {
  private phase: Phase = 'idle';
  private index = 0;
  private heard = '';
  private message = '';
  private results: Result[] = [];
  private misses = 0;
  // Every control bumps the generation, so a voice or microphone promise that
  // finishes after the person moved on is ignored.
  private generation = 0;
  private listeners = new Set<() => void>();
  private snapshot: Snapshot;

  constructor(private cards: TalkCard[], private options: TalkbackOptions) {
    this.snapshot = this.makeSnapshot();
  }

  // ------------------------------------------------------------- reading
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): Snapshot => this.snapshot;

  get canListen(): boolean {
    return !!this.options.ears;
  }

  setScreenReader(on: boolean) {
    this.options.screenReader = on;
  }

  // ------------------------------------------------------------ controls
  start() {
    if (!this.cards.length) return this.set('done', '');
    this.index = 0;
    this.results = [];
    this.ask();
  }

  /** Reads the current question again from the start. */
  repeat() {
    if (this.phase === 'done' || this.phase === 'idle') return;
    this.ask();
  }

  pause() {
    if (this.phase === 'done' || this.phase === 'idle' || this.phase === 'paused') return;
    this.halt();
    this.set('paused', 'Paused.');
  }

  resume() {
    if (this.phase !== 'paused') return;
    this.ask();
  }

  /** Starts listening by hand (screen reader on, or after nothing was heard). */
  listen() {
    if (!this.options.ears || !['ready', 'typing', 'asking'].includes(this.phase)) return;
    this.halt();
    this.startListening();
  }

  typeInstead() {
    if (this.phase === 'done' || this.phase === 'idle') return;
    this.halt();
    this.set('typing', '');
  }

  submitTyped(text: string) {
    if (this.phase === 'done' || this.phase === 'idle') return;
    this.halt();
    this.evaluate(text);
  }

  skip() {
    const card = this.current;
    if (!card || this.phase === 'done') return;
    this.halt();
    const result: Result = { card, answer: '', outcome: 'skipped', assessment: null };
    this.results = [...this.results, result];
    this.next();
  }

  next() {
    if (this.phase === 'done') return;
    this.halt();
    this.index += 1;
    this.misses = 0;
    if (this.index >= this.cards.length) {
      this.set('done', summaryText(this.results));
      if (!this.options.screenReader) void this.options.voice.say(this.message);
      return;
    }
    this.ask();
  }

  /** Stops the voice and the microphone (leaving the screen). */
  stop() {
    this.halt();
  }

  // ------------------------------------------------------------- the flow
  private get current(): TalkCard | null {
    return this.cards[this.index] ?? null;
  }

  private halt() {
    this.generation += 1;
    this.options.voice.stop();
    this.options.ears?.stop();
  }

  private async ask() {
    const card = this.current;
    if (!card) return;
    this.halt();
    const generation = this.generation;
    this.heard = '';
    this.set('asking', '');
    await this.options.voice.say(card.front);
    if (generation !== this.generation) return;
    if (this.options.screenReader) return this.set('ready', '');
    if (this.options.ears) this.startListening();
    else this.set('typing', '');
  }

  private async startListening() {
    const card = this.current;
    const ears = this.options.ears;
    if (!card || !ears) return;
    const generation = this.generation;
    this.set('listening', '');
    const result = await ears.listen(card.back.trim() ? [card.back.trim()] : []);
    if (generation !== this.generation) return;
    if ('transcript' in result && result.transcript.trim()) {
      this.heard = result.transcript.trim();
      return this.evaluate(this.heard);
    }
    // Nothing usable was heard: try once more, then offer typing.
    this.misses += 1;
    const error = 'error' in result ? result.error : 'no-speech';
    if (error === 'not-allowed' || error === 'service-not-allowed') {
      this.options.ears = null;
      return this.set('typing', 'Listening isn’t available, so type your answer instead.');
    }
    if (this.misses >= MISSES_BEFORE_TYPING || this.options.screenReader) {
      return this.set(this.options.screenReader ? 'ready' : 'typing', 'I didn’t catch that. Type your answer, or tap Answer aloud to try again.');
    }
    this.set('asking', 'I didn’t catch that.');
    await this.options.voice.say('I didn’t catch that. Please say it again.');
    if (generation !== this.generation) return;
    this.startListening();
  }

  private async evaluate(answer: string) {
    const card = this.current;
    if (!card) return;
    const generation = this.generation;
    const assessment = this.options.check(answer, card.back, card.front);
    const result: Result = { card, answer, outcome: outcomeOf(assessment), assessment };
    this.results = [...this.results, result];
    this.options.onRate?.(card, assessment);
    this.set('feedback', feedbackText(result));
    await this.options.voice.say(this.message);
    if (generation !== this.generation) return;
    if (this.options.screenReader) this.set('waiting', this.message);
    else this.next();
  }

  private set(phase: Phase, message: string) {
    this.phase = phase;
    this.message = message;
    this.snapshot = this.makeSnapshot();
    this.listeners.forEach((listener) => listener());
  }

  private makeSnapshot(): Snapshot {
    return {
      phase: this.phase,
      index: Math.min(this.index, this.cards.length),
      total: this.cards.length,
      card: this.current,
      heard: this.heard,
      message: this.message,
      last: this.results[this.results.length - 1] ?? null,
      results: this.results,
    };
  }
}

/**
 * Spoken questions from the quiz engine: a typed-answer question for each
 * card (its question, or a fill-in-the-blank from a longer answer), due and
 * weak cards first. The id stays the card's, so the rating goes to it.
 */
export function talkCards(cards: QuizCard[], seed = Date.now()): TalkCard[] {
  return buildQuiz(cards, cards.length, new Rng(seed), { types: ['recall', 'cloze'] }).map((q) => ({
    id: q.card_id,
    front: q.prompt.split(BLANK).join('(blank)'),
    back: q.answer,
  }));
}
