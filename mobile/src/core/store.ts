/**
 * Cards, progress and settings for one profile, plus the review scheduler.
 * A port of memorypal/store.py: same JSON payload, same scheduling rules.
 */
import { addDays, daysBetween, now, parseIso, todayIso, addDaysTo, isoDate } from './dates';
import { Card, Capture, DECK_INFO_FIELDS, DeckInfo, DeckInfoField, FeedbackEntry, captureFromDict, cardFromDict, deckInfoEmpty, deckInfoFromDict, deckName, feedbackFromDict, newCard, sampleCards } from './models';
import { Assessment } from './smartCheck';
import { pyMod, pyRound, strip } from './py';
import { AI_NOTE } from './questions';
import { hookKind, TECHNIQUE_KEYS } from './techniques';
import { normalizeSpace, splitStudyBits } from './text';

export type TextSize = 'Comfort' | 'Large' | 'Extra Large';

export interface Accessibility {
  text_size: TextSize;
  high_contrast: boolean;
  reduce_motion: boolean;
  simple_language: boolean;
  caregiver_mode: boolean;
  read_aloud: boolean;
  more_time: boolean;
  focus_outline: boolean;
}

export const ACCESSIBILITY_TOGGLES = ['high_contrast', 'reduce_motion', 'simple_language', 'caregiver_mode', 'read_aloud', 'more_time', 'focus_outline'] as const;

export const PERSONAS = ['student', 'everyday', 'caregiver', 'general'] as const;
export type PersonaKey = (typeof PERSONAS)[number];

export interface Onboarding {
  done: boolean;
  persona: PersonaKey | '';
}

export interface PlanSettings {
  unit: string;
  amount: string;
  deck: string;
  goal_label: string;
  habits: string[];
  [key: string]: unknown;
}

export interface StudyPlan {
  settings: PlanSettings;
  created: string;
  done: Record<string, number[]>;
  /** The day's steps as they stood at its first tick (ticks are saved by position). */
  today?: { date: string; steps: SavedPlanStep[] };
}

export type SavedPlanStep = Record<string, string | number | boolean | null>;
export const MAX_DAY_STEPS = 40;

/** A plan step with only values that save as JSON. */
export function plainPlanStep(step: object): SavedPlanStep {
  const out: SavedPlanStep = {};
  for (const [key, value] of Object.entries(step)) {
    if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) out[key] = value as string | number | boolean | null;
  }
  return out;
}

/**
 * The day's steps in the order they were first ticked in. Today's plan is
 * rebuilt from the cards each time it is shown, so steps come and go as the
 * day's work gets done. Saved steps keep their place (with the newer wording
 * when the step is still in the plan) and new steps go on the end.
 */
export function mergePlanSteps<T extends { title?: unknown }>(saved: readonly T[], live: readonly T[]): T[] {
  const keyed = (steps: readonly T[]) => {
    const seen = new Map<string, number>();
    return steps.map((step) => {
      const title = String(step.title ?? '');
      seen.set(title, (seen.get(title) ?? 0) + 1);
      return [`${seen.get(title)}:${title}`, step] as const;
    });
  };
  const fresh = new Map(keyed(live));
  const merged = keyed(saved).map(([key, step]) => {
    const now = fresh.get(key);
    fresh.delete(key);
    return now ?? step;
  });
  return [...merged, ...keyed(live).filter(([key]) => fresh.has(key)).map(([, step]) => step)].slice(0, MAX_DAY_STEPS);
}

export interface Payload {
  cards: Card[];
  captures: Capture[];
  decks: DeckInfo[];
  practiced: number;
  activity: Record<string, number>;
  daily_goal: number;
  nav_order: string[];
  accessibility: Accessibility;
  feedback: FeedbackEntry[];
  onboarding: Onboarding;
  study_plan: StudyPlan | Record<string, never>;
  practice_log: PracticeEntry[];
}

// The practice log: one line per answer on this device (never synced), so the
// study plan can learn the person's real pace, which ways of practicing work
// for them and when in the day they remember best (see store.py).
export const PRACTICE_LOG_MAX = 500;
/** A gap longer than this between two answers is a pause, not time on a card. */
export const PRACTICE_GAP_SECONDS = 300;
export const PRACTICE_METHODS = ['review', 'quiz', 'quiz_choices', 'talkback', 'tutor', 'repetition', 'puzzle'] as const;
export type PracticeMethod = (typeof PRACTICE_METHODS)[number];
const PRACTICE_HOOKS: readonly string[] = ['', 'own', ...TECHNIQUE_KEYS];

export interface PracticeEntry {
  /** Local time, YYYY-MM-DDTHH:MM:SS. */
  at: string;
  m: PracticeMethod;
  ok: boolean;
  /** Seconds since the answer before (0 when unknown or after a pause). */
  sec: number;
  /** The technique of the card's hook ('own', or '' for none). */
  hook: string;
}

export function normalizePracticeEntry(raw: unknown): PracticeEntry | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const source = raw as Record<string, unknown>;
  const at = source.at;
  if (typeof at !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(at)) return null;
  const method = source.m as PracticeMethod;
  if (!PRACTICE_METHODS.includes(method)) return null;
  const sec = source.sec;
  const hook = source.hook;
  return {
    at,
    m: method,
    ok: source.ok === true,
    sec: typeof sec === 'number' && Number.isInteger(sec) && sec >= 0 && sec <= PRACTICE_GAP_SECONDS ? sec : 0,
    hook: typeof hook === 'string' && PRACTICE_HOOKS.includes(hook) ? hook : '',
  };
}

export function normalizePracticeLog(raw: unknown): PracticeEntry[] {
  const entries = (Array.isArray(raw) ? raw : []).map(normalizePracticeEntry).filter((entry): entry is PracticeEntry => !!entry);
  // A stable sort by time, as Python's sort is.
  entries.sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
  return entries.slice(-PRACTICE_LOG_MAX);
}

/** Local date and time as the log writes it. */
export function localStamp(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${isoDate(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export interface StorageAdapter {
  load(): string | null;
  save(text: string): void;
}

/** A store that keeps everything in memory (tests, previews). */
export class MemoryAdapter implements StorageAdapter {
  text: string | null = null;
  load() {
    return this.text;
  }
  save(text: string) {
    this.text = text;
  }
}

/**
 * A change is written once changes have paused this long, so a run of quick
 * ratings is one write while the person reads the next card, instead of one
 * whole-profile write (a long pause on a big library) after every tap.
 */
export const WRITE_DELAY_MS = 1_500;
/** ...but never later than this after the first unsaved change. */
export const WRITE_MAX_DELAY_MS = 5_000;

export const MAX_DAILY_GOAL = 500;
export const MAX_INTERVAL = 365;

function safeInt(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === 'boolean') return Number(value);
  if (typeof value === 'string' && /^\s*[-+]?\d+\s*$/.test(value)) return parseInt(value, 10);
  return fallback;
}

export function clampGoal(value: unknown): number {
  return Math.max(1, Math.min(MAX_DAILY_GOAL, safeInt(value, 15)));
}

export function defaultAccessibility(): Accessibility {
  return {
    text_size: 'Comfort',
    high_contrast: false,
    reduce_motion: false,
    simple_language: false,
    caregiver_mode: false,
    read_aloud: false,
    more_time: false,
    focus_outline: false,
  };
}

export function normalizeAccessibility(raw: unknown): Accessibility {
  const prefs = defaultAccessibility();
  if (raw && typeof raw === 'object') {
    const source = raw as Record<string, unknown>;
    for (const key of Object.keys(prefs) as (keyof Accessibility)[]) {
      if (key in source) (prefs as unknown as Record<string, unknown>)[key] = source[key];
    }
  }
  if (!['Comfort', 'Large', 'Extra Large'].includes(prefs.text_size)) prefs.text_size = 'Comfort';
  for (const key of ACCESSIBILITY_TOGGLES) prefs[key] = Boolean(prefs[key]);
  return prefs;
}

export function normalizeOnboarding(raw: unknown): Onboarding {
  // Data saved before onboarding existed belongs to people already using the app.
  if (!raw || typeof raw !== 'object') return { done: true, persona: '' };
  const source = raw as Record<string, unknown>;
  const persona = source.persona as PersonaKey;
  return { done: source.done === undefined ? true : Boolean(source.done), persona: PERSONAS.includes(persona) ? persona : '' };
}

// What a saved plan may say. Plans arrive from other devices through sync, so
// a plan asking for a million days (or a habit that isn't a word) is cut down
// here instead of freezing the app when today's plan is worked out.
export const PLAN_AMOUNTS: Record<string, [number, number, string]> = { minutes: [1, 600, '30'], hours: [1, 24, '1'], days: [1, 365, '1'], weeks: [1, 52, '1'] };
export const PLAN_HABITS = ['mnemonics', 'repetition', 'quick_mc', 'games', 'breaks', 'explain'];
const MAX_PLAN_TEXT = 200;

const planText = (value: unknown, fallback: string) => (typeof value === 'string' && [...value].length <= MAX_PLAN_TEXT ? value : fallback);

export function normalizePlanSettings(raw: Record<string, unknown>): PlanSettings {
  const unit = typeof raw.unit === 'string' && Object.hasOwn(PLAN_AMOUNTS, raw.unit) ? raw.unit : 'minutes';
  const [low, high, fallback] = PLAN_AMOUNTS[unit];
  const value = raw.amount === undefined ? fallback : raw.amount;
  const clamp = (n: number) => String(Math.max(low, Math.min(high, n)));
  let amount = fallback;
  if (typeof value === 'number') amount = Number.isInteger(value) ? clamp(value) : fallback;
  // Plain digits only, as on the desktop.
  else if (typeof value === 'string' && /^[0-9]{1,12}$/.test(value)) amount = clamp(parseInt(value, 10));
  const habits = new Set(Array.isArray(raw.habits) ? raw.habits.filter((habit) => typeof habit === 'string') : []);
  return {
    unit,
    amount,
    deck: planText(raw.deck, 'All decks'),
    goal_label: planText(raw.goal_label, 'Long-term retention'),
    habits: PLAN_HABITS.filter((key) => habits.has(key)),
  };
}

export function normalizeStudyPlan(raw: unknown): StudyPlan | Record<string, never> {
  if (!raw || typeof raw !== 'object') return {};
  const source = raw as Record<string, unknown>;
  if (!source.settings || typeof source.settings !== 'object' || Array.isArray(source.settings)) return {};
  const done: Record<string, number[]> = {};
  if (source.done && typeof source.done === 'object') {
    for (const [day, indexes] of Object.entries(source.done as Record<string, unknown>)) {
      if (!Array.isArray(indexes)) continue;
      done[String(day)] = [...new Set(indexes.filter((index) => /^[0-9]{1,4}$/.test(String(index))).map((index) => Number(index)))].sort((a, b) => a - b);
    }
  }
  const plan: StudyPlan = { settings: normalizePlanSettings(source.settings as Record<string, unknown>), created: String(source.created || todayIso()), done };
  const today = source.today as { date?: unknown; steps?: unknown } | undefined;
  if (today && typeof today === 'object' && Array.isArray(today.steps) && today.date) {
    const steps = today.steps
      .slice(0, MAX_DAY_STEPS)
      .filter((step) => step && typeof step === 'object' && !Array.isArray(step) && (step as { title?: unknown }).title)
      .map((step) => plainPlanStep(step as object));
    if (steps.length) plan.today = { date: String(today.date), steps };
  }
  return plan;
}

function loadItems<T>(raw: unknown, factory: (item: Record<string, unknown>) => T): T[] {
  if (!Array.isArray(raw)) return [];
  const items: T[] = [];
  for (const item of raw) {
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      try {
        items.push(factory(item as Record<string, unknown>));
      } catch {
        // skip one damaged record rather than losing the whole file
      }
    }
  }
  return items;
}

/** Set details with one entry per set name (the last wins) and no empty ones. */
export function uniqueDecks(infos: DeckInfo[]): DeckInfo[] {
  const byName = new Map<string, DeckInfo>();
  for (const info of infos) {
    if (deckInfoEmpty(info)) continue;
    byName.delete(info.id);
    byName.set(info.id, info);
  }
  return [...byName.values()];
}

/**
 * The set a capture belongs to: its own `deck`, or for older notes a title
 * "<set>: ..." naming a set in `decks` (any set when decks is omitted).
 */
export function captureDeck(capture: Capture, decks?: string[]): string {
  if (capture.deck) return capture.deck;
  const title = String(capture.title || '');
  const at = title.indexOf(': ');
  const head = at >= 0 ? deckName(title.slice(0, at)) : '';
  return head && (!decks || decks.includes(head)) ? head : '';
}

const AI_PATHWAY = 'Made with AI';

/** The sentence an AI card's answer came from (its hook's Source: "..."), or ''. */
export function sourceQuote(card: Pick<Card, 'association'>): string {
  const match = /Source: "([\s\S]+)"\s*$/.exec(String(card.association || ''));
  return match ? match[1].trim() : '';
}

/** What an AI card was made from, by name ("Made with AI > <title>"), or ''. */
export function aiSourceTitle(card: Pick<Card, 'pathway'>): string {
  const pathway = String(card.pathway || '');
  const at = pathway.indexOf(' > ');
  return at >= 0 && pathway.slice(0, at) === AI_PATHWAY ? pathway.slice(at + 3).trim() : '';
}

/** Lower case words only, for finding a quote in notes whatever the punctuation. */
export function plainText(text: unknown): string {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]|_/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
}

/** Move notes to another set ('' for none), dropping an old "<set>: " title prefix. */
export function moveCapture(capture: Capture, from: string, to: string) {
  const prefix = `${from}: `;
  if (capture.title.startsWith(prefix) && capture.title.length > prefix.length) capture.title = capture.title.slice(prefix.length);
  capture.deck = to;
}

interface LastAction {
  cardId: string;
  snapshot: Card;
  activityKey: string;
  practicedBefore: number;
  /** The practice log's length before the rating, to take its line back on undo. */
  logged: number;
}

export class MemoryStore {
  cards: Card[] = [];
  captures: Capture[] = [];
  /** Each set's own details (exam date, AI style...), by set name. */
  deckInfos: DeckInfo[] = [];
  practiced = 0;
  activity: Record<string, number> = {};
  dailyGoal = 15;
  navOrder: string[] = [];
  accessibility: Accessibility = defaultAccessibility();
  feedback: FeedbackEntry[] = [];
  onboarding: Onboarding = { done: false, persona: '' };
  studyPlan: StudyPlan | Record<string, never> = {};
  /** This device's answers, newest last (see PracticeEntry). */
  practiceLog: PracticeEntry[] = [];
  lastAction: LastAction | null = null;
  /** Set when the saved data couldn't be read and the app started fresh. */
  loadProblem = '';
  /** Increases on every change; React screens re-render on it. */
  version = 0;

  private listeners = new Set<() => void>();
  private writeTimer: ReturnType<typeof setTimeout> | null = null;
  private firstUnsaved = 0;

  /**
   * With `deferWrites` (the app), a change updates the screens straight away
   * and reaches storage a moment later, in one write however many changes
   * came in between, so a tap never waits on the disk. `flush()` writes
   * anything still waiting; the app calls it whenever it leaves the screen.
   */
  constructor(private adapter: StorageAdapter = new MemoryAdapter(), private options: { deferWrites?: boolean } = {}) {
    this.load();
  }

  // ------------------------------------------------------------------ data
  load() {
    let text: string | null = null;
    try {
      text = this.adapter.load();
    } catch {
      text = null;
    }
    if (!text) {
      this.cards = sampleCards();
      this.onboarding = { done: false, persona: '' };
      this.save();
      return;
    }
    let raw: unknown = null;
    try {
      raw = JSON.parse(text);
    } catch {
      raw = null;
    }
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      this.loadProblem = 'Your saved MemoryPal data could not be read, so the app started fresh.';
      this.cards = sampleCards();
      return; // don't overwrite the damaged data until the person changes something
    }
    this.applyRaw(raw as Record<string, unknown>);
  }

  /** Fill the store from a saved payload, tolerating damaged fields. */
  applyRaw(raw: Record<string, unknown>) {
    const activity: Record<string, number> = {};
    if (raw.activity && typeof raw.activity === 'object' && !Array.isArray(raw.activity)) {
      for (const [day, count] of Object.entries(raw.activity as Record<string, unknown>)) {
        const value = safeInt(count, 0);
        if (value > 0) activity[String(day)] = value;
      }
    }
    this.cards = loadItems(raw.cards, cardFromDict);
    this.captures = loadItems(raw.captures, captureFromDict);
    this.deckInfos = uniqueDecks(loadItems(raw.decks, deckInfoFromDict));
    this.practiced = Math.max(0, safeInt(raw.practiced, 0));
    this.activity = activity;
    this.dailyGoal = clampGoal(raw.daily_goal ?? 15);
    this.navOrder = Array.isArray(raw.nav_order) ? raw.nav_order.map(String) : [];
    this.accessibility = normalizeAccessibility(raw.accessibility);
    this.feedback = loadItems(raw.feedback, feedbackFromDict);
    this.onboarding = normalizeOnboarding(raw.onboarding);
    this.studyPlan = normalizeStudyPlan(raw.study_plan);
    // Synced data never carries this device's log, so keep ours when it is missing.
    if ('practice_log' in raw) this.practiceLog = normalizePracticeLog(raw.practice_log);
  }

  payload(): Payload {
    return {
      cards: this.cards.map((card) => ({ ...card })),
      captures: this.captures.map((capture) => ({ ...capture, chunks: [...capture.chunks] })),
      decks: this.deckInfos.map((info) => ({ ...info })),
      practiced: this.practiced,
      activity: { ...this.activity },
      daily_goal: this.dailyGoal,
      nav_order: [...this.navOrder],
      accessibility: { ...this.accessibility },
      feedback: this.feedback.map((entry) => ({ ...entry })),
      onboarding: { ...this.onboarding },
      study_plan: normalizeStudyPlan(this.studyPlan),
      practice_log: this.practiceLog.map((entry) => ({ ...entry })),
    };
  }

  save() {
    this.loadProblem = '';
    if (this.options.deferWrites) this.queueWrite();
    else this.write();
    this.version += 1;
    this.listeners.forEach((listener) => listener());
  }

  /** Write any change that hasn't reached storage yet. */
  flush() {
    if (this.writeTimer) this.write();
  }

  private queueWrite() {
    const now = Date.now();
    if (this.writeTimer) clearTimeout(this.writeTimer);
    else this.firstUnsaved = now;
    const wait = Math.max(0, Math.min(WRITE_DELAY_MS, this.firstUnsaved + WRITE_MAX_DELAY_MS - now));
    this.writeTimer = setTimeout(() => this.write(), wait);
  }

  private write() {
    if (this.writeTimer) clearTimeout(this.writeTimer);
    this.writeTimer = null;
    try {
      // Compact: indenting made the saved text about a third bigger, and it
      // is written on every change.
      this.adapter.save(JSON.stringify(this.payload()));
    } catch {
      // storage full or unavailable; the change stays in memory
    }
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Replace everything with a backup (desktop or phone JSON). */
  importBackup(raw: Record<string, unknown>) {
    this.applyRaw(raw);
    this.onboarding = { done: true, persona: this.onboarding.persona };
    this.lastAction = null;
    this.save();
  }

  /** Take synced data (cards, captures, counts, settings) and save it. */
  replaceWith(raw: Record<string, unknown>) {
    // Screens hold card objects (the review queue, a quiz round), so keep the
    // same object for each id; otherwise later ratings change a detached copy.
    const liveCards = new Map(this.cards.map((card) => [card.id, card]));
    const liveCaptures = new Map(this.captures.map((capture) => [capture.id, capture]));
    this.applyRaw({ ...(this.payload() as unknown as Record<string, unknown>), ...raw });
    this.cards = this.cards.map((fresh) => {
      const existing = liveCards.get(fresh.id);
      return existing ? Object.assign(existing, fresh) : fresh;
    });
    this.captures = this.captures.map((fresh) => {
      const existing = liveCaptures.get(fresh.id);
      return existing ? Object.assign(existing, fresh) : fresh;
    });
    this.save();
  }

  exportBackup(): string {
    return JSON.stringify(this.payload(), null, 2);
  }

  reset() {
    this.cards = sampleCards();
    this.captures = [];
    this.deckInfos = [];
    this.practiced = 0;
    this.activity = {};
    this.dailyGoal = 15;
    this.navOrder = [];
    this.accessibility = defaultAccessibility();
    this.feedback = [];
    this.onboarding = { done: false, persona: '' };
    this.studyPlan = {};
    this.practiceLog = [];
    this.lastAction = null;
    this.save();
  }

  // ------------------------------------------------------------- settings
  setAccessibility(changes: Partial<Accessibility>) {
    this.accessibility = normalizeAccessibility({ ...this.accessibility, ...changes });
    this.save();
  }

  setDailyGoal(value: number) {
    this.dailyGoal = clampGoal(value);
    this.save();
  }

  finishOnboarding(persona: PersonaKey | '') {
    this.onboarding = { done: true, persona };
    this.save();
  }

  // ---------------------------------------------------------------- cards
  addCard(card: Card) {
    this.addCards([card]);
  }

  /** Add several cards (newest first) with a single save. */
  addCards(cards: Card[]) {
    if (!cards.length) return;
    this.cards = [...[...cards].reverse(), ...this.cards];
    this.save();
  }

  static EDITABLE_CARD_FIELDS = ['deck', 'front', 'back', 'pathway', 'association'] as const;

  /** Edit a card's words or deck. Its review schedule is left alone. */
  updateCard(card: Card, fields: Partial<Pick<Card, 'deck' | 'front' | 'back' | 'pathway' | 'association'>>) {
    for (const name of MemoryStore.EDITABLE_CARD_FIELDS) {
      if (!(name in fields)) continue;
      const value = String(fields[name] ?? '').trim();
      card[name] = name === 'deck' ? value || 'General' : value;
    }
    this.save();
  }

  deleteCards(ids: Iterable<string>): number {
    const doomed = new Set(ids);
    const before = this.cards.length;
    this.cards = this.cards.filter((card) => !doomed.has(card.id));
    if (this.lastAction && doomed.has(this.lastAction.cardId)) this.lastAction = null;
    const removed = before - this.cards.length;
    if (removed) this.save();
    return removed;
  }

  /** Make these cards new again, keeping their words and cues. */
  resetProgress(ids: Iterable<string>) {
    const chosen = new Set(ids);
    const fresh = newCard();
    for (const card of this.cards) {
      if (!chosen.has(card.id)) continue;
      Object.assign(card, {
        interval: fresh.interval,
        repetitions: fresh.repetitions,
        ease: fresh.ease,
        lapses: fresh.lapses,
        last_score: fresh.last_score,
        last_result: fresh.last_result,
        buried_until: fresh.buried_until,
        next_review: todayIso(),
      });
    }
    this.save();
  }

  findCard(id: string): Card | undefined {
    return this.cards.find((card) => card.id === id);
  }

  addCapture(capture: Capture) {
    this.captures = [capture, ...this.captures];
    this.save();
  }

  /** Save edited notes: a new title and text, split into study bits again. AI notes keep their first line. */
  updateCapture(id: string, title: string, text: string): Capture | undefined {
    const capture = this.findCapture(id);
    if (!capture) return undefined;
    const body = strip(text);
    const updated: Capture = {
      ...capture,
      title: normalizeSpace(title) || capture.title,
      notes: capture.notes.startsWith(AI_NOTE) ? `${AI_NOTE}\n${body}` : body,
      chunks: splitStudyBits(body),
    };
    this.captures = this.captures.map((item) => (item.id === id ? updated : item));
    this.save();
    return updated;
  }

  findCapture(id: string): Capture | undefined {
    return this.captures.find((capture) => capture.id === id);
  }

  deleteCapture(id: string): boolean {
    const before = this.captures.length;
    this.captures = this.captures.filter((capture) => capture.id !== id);
    if (this.captures.length === before) return false;
    this.save();
    return true;
  }

  /** Saved notes that belong to this set, newest first (older notes by their "<set>: " title). */
  notesForDeck(name: string): Capture[] {
    const deck = deckName(name);
    return deck ? this.captures.filter((capture) => captureDeck(capture) === deck) : [];
  }

  /**
   * The notes a card was made from and which bit holds its source sentence
   * (-1 when the quote spans bits or there is none), or null. Its own set's
   * notes are searched first; without a quote, notes titled like the card's
   * AI source count.
   */
  sourceNotes(card: Card): { capture: Capture; bit: number } | null {
    const own = this.notesForDeck(card.deck || 'General');
    const candidates = [...own, ...this.captures.filter((capture) => !own.includes(capture))];
    const quote = plainText(sourceQuote(card)).slice(0, 80);
    if (quote.length >= 12) {
      for (const capture of candidates) {
        const chunks = capture.chunks.length ? capture.chunks : splitStudyBits(capture.notes);
        const bit = chunks.findIndex((chunk) => plainText(chunk).includes(quote));
        if (bit >= 0) return { capture, bit };
        if (plainText(capture.notes).includes(quote)) return { capture, bit: -1 };
      }
    }
    const title = aiSourceTitle(card);
    if (title) {
      const capture = own.find((item) => plainText(item.title) === plainText(title));
      if (capture) return { capture, bit: -1 };
    }
    return null;
  }

  // ---------------------------------------------------------- set details
  /** A copy of this set's details (blank when it has none). */
  deckInfo(name: string): DeckInfo {
    const id = deckName(name);
    const found = this.deckInfos.find((info) => info.id === id);
    return found ? { ...found } : { id, exam_date: '', about: '', ai_style: '', ai_examples: '' };
  }

  /** Change some of a set's details and save. */
  setDeckInfo(name: string, fields: Partial<Pick<DeckInfo, DeckInfoField>>): DeckInfo {
    const current = this.deckInfo(name);
    if (!current.id) return current;
    const raw: Record<string, unknown> = { ...current };
    for (const field of DECK_INFO_FIELDS) if (field in fields) raw[field] = fields[field];
    const info = deckInfoFromDict(raw);
    if (this.storeDeckInfo(info)) this.save();
    return info;
  }

  /** Put info in place (or remove it when empty). True if anything changed. */
  storeDeckInfo(info: DeckInfo): boolean {
    if (!info.id) return false;
    if (deckInfoEmpty(info)) return this.dropDeckInfo(info.id);
    const existing = this.deckInfos.find((item) => item.id === info.id);
    if (existing) {
      if (DECK_INFO_FIELDS.every((field) => existing[field] === info[field])) return false;
      Object.assign(existing, info);
      return true;
    }
    this.deckInfos = [...this.deckInfos, info];
    return true;
  }

  dropDeckInfo(name: string): boolean {
    const id = deckName(name);
    const before = this.deckInfos.length;
    this.deckInfos = this.deckInfos.filter((info) => info.id !== id);
    return this.deckInfos.length !== before;
  }

  // ------------------------------------------------------------- queries
  decks(): string[] {
    const names: string[] = [];
    for (const card of this.cards) {
      const name = card.deck || 'General';
      if (!names.includes(name)) names.push(name);
    }
    return names.sort((a, b) => (a.toLowerCase() < b.toLowerCase() ? -1 : a.toLowerCase() > b.toLowerCase() ? 1 : 0));
  }

  deckSummary(): Record<string, { total: number; due: number; weak: number; mastery: number }> {
    const summary: Record<string, { total: number; due: number; weak: number; mastery: number }> = {};
    const today = todayIso();
    for (const deck of this.decks()) {
      const cards = this.cards.filter((card) => (card.deck || 'General') === deck);
      const mastered = cards.filter((card) => card.last_score >= 82).length;
      summary[deck] = {
        total: cards.length,
        due: cards.filter((card) => card.next_review <= today && card.buried_until <= today).length,
        weak: cards.filter((card) => card.lapses > 0 || card.last_score < 64 || card.repetitions === 0).length,
        mastery: cards.length ? pyRound((mastered / cards.length) * 100) : 0,
      };
    }
    return summary;
  }

  /** Cards due by `on` (today by default); with `since`, only those first due after it. */
  dueCards(deck?: string | null, on?: string, since?: string | null): Card[] {
    const day = on || todayIso();
    let cards = this.cards.filter((card) => card.next_review <= day && card.buried_until <= day);
    if (since) cards = cards.filter((card) => card.next_review > since);
    if (deck) cards = cards.filter((card) => (card.deck || 'General') === deck);
    return cards;
  }

  weakCards(): Card[] {
    const scored = this.cards.filter((card) => card.lapses > 0 || card.last_score < 64 || card.repetitions === 0);
    return scored.sort((a, b) =>
      b.lapses - a.lapses
      || a.last_score - b.last_score
      || (a.next_review < b.next_review ? -1 : a.next_review > b.next_review ? 1 : 0)
      || (a.front.toLowerCase() < b.front.toLowerCase() ? -1 : a.front.toLowerCase() > b.front.toLowerCase() ? 1 : 0));
  }

  upcomingCards(): Card[] {
    const today = todayIso();
    return this.cards.filter((card) => card.next_review > today).sort((a, b) => (a.next_review < b.next_review ? -1 : a.next_review > b.next_review ? 1 : 0));
  }

  isLeech(card: Card): boolean {
    return card.lapses >= 8;
  }

  todayCount(): number {
    return this.activity[todayIso()] ?? 0;
  }

  currentStreak(): number {
    let streak = 0;
    let cursor = now();
    if ((this.activity[isoDate(cursor)] ?? 0) <= 0) cursor = addDaysTo(cursor, -1);
    while ((this.activity[isoDate(cursor)] ?? 0) > 0) {
      streak += 1;
      cursor = addDaysTo(cursor, -1);
    }
    return streak;
  }

  /** Count practice that isn't a scheduled review (quiz answers, puzzle rounds). */
  recordPractice(count = 1) {
    this.practiced += count;
    this.logActivity(count);
    this.save();
  }

  logActivity(count = 1) {
    const key = todayIso();
    this.activity[key] = (this.activity[key] ?? 0) + count;
  }

  // ------------------------------------------------------------ scheduler
  static daysOverdue(card: Card): number {
    const due = parseIso(card.next_review);
    return due ? Math.max(0, daysBetween(due, now())) : 0;
  }

  /**
   * SM-2 style spacing with hard/easy steps and credit for late reviews.
   * quality 3 = recalled with effort, 4 = good, 5 = easy.
   */
  nextInterval(card: Card, quality: number): number {
    let interval: number;
    if (card.repetitions === 0) {
      interval = ({ 3: 1, 4: 1 } as Record<number, number>)[quality] ?? 3;
    } else if (card.repetitions === 1) {
      interval = ({ 3: 2, 4: 3 } as Record<number, number>)[quality] ?? 5;
    } else {
      const overdueCredit = (({ 3: 0.25, 4: 0.5 } as Record<number, number>)[quality] ?? 1.0) * MemoryStore.daysOverdue(card);
      const factor = ({ 3: 1.2, 4: card.ease } as Record<number, number>)[quality] ?? card.ease * 1.3;
      interval = Math.max(card.interval + 1, pyRound((card.interval + overdueCredit) * factor));
      if (interval >= 7) {
        // Spread cards learned together across nearby days (deterministic per card).
        const spread = Math.max(1, pyRound(interval * 0.05));
        let sum = 0;
        for (const char of card.id) sum += char.codePointAt(0) ?? 0;
        interval += pyMod(sum + card.repetitions, 2 * spread + 1) - spread;
        // The spread must never undo the growth a success earned.
        interval = Math.max(interval, card.interval + 1);
      }
    }
    return Math.max(1, Math.min(MAX_INTERVAL, interval));
  }

  /** Note one answer in the practice log (how long it took is the gap since the last one). */
  logPractice(method: PracticeMethod, ok: boolean, card?: Card | null, when?: Date, save = false) {
    if (!PRACTICE_METHODS.includes(method)) return;
    const at = localStamp(when ?? now());
    let sec = 0;
    const last = this.practiceLog[this.practiceLog.length - 1];
    if (last) {
      const gap = (new Date(at).getTime() - new Date(last.at).getTime()) / 1000;
      sec = gap > 0 && gap <= PRACTICE_GAP_SECONDS ? Math.trunc(gap) : 0;
    }
    this.practiceLog.push({ at, m: method, ok: !!ok, sec, hook: card ? hookKind(card.association) : '' });
    if (this.practiceLog.length > PRACTICE_LOG_MAX) this.practiceLog.splice(0, this.practiceLog.length - PRACTICE_LOG_MAX);
    if (save) this.save();
  }

  schedule(card: Card, quality: number, assessment?: Assessment | null, method: PracticeMethod = 'review') {
    const snapshot = { ...card };
    const logged = this.practiceLog.length;
    // The answer's hook is the one the card had while it was being recalled.
    this.logPractice(method, quality >= 3, card);
    const activityKey = todayIso();
    if (quality < 3) {
      card.repetitions = 0;
      card.interval = 1;
      card.lapses += 1;
    } else {
      card.interval = this.nextInterval(card, quality);
      card.repetitions += 1;
    }
    card.ease = Math.min(3.5, Math.max(1.3, card.ease + (0.1 - (5 - quality) * 0.08)));
    card.next_review = addDays(card.interval);
    if (assessment) {
      card.last_score = Math.trunc(assessment.score);
      card.last_result = assessment.label || 'Checked';
    } else {
      card.last_score = ({ 1: 20, 2: 35, 3: 55, 4: 78, 5: 95 } as Record<number, number>)[quality] ?? 0;
      card.last_result = ({ 1: 'Again', 2: 'Weak', 3: 'Review', 4: 'Good', 5: 'Easy' } as Record<number, string>)[quality] ?? 'Checked';
    }
    this.practiced += 1;
    this.logActivity();
    this.lastAction = { cardId: card.id, snapshot, activityKey, practicedBefore: this.practiced - 1, logged };
    this.save();
  }

  undoLast(): boolean {
    const action = this.lastAction;
    if (!action) return false;
    const card = this.findCard(action.cardId);
    if (!card) return false;
    Object.assign(card, action.snapshot);
    // Step back by one: a sync since the rating may have added other devices' counts.
    this.practiced = Math.max(0, this.practiced - 1);
    const key = action.activityKey;
    if ((this.activity[key] ?? 0) > 0) {
      this.activity[key] -= 1;
      if (this.activity[key] <= 0) delete this.activity[key];
    }
    if (this.practiceLog.length === action.logged + 1) this.practiceLog.pop();
    this.lastAction = null;
    this.save();
    return true;
  }

  /** Skip for today: the card comes back tomorrow without counting as a miss. */
  buryCard(card: Card, days = 1) {
    card.buried_until = addDays(days);
    this.save();
  }

  // ----------------------------------------------------------- study plan
  setStudyPlan(settings: PlanSettings | null) {
    this.studyPlan = settings ? { settings: { ...settings }, created: todayIso(), done: {} } : {};
    this.save();
  }

  planStepsDone(day?: string): Set<number> {
    const plan = this.studyPlan as StudyPlan;
    if (!plan.settings) return new Set();
    return new Set(plan.done?.[day || todayIso()] ?? []);
  }

  /** The steps to show for the day: fixed in place once one is ticked. */
  planDaySteps<T extends { title?: unknown }>(steps: readonly T[], day?: string): T[] {
    const saved = (this.studyPlan as StudyPlan).today;
    if (!saved || saved.date !== (day || todayIso())) return [...steps];
    return mergePlanSteps(saved.steps as unknown as T[], steps);
  }

  /** Tick or untick a step; `steps` is the list the person is looking at. */
  togglePlanStep(index: number, day?: string, steps?: readonly { title?: unknown }[]): boolean {
    const plan = this.studyPlan as StudyPlan;
    if (!plan.settings) return false;
    const key = day || todayIso();
    if (steps) plan.today = { date: key, steps: this.planDaySteps(steps, key).map((step) => plainPlanStep(step)) };
    const done = this.planStepsDone(key);
    if (done.has(index)) done.delete(index);
    else done.add(index);
    // Keep only the last couple of weeks of ticks.
    const cutoff = addDays(-14);
    const history: Record<string, number[]> = {};
    for (const [date, indexes] of Object.entries(plan.done ?? {})) {
      if (date >= cutoff) history[date] = indexes;
    }
    history[key] = [...done].sort((a, b) => a - b);
    plan.done = history;
    this.save();
    return done.has(index);
  }
}
