/**
 * What the daily study reminder says on each of the next few days.
 *
 * The phone can't run MemoryPal at the moment a reminder fires, so the next
 * week of reminders is worked out ahead of time (each time the app goes to
 * the background) from the review schedule: how many cards will be due that
 * day if nothing is studied before then. Days with nothing due and no
 * streak to keep get no reminder at all, so it never nags for nothing.
 */
import { addDaysTo, isoDate, now } from '../core/dates';
import { MemoryStore } from '../core/store';

export const REMINDER_TIMES = ['08:00', '13:00', '19:00', '21:00'] as const;
export type ReminderTime = (typeof REMINDER_TIMES)[number];
export const REMINDER_DAYS = 7;

export interface PlannedReminder {
  /** Local time the reminder shows. */
  at: Date;
  title: string;
  body: string;
  /** Cards due that day, also shown on the app icon badge. */
  due: number;
}

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

/** "19:00" as [19, 0]; anything else falls back to 7pm. */
export function reminderClock(time: string): [number, number] {
  const match = /^(\d{1,2}):(\d{2})$/.exec(time ?? '');
  const hour = match ? Number(match[1]) : 19;
  const minute = match ? Number(match[2]) : 0;
  return hour < 24 && minute < 60 ? [hour, minute] : [19, 0];
}

export function reminderLabel(time: string): string {
  const [hour, minute] = reminderClock(time);
  const date = new Date(2000, 0, 1, hour, minute);
  try {
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  } catch {
    return time;
  }
}

/** The reminders for the next `days` days, soonest first. */
export function planReminders(store: MemoryStore, time: string, days = REMINDER_DAYS, from?: Date): PlannedReminder[] {
  const start = from ?? now();
  const [hour, minute] = reminderClock(time);
  const studiedToday = (store.activity[isoDate(start)] ?? 0) > 0;
  const streak = store.currentStreak();
  const plan: PlannedReminder[] = [];
  for (let offset = 0; offset < days; offset += 1) {
    const day = addDaysTo(start, offset);
    const at = new Date(day.getFullYear(), day.getMonth(), day.getDate(), hour, minute);
    if (at.getTime() <= start.getTime()) continue;
    // Already studied today: today's reminder would only nag.
    if (offset === 0 && studiedToday) continue;
    const due = store.dueCards(null, isoDate(day)).length;
    // The streak runs up to yesterday when today isn't done yet.
    const keep = offset === 0 ? streak : offset === 1 && studiedToday ? streak : 0;
    if (due > 0) {
      plan.push({
        at,
        due,
        title: due === 1 ? 'A card is ready to review' : `${plural(due, 'card')} are ready to review`,
        body: keep >= 2 ? `A few minutes keeps your ${keep}-day streak going.` : 'A few minutes now helps them stick.',
      });
    } else if (keep >= 2) {
      plan.push({ at, due: 0, title: `Keep your ${keep}-day streak`, body: 'Nothing is due, so a quick quiz will do.' });
    }
  }
  return plan;
}
