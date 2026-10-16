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
