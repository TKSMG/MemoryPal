/**
 * @jest-environment node
 *
 * The phone's half of the desktop <-> phone drive sync check. Run by
 * tools/parity/drive_interop.py, which plays the laptop (with the real Python
 * code) before and after this test, using a local folder as the drive.
 * Skipped in a normal `npm test` (no folder).
 */
import { CloudAccount } from '../src/cloud/account';
import { CloudClient, CloudError } from '../src/cloud/client';
import { DriveFile, FileStore } from '../src/cloud/drive';
import { todayIso } from '../src/core/dates';
import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: {} } } }));
jest.mock('../src/cloud/googleAuth', () => ({
  googleConfigured: () => true,
  connectGoogle: async () => ({ user_id: 'google-1', email: 'pat@gmail.com' }),
  disconnectGoogle: async () => undefined,
  googleAccessToken: async () => 'token',
}));
jest.mock('../src/cloud/secrets', () => ({ readSecret: async () => null, writeSecret: async () => undefined }));
jest.mock('../src/state/storage', () => {
  const values = new Map<string, string>();
  return { keyAdapter: (key: string) => ({ load: () => values.get(key) ?? null, save: (text: string) => values.set(key, text) }) };
});

// Node's fs (this test runs in the Node environment).
// eslint-disable-next-line @typescript-eslint/no-require-imports
const fs = require('fs') as { readdirSync(path: string): string[]; readFileSync(path: string, encoding: string): string; writeFileSync(path: string, text: string): void; statSync(path: string): { mtimeMs: number } };

const folder = process.env.MEMORYPAL_DRIVE_FOLDER;
const maybe = folder ? test : test.skip;

/** The same folder the Python FolderFiles uses: the file name is its id. */
class FolderFiles implements FileStore {
  constructor(private dir: string) {}
  async list(): Promise<DriveFile[]> {
    return fs.readdirSync(this.dir).filter((name) => name.startsWith('memorypal-')).map((name) => ({ id: name, name, version: String(fs.statSync(`${this.dir}/${name}`).mtimeMs) }));
  }
  async read(id: string): Promise<string> {
    try {
      return fs.readFileSync(`${this.dir}/${id}`, 'utf-8');
    } catch {
      throw new CloudError('gone', 'drive_missing');
    }
  }
  async write(name: string, body: string, id?: string) {
    fs.writeFileSync(`${this.dir}/${id ?? name}`, body);
    return { id: id ?? name, version: String(fs.statSync(`${this.dir}/${id ?? name}`).mtimeMs) };
  }
}

maybe('the phone syncs with the laptop through the drive folder', async () => {
  const account = new CloudAccount({} as CloudClient, () => new FolderFiles(folder as string));
  await account.connectDrive();
  const store = new MemoryStore(new MemoryAdapter());
  store.finishOnboarding('student');
  await account.sync(store);

  const fromLaptop = store.findCard('from-laptop');
  expect(fromLaptop?.back).toBe('Paris');
  expect(store.cards.filter((card) => card.id.startsWith('sample-')).length).toBe(4);
  expect(store.activity[todayIso()]).toBe(2);
  expect(store.dailyGoal).toBe(25);

  store.addCard(newCard({ id: 'from-phone', deck: 'Spanish', front: 'Hola?', back: 'Hello' }));
  store.schedule(fromLaptop!, 4);
  store.schedule(store.findCard('from-laptop')!, 4);
  store.replaceWith({ ...store.payload(), cards: store.cards.filter((card) => card.id !== 'sample-chunking') });
  await account.sync(store);
});
