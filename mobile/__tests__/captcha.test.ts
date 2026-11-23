/** The CAPTCHA check before sign-in, sign-up and emailed codes. */
import { allowedInCheck, fromCheckPage, readCheckMessage } from '../src/cloud/checkPage';
import { CloudClient, forgetSpares, keepSpares, needsCaptcha, SPARE_MS, takeSpare } from '../src/cloud/client';

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
  beforeEach(() => forgetSpares());

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

  it('takes messages from the check page, also when Android reports only its origin', () => {
    expect(fromCheckPage(PAGE, PAGE)).toBe(true);
    expect(fromCheckPage('https://tksmg.github.io/MemoryPal/verify/#x', PAGE)).toBe(true);
    expect(fromCheckPage('https://tksmg.github.io', PAGE)).toBe(true);
    expect(fromCheckPage('https://tksmg.github.io/', PAGE)).toBe(true);
    expect(fromCheckPage('https://challenges.cloudflare.com', PAGE)).toBe(false);
    expect(fromCheckPage('https://tksmg.github.io.evil.example', PAGE)).toBe(false);
    expect(fromCheckPage('http://tksmg.github.io', PAGE)).toBe(false);
    expect(fromCheckPage('', PAGE)).toBe(false);
    expect(fromCheckPage(PAGE, '')).toBe(false);
  });

  it('reads only the check page messages it expects', () => {
    expect(readCheckMessage(JSON.stringify({ type: 'turnstile', token: 'abc' }))).toEqual({ token: 'abc', spares: [] });
    expect(readCheckMessage(JSON.stringify({ type: 'turnstile', token: 'abc', spares: ['b', 7, 'c'] }))).toEqual({ token: 'abc', spares: ['b', 'c'] });
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

  it('uses spare passes for the next tries, then checks again', async () => {
    const { sent, client } = recordingClient();
    let issued = 0;
    client.setCaptcha(async () => {
      issued += 1;
      keepSpares([`spare-${issued}-a`, `spare-${issued}-b`]);
      return `token-${issued}`;
    });
    for (let n = 0; n < 4; n++) await client.signIn('pat@example.com', 'correct horse 7');
    expect(sent.map((request) => (request.body?.gotrue_meta_security as { captcha_token?: string }).captcha_token)).toEqual(['token-1', 'spare-1-a', 'spare-1-b', 'token-2']);
    expect(issued).toBe(2);
  });

  it('lets spares expire before Cloudflare does', () => {
    keepSpares(['a', 'b'], 0);
    expect(takeSpare(SPARE_MS - 1)).toBe('a');
    expect(takeSpare(SPARE_MS + 1)).toBeUndefined();
  });

  it('drops refused spares and checks afresh once', async () => {
    const sent: string[] = [];
    const fetcher = (async (_url: string, init: { body?: string }) => {
      const token = (JSON.parse(init.body ?? '{}').gotrue_meta_security ?? {}).captcha_token as string;
      sent.push(token);
      if (token.startsWith('stale')) return { ok: false, status: 400, text: async () => JSON.stringify({ error_code: 'captcha_failed' }) };
      return { ok: true, status: 200, text: async () => JSON.stringify({ access_token: 'a', refresh_token: 'r', expires_in: 3600, user: { id: 'u', email: 'pat@example.com' } }) };
    }) as unknown as typeof fetch;
    const client = new CloudClient('https://example.supabase.co', 'sb_publishable_test', fetcher);
    client.setCaptcha(async () => 'fresh');
    keepSpares(['stale-1', 'stale-2']);
    await client.signIn('pat@example.com', 'correct horse 7');
    expect(sent).toEqual(['stale-1', 'fresh']);
    expect(takeSpare()).toBeUndefined();
  });
});
