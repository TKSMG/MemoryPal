/** Dates as people say them: "today", "tomorrow", "in 4 days", then "20 Oct". */
import { daysBetween, now, parseIso } from '../core/dates';

/**
 * A card's next review in words. Anything overdue reads "today", since that's
 * when it will come up. Falls back to the raw value if it isn't a valid date.
 */
export function relativeDay(iso: string, from: Date = now()): string {
  const date = parseIso(iso);
  if (!date) return iso;
  const days = daysBetween(from, date);
  if (days <= 0) return 'today';
  if (days === 1) return 'tomorrow';
  if (days < 7) return `in ${days} days`;
  const sameYear = date.getFullYear() === from.getFullYear();
  return `on ${date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', ...(sameYear ? {} : { year: 'numeric' }) })}`;
}

/**
 * When notes were saved, as "4 Nov, 5:30 pm" (with the year if it isn't this
 * one). Notes store "YYYY-MM-DD HH:MM"; anything else is shown as it is.
 */
export function savedLabel(value: string, from: Date = now()): string {
  const match = /^(\d{4}-\d{2}-\d{2})(?: (\d{1,2}):(\d{2}))?$/.exec((value || '').trim());
  const date = match ? parseIso(match[1]) : null;
  if (!match || !date) return value;
  const sameYear = date.getFullYear() === from.getFullYear();
  const day = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', ...(sameYear ? {} : { year: 'numeric' }) });
  if (match[2] === undefined) return day;
  date.setHours(Number(match[2]), Number(match[3]));
  return `${day}, ${date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`;
}
