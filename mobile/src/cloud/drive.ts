/**
 * Syncing through the person's own Google Drive: a port of
 * latest_app/memorypal/drive.py (DriveFiles and sync_files). Each device
 * keeps one file, memorypal-<device id>.json, in the Drive's hidden app
 * folder; core/sync.ts explains how the files are combined.
 */
import { entriesAfter, Entries, entriesOf, fileContent, fileName, FILE_PREFIX, newestStamp, nextStamp, remoteFromFiles, Remote, same, SyncPlan } from '../core/sync';
import { CloudError } from './client';
import { driveError } from './driveErrors';

const FILES_URL = 'https://www.googleapis.com/drive/v3/files';
const UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v3/files';
const TIMEOUT_MS = 30_000;
const MAX_FILE_BYTES = 64 * 1024 * 1024;

export interface DriveFile {
  id: string;
  name: string;
  version: string;
}

/** What sync needs from a drive: Google Drive, or MemoryFiles in tests. */
export interface FileStore {
  list(): Promise<DriveFile[]>;
  read(id: string): Promise<string>;
  write(name: string, body: string, id?: string): Promise<{ id: string; version: string }>;
}

export class DriveFiles implements FileStore {
  constructor(
    private accessToken: (renew?: boolean) => Promise<string>,
    private fetcher: typeof fetch = (...args) => fetch(...args),
  ) {}

  private async request(method: string, url: string, body?: string, contentType?: string, retry = true): Promise<string> {
    const headers: Record<string, string> = { Authorization: `Bearer ${await this.accessToken()}`, Accept: 'application/json' };
    if (contentType) headers['Content-Type'] = contentType;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    let response: Response;
    try {
      response = await this.fetcher(url, { method, headers, body, signal: controller.signal });
    } catch {
      throw driveError('drive_offline');
    } finally {
      clearTimeout(timer);
    }
    if (response.status === 401 && retry) {
      await this.accessToken(true);
      return this.request(method, url, body, contentType, false);
    }
    const text = await response.text();
    if (response.ok) return text;
    if (response.status === 401) throw driveError('drive_signed_out');
    if (response.status === 404) throw new CloudError('That file is no longer in Google Drive.', 'drive_missing');
    if (text.includes('storageQuotaExceeded')) throw driveError('drive_full');
    if (response.status === 403 && text.includes('insufficientPermissions')) throw driveError('drive_scope');
    throw driveError('drive_busy');
  }

  async list(): Promise<DriveFile[]> {
    const files: DriveFile[] = [];
    let page = '';
    for (;;) {
      const query = new URLSearchParams({ spaces: 'appDataFolder', pageSize: '1000', fields: 'nextPageToken,files(id,name,version,size)' });
      if (page) query.set('pageToken', page);
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse((await this.request('GET', `${FILES_URL}?${query}`)) || '{}');
      } catch (error) {
        if (error instanceof CloudError) throw error;
      }
      for (const item of (Array.isArray(data.files) ? data.files : []) as Record<string, unknown>[]) {
        const name = String(item.name ?? '');
        if (name.startsWith(FILE_PREFIX) && Number(item.size ?? 0) <= MAX_FILE_BYTES) {
          files.push({ id: String(item.id), name, version: String(item.version ?? '') });
        }
      }
      page = typeof data.nextPageToken === 'string' ? data.nextPageToken : '';
      if (!page) return files;
    }
  }

  read(id: string): Promise<string> {
    return this.request('GET', `${FILES_URL}/${encodeURIComponent(id)}?alt=media`);
  }

  async write(name: string, body: string, id?: string): Promise<{ id: string; version: string }> {
    let text: string;
    if (id) {
      text = await this.request('PATCH', `${UPLOAD_URL}/${encodeURIComponent(id)}?uploadType=media&fields=id,version`, body, 'application/json');
    } else {
      const boundary = `memorypal${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
      const meta = JSON.stringify({ name, parents: ['appDataFolder'], mimeType: 'application/json' });
      const multipart = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${meta}\r\n--${boundary}\r\nContent-Type: application/json\r\n\r\n${body}\r\n--${boundary}--`;
      text = await this.request('POST', `${UPLOAD_URL}?uploadType=multipart&fields=id,version`, multipart, `multipart/related; boundary=${boundary}`);
    }
    let info: Record<string, unknown> = {};
    try {
      info = JSON.parse(text || '{}');
    } catch {
      info = {};
    }
    return { id: String(info.id ?? id ?? ''), version: String(info.version ?? '') };
  }
}

/** A drive in memory (tests, and two phones sharing one in the interop test). */
export class MemoryFiles implements FileStore {
  files = new Map<string, { name: string; body: string; version: number }>();
  private version = 0;

  async list(): Promise<DriveFile[]> {
    return [...this.files.entries()].filter(([, file]) => file.name.startsWith(FILE_PREFIX)).map(([id, file]) => ({ id, name: file.name, version: String(file.version) }));
  }

  async read(id: string): Promise<string> {
    const file = this.files.get(id);
    if (!file) throw new CloudError('That file is no longer in Google Drive.', 'drive_missing');
    return file.body;
  }

  async write(name: string, body: string, id?: string): Promise<{ id: string; version: string }> {
    if (id && !this.files.has(id)) throw new CloudError('That file is no longer in Google Drive.', 'drive_missing');
    const key = id ?? `f${this.files.size + 1}-${name}`;
    this.version += 1;
    this.files.set(key, { name, body, version: this.version });
    return { id: key, version: String(this.version) };
  }
}

async function readEntries(files: FileStore, id: string): Promise<Entries> {
  let text: string;
  try {
    text = await files.read(id);
  } catch (error) {
    if (error instanceof CloudError && error.code === 'drive_missing') return {}; // removed between listing and reading
    throw error;
  }
  try {
    return entriesOf(JSON.parse(text));
  } catch {
    return {}; // a damaged file is skipped, never read as deletions
  }
}

/** The parts of the sync state that drive sync reads and changes. */
export interface DriveState {
  device_id: string;
  drive_user: string;
  drive_file: string;
  drive_seen: Record<string, string>;
  entries: Entries;
}

/**
 * One full sync through the device files, as drive.sync_files: read the
 * files that changed, merge here (`merge` returns the plan), then write this
 * device's own file when it changed. Returns the new drive state.
 */
export async function syncFiles(
  files: FileStore,
  state: DriveState,
  merge: (remote: Remote) => SyncPlan,
  nowMs = Date.now(),
): Promise<{ state: DriveState; plan: SyncPlan; remote: Remote }> {
  const listing = await files.list();
  const ownName = fileName(state.device_id);
  let ownFile = listing.some((item) => item.id === state.drive_file) ? state.drive_file : '';
  if (!ownFile) ownFile = listing.find((item) => item.name === ownName)?.id ?? '';
  const seen: Record<string, string> = { ...state.drive_seen };
  const all: Entries[] = [state.entries];
  for (const item of listing) {
    if (item.id === ownFile || seen[item.id] === item.version) continue;
    all.push(await readEntries(files, item.id));
    seen[item.id] = item.version;
  }
  const [remote, stamps] = remoteFromFiles(all);
  const plan = merge(remote);
  const stamp = nextStamp(newestStamp(stamps), state.device_id, nowMs);
  const own = entriesAfter(state.entries, plan, remote, stamps, stamp);
  if (!same(own, state.entries) || !ownFile) {
    const body = JSON.stringify(fileContent(state.device_id, own, stamp));
    let written: { id: string; version: string };
    try {
      written = await files.write(ownName, body, ownFile || undefined);
    } catch (error) {
      if (!(error instanceof CloudError) || error.code !== 'drive_missing') throw error;
      written = await files.write(ownName, body); // the file was removed: make it again
    }
    ownFile = written.id;
    seen[ownFile] = written.version;
  }
  const present = new Set([...listing.map((item) => item.id), ownFile]);
  const driveSeen = Object.fromEntries(Object.entries(seen).filter(([id]) => present.has(id)));
  return { state: { ...state, drive_file: ownFile, drive_seen: driveSeen, entries: own }, plan, remote };
}

