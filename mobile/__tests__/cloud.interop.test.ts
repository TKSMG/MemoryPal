/**
 * @jest-environment node
 *
 * (Node's real fetch: the React Native test environment stubs out networking.)
 *
 * The phone's half of the desktop <-> phone sync check. Run by
 * tools/parity/sync_interop.py, which starts a local fake Supabase and plays
 * the laptop (with the real Python code) before and after this test.
 * Skipped in a normal `npm test` (no server).
 */
import { CloudClient, needsSecondStep, sessionLevel } from '../src/cloud/client';
import { CloudAccount } from '../src/cloud/account';
import { todayIso } from '../src/core/dates';
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

// Node's Buffer (this test runs in the Node environment).
declare const Buffer: { byteLength(text: string): number; concat(chunks: Uint8Array[]): { toString(encoding: string): string } };
type Buffer = Uint8Array;

const url = process.env.MEMORYPAL_INTEROP_URL;
const step = process.env.MEMORYPAL_INTEROP_STEP;
const maybe = url ? test : test.skip;

/** A minimal fetch over Node's http module (Expo's test preset replaces the global fetch). */
const nodeFetch = ((target: string, init: { method?: string; headers?: Record<string, string>; body?: string } = {}) =>
  new Promise((resolve, reject) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const http = require('node:http');
    const headers = { ...(init.headers ?? {}), ...(init.body ? { 'Content-Length': String(Buffer.byteLength(init.body)) } : {}) };
    const request = http.request(target, { method: init.method ?? 'GET', headers }, (response: { statusCode: number; on: (event: string, fn: (chunk?: Buffer) => void) => void }) => {
      const chunks: Buffer[] = [];
      response.on('data', (chunk) => chunks.push(chunk as Buffer));
      response.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        resolve({ ok: response.statusCode < 400, status: response.statusCode, text: async () => text });
      });
    });
    request.on('error', reject);
    if (init.body) request.write(init.body);
    request.end();
  })) as unknown as typeof fetch;

maybe('phone syncs with the laptop through the same account', async () => {
  const client = new CloudClient(url, 'sb_publishable_test', nodeFetch);
  const account = new CloudAccount(client);
  const store = new MemoryStore(new MemoryAdapter());
  store.finishOnboarding('student');
  await account.remember(await client.signIn('pat@example.com', 'correct horse battery 7'));
  expect(step).toBe('phone');

  // The phone already has some practice of its own before its first sync.
  store.schedule(store.findCard('sample-chunking')!, 4);
  const first = await account.sync(store);
  expect(first.pulled).toBeGreaterThan(0);

  // The laptop's card and its two reviews arrived; the starter cards merged.
  const fromLaptop = store.findCard('from-laptop');
  expect(fromLaptop?.back).toBe('Paris');
  expect(store.cards.filter((card) => card.id.startsWith('sample-')).length).toBe(4);
  expect(store.activity[todayIso()]).toBe(3); // laptop 2 + phone 1
  expect(store.dailyGoal).toBe(25); // a setting changed on the laptop

  // Now the phone adds a card and reviews the laptop's card twice.
  store.addCard(newCard({ id: 'from-phone', deck: 'Spanish', front: 'Hola?', back: 'Hello' }));
  store.schedule(fromLaptop!, 4);
  store.schedule(fromLaptop!, 5);
  const second = await account.sync(store);
  expect(second.pushed).toBeGreaterThan(0);
  expect(store.activity[todayIso()]).toBe(5);

  // Two-step sign-in: turn it on, sign in again, and the code is required.
  const setup = await client.enrollAuthenticator(await account.activeSession());
  expect(setup.secret).toBeTruthy();
  await account.remember(await client.verifyAuthenticator(await account.activeSession(), setup.factorId, '246810'));
  const halfway = await client.signIn('pat@example.com', 'correct horse battery 7');
  expect(needsSecondStep(halfway)).toBe(true);
  const fresh = new CloudAccount(client);
  await expect(fresh.remember(halfway)).rejects.toMatchObject({ code: 'insufficient_aal' });
  await expect(client.pull(halfway, null)).rejects.toMatchObject({ code: '42501' });
  await expect(client.verifyAuthenticator(halfway, halfway.factors[0].id, '000000')).rejects.toMatchObject({ code: 'mfa_verification_failed' });
  const full = await client.verifyAuthenticator(halfway, halfway.factors[0].id, '246810');
  expect(sessionLevel(full)).toBe('aal2');
  await fresh.remember(full);
  expect((await fresh.sync(store)).pulled).toBeGreaterThan(0);

  // Turn it off again so the laptop's next sync (signed in with only a password) still works.
  await client.removeAuthenticator(full, full.factors[0].id);
  expect(await client.factors(full)).toEqual([]);
});
