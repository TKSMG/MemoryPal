/** Signing in to a different account, and signing out, on the phone. */
import { CloudAccount } from '../src/cloud/account';
import { CloudClient, CloudError, Session } from '../src/cloud/client';
import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: {} } } }));
jest.mock('../src/cloud/secrets', () => {
  const secrets = new Map<string, string>();
  return {
    readSecret: async (key: string) => secrets.get(key) ?? null,
    writeSecret: async (key: string, value: string | null) => (value === null ? secrets.delete(key) : secrets.set(key, value)),
  };
});
jest.mock('../src/state/storage', () => {
  const values = new Map<string, string>();
  return { keyAdapter: (key: string) => ({ load: () => values.get(key) ?? null, save: (text: string) => values.set(key, text) }) };
});

type Data = Record<string, unknown> | null;

/** One fake cloud: rows per account. */
function fakeCloud() {
  const rows: Record<string, Record<string, Data>> = {};
  const session = (userId: string): Session => ({
    accessToken: `a-${userId}`, refreshToken: `r-${userId}`, expiresAt: 9e12, userId, email: `${userId}@example.com`, factors: [],
  });
  const client = {
    signedOut: [] as string[],
    refresh: jest.fn(async (token: string) => session(token.slice(2))),
    signOut: jest.fn(async (s: Session) => {
      client.signedOut.push(s.userId);
    }),
    pull: jest.fn(async (s: Session) => Object.entries(rows[s.userId] ?? {}).map(([key, data]) => [key, data, '2026-10-15T00:00:00Z'])),
    push: jest.fn(async (s: Session, changes: Record<string, Data>) => {
      rows[s.userId] = { ...(rows[s.userId] ?? {}), ...changes };
    }),
  };
  return { rows, session, client: client as unknown as CloudClient & typeof client };
}

function storeWith(cardId: string) {
  const store = new MemoryStore(new MemoryAdapter());
  store.finishOnboarding('student');
  store.addCard(newCard({ id: cardId, deck: 'Mine', front: `Front ${cardId}`, back: 'Back' }));
  return store;
}

test('signing in to a different account asks first and sends nothing', async () => {
  const cloud = fakeCloud();
  const account = new CloudAccount(cloud.client);
  const store = storeWith('only-in-a');
  await account.remember(cloud.session('a'));
  await account.sync(store);
  await account.remember(cloud.session('b'));
  const refused = await account.sync(store).catch((error) => error);
  expect(refused).toBeInstanceOf(CloudError);
  expect(refused.code).toBe('other_account');
  expect(cloud.rows.b).toBeUndefined();
});

test('replace swaps in the account cards; merge adds this phone cards', async () => {
  // (Every CloudAccount here shares the one saved sync state, like a real phone.)
  const cloud = fakeCloud();
  cloud.rows.b = { 'card:only-in-b': { ...newCard({ id: 'only-in-b', deck: 'Theirs', front: 'B', back: 'B' }) } };
  const account = new CloudAccount(cloud.client);
  const store = storeWith('only-in-a');
  await account.remember(cloud.session('a'));
  await account.sync(store, undefined, 'merge');
  await account.remember(cloud.session('b'));
  await account.sync(store, undefined, 'replace');
  expect(store.findCard('only-in-b')).toBeTruthy();
  expect(store.findCard('only-in-a')).toBeFalsy();
  expect(Object.keys(cloud.rows.b)).not.toContain('card:only-in-a');

  await account.remember(cloud.session('c'));
  await account.sync(store, undefined, 'merge');
  expect(Object.keys(cloud.rows.c)).toContain('card:only-in-b');
});

test('signing out ends the session on the server even before any sync', async () => {
  const cloud = fakeCloud();
  const first = new CloudAccount(cloud.client);
  await first.remember(cloud.session('a'));
  const relaunched = new CloudAccount(cloud.client);
  await relaunched.restore(); // only the saved sign-in, no session in memory
  await relaunched.signOut();
  expect(cloud.client.signedOut).toEqual(['a']);
  expect(relaunched.signedIn).toBe(false);
});

describe('rate limits', () => {
  test('are explained, with the wait when Supabase gives one', () => {
    const tooSoon = CloudClient.errorFrom(429, { error_code: 'over_email_send_rate_limit', msg: 'For security purposes, you can only request this after 42 seconds.' });
    expect(tooSoon.code).toBe('email_too_soon');
    expect(tooSoon.message).toContain('Wait 42 seconds');
    expect(CloudClient.errorFrom(429, { error_code: 'over_email_send_rate_limit', msg: 'Email rate limit exceeded' }).code).toBe('over_email_send_rate_limit');
    expect(CloudClient.errorFrom(429, { error_code: 'over_request_rate_limit' }).code).toBe('over_request_rate_limit');
    expect(CloudClient.errorFrom(429, {}).code).toBe('rate_limited');
  });
});
