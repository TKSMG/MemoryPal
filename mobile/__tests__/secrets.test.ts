/** A new install never picks up a sign-in an earlier install left in the iOS Keychain. */
const mockKeychain = new Map<string, string>();
const mockKv = new Map<string, string>();

jest.mock('expo-secure-store', () => ({
  getItemAsync: async (key: string) => mockKeychain.get(key) ?? null,
  setItemAsync: async (key: string, value: string) => void mockKeychain.set(key, value),
  deleteItemAsync: async (key: string) => void mockKeychain.delete(key),
}));
jest.mock('../src/state/storage', () => ({
  keyAdapter: (key: string) => ({ load: () => mockKv.get(key) ?? null, save: (text: string) => void mockKv.set(key, text) }),
}));

function launch(): typeof import('../src/cloud/secrets') {
  let secrets!: typeof import('../src/cloud/secrets');
  jest.isolateModules(() => {
    secrets = require('../src/cloud/secrets');
  });
  return secrets;
}

const SIGN_IN = '{"refresh_token":"old"}';

beforeEach(() => {
  mockKeychain.clear();
  mockKv.clear();
});

test('a reinstall (no app data, old Keychain entry) starts signed out', async () => {
  mockKeychain.set('memorypal-account', SIGN_IN);
  mockKeychain.set('memorypal-age-gate', '123');
  const secrets = launch();
  expect(await secrets.readSecret('memorypal-account')).toBeNull();
  expect(await secrets.readSecret('memorypal-age-gate')).toBe('123');
  // Signing in on this install is kept across launches.
  await secrets.writeSecret('memorypal-account', SIGN_IN);
  mockKv.set('memorypal-data', '{}');
  expect(await launch().readSecret('memorypal-account')).toBe(SIGN_IN);
});

test('an update from a version without the marker keeps its sign-in', async () => {
  mockKeychain.set('memorypal-account', SIGN_IN);
  mockKv.set('memorypal-data', '{"cards": []}');
  expect(await launch().readSecret('memorypal-account')).toBe(SIGN_IN);
  expect(await launch().readSecret('memorypal-account')).toBe(SIGN_IN);
});
