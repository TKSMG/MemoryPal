/** Study plans for one session or several days (port of memorypal/planning.py). */
import { addDaysTo, daysBetween, isoDate, now, parseIso } from './dates';
import { pyInt, pyRound } from './py';
import { Capture, Card } from './models';
import { captureDeck, MemoryStore, plainText, PracticeEntry, sourceQuote, StudyPlan } from './store';
import { pickTechnique, TECHNIQUE_TITLES } from './techniques';
import { splitStudyBits } from './text';

export const STUDY_HABIT_OPTIONS: [string, string][] = [
  ['mnemonics', 'I remember better with mnemonics, stories, or images'],
  ['repetition', 'I like structured repetition drilling'],
  ['quick_mc', 'I prefer quick multiple choice over typing answers'],
  ['games', 'I like short recall-game breaks to reset focus'],
  ['breaks', 'I focus better with short rest breaks (Pomodoro style)'],
  ['explain', 'I learn by explaining ideas in my own words'],
];

export const TIME_UNIT_OPTIONS: Record<string, string[]> = {
  minutes: ['15', '30', '45', '60', '90'],
  hours: ['1', '2', '3', '4'],
  days: ['1', '2', '3', '5', '7'],
  weeks: ['1', '2', '3', '4'],
};
export const TIME_UNIT_ORDER = ['minutes', 'hours', 'days', 'weeks'];

export const MINUTES_PER_CARD = 0.6;
export const NEW_MATERIAL_REVIEW_DAYS = [2, 4, 7, 14, 21, 30];
export const SHORT_SESSION_MINUTES = 12;
export const MIN_STEP_MINUTES = 2;
export const FOCUS_BLOCK_MINUTES = 25;
export const BREAK_MINUTES = 5;
export const MINUTES_PER_NEW_CARD = 1.5;
export const MAX_NEW_CARDS_PER_SESSION = 20;
// The longest plans the app makes (a year of weeks; a day of minutes). A
// synced plan asking for more is cut to this rather than built day by day.
export const MAX_PLAN_DAYS = 400;
export const MAX_PLAN_MINUTES = 24 * 60;

export type Goal = 'cram' | 'exam_prep' | 'long_term';

/** Where a step sends the person: the desktop page key it was built for ('shuffle' is the repetition path).
 * 'focus' and 'testing' only appear in plans saved before those pages became Review modes. */
export type StepView = 'capture' | 'tools' | 'quiz' | 'review' | 'focus' | 'shuffle' | 'testing' | 'games' | 'stats' | 'break' | 'talkback' | 'notes';

export interface PlanStep {
  title: string;
  share: number;
  view: StepView;
  blurb: string;
  deck: string | null;
  minutes: number;
  quiz_mode?: 'self' | 'choices';
  /** A Review mode to start ('gentle', 'new'). */
  review_mode?: string;
  /** The memory technique a 'tools' step makes (techniques.ts keys). */
  technique?: string;
  /** The puzzle a 'games' step opens. */
  puzzle_kind?: string;
  /** The notes a 'notes' step opens, and the part to show (-1 for the top). */
  capture_id?: string;
  bit?: number;
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`;
}

/** Split minutes across steps in proportion to shares, summing exactly. */
export function allocateMinutes(shares: number[], minutes: number): number[] {
  const count = shares.length;
  if (!count) return [];
  const floor = minutes >= MIN_STEP_MINUTES * count ? MIN_STEP_MINUTES : 0;
  const spare = minutes - floor * count;
  const total = shares.reduce((sum, share) => sum + share, 0) || 1;
  const exact = shares.map((share) => (spare * share) / total);
  const allotted = exact.map((value) => pyInt(value));
  const leftovers = [...Array(count).keys()].sort((a, b) => (exact[b] - allotted[b]) - (exact[a] - allotted[a]));
  const extra = spare - allotted.reduce((sum, value) => sum + value, 0);
  for (const index of leftovers.slice(0, Math.max(0, extra))) allotted[index] += 1;
  return allotted.map((value) => floor + value);
}

function reviewDetail(dueCount: number, shareMinutes: number, perCard = MINUTES_PER_CARD): string {
  if (!dueCount) return 'Nothing is due, so this works through weak and fresh cards instead.';
  const needed = Math.max(1, pyRound(dueCount * perCard));
  if (needed > shareMinutes) {
    return `${plural(dueCount, 'card')} due (about ${needed} min) — do the oldest first; the rest can wait for tomorrow.`;
  }
  return `${plural(dueCount, 'card')} due, about ${needed} min.`;
}

// ------------------------------------------------------------ the learner
// What the practice log (store.practiceLog, this device only) says about the
// person. Each finding needs enough answers behind it before the plan uses it.
export const PROFILE_DAYS = 60;
export const MIN_PACE_ANSWERS = 15;
export const MIN_METHOD_ANSWERS = 8;
export const MIN_HOOK_ANSWERS = 6;
export const MIN_TIME_ANSWERS = 10;
const RECALL_METHODS: readonly string[] = ['review', 'quiz', 'quiz_choices', 'talkback', 'tutor'];
const TIMES_OF_DAY: [string, number, number][] = [['morning', 5, 12], ['afternoon', 12, 17], ['evening', 17, 22]];
export const GENTLE_PERSONAS: readonly string[] = ['everyday', 'caregiver'];
export const GENTLE_FOCUS_MINUTES = 15;
/** Missing this share of answers in the last week slows new cards down. */
export const STRUGGLING_MISS_RATE = 0.4;

const byText = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

export function timeOfDay(hour: number): string {
  return TIMES_OF_DAY.find(([, start, stop]) => start <= hour && hour < stop)?.[0] ?? 'night';
}

function recallRate(entries: PracticeEntry[]): number {
  return entries.length ? entries.filter((entry) => entry.ok).length / entries.length : 0;
}

export interface Rate {
  answers: number;
  rate: number;
}

export interface LearnerProfile {
  answers: number;
  minutes_per_card: number;
  measured_pace: boolean;
  methods: Record<string, Rate>;
  hooks: Record<string, Rate>;
  best_hook: string;
  miss_rate: number | null;
  best_time: string;
  best_hour: number | null;
}

/** Local calendar day of a date, at midnight. */
function dayOf(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

/** Pace, best methods, best technique and best time of day from the practice log. */
export function learnerProfile(store: MemoryStore, todayIn?: Date): LearnerProfile {
  const today = dayOf(todayIn ?? now());
  const cutoff = isoDate(addDaysTo(today, -PROFILE_DAYS));
  const week = isoDate(addDaysTo(today, -7));
  const log = (store.practiceLog ?? []).filter((entry) => entry.at.slice(0, 10) >= cutoff);
  const timed = log.filter((entry) => entry.sec >= 3 && RECALL_METHODS.includes(entry.m)).map((entry) => entry.sec).sort((a, b) => a - b);
  let perCard: number;
  let measured: boolean;
  if (timed.length >= MIN_PACE_ANSWERS) {
    // The middle answer's time, plus a few seconds to rate it.
    perCard = Math.min(2.5, Math.max(0.3, timed[Math.floor(timed.length / 2)] / 60 + 0.1));
    measured = true;
  } else {
    perCard = MINUTES_PER_CARD * (store.accessibility?.more_time ? 1.5 : 1);
    measured = false;
  }
  const methods: Record<string, Rate> = {};
  for (const method of [...new Set(log.map((entry) => entry.m))].sort(byText)) {
    const entries = log.filter((entry) => entry.m === method);
    methods[method] = { answers: entries.length, rate: recallRate(entries) };
  }
  const recall = log.filter((entry) => RECALL_METHODS.includes(entry.m));
  const hooks: Record<string, Rate> = {};
  const hookKinds = [...new Set(recall.map((entry) => entry.hook))].sort(byText);
  for (const kind of hookKinds) {
    const entries = recall.filter((entry) => entry.hook === kind);
    hooks[kind] = { answers: entries.length, rate: recallRate(entries) };
  }
  const plain = hooks[''] ?? { answers: 0, rate: 0 };
  let bestHook = '';
  let bestRate = 0.5;
  for (const kind of hookKinds) {
    const found = hooks[kind];
    if (kind === '' || kind === 'own' || found.answers < MIN_HOOK_ANSWERS) continue;
    const beatsPlain = plain.answers < MIN_HOOK_ANSWERS || found.rate >= plain.rate + 0.1;
    if (beatsPlain && found.rate > bestRate) [bestHook, bestRate] = [kind, found.rate];
  }
  const recent = recall.filter((entry) => entry.at.slice(0, 10) >= week);
  const missRate = recent.length >= 10 ? 1 - recallRate(recent) : null;
  const hourOf = (entry: PracticeEntry) => parseInt(entry.at.slice(11, 13), 10);
  const times: Record<string, Rate> = {};
  for (const name of [...TIMES_OF_DAY.map(([name]) => name), 'night']) {
    const entries = recall.filter((entry) => timeOfDay(hourOf(entry)) === name);
    if (entries.length >= MIN_TIME_ANSWERS) times[name] = { answers: entries.length, rate: recallRate(entries) };
  }
  let bestTime = '';
  let bestHour: number | null = null;
  const timeNames = Object.keys(times);
  if (timeNames.length >= 2) {
    const ranked = [...timeNames].sort((a, b) => times[b].rate - times[a].rate || byText(a, b));
    if (times[ranked[0]].rate - times[ranked[ranked.length - 1]].rate >= 0.1) {
      bestTime = ranked[0];
      const counts = new Map<number, number>();
      for (const entry of recall) {
        const hour = hourOf(entry);
        if (timeOfDay(hour) === bestTime) counts.set(hour, (counts.get(hour) ?? 0) + 1);
      }
      bestHour = [...counts.keys()].sort((a, b) => (counts.get(b) ?? 0) - (counts.get(a) ?? 0) || a - b)[0];
    }
  }
  return { answers: log.length, minutes_per_card: perCard, measured_pace: measured, methods, hooks, best_hook: bestHook, miss_rate: missRate, best_time: bestTime, best_hour: bestHour };
}

/** The hour (0-23) this person tends to remember best at, or null until the log can tell. */
export function bestStudyHour(store: MemoryStore, today?: Date): number | null {
  return learnerProfile(store, today).best_hour;
}

/** What the plan has learned about the person, in plain sentences (empty until it knows something). */
export function planInsights(store: MemoryStore, today?: Date): string[] {
  const profile = learnerProfile(store, today);
  const lines: string[] = [];
  if (profile.measured_pace) lines.push(`You take about ${Math.trunc(profile.minutes_per_card * 60 + 0.5)} seconds a card, so the plan times reviews to your pace.`);
  if (profile.best_hook) lines.push(`Cards with ${TECHNIQUE_TITLES[profile.best_hook].toLowerCase()} hooks are the ones you remember best, so the plan uses it more.`);
  const quiz = profile.methods.quiz;
  if (quiz && quiz.answers >= MIN_METHOD_ANSWERS && quiz.rate < 0.5) lines.push('Typed quiz answers have been hard lately, so quizzes start with multiple choice.');
  if (profile.miss_rate !== null && profile.miss_rate >= STRUGGLING_MISS_RATE) lines.push("You've missed quite a few this week, so the plan adds fewer new cards until they settle.");
  if (profile.best_time) lines.push(profile.best_time !== 'night' ? `You remember best in the ${profile.best_time}.` : 'You remember best at night.');
  return lines;
}

// ------------------------------------------------------------- the material
export const MAX_NOTE_CAPTURES = 40;
export const MAX_NOTE_BITS = 60;

const oneLine = (text: unknown) => String(text ?? '').split(/\s+/).filter(Boolean).join(' ');
const deckOf = (card: Card) => card.deck || 'General';
const wordCount = (text: string) => (text ? text.split(' ').length : 0);

function techniqueItem(card: Card): string {
  const back = oneLine(card.back);
  return back && back.split(' ').length <= 8 ? back : oneLine(card.front);
}

/** The set a step works on: the plan's own, else the one with the most weak cards. */
function focusDeck(store: MemoryStore, deck: string | null, weak: Card[]): string | null {
  if (deck) return deck;
  const counts = new Map<string, number>();
  for (const card of weak) counts.set(deckOf(card), (counts.get(deckOf(card)) ?? 0) + 1);
  if (!counts.size) for (const card of store.cards) counts.set(deckOf(card), (counts.get(deckOf(card)) ?? 0) + 1);
  return [...counts.keys()].sort((a, b) => (counts.get(b) ?? 0) - (counts.get(a) ?? 0) || byText(a, b))[0] ?? null;
}

type CardIndex = { byWord: Map<string, string[]>; joined: string };
export type PlanMemo = Map<string, unknown>;

function cardIndex(cards: Card[]): CardIndex {
  const byWord = new Map<string, string[]>();
  for (const card of cards) {
    for (const text of [plainText(card.back), plainText(sourceQuote(card)).slice(0, 80)]) {
      if (text.length >= 4) {
        const first = text.split(' ')[0];
        byWord.set(first, [...(byWord.get(first) ?? []), text]);
      }
    }
  }
  return { byWord, joined: cards.map((card) => `${plainText(card.front)} ${plainText(card.back)}`).join('\n') };
}

/** A note part is a card already when a card's answer or quote is in it, or it opens a card. */
function bitCovered(words: string, index: CardIndex): boolean {
  if (index.joined.includes(words.slice(0, 40))) return true;
  for (const word of new Set(words.split(' '))) {
    if ((index.byWord.get(word) ?? []).some((text) => words.includes(text))) return true;
  }
  return false;
}

/** The notes with the most parts no card covers, and how many ({ capture: null, count: 0 } for none). */
export function notesNotYetCards(store: MemoryStore, deck: string | null, memo: PlanMemo = new Map()): { capture: Capture | null; count: number } {
  const key = `notes\u0000${deck ?? ''}\u0000${deck === null ? 'all' : 'one'}`;
  const cached = memo.get(key) as { capture: Capture | null; count: number } | undefined;
  if (cached) return cached;
  let best: Capture | null = null;
  let bestCount = 0;
  for (const capture of (store.captures ?? []).slice(0, MAX_NOTE_CAPTURES)) {
    const owner = captureDeck(capture);
    if (deck && owner !== deck) continue;
    const cardsKey = `cards\u0000${owner}`;
    if (!memo.has(cardsKey)) memo.set(cardsKey, cardIndex(store.cards.filter((card) => !owner || deckOf(card) === owner)));
    const index = memo.get(cardsKey) as CardIndex;
    let count = 0;
    for (const bit of (capture.chunks.length ? capture.chunks : splitStudyBits(capture.notes)).slice(0, MAX_NOTE_BITS)) {
      const words = plainText(bit);
      if (wordCount(words) >= 4 && !bitCovered(words, index)) count += 1;
    }
    if (count > bestCount) [best, bestCount] = [capture, count];
  }
  const found = { capture: best, count: bestCount };
  memo.set(key, found);
  return found;
}

/** The weakest card whose source notes can be found, with them. */
function notesBehindWeak(store: MemoryStore, weak: Card[], memo: PlanMemo): { card: Card; capture: Capture; bit: number } | null {
  const key = `weak\u0000${weak.slice(0, 20).map((card) => card.id).join('\u0000')}`;
  if (!memo.has(key)) {
    let found: { card: Card; capture: Capture; bit: number } | null = null;
    for (const card of weak.slice(0, 20)) {
      const source = store.sourceNotes(card);
      if (source) {
        found = { card, capture: source.capture, bit: source.bit };
        break;
      }
    }
    memo.set(key, found);
  }
  return memo.get(key) as { card: Card; capture: Capture; bit: number } | null;
}

/** Days since 1970-01-01 of an ISO date (today when absent), as the desktop counts them. */
function dayTurn(on?: string): number {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(on ?? '') ?? /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate(now()));
  const [, year, month, day] = match!;
  return Math.round(Date.UTC(Number(year), Number(month) - 1, Number(day)) / 86_400_000);
}

const TECHNIQUE_REASONS: Record<string, string> = {
  acronym: 'A few short items with different first letters fit one word made of their initials.',
  chunk: 'Numbers and long lists are easier in small groups of three.',
  chain: 'Longer ideas link well, each one handing a clue to the next.',
  peg: 'Up to ten items hang on rhyming number pictures, so you can recall them in order or by number.',
  palace: 'Placing each item along a walk through a home you know keeps a long list in order.',
  story: 'A short scene for each item turns a dry list into something you can picture.',
};

/**
 * One session's steps. The person's practice log, persona, More time setting
 * and notes shape it; `memo` keeps the notes checks between the days of one
 * multi-day plan.
 */
export function buildStudyPlan(
  store: MemoryStore,
  minutesIn: number,
  deckChoice: string,
  habitsIn: Iterable<string>,
  goal: string,
  on?: string,
  since?: string | null,
  memo: PlanMemo = new Map(),
): PlanStep[] {
  const minutes = Math.max(MIN_STEP_MINUTES, Math.trunc(minutesIn));
  const habits = new Set(habitsIn ?? []);
  const deck = deckChoice === 'All decks' || deckChoice === 'New material' ? null : deckChoice;
  const inDeck = (cardDeck: string) => !deck || (cardDeck || 'General') === deck;
  const due = store.dueCards(deck, on, since);
  const weak = store.weakCards().filter((card) => inDeck(card.deck));
  const fresh = store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0 && inDeck(card.deck));
  const deckNames = new Set(store.cards.filter((card) => inDeck(card.deck)).map((card) => card.deck || 'General'));
  const hasCards = deckNames.size > 0;
  const profile = learnerProfile(store, on ? parseIso(on) ?? undefined : undefined);
  const perCard = profile.minutes_per_card;
  const persona = store.onboarding?.persona ?? '';
  const gentle = GENTLE_PERSONAS.includes(persona) && goal === 'long_term' && hasCards && deckChoice !== 'New material';
  const focusBlock = gentle ? GENTLE_FOCUS_MINUTES : FOCUS_BLOCK_MINUTES;
  const breaks = (habits.has('breaks') || gentle) && minutes >= 2 * focusBlock - 5;
  const studyMinutes = minutes - (breaks ? BREAK_MINUTES * Math.max(0, pyRound(minutes / (focusBlock + BREAK_MINUTES)) - 1) : 0);
  const quiz = profile.methods.quiz;
  const typedIsHard = !!quiz && quiz.answers >= MIN_METHOD_ANSWERS && quiz.rate < 0.5;
  const selfCheckMode = habits.has('quick_mc') || typedIsHard ? 'choices' : 'self';
  const struggling = profile.miss_rate !== null && profile.miss_rate >= STRUGGLING_MISS_RATE;
  const turn = dayTurn(on);
  const focus = hasCards ? focusDeck(store, deck, weak) : null;
  let steps: PlanStep[] = [];

  const add = (title: string, share: number, view: StepView, blurb: string, extra: Partial<PlanStep> = {}) => {
    steps.push({ title, share, view, blurb, deck, minutes: 0, ...extra });
  };

  /** A memory hook step that names the technique that suits the set (and the person). */
  const addTechnique = (title: string, share: number, fallback: string) => {
    const items = focus ? [...store.cards].reverse().filter((card) => deckOf(card) === focus).map(techniqueItem) : [];
    const kind = pickTechnique(items, profile.best_hook, turn);
    if (!kind) {
      add(title, share, 'tools', fallback);
      return;
    }
    const name = TECHNIQUE_TITLES[kind];
    let blurb = `Make a ${name.toLowerCase()} from ${focus}'s cards and save it as their hooks. ${TECHNIQUE_REASONS[kind]}`;
    if (kind === profile.best_hook) blurb += ` Your cards with ${name.toLowerCase()} hooks are the ones you remember best.`;
    steps.push({ title: `${title}: ${name.toLowerCase()}`, share, view: 'tools', blurb, deck: focus, minutes: 0, technique: kind });
  };

  const addPuzzle = (title: string, share: number, blurb: string) => {
    add(title, share, 'games', blurb, { puzzle_kind: focus ? 'pairs' : 'sequence', ...(focus ? { deck: focus } : {}) });
  };

  const addNotesSteps = () => {
    const { capture, count } = notesNotYetCards(store, deck, memo);
    if (capture && count >= 2) {
      add('Turn notes into cards', 0.12, 'notes', `“${capture.title || 'Your notes'}” has ${plural(count, 'part')} that aren't cards yet. Make cards from them so the plan can bring them back.`, { capture_id: capture.id });
    }
    if (minutes >= 20) {
      const behind = notesBehindWeak(store, weak, memo);
      if (behind) {
        add('Reread the notes behind a missed card', 0.08, 'notes', `You keep missing “${oneLine(behind.card.front).slice(0, 60)}”. Read the part of “${behind.capture.title || 'your notes'}” it came from before you review.`, { capture_id: behind.capture.id, bit: behind.bit });
      }
    }
  };

  const reviewView: StepView = due.length ? 'review' : 'focus';
  if (deckChoice === 'New material' || !hasCards) {
    const { capture, count } = notesNotYetCards(store, null, memo);
    if (capture && count >= 2) {
      add('Capture your material', 0.3, 'notes', `Start with “${capture.title || 'your notes'}”: ${plural(count, 'part')} aren't cards yet. One idea per card.`, { capture_id: capture.id });
    } else {
      add('Capture your material', 0.3, 'capture', 'Break the new material into small study bits and Q/A cards before anything else. One idea per card.');
    }
    if (habits.has('mnemonics')) add('Build memory hooks', 0.2, 'tools', 'Turn the trickiest new terms into acronyms or a mini-story before you try to recall them cold.');
    add('First recall attempt', 0.3, 'quiz', 'Close your notes and try to recall each card. Getting it wrong now still helps it stick.', { quiz_mode: 'self' });
    add('Schedule spaced review', 0.2, 'review', 'Rate what you just captured so the scheduler brings it back at the right time.');
  } else if (gentle) {
    // Calm, short steps for everyday memory: familiar things first, the same
    // few things often (spaced retrieval), and a game from their own cards.
    const short = minutes <= SHORT_SESSION_MINUTES;
    add('Gentle review', short ? 0.7 : 0.4, 'review', 'A few cards at a calm pace, people, routines and places first. Take as long as you need on each one.', { review_mode: 'gentle' });
    if (!short) {
      add('Repetition path', 0.25, 'shuffle', 'Recall a short list in growing runs. Coming back to the same few things often is one of the best ways to keep them.');
      if (habits.has('mnemonics')) addTechnique('Make a memory picture', 0.15, 'Turn something you keep forgetting into a picture or a short story.');
      if (habits.has('explain') || store.accessibility?.read_aloud) add('Listen and answer', 0.15, 'talkback', 'Hear each question read aloud and answer out loud, in your own words.');
    }
    addPuzzle("Today's puzzle", short ? 0.3 : 0.2, 'A short, friendly memory game made from your own cards.');
    if (fresh.length && !short) add('Meet a few new cards', 0.1, 'review', `Look at ${plural(Math.min(3, fresh.length), 'new card')}, no more. A few at a time is plenty.`, { review_mode: 'new' });
    if (minutes >= 20) add('See how you did', 0.06, 'stats', 'A quick look at what you practised today.');
  } else if (minutes <= SHORT_SESSION_MINUTES) {
    // Too short to split usefully: one review block and one quick check.
    add('Quick review', 0.7, reviewView, 'Clear the most important cards first. ' + reviewDetail(due.length, minutes, perCard));
    add('Quick check', 0.3, 'quiz', 'A fast self-test to finish on a win.', { quiz_mode: 'choices' });
  } else if (goal === 'cram') {
    if (due.length || weak.length) add('Warm-up: quick multiple choice', 0.15, 'quiz', 'Fast recall check to see where you stand before the clock starts.', { quiz_mode: 'choices' });
    add('Focused review', 0.45, reviewView, 'Work through due and weak cards with Smart Check, prioritising the ones you keep missing. ' + reviewDetail(due.length, pyRound(minutes * 0.45), perCard));
    if (habits.has('repetition')) add('Repetition drilling', 0.2, 'shuffle', 'Run the 5, 5-4, 5-4-3, 3-2-1 pattern on your weakest cards for extra reps right before the test.');
    add('Final confidence pass', 0.2, 'quiz', "One more quick pass. Multiple choice if you're short on time, self-check if you have a few extra minutes.", { quiz_mode: selfCheckMode });
  } else if (goal === 'exam_prep') {
    if (due.length || weak.length) add('Quick warm-up', 0.12, 'quiz', 'A short recall check to activate what you already know before digging in.', { quiz_mode: 'choices' });
    add('Spaced review', 0.33, reviewView, "Work through what's due with Smart Check so nothing quietly slips. " + reviewDetail(due.length, pyRound(minutes * 0.33), perCard));
    if (habits.has('mnemonics')) addTechnique('Strengthen weak hooks', 0.15, "Build a fresh association for your shakiest cards while there's still time to let it sink in.");
    add('Repetition drilling', 0.2, 'shuffle', "Run the repetition path on your weakest cards so they're solid well before exam day.");
    add('Self-check quiz', 0.2, 'quiz', 'Confirm recall without leaning on the saved answer.', { quiz_mode: selfCheckMode });
  } else {
    add('Spaced review', 0.35, reviewView, 'Work through everything due with Smart Check so your intervals stay honest. ' + reviewDetail(due.length, pyRound(minutes * 0.35), perCard));
    if (habits.has('mnemonics')) addTechnique('Strengthen weak hooks', 0.2, 'Build a fresh association for anything you recently rated Again or Review.');
    if (habits.has('repetition')) add('Repetition path', 0.2, 'shuffle', 'Walk the backward-then-forward pattern on your weakest cards until each one comes easily.');
    add('Self-check quiz', habits.has('mnemonics') || habits.has('repetition') ? 0.15 : 0.25, 'quiz', 'Confirm recall without leaning on the saved answer.', { quiz_mode: selfCheckMode });
  }

  if (!gentle && fresh.length && hasCards && deckChoice !== 'New material' && minutes > SHORT_SESSION_MINUTES && goal !== 'cram') {
    let newLimit = Math.min(fresh.length, Math.max(3, Math.min(MAX_NEW_CARDS_PER_SESSION, pyInt((studyMinutes * 0.2) / MINUTES_PER_NEW_CARD))));
    if (struggling) {
      newLimit = Math.min(fresh.length, Math.max(2, Math.floor(newLimit / 2)));
      add('Learn new cards', 0.1, 'review', `Meet up to ${plural(newLimit, 'new card')} (${fresh.length} waiting). You've missed quite a few this week, so fewer new cards today while those settle.`, { review_mode: 'new' });
    } else {
      add('Learn new cards', 0.15, 'review', `Meet up to ${plural(newLimit, 'new card')} (${fresh.length} waiting). Keeping new cards to a steady number stops tomorrow's reviews from piling up.`, { review_mode: 'new' });
    }
  }
  if (!gentle && habits.has('explain') && hasCards && minutes > SHORT_SESSION_MINUTES) {
    add('Explain it back', 0.15, 'talkback', 'Use Talk-back: hear each question and answer out loud in your own words, as if teaching a friend. With AI on, the live tutor can ask you follow-up questions instead.');
  }
  if (hasCards && deckChoice !== 'New material' && minutes > SHORT_SESSION_MINUTES && goal !== 'cram' && !gentle) addNotesSteps();
  // Interleaving: mixing topics feels harder but transfers better to tests.
  if (!gentle && hasCards && deck === null && deckNames.size > 1 && goal !== 'cram' && deckChoice !== 'New material' && minutes >= 30) {
    add('Mixed practice across decks', 0.15, 'quiz', `Shuffle questions from ${plural(deckNames.size, 'deck')} together. Switching topics is harder, and that is what makes it stick.`, { quiz_mode: selfCheckMode });
  }
  if (!gentle && habits.has('games') && minutes >= 20 && deckChoice !== 'New material' && hasCards) {
    addPuzzle('Short recall game break', 0.1, `A quick Pair recall round from ${focus}'s cards to reset attention between study blocks.`);
  }
  if (!gentle && minutes >= 30 && hasCards) {
    let wrap = "Look at what you got done and what's due tomorrow. Ending with a quick look back helps the session stick.";
    if (profile.best_time) {
      wrap += profile.best_time !== 'night' ? ` You remember best in the ${profile.best_time}, so that's a good time for the next session.` : " You remember best at night, so that's a good time for the next session.";
    }
    add('Wrap up', 0.06, 'stats', wrap);
  }

  const budget = breaks ? studyMinutes : minutes;
  allocateMinutes(steps.map((step) => step.share), budget).forEach((allotted, index) => {
    steps[index].minutes = allotted;
  });
  if (breaks) steps = insertBreaks(steps, minutes - budget, focusBlock);
  return steps;
}

/** Put a short rest after each ~25 minutes of study (15 for gentle plans; never at the very end). */
export function insertBreaks(steps: PlanStep[], breakMinutes: number, focusBlock = FOCUS_BLOCK_MINUTES): PlanStep[] {
  let count = Math.floor(breakMinutes / BREAK_MINUTES);
  if (count <= 0) return steps;
  const planned: PlanStep[] = [];
  let sinceBreak = 0;
  steps.forEach((step, index) => {
    planned.push(step);
    sinceBreak += step.minutes;
    if (count && sinceBreak >= focusBlock - 5 && index < steps.length - 1) {
      planned.push({
        title: 'Rest break', share: 0, view: 'break', deck: step.deck, minutes: BREAK_MINUTES,
        blurb: 'Stand up, stretch, get water, look away from the screen. Short rests keep attention sharp for the next block.',
      });
      count -= 1;
      sinceBreak = 0;
    }
  });
  // Any break time that didn't fit between steps goes back to the longest step.
  if (count) {
    let longest: PlanStep | null = null;
    for (const step of planned) {
      if (step.view !== 'break' && (!longest || step.minutes > longest.minutes)) longest = step;
    }
    if (longest) longest.minutes += count * BREAK_MINUTES;
  }
  return planned;
}

export type DayKind = 'study' | 'learn' | 'review' | 'maintenance' | 'light';

export interface PlanDay {
  day: number;
  date: string;
  kind: DayKind;
  due: number;
  minutes: number;
  steps: PlanStep[];
}

/** Plan several days ahead, projecting which cards come due on each day. */
export function buildMultiDayPlan(store: MemoryStore, totalDaysIn: number, deckChoice: string, habits: Iterable<string>, goal: string, start?: Date): PlanDay[] {
  const totalDays = Math.max(1, Math.min(MAX_PLAN_DAYS, Math.trunc(totalDaysIn)));
  const habitSet = [...(habits ?? [])];
  const gentle = GENTLE_PERSONAS.includes(store.onboarding?.persona ?? '') && goal === 'long_term';
  const baseMinutes = goal === 'cram' ? 45 : gentle ? 20 : 30;
  const longest = gentle ? 45 : 90;
  const today = start ?? now();
  const perCard = learnerProfile(store, today).minutes_per_card;
  const memo: PlanMemo = new Map();
  const days: PlanDay[] = [];
  for (let dayNumber = 1; dayNumber <= totalDays; dayNumber++) {
    const on = isoDate(addDaysTo(today, dayNumber - 1));
    const progress = dayNumber / totalDays;
    let kind: DayKind = 'study';
    let dayDeckChoice = deckChoice;
    let phaseGoal = goal;
    let minutes = baseMinutes;

    if (deckChoice === 'New material') {
      // Learn on day 1, then revisit on expanding intervals.
      if (dayNumber === 1) kind = 'learn';
      else if (NEW_MATERIAL_REVIEW_DAYS.includes(dayNumber)) [kind, dayDeckChoice] = ['review', 'All decks'];
      else [kind, dayDeckChoice, minutes] = ['maintenance', 'All decks', 15];
    } else if (goal === 'exam_prep') {
      if (progress <= 0.34) phaseGoal = 'long_term';
      else if (progress <= 0.75) phaseGoal = 'exam_prep';
      else [phaseGoal, minutes] = ['cram', baseMinutes + 15];
    }
    if ((goal === 'exam_prep' || goal === 'cram') && totalDays >= 3 && dayNumber === totalDays) {
      // The day before a test: a light confidence pass, then rest.
      [kind, phaseGoal, minutes] = ['light', 'cram', 20];
    }

    // Day 1 faces everything already due; later days only what newly comes due.
    const since = dayNumber === 1 ? null : isoDate(addDaysTo(today, dayNumber - 2));
    const deckFilter = dayDeckChoice === 'All decks' || dayDeckChoice === 'New material' ? null : dayDeckChoice;
    const due = store.dueCards(deckFilter, on, since).length;
    if (kind === 'study' || kind === 'review') {
      // Make room for a heavy review day instead of a fixed block.
      minutes = Math.max(minutes, Math.min(longest, pyRound(due * perCard) + 15));
    }
    const steps = buildStudyPlan(store, minutes, dayDeckChoice, habitSet, phaseGoal, on, since, memo);
    if (kind === 'light') {
      steps[steps.length - 1].blurb += ' Then stop for the day — sleep does more for recall than a late-night cram.';
    }
    days.push({ day: dayNumber, date: on, kind, due, minutes, steps });
  }
  return days;
}

/** Session length in minutes for a saved plan's time choice (null for day/week plans). */
export function planMinutes(settings: Record<string, unknown>): number | null {
  const unit = String(settings.unit ?? 'minutes');
  let amount = parseInt(String(settings.amount ?? '30'), 10);
  if (!Number.isFinite(amount)) amount = 30;
  if (unit === 'hours') return Math.min(MAX_PLAN_MINUTES, amount * 60);
  if (unit === 'minutes') return Math.min(MAX_PLAN_MINUTES, amount);
  return null;
}

export const GOAL_KEYS: Record<string, Goal> = { Cram: 'cram', 'Exam prep': 'exam_prep', 'Long-term retention': 'long_term' };

export interface TodayPlan {
  title: string;
  steps: PlanStep[];
  finished: boolean;
  day: number | null;
  totalDays: number | null;
}

/** Today's part of the saved plan. */
export function planForToday(store: MemoryStore, planIn?: StudyPlan | null, todayIn?: Date): TodayPlan | null {
  const plan = (planIn ?? (store.studyPlan as StudyPlan)) as StudyPlan;
  if (!plan || !plan.settings) return null;
  const settings = plan.settings;
  const today = todayIn ?? now();
  const deckChoice = String(settings.deck ?? 'All decks');
  const goalLabel = String(settings.goal_label ?? 'Long-term retention');
  const goal = GOAL_KEYS[goalLabel] ?? 'long_term';
  const habits = Array.isArray(settings.habits) ? settings.habits.filter((habit) => typeof habit === 'string') : [];
  const minutes = planMinutes(settings);
  if (minutes !== null) {
    const steps = buildStudyPlan(store, minutes, deckChoice, habits, goal);
    return { title: `${minutes} min • ${goalLabel} • ${deckChoice}`, steps, finished: false, day: null, totalDays: null };
  }
  const created = parseIso(plan.created) ?? today;
  let amount = parseInt(String(settings.amount ?? '1'), 10);
  if (!Number.isFinite(amount)) amount = 1;
  const totalDays = Math.min(MAX_PLAN_DAYS, amount * (settings.unit === 'weeks' ? 7 : 1));
  const dayNumber = Math.max(1, daysBetween(created, today) + 1); // a plan made in a later time zone starts today
  if (dayNumber > totalDays) {
    return { title: `Your ${totalDays}-day plan is complete`, steps: [], finished: true, day: dayNumber, totalDays };
  }
  const days = buildMultiDayPlan(store, totalDays, deckChoice, habits, goal, created);
  const day = days[Math.max(0, dayNumber - 1)];
  const kind = ({ learn: 'Learn day', review: 'Spaced review day', maintenance: 'Short maintenance day', light: 'Light day', study: 'Study day' } as Record<string, string>)[day.kind] ?? 'Study day';
  return { title: `Day ${dayNumber} of ${totalDays} • ${kind} • ${day.minutes} min`, steps: day.steps, finished: false, day: dayNumber, totalDays };
}
