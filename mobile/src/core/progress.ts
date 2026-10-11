/** Levels, charts and badges, computed from saved activity (port of memorypal/progress.py). */
import { addDaysTo, daysBetween, isoDate, now, parseIso, weekday } from './dates';
import { Card } from './models';
import { MemoryStore } from './store';

export const XP_PER_REVIEW = 10;
export const MATURE_DAYS = 21;
export const YOUNG_DAYS = 7;
export const MASTERED_SCORE = 82;
export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** Level from total reviews. Each level needs 100 XP more than the last. */
export function levelInfo(practiced: number) {
  let xp = Math.max(0, Math.trunc(practiced)) * XP_PER_REVIEW;
  let level = 1;
  let need = 100;
  while (xp >= need) {
    xp -= need;
    level += 1;
    need += 100;
  }
  return { level, xp, need, pct: xp / need };
}

/** [date, count] for the last `days` days, oldest first. */
export function dailySeries(activity: Record<string, number>, days: number, end?: Date): [Date, number][] {
  const last = end ?? now();
  const start = addDaysTo(last, -(days - 1));
  return Array.from({ length: days }, (_, offset) => {
    const day = addDaysTo(start, offset);
    return [day, Math.trunc(activity[isoDate(day)] || 0)] as [Date, number];
  });
}

export function bestStreak(activity: Record<string, number>): number {
  const active = Object.entries(activity)
    .filter(([day, count]) => (count || 0) > 0 && parseIso(day))
    .map(([day]) => parseIso(day) as Date)
    .sort((a, b) => a.getTime() - b.getTime());
  let best = 0;
  let run = 0;
  let previous: Date | null = null;
  for (const day of active) {
    run = previous && daysBetween(previous, day) === 1 ? run + 1 : 1;
    best = Math.max(best, run);
    previous = day;
  }
  return best;
}

/** Cards coming due on each of the next `days` days; overdue counts as today. */
export function dueForecast(cards: Card[], days = 14, today?: Date): [Date, number][] {
  const start = today ?? now();
  const counts = new Array(days).fill(0);
  for (const card of cards) {
    const due = parseIso(card.next_review);
    if (!due) continue;
    const offset = Math.max(0, daysBetween(start, due));
    if (offset < days) counts[offset] += 1;
  }
  return counts.map((count, offset) => [addDaysTo(start, offset), count] as [Date, number]);
}

export function maturityBreakdown(cards: Card[]) {
  const groups = { new: 0, learning: 0, young: 0, mature: 0 };
  for (const card of cards) {
    if (card.repetitions === 0) groups.new += 1;
    else if (card.interval < YOUNG_DAYS) groups.learning += 1;
    else if (card.interval < MATURE_DAYS) groups.young += 1;
    else groups.mature += 1;
  }
  return groups;
}

const RATING_BUCKETS: [string, string[]][] = [
  ['Again', ['Again', 'Weak', 'Weak match', 'Missed context', 'Needs response']],
  ['Hard', ['Review', 'Partial match']],
  ['Good', ['Good', 'Close enough']],
  ['Easy', ['Easy', 'Strong match']],
];

export function ratingMix(cards: Card[]): Record<string, number> {
  const counts: Record<string, number> = { Again: 0, Hard: 0, Good: 0, Easy: 0 };
  for (const card of cards) {
    if (card.repetitions === 0 && card.lapses === 0 && (card.last_result === '' || card.last_result === 'New')) continue;
    const result = card.last_result || '';
    const bucket = RATING_BUCKETS.find(([, labels]) => labels.includes(result));
    if (bucket) {
      counts[bucket[0]] += 1;
    } else {
      const score = card.last_score || 0;
      if (score || result) counts[score >= 90 ? 'Easy' : score >= 70 ? 'Good' : score >= 45 ? 'Hard' : 'Again'] += 1;
    }
  }
  return counts;
}

export function weekdayRhythm(activity: Record<string, number>, weeks = 12, today?: Date): [string, number][] {
  const totals = new Array(7).fill(0);
  for (const [day, count] of dailySeries(activity, weeks * 7, today)) totals[weekday(day)] += count;
  return WEEKDAYS.map((name, index) => [name, totals[index] / weeks] as [string, number]);
}

export function masteredCount(cards: Card[]): number {
  return cards.filter((card) => card.last_score >= MASTERED_SCORE || card.last_result === 'Strong match').length;
}

export interface Badge {
  key: string;
  icon: string;
  title: string;
  body: string;
  current: number;
  target: number;
  done: boolean;
}

/** Badges with progress. Earned ones first, then the closest to earning. */
export function achievements(store: MemoryStore): Badge[] {
  const activity = store.activity;
  const best = Math.max(bestStreak(activity), store.currentStreak());
  const mastered = masteredCount(store.cards);
  const goalDays = Object.values(activity).filter((count) => (count || 0) >= Math.max(1, store.dailyGoal)).length;
  const planSaved = 'settings' in store.studyPlan ? 1 : 0;
  const items: [string, string, string, string, number, number][] = [
    ['first_review', '✨', 'First step', 'Finish your first review.', store.practiced, 1],
    ['reviews_50', '💪', 'Warming up', 'Finish 50 reviews.', store.practiced, 50],
    ['reviews_250', '🏃', 'Memory athlete', 'Finish 250 reviews.', store.practiced, 250],
    ['reviews_1000', '🏆', 'Recall legend', 'Finish 1,000 reviews.', store.practiced, 1000],
    ['streak_3', '🔥', 'On a roll', 'Practise 3 days in a row.', best, 3],
    ['streak_7', '📅', 'Week warrior', 'Practise 7 days in a row.', best, 7],
    ['streak_30', '👑', 'Habit locked in', 'Practise 30 days in a row.', best, 30],
    ['goal_day', '🎯', 'Goal getter', 'Reach your daily goal once.', goalDays, 1],
    ['goal_10', '🌟', 'Reliable', 'Reach your daily goal on 10 days.', goalDays, 10],
    ['mastered_10', '🧠', 'Ten solid', 'Master 10 cards.', mastered, 10],
    ['mastered_50', '🎓', 'Deep roots', 'Master 50 cards.', mastered, 50],
    ['decks_3', '🗂', 'Collector', 'Study cards in 3 decks.', store.decks().length, 3],
    ['capture_1', '📝', 'Note taker', 'Capture your own material.', store.captures.length, 1],
    ['planner', '🗺', 'Planner', 'Save a study plan.', planSaved, 1],
  ];
  const badges = items.map(([key, icon, title, body, currentRaw, target]) => {
    const current = Math.min(Math.trunc(currentRaw), target);
    return { key, icon, title, body, current, target, done: current >= target };
  });
  // Stable sort: earned first, then by how close each badge is.
  return badges
    .map((badge, index) => ({ badge, index }))
    .sort((a, b) => Number(a.badge.done === false) - Number(b.badge.done === false) || b.badge.current / b.badge.target - a.badge.current / a.badge.target || a.index - b.index)
    .map(({ badge }) => badge);
}

export function nextAchievement(store: MemoryStore): Badge | null {
  return achievements(store).find((badge) => !badge.done) ?? null;
}
