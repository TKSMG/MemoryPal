/** What the CAPTCHA sheet trusts from the check page (site/verify/); kept apart from the UI so it can be tested. */
import { captchaUrl } from './client';

/** Pages the sheet may load: the check page, Cloudflare's challenge, and the blank frames it uses. */
export function allowedInCheck(url: string, page = captchaUrl()): boolean {
  return (!!page && url.startsWith(page)) || url.startsWith('https://challenges.cloudflare.com/') || url === 'about:blank' || url === 'about:srcdoc';
}

/** What the page posted: a token, a failure, or null for anything else. */
export function readCheckMessage(data: string): { token?: string; spares?: string[]; error?: string } | null {
  try {
    const message = JSON.parse(data) as { type?: unknown; token?: unknown; spares?: unknown; error?: unknown };
    if (message?.type !== 'turnstile') return null;
    if (typeof message.token === 'string' && message.token) {
      const spares = Array.isArray(message.spares) ? message.spares.filter((spare): spare is string => typeof spare === 'string' && !!spare).slice(0, 4).map((spare) => spare.slice(0, 4096)) : [];
      return { token: message.token.slice(0, 4096), spares };
    }
    return { error: String(message.error ?? 'failed') };
  } catch {
    return null;
  }
}
