/**
 * Accounts and sync with the MemoryPal cloud (Supabase) over plain fetch,
 * mirroring latest_app/memorypal/cloud.py: email + password, emailed
 * codes for confirming an account and resetting a password, and the
 * sync_records table protected by Row Level Security (supabase/schema.sql),
 * plus optional two-step sign-in with an authenticator app (TOTP).
 */
import Constants from 'expo-constants';

import { MIN_ACCOUNT_AGE, MIN_PASSWORD, passwordProblems, TERMS_VERSION } from '../core/security';
import { kindOf } from '../core/sync';
import type { Data } from '../core/sync';

export { MIN_PASSWORD };
const PAGE_SIZE = 1000;
const PUSH_BATCH = 400;
const TIMEOUT_MS = 20000;

/** URL and publishable key from app.json (expo.extra); empty means sync isn't set up. */
export function cloudConfig(): { url: string; key: string } {
  const extra = (Constants.expoConfig?.extra ?? {}) as { supabaseUrl?: string; supabasePublishableKey?: string };
  return { url: String(extra.supabaseUrl ?? '').replace(/\/+$/, ''), key: String(extra.supabasePublishableKey ?? '') };
}

export function cloudConfigured(): boolean {
  const { url, key } = cloudConfig();
  return Boolean(url && key);
}

/** The CAPTCHA check page (app.json expo.extra captchaUrl; site/verify/ in the repo); empty turns the check off. */
export function captchaUrl(): string {
  const extra = (Constants.expoConfig?.extra ?? {}) as { captchaUrl?: string };
  return String(extra.captchaUrl ?? '').trim();
}

/** Requests the server refuses without a CAPTCHA token once CAPTCHA protection is on (cloud.py needs_captcha). */
export function needsCaptcha(path: string, query: Record<string, string | number> = {}): boolean {
  return ['/auth/v1/signup', '/auth/v1/recover', '/auth/v1/resend'].includes(path) || (path === '/auth/v1/token' && query.grant_type === 'password');
}

/** The published Terms of Use and Privacy Policy (app.json expo.extra termsUrl / privacyUrl). */
export function legalLinks(): { terms: string; privacy: string } {
  const extra = (Constants.expoConfig?.extra ?? {}) as { termsUrl?: string; privacyUrl?: string };
  return { terms: String(extra.termsUrl ?? ''), privacy: String(extra.privacyUrl ?? '') };
}

/** What a new account keeps about consent: no birth date, just the outcome (cloud.py consent_record). */
export function consentRecord(now = Date.now()): Record<string, string> {
  return {
    age_confirmed: `${MIN_ACCOUNT_AGE}+`,
    terms_version: TERMS_VERSION,
    terms_accepted_at: new Date(Math.floor(now / 1000) * 1000).toISOString().replace('.000Z', 'Z'),
  };
}

export class CloudError extends Error {
  constructor(message: string, public code = '') {
    super(message);
  }
}

const FRIENDLY: Record<string, string> = {
  invalid_credentials: "That email and password don't match. Check them, or reset your password.",
  invalid_grant: "That email and password don't match. Check them, or reset your password.",
  email_not_confirmed: 'Confirm your email first: enter the code we emailed you.',
  captcha_failed: "The quick check that keeps out bots didn't work. Try again.",
  captcha_cancelled: 'The quick check was closed before it finished. Try again when you\'re ready.',
  user_already_exists: "There's already an account with this email. Sign in instead.",
  email_exists: "There's already an account with this email. Sign in instead.",
  weak_password: `Choose a stronger password: at least ${MIN_PASSWORD} characters with letters and at least one number.`,
  over_email_send_rate_limit: 'Too many emails were sent just now. Wait a few minutes and try again.',
  over_request_rate_limit: 'Too many tries in a short time. Wait a minute and try again.',
  otp_expired: 'That code is wrong or has expired. Ask for a new one.',
  validation_failed: 'Check the email address and try again.',
  email_address_invalid: "That doesn't look like an email address.",
  signup_disabled: "New accounts can't be made right now.",
  refresh_token_not_found: "You've been signed out. Please sign in again.",
  session_not_found: "You've been signed out. Please sign in again.",
  refresh_token_already_used: "You've been signed out. Please sign in again.",
  other_account: 'This phone last synced with a different account. Choose what to do with its cards before syncing.',
  two_step_now_on: 'This account now uses two-step sign-in. Sign in again with your authenticator code.',
  mfa_verification_failed: "That authenticator code isn't right. Check the time on this device and try the newest code.",
  mfa_challenge_expired: 'That took too long. Try again with a fresh code.',
  insufficient_aal: 'Finish two-step sign-in first: enter the code from your authenticator app.',
  mfa_factor_not_found: "Two-step sign-in isn't set up for this account any more.",
  too_many_enrolled_mfa_factors: 'Two-step sign-in is already set up. Turn it off first to set it up again.',
  // Row Level Security refused the request (for two-step accounts: no second step yet).
  // The per-person storage allowance in supabase/schema.sql (sync_records_quota).
  P0001: 'Your cloud copy is full. Delete cards or notes you no longer need, then sync again.',
  '42501': "MemoryPal couldn't reach your cloud data. Sign out and sign in again (with your authenticator code if you use one).",
};

export const friendly = (code: string) => FRIENDLY[code] ?? '';

export interface Factor {
  id: string;
  friendly_name: string;
}

export interface Session {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // seconds since 1970
  userId: string;
  email: string;
  /** Verified authenticator-app factors on the account. */
  factors: Factor[];
}

function sessionFrom(data: Record<string, unknown>): Session {
  const user = (data.user ?? {}) as Record<string, unknown>;
  const expiresAt = Number(data.expires_at) || Date.now() / 1000 + (Number(data.expires_in) || 3600);
  const factors = ((user.factors ?? []) as Record<string, unknown>[])
    .filter((factor) => factor.status === 'verified' && factor.factor_type === 'totp')
    .map((factor) => ({ id: String(factor.id ?? ''), friendly_name: String(factor.friendly_name ?? '') }));
  return { accessToken: String(data.access_token ?? ''), refreshToken: String(data.refresh_token ?? ''), expiresAt, userId: String(user.id ?? ''), email: String(user.email ?? ''), factors };
}

/** The (unverified) claims inside an access token, to read its assurance level. */
export function jwtClaims(token: string): Record<string, unknown> {
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = part + '='.repeat((4 - (part.length % 4)) % 4);
    const bytes = Array.from(atob(padded), (ch) => '%' + ch.charCodeAt(0).toString(16).padStart(2, '0')).join('');
    return JSON.parse(decodeURIComponent(bytes)) ?? {};
  } catch {
    return {};
  }
}

/** 'aal1' after a password, 'aal2' after the second step too. */
export const sessionLevel = (session: Session) => String(jwtClaims(session.accessToken).aal ?? 'aal1');

export const needsSecondStep = (session: Session) => session.factors.length > 0 && sessionLevel(session) !== 'aal2';

export const expiring = (session: Session, margin = 60) => Date.now() / 1000 > session.expiresAt - margin;

export function looksLikeEmail(text: string): boolean {
  const value = (text ?? '').trim();
  const at = value.indexOf('@');
  const domain = value.slice(at + 1);
  return at > 0 && domain.includes('.') && !value.includes(' ') && !domain.startsWith('.') && !domain.endsWith('.');
}

/** Refuse weak passwords before they reach the server (which checks again). */
export function checkPassword(password: string, email = '') {
  const problems = passwordProblems(password, email);
  if (problems.length) throw new CloudError(problems[0], 'weak_password');
}

export type Row = [key: string, data: Data | null, updatedAt: string];

export class CloudClient {
  /** Asked for a CAPTCHA token before sign-in, sign-up and emailed codes (the account screen sets it). */
  private captcha?: () => Promise<string>;

  setCaptcha(check?: () => Promise<string>) {
    this.captcha = check;
  }

  constructor(
    private url = cloudConfig().url,
    private key = cloudConfig().key,
    private fetcher: typeof fetch = (...args) => fetch(...args),
  ) {}

  async request(method: string, path: string, options: { body?: unknown; token?: string; query?: Record<string, string | number>; prefer?: string } = {}): Promise<unknown> {
    if (!this.url || !this.key) throw new CloudError("Sync isn't set up in this copy of MemoryPal yet.", 'not_configured');
    const query = options.query ? '?' + Object.entries(options.query).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v)).replace(/%2C/g, ',').replace(/%3A/g, ':')}`).join('&') : '';
    const headers: Record<string, string> = { apikey: this.key, Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.token) headers.Authorization = `Bearer ${options.token}`;
    if (options.prefer) headers.Prefer = options.prefer;
    let body = options.body;
    if (this.captcha && body !== undefined && needsCaptcha(path, options.query)) {
      body = { ...(body as Record<string, unknown>), gotrue_meta_security: { captcha_token: await this.captcha() } };
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    let response: Response;
    try {
      response = await this.fetcher(`${this.url}${path}${query}`, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined, signal: controller.signal });
    } catch {
      throw new CloudError("Couldn't reach the MemoryPal cloud. Check the internet connection and try again.", 'offline');
    } finally {
      clearTimeout(timer);
    }
    const text = await response.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = null;
    }
    if (!response.ok) throw CloudClient.errorFrom(response.status, (data ?? {}) as Record<string, unknown>);
    return data;
  }

  static errorFrom(status: number, detail: Record<string, unknown>): CloudError {
    const code = String(detail.error_code ?? detail.error ?? detail.code ?? '');
    const text = String(detail.msg ?? detail.error_description ?? detail.message ?? '');
    const wait = /after (\d+) seconds?/.exec(text);
    if (status === 429 && wait) {
      // Supabase allows one email to an address per minute or so.
      return new CloudError(`An email was sent to this address moments ago. Wait ${wait[1]} seconds, then try again.`, 'email_too_soon');
    }
    if (FRIENDLY[code]) return new CloudError(FRIENDLY[code], code);
    if (text.includes('Invalid login credentials')) return new CloudError(FRIENDLY.invalid_credentials, 'invalid_credentials');
    if (status === 401) return new CloudError(FRIENDLY.session_not_found, 'unauthorized');
    if (status === 429) return new CloudError(FRIENDLY.over_request_rate_limit, 'rate_limited');
    return new CloudError(text || `The MemoryPal cloud answered with an error (${status}).`, code || String(status));
  }

  /** Create an account: a Session, or null when the email must be confirmed with a code first. */
  async signUp(email: string, password: string, consent?: Record<string, string>): Promise<Session | null> {
    checkPassword(password, email);
    const body: Record<string, unknown> = { email: email.trim(), password };
    if (consent) body.data = { ...consent };
    const data = ((await this.request('POST', '/auth/v1/signup', { body })) ?? {}) as Record<string, unknown>;
    return data.access_token ? sessionFrom(data) : null;
  }

  async verifyCode(email: string, code: string, kind: 'signup' | 'recovery' = 'signup'): Promise<Session> {
    const token = String(code).replace(/\D/g, '');
    const data = ((await this.request('POST', '/auth/v1/verify', { body: { type: kind, email: email.trim(), token } })) ?? {}) as Record<string, unknown>;
    if (!data.access_token) throw new CloudError(FRIENDLY.otp_expired, 'otp_expired');
    return sessionFrom(data);
  }

  async resendConfirmation(email: string) {
    await this.request('POST', '/auth/v1/resend', { body: { type: 'signup', email: email.trim() } });
  }

  async signIn(email: string, password: string): Promise<Session> {
    return sessionFrom(((await this.request('POST', '/auth/v1/token', { body: { email: email.trim(), password }, query: { grant_type: 'password' } })) ?? {}) as Record<string, unknown>);
  }

  async refresh(refreshToken: string): Promise<Session> {
    return sessionFrom(((await this.request('POST', '/auth/v1/token', { body: { refresh_token: refreshToken }, query: { grant_type: 'refresh_token' } })) ?? {}) as Record<string, unknown>);
  }

  async requestPasswordReset(email: string) {
    await this.request('POST', '/auth/v1/recover', { body: { email: email.trim() } });
  }

  async setPassword(session: Session, password: string) {
    checkPassword(password, session.email);
    await this.request('PUT', '/auth/v1/user', { body: { password }, token: session.accessToken });
  }

  async signOut(session: Session) {
    try {
      await this.request('POST', '/auth/v1/logout', { body: {}, token: session.accessToken });
    } catch {
      // signing out on this phone still works offline
    }
  }

  async deleteAccount(session: Session) {
    await this.request('POST', '/rest/v1/rpc/delete_my_account', { body: {}, token: session.accessToken });
  }

  // ------------------------------------------------- two-step sign-in (TOTP)
  /** The account's verified authenticator-app factors (fresh from the server). */
  async factors(session: Session): Promise<Factor[]> {
    const user = ((await this.request('GET', '/auth/v1/user', { token: session.accessToken })) ?? {}) as Record<string, unknown>;
    return sessionFrom({ access_token: session.accessToken, user }).factors;
  }

  /** Start adding an authenticator app: the key and otpauth:// link to show the person. */
  async enrollAuthenticator(session: Session): Promise<{ factorId: string; secret: string; uri: string }> {
    const stamp = new Date().toISOString().slice(0, 16).replace('T', ' ');
    const body = { factor_type: 'totp', friendly_name: `Authenticator ${stamp}`, issuer: 'MemoryPal' };
    const data = ((await this.request('POST', '/auth/v1/factors', { body, token: session.accessToken })) ?? {}) as Record<string, unknown>;
    const totp = (data.totp ?? {}) as Record<string, unknown>;
    return { factorId: String(data.id ?? ''), secret: String(totp.secret ?? ''), uri: String(totp.uri ?? '') };
  }

  /** Prove a 6-digit authenticator code; returns the upgraded (aal2) Session. */
  async verifyAuthenticator(session: Session, factorId: string, code: string): Promise<Session> {
    const digits = String(code).replace(/\D/g, '');
    const challenge = ((await this.request('POST', `/auth/v1/factors/${factorId}/challenge`, { body: {}, token: session.accessToken })) ?? {}) as Record<string, unknown>;
    const body = { challenge_id: String(challenge.id ?? ''), code: digits };
    const data = ((await this.request('POST', `/auth/v1/factors/${factorId}/verify`, { body, token: session.accessToken })) ?? {}) as Record<string, unknown>;
    if (!data.access_token) throw new CloudError(FRIENDLY.mfa_verification_failed, 'mfa_verification_failed');
    return sessionFrom(data);
  }

  async removeAuthenticator(session: Session, factorId: string) {
    await this.request('DELETE', `/auth/v1/factors/${factorId}`, { token: session.accessToken });
  }

  // ----------------------------------------------------------------- data
  async pull(session: Session, since: string | null): Promise<Row[]> {
    const rows: Row[] = [];
    for (let offset = 0; ; offset += PAGE_SIZE) {
      const query: Record<string, string | number> = { select: 'key,kind,data,deleted,updated_at', order: 'updated_at.asc,key.asc', limit: PAGE_SIZE, offset };
      if (since) query.updated_at = `gte.${since}`;
      const page = ((await this.request('GET', '/rest/v1/sync_records', { token: session.accessToken, query })) ?? []) as Record<string, unknown>[];
      for (const row of page) {
        const data = row.deleted ? null : row.data;
        // A malformed row is skipped, never read as a delete.
        if (!row.deleted && (data === null || typeof data !== 'object' || Array.isArray(data))) continue;
        rows.push([String(row.key), (data ?? null) as Data | null, String(row.updated_at ?? '')]);
      }
      if (page.length < PAGE_SIZE) return rows;
    }
  }

  async push(session: Session, changes: Record<string, Data | null>) {
    const rows = Object.keys(changes).sort().map((key) => ({ key, kind: kindOf(key), data: changes[key], deleted: changes[key] === null }));
    for (let start = 0; start < rows.length; start += PUSH_BATCH) {
      await this.request('POST', '/rest/v1/sync_records', {
        body: rows.slice(start, start + PUSH_BATCH),
        token: session.accessToken,
        query: { on_conflict: 'user_id,key' },
        prefer: 'resolution=merge-duplicates,return=minimal',
      });
    }
  }
}
