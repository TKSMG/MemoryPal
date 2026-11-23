/** What the CAPTCHA sheet trusts from the check page (site/verify/); kept apart from the UI so it can be tested. */
import { captchaUrl } from './client';

/** Pages the sheet may load: the check page, Cloudflare's challenge, and the blank frames it uses. */
export function allowedInCheck(url: string, page = captchaUrl()): boolean {
  return (!!page && url.startsWith(page)) || url.startsWith('https://challenges.cloudflare.com/') || url === 'about:blank' || url === 'about:srcdoc';
}

/**
 * Whether a message came from the check page. Android's WebView (with the
 * web message listener every current phone has) reports only the sender's
 * origin, "https://tksmg.github.io", not the page address, so the address
 * alone used to turn every Android token away and the sheet sat on
 * "Done, continuing". The sheet only ever loads the check page itself at that
 * origin (allowedInCheck), so its origin is enough.
 */
export function fromCheckPage(url: string, page = captchaUrl()): boolean {
  if (!page || !url) return false;
  if (url.startsWith(page)) return true;
  const origin = originOf(page);
  return !!origin && originOf(url) === origin;
}

function originOf(url: string): string {
  const match = /^(https:\/\/[^/?#]+)/i.exec(url.trim());
  return match ? match[1].toLowerCase() : '';
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
