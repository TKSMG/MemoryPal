/** Study plans for one session or several days (port of memorypal/planning.py). */
import { addDaysTo, daysBetween, isoDate, now, parseIso } from './dates';
import { pyInt, pyRound } from './py';
import { MemoryStore, StudyPlan } from './store';

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

/** Where a step sends the person: the desktop page key it was built for. */
export type StepView = 'capture' | 'tools' | 'quiz' | 'review' | 'focus' | 'shuffle' | 'testing' | 'games' | 'stats' | 'break';

export interface PlanStep {
  title: string;
  share: number;
  view: StepView;
  blurb: string;
  deck: string | null;
  minutes: number;
  quiz_mode?: 'self' | 'choices';
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

function reviewDetail(dueCount: number, shareMinutes: number): string {
  if (!dueCount) return 'Nothing is due, so this works through weak and fresh cards instead.';
  const needed = Math.max(1, pyRound(dueCount * MINUTES_PER_CARD));
  if (needed > shareMinutes) {
    return `${plural(dueCount, 'card')} due (about ${needed} min) — do the oldest first; the rest can wait for tomorrow.`;
  }
  return `${plural(dueCount, 'card')} due, about ${needed} min.`;
}

export function buildStudyPlan(
  store: MemoryStore,
  minutesIn: number,
  deckChoice: string,
  habitsIn: Iterable<string>,
  goal: string,
  on?: string,
  since?: string | null,
): PlanStep[] {
  const minutes = Math.max(MIN_STEP_MINUTES, Math.trunc(minutesIn));
  const habits = new Set(habitsIn ?? []);
  const deck = deckChoice === 'All decks' || deckChoice === 'New material' ? null : deckChoice;
  const inDeck = (cardDeck: string) => !deck || (cardDeck || 'General') === deck;
  const due = store.dueCards(deck, on, since);
  const weak = store.weakCards().filter((card) => inDeck(card.deck));
  const fresh = store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0 && inDeck(card.deck));
  const breaks = habits.has('breaks') && minutes >= 2 * FOCUS_BLOCK_MINUTES - 5;
  const studyMinutes = minutes - (breaks ? BREAK_MINUTES * Math.max(0, pyRound(minutes / (FOCUS_BLOCK_MINUTES + BREAK_MINUTES)) - 1) : 0);
  const deckNames = new Set(store.cards.filter((card) => inDeck(card.deck)).map((card) => card.deck || 'General'));
  const hasCards = deckNames.size > 0;
  const selfCheckMode = habits.has('quick_mc') ? 'choices' : 'self';
  let steps: PlanStep[] = [];

  const add = (title: string, share: number, view: StepView, blurb: string, extra: Partial<PlanStep> = {}) => {
    steps.push({ title, share, view, blurb, deck, minutes: 0, ...extra });
  };

  const reviewView: StepView = due.length ? 'review' : 'focus';
  if (deckChoice === 'New material' || !hasCards) {
    add('Capture your material', 0.3, 'capture', 'Break the new material into small study bits and Q/A cards before anything else. One idea per card.');
    if (habits.has('mnemonics')) add('Build memory hooks', 0.2, 'tools', 'Turn the trickiest new terms into acronyms or a mini-story before you try to recall them cold.');
    add('First recall attempt', 0.3, 'quiz', 'Close your notes and try to recall each card. Getting it wrong now still helps it stick.', { quiz_mode: 'self' });
    add('Schedule spaced review', 0.2, 'review', 'Rate what you just captured so the scheduler brings it back at the right time.');
  } else if (minutes <= SHORT_SESSION_MINUTES) {
    // Too short to split usefully: one review block and one quick check.
    add('Quick review', 0.7, reviewView, 'Clear the most important cards first. ' + reviewDetail(due.length, minutes));
    add('Quick check', 0.3, 'quiz', 'A fast self-test to finish on a win.', { quiz_mode: 'choices' });
  } else if (goal === 'cram') {
    if (due.length || weak.length) add('Warm-up: quick multiple choice', 0.15, 'quiz', 'Fast recall check to see where you stand before the clock starts.', { quiz_mode: 'choices' });
    add('Focused review', 0.45, reviewView, 'Work through due and weak cards with Smart Check, prioritising the ones you keep missing. ' + reviewDetail(due.length, pyRound(minutes * 0.45)));
    if (habits.has('repetition')) add('Repetition drilling', 0.2, 'shuffle', 'Run the 5, 5-4, 5-4-3, 3-2-1 pattern on your weakest items for extra reps right before the test.');
    add('Final confidence pass', 0.2, 'quiz', "One more quick pass. Multiple choice if you're short on time, self-check if you have a few extra minutes.", { quiz_mode: selfCheckMode });
  } else if (goal === 'exam_prep') {
    if (due.length || weak.length) add('Quick warm-up', 0.12, 'quiz', 'A short recall check to activate what you already know before digging in.', { quiz_mode: 'choices' });
    add('Spaced review', 0.33, reviewView, "Work through what's due with Smart Check so nothing quietly slips. " + reviewDetail(due.length, pyRound(minutes * 0.33)));
    if (habits.has('mnemonics')) add('Strengthen weak hooks', 0.15, 'tools', "Build a fresh association for your shakiest cards while there's still time to let it sink in.");
    add('Repetition drilling', 0.2, 'shuffle', "Run the repetition path on your weakest items so they're solid well before exam day.");
    add('Self-check quiz', 0.2, 'quiz', 'Confirm recall without leaning on the saved answer.', { quiz_mode: selfCheckMode });
  } else {
    add('Spaced review', 0.35, reviewView, 'Work through everything due with Smart Check so your intervals stay honest. ' + reviewDetail(due.length, pyRound(minutes * 0.35)));
    if (habits.has('mnemonics')) add('Strengthen weak hooks', 0.2, 'tools', 'Build a fresh association for anything you recently rated Again or Review.');
    if (habits.has('repetition')) add('Repetition path', 0.2, 'shuffle', 'Walk the backward-then-forward pattern on your weakest deck items.');
    add('Self-check quiz', habits.has('mnemonics') || habits.has('repetition') ? 0.15 : 0.25, 'quiz', 'Confirm recall without leaning on the saved answer.', { quiz_mode: selfCheckMode });
  }

  if (fresh.length && hasCards && deckChoice !== 'New material' && minutes > SHORT_SESSION_MINUTES && goal !== 'cram') {
    const newLimit = Math.min(fresh.length, Math.max(3, Math.min(MAX_NEW_CARDS_PER_SESSION, pyInt((studyMinutes * 0.2) / MINUTES_PER_NEW_CARD))));
    add('Learn new cards', 0.15, 'focus', `Meet up to ${plural(newLimit, 'new card')} (${fresh.length} waiting). Keeping new cards to a steady number stops tomorrow's reviews from piling up.`);
  }
  if (habits.has('explain') && hasCards && minutes > SHORT_SESSION_MINUTES) {
    add('Explain it back', 0.15, 'testing', 'Pick a card and explain the answer out loud or in writing as if teaching a friend. Gaps in the explanation show exactly what to review.');
  }
  // Interleaving: mixing topics feels harder but transfers better to tests.
  if (hasCards && deck === null && deckNames.size > 1 && goal !== 'cram' && deckChoice !== 'New material' && minutes >= 30) {
    add('Mixed practice across decks', 0.15, 'quiz', `Shuffle questions from ${plural(deckNames.size, 'deck')} together. Switching topics is harder, and that is what makes it stick.`, { quiz_mode: selfCheckMode });
  }
  if (habits.has('games') && minutes >= 20 && deckChoice !== 'New material' && hasCards) {
    add('Short recall game break', 0.1, 'games', 'A quick puzzle round to reset attention between study blocks.');
  }
  if (minutes >= 30 && hasCards) {
    add('Wrap up', 0.06, 'stats', "Look at what you got done and what's due tomorrow. Ending with a quick look back helps the session stick.");
  }

  const budget = breaks ? studyMinutes : minutes;
  allocateMinutes(steps.map((step) => step.share), budget).forEach((allotted, index) => {
    steps[index].minutes = allotted;
  });
  if (breaks) steps = insertBreaks(steps, minutes - budget);
  return steps;
}

/** Put a short rest after each ~25 minutes of study (never at the very end). */
export function insertBreaks(steps: PlanStep[], breakMinutes: number): PlanStep[] {
  let count = Math.floor(breakMinutes / BREAK_MINUTES);
  if (count <= 0) return steps;
  const planned: PlanStep[] = [];
  let sinceBreak = 0;
  steps.forEach((step, index) => {
    planned.push(step);
    sinceBreak += step.minutes;
    if (count && sinceBreak >= FOCUS_BLOCK_MINUTES - 5 && index < steps.length - 1) {
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
  const baseMinutes = goal === 'cram' ? 45 : 30;
  const today = start ?? now();
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
      minutes = Math.max(minutes, Math.min(90, pyRound(due * MINUTES_PER_CARD) + 15));
    }
    const steps = buildStudyPlan(store, minutes, dayDeckChoice, habitSet, phaseGoal, on, since);
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
