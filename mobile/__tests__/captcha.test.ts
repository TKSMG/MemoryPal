/** The CAPTCHA check before sign-in, sign-up and emailed codes. */
import { allowedInCheck, readCheckMessage } from '../src/cloud/checkPage';
import { CloudClient, needsCaptcha } from '../src/cloud/client';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { captchaUrl: 'https://tksmg.github.io/MemoryPal/verify/' } } } }));

const PAGE = 'https://tksmg.github.io/MemoryPal/verify/';

function recordingClient() {
  const sent: { url: string; body: Record<string, unknown> | null }[] = [];
  const fetcher = (async (url: string, init: { body?: string }) => {
    sent.push({ url, body: init.body ? JSON.parse(init.body) : null });
    const reply = url.includes('/token') ? { access_token: 'a', refresh_token: 'r', expires_in: 3600, user: { id: 'u', email: 'pat@example.com' } } : {};
    return { ok: true, status: 200, text: async () => JSON.stringify(reply) };
  }) as unknown as typeof fetch;
  return { sent, client: new CloudClient('https://example.supabase.co', 'sb_publishable_test', fetcher) };
}

describe('captcha', () => {
  it('knows which requests need a check', () => {
    expect(needsCaptcha('/auth/v1/signup')).toBe(true);
    expect(needsCaptcha('/auth/v1/recover')).toBe(true);
    expect(needsCaptcha('/auth/v1/resend')).toBe(true);
    expect(needsCaptcha('/auth/v1/token', { grant_type: 'password' })).toBe(true);
    expect(needsCaptcha('/auth/v1/token', { grant_type: 'refresh_token' })).toBe(false);
    expect(needsCaptcha('/auth/v1/verify')).toBe(false);
  });

  it('sends a fresh token with each protected request, and none with a refresh', async () => {
    const { sent, client } = recordingClient();
    let issued = 0;
    client.setCaptcha(async () => `token-${++issued}`);
    await client.signIn('pat@example.com', 'correct horse 7');
    await client.requestPasswordReset('pat@example.com');
    await client.refresh('r');
    expect(sent.map((request) => (request.body?.gotrue_meta_security as { captcha_token?: string } | undefined)?.captcha_token)).toEqual(['token-1', 'token-2', undefined]);
    expect(sent[0].body?.email).toBe('pat@example.com');
  });

  it('sends nothing extra when the check is off', async () => {
    const { sent, client } = recordingClient();
    await client.signIn('pat@example.com', 'correct horse 7');
    expect(sent[0].body).not.toHaveProperty('gotrue_meta_security');
  });

  it('stops when the check fails, before anything is sent', async () => {
    const { sent, client } = recordingClient();
    client.setCaptcha(async () => {
      throw new Error('closed');
    });
    await expect(client.signIn('pat@example.com', 'correct horse 7')).rejects.toThrow('closed');
    expect(sent).toHaveLength(0);
  });

  it('reads only the check page messages it expects', () => {
    expect(readCheckMessage(JSON.stringify({ type: 'turnstile', token: 'abc' }))).toEqual({ token: 'abc' });
    expect(readCheckMessage(JSON.stringify({ type: 'turnstile', error: '110200' }))).toEqual({ error: '110200' });
    expect(readCheckMessage(JSON.stringify({ type: 'other', token: 'abc' }))).toBeNull();
    expect(readCheckMessage('not json')).toBeNull();
  });

  it('keeps the sheet on the check page and Cloudflare', () => {
    expect(allowedInCheck(PAGE, PAGE)).toBe(true);
    expect(allowedInCheck('https://challenges.cloudflare.com/cdn-cgi/challenge-platform/x', PAGE)).toBe(true);
    expect(allowedInCheck('about:blank', PAGE)).toBe(true);
    expect(allowedInCheck('https://evil.example/', PAGE)).toBe(false);
    expect(allowedInCheck('https://tksmg.github.io/other/', PAGE)).toBe(false);
  });
});
