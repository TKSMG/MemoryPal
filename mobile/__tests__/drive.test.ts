/** Syncing through Google Drive on the phone: two phones, the move off the MemoryPal cloud, and the Drive API. */
import { CloudAccount } from '../src/cloud/account';
import { CloudClient, CloudError, Session } from '../src/cloud/client';
import { DriveFiles, MemoryFiles } from '../src/cloud/drive';
import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { supabaseUrl: 'https://example.supabase.co', supabasePublishableKey: 'sb_publishable_test' } } } }));
jest.mock('../src/cloud/googleAuth', () => ({
  googleConfigured: () => true,
  connectGoogle: jest.fn(async () => ({ user_id: 'google-1', email: 'pat@gmail.com' })),
  disconnectGoogle: jest.fn(async () => undefined),
  googleAccessToken: jest.fn(async () => 'token'),
}));
jest.mock('../src/cloud/secrets', () => {
  const secrets = new Map<string, string>();
  return {
    readSecret: async (key: string) => secrets.get(key) ?? null,
    writeSecret: async (key: string, value: string | null) => (value === null ? secrets.delete(key) : secrets.set(key, value)),
  };
});
// Every CloudAccount gets its own key-value store, like a separate phone.
let mockPhoneStorage = new Map<string, string>();
jest.mock('../src/state/storage', () => ({
  keyAdapter: (key: string) => {
    const values = mockPhoneStorage;
    return { load: () => values.get(key) ?? null, save: (text: string) => values.set(key, text) };
  },
}));

type Data = Record<string, unknown> | null;

function fakeCloud() {
  const rows: Record<string, Record<string, Data>> = {};
  const session = (userId: string): Session => ({
    accessToken: `a-${userId}`, refreshToken: `r-${userId}`, expiresAt: 9e12, userId, email: `${userId}@example.com`, factors: [],
  });
  const client = {
    refresh: jest.fn(async (token: string) => session(token.slice(2))),
    pull: jest.fn(async (s: Session) => Object.entries(rows[s.userId] ?? {}).map(([key, data]) => [key, data, '2026-10-15T00:00:00Z'])),
    push: jest.fn(async (s: Session, changes: Record<string, Data>) => {
      rows[s.userId] = { ...(rows[s.userId] ?? {}), ...changes };
    }),
    deleteSyncRecords: jest.fn(async (s: Session) => {
      delete rows[s.userId];
    }),
  };
  return { rows, session, client: client as unknown as CloudClient & typeof client };
}

function phone(drive: MemoryFiles, client = fakeCloud().client) {
  mockPhoneStorage = new Map();
  const account = new CloudAccount(client, () => drive);
  const store = new MemoryStore(new MemoryAdapter());
  store.finishOnboarding('student');
  return { account, store };
}

const cardIds = (store: MemoryStore) => store.cards.map((card) => card.id).sort();

test('two phones share cards through the drive, each writing only its own file', async () => {
  const drive = new MemoryFiles();
  const a = phone(drive);
  const b = phone(drive);
  await a.account.connectDrive();
  await b.account.connectDrive();
  a.store.addCard(newCard({ id: 'from-a', deck: 'Mine', front: 'A', back: 'a' }));
  b.store.addCard(newCard({ id: 'from-b', deck: 'Mine', front: 'B', back: 'b' }));
  await a.account.sync(a.store);
  await b.account.sync(b.store);
  await a.account.sync(a.store);
  expect(cardIds(a.store)).toEqual(cardIds(b.store));
  expect(cardIds(a.store)).toEqual(expect.arrayContaining(['from-a', 'from-b']));
  const names = [...drive.files.values()].map((file) => file.name).sort();
  expect(names).toEqual([`memorypal-${a.account.state.device_id}.json`, `memorypal-${b.account.state.device_id}.json`].sort());

  // A delete reaches the other phone.
  a.store.replaceWith({ ...a.store.payload(), cards: a.store.cards.filter((card) => card.id !== 'from-b') });
  await a.account.sync(a.store);
  await b.account.sync(b.store);
  expect(cardIds(b.store)).not.toContain('from-b');

  // Nothing changed: no file is rewritten.
  const versions = [...drive.files.values()].map((file) => file.version);
  await a.account.sync(a.store);
  expect([...drive.files.values()].map((file) => file.version)).toEqual(versions);
});

test('the first Drive sync brings the MemoryPal cloud records along, then removes them there', async () => {
  const cloud = fakeCloud();
  cloud.rows.u1 = { 'card:cloud-only': { ...newCard({ id: 'cloud-only', deck: 'Old', front: 'From the cloud', back: 'yes' }) } };
  const drive = new MemoryFiles();
  const p = phone(drive, cloud.client);
  await p.account.remember(cloud.session('u1'));
  await p.account.connectDrive();
  await p.account.sync(p.store);
  expect(cardIds(p.store)).toContain('cloud-only');
  expect(cloud.rows.u1).toBeUndefined();
  expect(cloud.client.deleteSyncRecords).toHaveBeenCalledTimes(1);
  const file = JSON.parse([...drive.files.values()][0].body);
  expect(file.records['card:cloud-only']).toBeTruthy();
  cloud.client.pull.mockClear();
  await p.account.sync(p.store);
  expect(cloud.client.pull).not.toHaveBeenCalled();
});

test('a different Google account asks first; not connected says so', async () => {
  const p = phone(new MemoryFiles());
  const refused = await p.account.sync(p.store).catch((error) => error);
  expect(refused).toBeInstanceOf(CloudError);
  expect(refused.code).toBe('drive_not_linked');
  expect(p.account.canSync).toBe(false);
  await p.account.connectDrive();
  await p.account.sync(p.store);
  p.account.drive = { user_id: 'google-2', email: 'other@gmail.com' };
  const other = await p.account.sync(p.store).catch((error) => error);
  expect(other.code).toBe('other_account');
  await p.account.sync(p.store, undefined, 'merge');
  expect(p.account.state.drive_user).toBe('google-2');
});

describe('the Drive API', () => {
  function fakeDrive() {
    const files = new Map<string, { name: string; body: string; version: number }>();
    let version = 0;
    // What Google accepts, and what the phone has cached.
    let valid = 'token-1';
    let cached = valid;
    const tokens = jest.fn(async (renew?: boolean) => {
      if (renew) cached = valid;
      return cached;
    });
    let failNext: [number, string] | null = null;
    const fetcher = jest.fn(async (url: string, init: RequestInit) => {
      const respond = (status: number, body: unknown) => ({ ok: status < 300, status, text: async () => (typeof body === 'string' ? body : JSON.stringify(body)) }) as Response;
      if (failNext) {
        const [status, body] = failNext;
        failNext = null;
        return respond(status, body);
      }
      if ((init.headers as Record<string, string>).Authorization !== `Bearer ${valid}`) return respond(401, {});
      const parsed = new URL(url);
      if (parsed.pathname === '/drive/v3/files' && init.method === 'GET') {
        expect(parsed.searchParams.get('spaces')).toBe('appDataFolder');
        return respond(200, { files: [...files.entries()].map(([id, f]) => ({ id, name: f.name, version: String(f.version), size: String(f.body.length) })) });
      }
      if (parsed.searchParams.get('alt') === 'media') return respond(200, files.get(parsed.pathname.split('/').pop() as string)?.body ?? '');
      if (parsed.pathname === '/upload/drive/v3/files' && init.method === 'POST') {
        const body = String(init.body);
        const meta = JSON.parse(body.split('\r\n\r\n')[1].split('\r\n')[0]);
        expect(meta.parents).toEqual(['appDataFolder']);
        const content = body.split('\r\n\r\n')[2].split('\r\n--')[0];
        version += 1;
        const id = `f${files.size + 1}`;
        files.set(id, { name: meta.name, body: content, version });
        return respond(200, { id, version: String(version) });
      }
      if (init.method === 'PATCH') {
        const id = parsed.pathname.split('/').pop() as string;
        version += 1;
        files.set(id, { ...(files.get(id) as { name: string }), body: String(init.body), version });
        return respond(200, { id, version: String(version) });
      }
      throw new Error(`unexpected ${init.method} ${url}`);
    });
    return { files, tokens, fetcher, expire: () => (valid = 'token-2'), fail: (status: number, body: string) => (failNext = [status, body]) };
  }

  test('creates, reads and updates files in the hidden app folder', async () => {
    const fake = fakeDrive();
    const api = new DriveFiles(fake.tokens, fake.fetcher as unknown as typeof fetch);
    const created = await api.write('memorypal-x.json', '{"records":{}}');
    expect((await api.list()).map((file) => file.name)).toEqual(['memorypal-x.json']);
    expect(await api.read(created.id)).toBe('{"records":{}}');
    await api.write('memorypal-x.json', '{"records":{"card:a":["0000000001000:000000:x",null]}}', created.id);
    expect(fake.files.size).toBe(1);
    expect(await api.read(created.id)).toContain('card:a');
  });

  test('an expired token is renewed once; a full drive says so', async () => {
    const fake = fakeDrive();
    const api = new DriveFiles(fake.tokens, fake.fetcher as unknown as typeof fetch);
    await api.list();
    fake.expire();
    await api.list();
    expect(fake.tokens).toHaveBeenCalledWith(true);
    fake.fail(403, '{"error":{"errors":[{"reason":"storageQuotaExceeded"}]}}');
    const full = await api.write('memorypal-x.json', '{}').catch((error) => error);
    expect(full.code).toBe('drive_full');
  });
});
