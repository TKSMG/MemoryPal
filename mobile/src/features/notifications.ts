/**
 * What MemoryPal's notifications say, and when, for the next week.
 *
 * The phone can't run MemoryPal at the moment a notification shows, so the
 * next week is worked out ahead of time (each time the app goes to the
 * background, and when the settings change) and handed to the phone to
 * show. Opening MemoryPal and studying works the week out again, so a
 * reminder about something already done is taken back.
 *
 * The phone's copy of latest_app/memorypal/notifications.py: it must give
 * the same answers (tools/parity/make_notification_fixtures.py).
 */
import { addDaysTo, isoDate, now, parseIso, weekday } from '../core/dates';
import * as planning from '../core/planning';
import { PlanStep } from '../core/planning';
import { captureDeck, MemoryStore, plainText, sourceQuote, StudyPlan } from '../core/store';

export const KINDS = ['cards_due', 'plan_today', 'plan_unfinished', 'test_countdown', 'streak', 'notes_waiting', 'weekly_recap'] as const;
export type NotificationKind = (typeof KINDS)[number];
/** Which one stays when only one a day is allowed: the most time-sensitive. */
export const PRIORITY: NotificationKind[] = ['test_countdown', 'plan_today', 'cards_due', 'streak', 'plan_unfinished', 'weekly_recap', 'notes_waiting'];
export const KIND_LABELS: Record<NotificationKind, [string, string]> = {
  cards_due: ['Cards due', 'When cards are ready to review.'],
  plan_today: ['Today’s study plan', 'What your plan has for the day, instead of the cards reminder.'],
  plan_unfinished: ['Plan not finished', 'An evening nudge if steps of today’s plan are left.'],
  test_countdown: ['Test countdown', 'A week, 3 days and a day before a set’s test date, and that morning.'],
  streak: ['Streak saver', 'Late in the evening if you haven’t studied and have a streak of 2 days or more.'],
  notes_waiting: ['Notes waiting', 'Saturdays, if some of your notes aren’t cards yet.'],
  weekly_recap: ['Weekly recap', 'Sunday evening: how your week went.'],
};

export const REMINDER_TIMES = ['08:00', '13:00', '19:00', '21:00'] as const;
export const BEST_TIME = 'best';
export const DEFAULT_TIME = '19:00';
export const QUIET_CHOICES = ['off', '21:00-08:00', '22:00-07:00', '23:00-07:00'] as const;
export const DEFAULT_QUIET = '22:00-07:00';
const PLAN_NUDGE_TIME = '20:30';
const STREAK_TIME = '21:00';
const TEST_MORNING_TIME = '07:30';
const RECAP_TIME = '18:00';
const COUNTDOWN_DAYS = [7, 3, 1, 0];
const NOTES_WEEKDAY = 5; // Saturday (Monday = 0)
const RECAP_WEEKDAY = 6; // Sunday
export const DAYS_AHEAD = 7;
const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export interface NotificationSettings {
  enabled: boolean;
  /** "HH:MM" from REMINDER_TIMES, or "best". */
  time: string;
  kinds: NotificationKind[];
  quiet: string;
  one_a_day: boolean;
}

export interface PlannedNotification {
  kind: NotificationKind;
  /** Local time it shows. */
  at: Date;
  title: string;
  body: string;
  /** Where tapping it goes: review, plan, progress, notes or deck:<set>. */
  open: string;
  /** Cards due that day (for the icon badge). */
  due: number;
}

/** Where tapping a notification goes, as a route. */
export function routeFor(open: string): string {
  if (open.startsWith('deck:')) return `/review?mode=weak&deck=${encodeURIComponent(open.slice(5))}`;
  return ({ review: '/review', plan: '/plan', progress: '/progress', notes: '/notes' } as Record<string, string>)[open] ?? '/review';
}


const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

export function defaultSettings(): NotificationSettings {
  return { enabled: false, time: DEFAULT_TIME, kinds: [...KINDS], quiet: DEFAULT_QUIET, one_a_day: false };
}

export function normalizeSettings(raw: unknown): NotificationSettings {
  const settings = defaultSettings();
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return settings;
  const value = raw as Record<string, unknown>;
  settings.enabled = value.enabled === true;
  settings.time = value.time === BEST_TIME || (REMINDER_TIMES as readonly unknown[]).includes(value.time) ? String(value.time) : DEFAULT_TIME;
  if (Array.isArray(value.kinds)) settings.kinds = KINDS.filter((kind) => (value.kinds as unknown[]).includes(kind));
  settings.quiet = (QUIET_CHOICES as readonly unknown[]).includes(value.quiet) ? String(value.quiet) : DEFAULT_QUIET;
  settings.one_a_day = value.one_a_day === true;
  return settings;
}

/** "19:00" as [19, 0]; anything else is the fallback. */
export function clock(text: string, fallback: [number, number] = [19, 0]): [number, number] {
  const match = /^(\d+):(\d{2})$/.exec(String(text ?? ''));
  if (match) {
    const hour = Number(match[1]);
    const minute = Number(match[2]);
    if (hour < 24 && minute < 60) return [hour, minute];
  }
  return fallback;
}

/** The reminder time; "best" is the hour the practice log likes best (7pm until it knows). */
export function reminderClock(store: MemoryStore, time: string): [number, number] {
  if (time === BEST_TIME) {
    const finder = (planning as unknown as { bestStudyHour?: (store: MemoryStore) => number | null }).bestStudyHour;
    let hour: number | null = null;
    try {
      hour = finder ? finder(store) : null;
    } catch {
      hour = null;
    }
    return typeof hour === 'number' && Number.isInteger(hour) && hour >= 0 && hour < 24 ? [hour, 0] : clock(DEFAULT_TIME);
  }
  return clock(time);
}

/** "7:00 PM" (in the phone's own style) for "19:00"; "Best time for you" for "best". */
export function timeLabel(time: string): string {
  if (time === BEST_TIME) return 'Best time for you';
  const [hour, minute] = clock(time);
  try {
    return new Date(2000, 0, 1, hour, minute).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return time;
  }
}

export function quietLabel(quiet: string): string {
  if (quiet === 'off') return 'Off';
  const [start, end] = quiet.split('-');
  return `${timeLabel(start)} to ${timeLabel(end)}`;
}

function quietWindow(quiet: string): [number, number] | null {
  if (quiet === 'off' || !(QUIET_CHOICES as readonly string[]).includes(quiet)) return null;
  const [start, end] = quiet.split('-');
  const [startHour, startMinute] = clock(start);
  const [endHour, endMinute] = clock(end);
  return [startHour * 60 + startMinute, endHour * 60 + endMinute];
}

function isQuiet(at: Date, window: [number, number] | null): boolean {
  if (!window) return false;
  const minute = at.getHours() * 60 + at.getMinutes();
  const [start, end] = window;
  return start > end ? start <= minute || minute < end : start <= minute && minute < end;
}

const atTime = (day: Date, [hour, minute]: [number, number]) => new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute);
const later = (a: [number, number], b: [number, number]) => a[0] * 60 + a[1] > b[0] * 60 + b[1];

/** {iso day: steps} of the saved plan for the coming days (skips days it has ended). */
export function planDays(store: MemoryStore, firstDay: Date, days: number): Record<string, PlanStep[]> {
  const plan = store.studyPlan as StudyPlan;
  if (!plan || !plan.settings) return {};
  const settings = plan.settings as unknown as Record<string, unknown>;
  const deckChoice = String(settings.deck ?? 'All decks');
  const goal = planning.GOAL_KEYS[String(settings.goal_label ?? 'Long-term retention')] ?? 'long_term';
  const habits = Array.isArray(settings.habits) ? (settings.habits as unknown[]).filter((habit): habit is string => typeof habit === 'string') : [];
  const minutes = planning.planMinutes(settings);
  const found: Record<string, PlanStep[]> = {};
  if (minutes !== null) {
    const steps = planning.buildStudyPlan(store, minutes, deckChoice, habits, goal);
    for (let offset = 0; offset < days; offset += 1) found[isoDate(addDaysTo(firstDay, offset))] = steps;
    return found;
  }
  const created = parseIso(plan.created) ?? firstDay;
  let amount = parseInt(String(settings.amount ?? '1'), 10);
  if (!Number.isFinite(amount)) amount = 1;
  const totalDays = Math.min(planning.MAX_PLAN_DAYS, amount * (settings.unit === 'weeks' ? 7 : 1));
  let built: planning.PlanDay[] | null = null;
  for (let offset = 0; offset < days; offset += 1) {
    const day = addDaysTo(firstDay, offset);
    const start = Date.UTC(created.getFullYear(), created.getMonth(), created.getDate());
    const end = Date.UTC(day.getFullYear(), day.getMonth(), day.getDate());
    const number = Math.max(1, Math.round((end - start) / 86400000) + 1);
    if (number > totalDays) continue;
    built ??= planning.buildMultiDayPlan(store, totalDays, deckChoice, habits, goal, created);
    found[isoDate(day)] = built[number - 1].steps;
  }
  return found;
}

function planLeft(store: MemoryStore, stepsIn: PlanStep[], iso: string): [number, number] {
  const steps = store.planDaySteps(stepsIn, iso);
  const done = store.planStepsDone(iso);
  const left = steps.filter((step, index) => !done.has(index) && step.view !== 'break');
  return [left.length, left.reduce((sum, step) => sum + (Number(step.minutes) || 0), 0)];
}

function weakCount(store: MemoryStore, deck: string): number {
  return store.cards.filter((card) => (card.deck || 'General') === deck && (card.lapses > 0 || card.last_score < 64 || card.repetitions === 0)).length;
}

/**
 * Notes with study bits that no card seems to come from yet. Notes in a set
 * that has cards count as used (cards typed by hand from notes don't say
 * where they came from); other notes count as used when an AI card quotes them.
 */
export function notesWaiting(store: MemoryStore) {
  const withCards = new Set(store.cards.map((card) => card.deck || 'General'));
  const quotes = store.cards.map((card) => plainText(sourceQuote(card)).slice(0, 80)).filter((quote) => quote.length >= 12);
  return store.captures.filter((capture) => {
    if (!(capture.chunks.length || String(capture.notes || '').trim())) return false;
    if (withCards.has(captureDeck(capture))) return false;
    const text = plainText([capture.notes || '', ...capture.chunks].join(' '));
    return !quotes.some((quote) => text.includes(quote));
  });
}

const item = (kind: NotificationKind, at: Date, title: string, body: string, open: string, due = 0): PlannedNotification => ({ kind, at, title, body, open, due });

/** The notifications for the next `days` days, soonest first. */
export function planNotifications(store: MemoryStore, settingsIn: unknown, from?: Date, days = DAYS_AHEAD): PlannedNotification[] {
  const settings = normalizeSettings(settingsIn);
  if (!settings.enabled) return [];
  const kinds = new Set<NotificationKind>(settings.kinds);
  const start = from ?? now();
  const today = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const main = reminderClock(store, settings.time);
  const window = quietWindow(settings.quiet);
  const studiedToday = (store.activity[isoDate(today)] ?? 0) > 0;
  const streak = store.currentStreak();
  const plans = kinds.has('plan_today') || kinds.has('plan_unfinished') ? planDays(store, today, days) : {};
  const exams: [string, Date][] = [];
  if (kinds.has('test_countdown')) {
    const decks = new Set(store.decks());
    for (const info of store.deckInfos) {
      const exam = info.exam_date ? parseIso(info.exam_date) : null;
      if (exam && decks.has(info.id)) exams.push([info.id, exam]);
    }
  }
  const waiting = kinds.has('notes_waiting') ? notesWaiting(store) : [];
  const found: PlannedNotification[] = [];
  for (let offset = 0; offset < days; offset += 1) {
    const day = addDaysTo(today, offset);
    const iso = isoDate(day);
    let todays: PlannedNotification[] = [];
    // The streak runs up to yesterday when today isn't done yet.
    const keep = offset === 0 || (offset === 1 && studiedToday) ? streak : 0;
    const skipStudy = offset === 0 && studiedToday;

    // One countdown a day: the nearest test, naming any others.
    const coming = exams
      .map(([deck, exam]): [number, string] => [Math.round((Date.UTC(exam.getFullYear(), exam.getMonth(), exam.getDate()) - Date.UTC(day.getFullYear(), day.getMonth(), day.getDate())) / 86400000), deck])
      .filter(([away]) => COUNTDOWN_DAYS.includes(away))
      .sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    if (coming.length) {
      const [away, deck] = coming[0];
      const weak = weakCount(store, deck);
      const when = ({ 0: 'today', 1: 'tomorrow', 7: 'in a week' } as Record<number, string>)[away] ?? `in ${away} days`;
      let body = weak ? `${plural(weak, 'card')} still ${weak === 1 ? 'needs' : 'need'} work. A short review now helps.` : 'Your cards look solid. A quick run-through keeps them fresh.';
      const others = coming.slice(1).map(([, name]) => name);
      if (others.length) body += ` Also coming up: ${others.join(', ')}.`;
      todays.push(item('test_countdown', atTime(day, away === 0 ? clock(TEST_MORNING_TIME) : main), `${deck} test ${when}`, body, `deck:${deck}`, weak));
    }
    // A countdown at the reminder time already says to review.
    const counted = todays.some((entry) => entry.at.getTime() === atTime(day, main).getTime());

    const due = store.dueCards(null, iso).length;
    const steps = plans[iso];
    const [left, leftMinutes] = steps ? planLeft(store, steps, iso) : [0, 0];
    // Once a step is ticked the plan is under way: only the evening nudge is left.
    const started = !!steps && left < steps.filter((step) => step.view !== 'break').length;
    let planned = false;
    if (kinds.has('plan_today') && left && !started) {
      const first = steps!.find((step) => step.view !== 'break')?.title ?? '';
      todays.push(item('plan_today', atTime(day, main), `Today's plan: ${plural(left, 'step')}, about ${leftMinutes} min`, first ? `First: ${first}.` : 'Open your plan to start.', 'plan', due));
      planned = true;
    }
    if (kinds.has('cards_due') && due && !skipStudy && !planned && !counted) {
      const title = due === 1 ? 'A card is ready to review' : `${plural(due, 'card')} are ready to review`;
      const body = keep >= 2 ? `A few minutes keeps your ${keep}-day streak going.` : 'A few minutes now helps them stick.';
      todays.push(item('cards_due', atTime(day, main), title, body, 'review', due));
    }
    if (kinds.has('plan_unfinished') && left) {
      const nudge = clock(PLAN_NUDGE_TIME);
      if (later(nudge, main)) todays.push(item('plan_unfinished', atTime(day, nudge), `Your plan has ${plural(left, 'step')} left`, `About ${leftMinutes} min finishes today's plan.`, 'plan', due));
    }
    if (kinds.has('streak') && keep >= 2 && !skipStudy) {
      const late = clock(STREAK_TIME);
      const reminded = todays.some((entry) => entry.kind === 'cards_due' || entry.kind === 'plan_today');
      if (later(late, main) || !reminded) todays.push(item('streak', atTime(day, late), `Keep your ${keep}-day streak`, 'A few cards before bed keeps it going.', 'review', due));
    }
    if (kinds.has('notes_waiting') && waiting.length && weekday(day) === NOTES_WEEKDAY) {
      const title = waiting.length > 1 ? `${plural(waiting.length, 'set')} of notes aren't cards yet` : "Some notes aren't cards yet";
      todays.push(item('notes_waiting', atTime(day, main), title, `Turn “${waiting[0].title}” into cards to start remembering it.`, 'notes'));
    }
    if (kinds.has('weekly_recap') && weekday(day) === RECAP_WEEKDAY) {
      const week = [6, 5, 4, 3, 2, 1, 0].map((back) => addDaysTo(day, -back));
      const counts = week.map((each) => store.activity[isoDate(each)] ?? 0);
      const reviews = counts.reduce((sum, count) => sum + count, 0);
      if (reviews) {
        let best = 0;
        counts.forEach((count, index) => {
          if (count > counts[best]) best = index;
        });
        const studied = counts.filter((count) => count > 0).length;
        const tomorrow = store.dueCards(null, isoDate(addDaysTo(day, 1))).length;
        const body = `Best day: ${WEEKDAY_NAMES[weekday(week[best])]} (${counts[best]}). ${plural(tomorrow, 'card')} due tomorrow.`;
        todays.push(item('weekly_recap', atTime(day, clock(RECAP_TIME)), `Your week: ${plural(reviews, 'review')} on ${plural(studied, 'day')}`, body, 'progress'));
      }
    }

    todays = todays.filter((entry) => entry.at.getTime() > start.getTime() && !isQuiet(entry.at, window));
    if (settings.one_a_day && todays.length) {
      todays = [todays.reduce((best, entry) => (PRIORITY.indexOf(entry.kind) < PRIORITY.indexOf(best.kind) ? entry : best))];
    }
    found.push(...todays);
  }
  return found.sort((a, b) => a.at.getTime() - b.at.getTime() || PRIORITY.indexOf(a.kind) - PRIORITY.indexOf(b.kind));
}
