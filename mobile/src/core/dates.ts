/** Local calendar dates as ISO "YYYY-MM-DD" strings, like Python's date.isoformat(). */

const pad = (value: number) => String(value).padStart(2, '0');

export function isoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Overridable "now" so tests (and the parity fixtures) can pin a date. */
let clock: () => Date = () => new Date();

export function setClock(next: (() => Date) | null) {
  clock = next ?? (() => new Date());
}

export function now(): Date {
  return clock();
}

export function todayIso(): string {
  return isoDate(now());
}

export function parseIso(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value ?? '');
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return isoDate(date) === value ? date : null;
}

export function addDaysTo(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function addDays(days: number): string {
  return isoDate(addDaysTo(now(), days));
}

/** Whole calendar days from a to b (b - a). */
export function daysBetween(a: Date, b: Date): number {
  const start = Date.UTC(a.getFullYear(), a.getMonth(), a.getDate());
  const end = Date.UTC(b.getFullYear(), b.getMonth(), b.getDate());
  return Math.round((end - start) / 86400000);
}

/** "YYYY-MM-DD HH:MM", the desktop's created_at format. */
export function nowLabel(): string {
  const date = now();
  return `${isoDate(date)} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Monday = 0 ... Sunday = 6, like Python's date.weekday(). */
export function weekday(date: Date): number {
  return (date.getDay() + 6) % 7;
}
