/**
 * Password strength and a sign-in attempt limiter: a line-by-line port of
 * latest_app/memorypal/security.py (checked by the parity tests).
 * Device-side checks give quick, friendly feedback; the server's rate limits
 * and password policy are the real protection.
 */
import { pyRound } from './py';

export const MIN_PASSWORD = 10;

const COMMON_PASSWORDS = new Set([
  '123456', 'password', '12345678', 'qwerty', '123456789', '12345', '1234', '111111', '1234567', 'dragon',
  '123123', 'baseball', 'abc123', 'football', 'monkey', 'letmein', '696969', 'shadow', 'master', '666666',
  'qwertyuiop', '123321', 'mustang', '1234567890', 'michael', '654321', 'superman', '1qaz2wsx', '7777777',
  '121212', '000000', 'qazwsx', '123qwe', 'killer', 'trustno1', 'jordan', 'jennifer', 'zxcvbnm', 'asdfgh',
  'hunter', 'buster', 'soccer', 'harley', 'batman', 'andrew', 'tigger', 'sunshine', 'iloveyou', '2000',
  'charlie', 'robert', 'thomas', 'hockey', 'ranger', 'daniel', 'starwars', 'klaster', '112233', 'george',
  'computer', 'michelle', 'jessica', 'pepper', '1111', 'zxcvbn', '555555', '11111111', '131313', 'freedom',
  '777777', 'pass', 'maggie', '159753', 'aaaaaa', 'ginger', 'princess', 'joshua', 'cheese', 'amanda',
  'summer', 'love', 'ashley', 'nicole', 'chelsea', 'biteme', 'matthew', 'access', 'yankees', '987654321',
  'dallas', 'austin', 'thunder', 'taylor', 'matrix', 'welcome', 'admin', 'passw0rd', 'password1', 'password123',
  'welcome1', 'qwerty123', 'iloveyou1', 'abcdef', 'abcd1234', 'changeme', 'secret', 'login', 'memorypal',
  'memory', 'remember', 'flashcards', 'student', 'teacher', 'school', 'football1', 'baseball1', 'letmein1',
]);

const SEQUENCES = ['abcdefghijklmnopqrstuvwxyz', '0123456789', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm'];

export function characterClasses(password: string): number {
  return [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((pattern) => pattern.test(password)).length;
}

/** True when most of the password is one repeated character or a keyboard/alphabet run. */
export function predictable(password: string): boolean {
  const text = password.toLowerCase();
  if (text.length < 4) return false;
  if (new Set(text).size <= 2) return true;
  let longest = 0;
  for (const sequence of SEQUENCES) {
    for (const direction of [sequence, [...sequence].reverse().join('')]) {
      let run = 0;
      for (let i = 0; i + 1 < text.length; i++) {
        if (direction.includes(text[i] + text[i + 1])) run = run ? run + 1 : 2;
        else run = 0;
        longest = Math.max(longest, run);
      }
    }
  }
  return longest >= Math.max(4, Math.trunc(text.length * 0.6));
}

/** Plain-language reasons a password is too weak (empty = acceptable). */
export function passwordProblems(password: string, email = ''): string[] {
  const value = password ?? '';
  const problems: string[] = [];
  if (value.length < MIN_PASSWORD) problems.push(`Use at least ${MIN_PASSWORD} characters. A few unrelated words work well.`);
  const stripped = value.toLowerCase().replace(/[^a-z]/g, '');
  if (COMMON_PASSWORDS.has(value.toLowerCase()) || (stripped.length >= 4 && COMMON_PASSWORDS.has(stripped))) {
    problems.push('This is one of the most common passwords. Choose something less guessable.');
  }
  const name = (email ?? '').split('@')[0].toLowerCase().replace(/[^a-z0-9]/g, '');
  if (name.length >= 3 && value.toLowerCase().replace(/[^a-z0-9]/g, '').includes(name)) {
    problems.push("Don't use your email name in your password.");
  }
  if (predictable(value)) problems.push('Avoid repeated letters and runs like 1234 or qwerty.');
  // The account server requires both (Supabase: letters and digits).
  if (!/[A-Za-z]/.test(value) || !/[0-9]/.test(value)) problems.push('Include at least one letter and one number.');
  return problems;
}

/** 0 (very weak) to 4 (strong), for a strength meter. */
export function passwordStrength(password: string, email = ''): number {
  const value = password ?? '';
  if (!value) return 0;
  let score = 0;
  if (value.length >= MIN_PASSWORD) score += 1;
  if (value.length >= 14) score += 1;
  // Length counts most: a long passphrase is strong even without symbols.
  if (characterClasses(value) >= 3 || value.length >= 20) score += 1;
  if (value.length >= 24 || (value.length >= 12 && characterClasses(value) === 4)) score += 1;
  if (passwordProblems(value, email).length) score = Math.min(score, 1);
  return score;
}

export const STRENGTH_LABELS = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong'];

/** Slows repeated failed attempts on this device (the server enforces the real limit). */
export class AttemptLimiter {
  static FREE_TRIES = 5;
  static FIRST_WAIT = 30;
  static MAX_WAIT = 15 * 60;
  static FORGET_AFTER = 60 * 60;
  private failures = new Map<string, [number, number]>();

  constructor(private clock: () => number = () => Date.now() / 1000) {}

  waitSeconds(key: string): number {
    const [count, last] = this.failures.get(key.trim().toLowerCase()) ?? [0, 0];
    if (count < AttemptLimiter.FREE_TRIES || this.clock() - last > AttemptLimiter.FORGET_AFTER) return 0;
    const wait = Math.min(AttemptLimiter.MAX_WAIT, AttemptLimiter.FIRST_WAIT * 2 ** (count - AttemptLimiter.FREE_TRIES));
    return Math.max(0, pyRound(last + wait - this.clock()));
  }

  failed(key: string) {
    const id = key.trim().toLowerCase();
    let [count, last] = this.failures.get(id) ?? [0, 0];
    if (this.clock() - last > AttemptLimiter.FORGET_AFTER) count = 0;
    this.failures.set(id, [count + 1, this.clock()]);
  }

  succeeded(key: string) {
    this.failures.delete(key.trim().toLowerCase());
  }
}

export function waitMessage(seconds: number): string {
  return seconds >= 90
    ? `Too many tries. Please wait about ${pyRound(seconds / 60)} minutes before trying again.`
    : `Too many tries. Please wait ${seconds} seconds before trying again.`;
}

// Accounts (and so any personal data leaving the device) are for people 13
// and older, as children's privacy laws expect (COPPA in the US). Everything
// else in MemoryPal works without an account, for any age.
export const MIN_ACCOUNT_AGE = 13;
// A refused age check holds on that device for a day, so the answer can't
// simply be changed and sent again.
export const AGE_RETRY_SECONDS = 24 * 60 * 60;
// Bump when the Terms or Privacy Policy change; stored with each new account.
export const TERMS_VERSION = '2026-10-23';
export const AGE_FORMAT_MESSAGE = 'Enter the month (1-12) and the year you were born.';
export const UNDER_AGE_MESSAGE =
  `MemoryPal accounts are for people ${MIN_ACCOUNT_AGE} and older. You can keep using ` +
  'everything on this device without an account; your cards stay saved here.';

/** ['', false] when old enough for an account, else [message, underAge]. See security.py. */
export function accountAgeCheck(month: string | number, year: string | number, todayYear: number, todayMonth: number): [string, boolean] {
  const m = String(month).trim();
  const y = String(year).trim();
  if (!/^[+-]?\d+$/.test(m) || !/^[+-]?\d+$/.test(y)) return [AGE_FORMAT_MESSAGE, false];
  const birthMonth = parseInt(m, 10);
  const birthYear = parseInt(y, 10);
  if (birthMonth < 1 || birthMonth > 12 || birthYear < todayYear - 120 || birthYear > todayYear) return [AGE_FORMAT_MESSAGE, false];
  const age = todayYear - birthYear - (todayMonth <= birthMonth ? 1 : 0);
  if (age < MIN_ACCOUNT_AGE) return [UNDER_AGE_MESSAGE, true];
  return ['', false];
}
