/**
 * Two-way sync of the profile with the person's cloud account: the pure logic.
 * A line-by-line port of latest_app/memorypal/sync.py (checked by the parity
 * tests). See that file for the full explanation; in short:
 * - every synced thing is a record (card:, capture:, deck: (a set's details), settings:profile, and
 *   each device's own review counts, which are added up across devices);
 * - a record changed on one side wins; changed on both sides, it is merged
 *   field by field against the last synced version, and for a card's review
 *   schedule the side with more reviews wins;
 * - deletions travel as tombstones, and an edit beats a delete.
 */

export type Data = Record<string, unknown>;
export type Records = Record<string, Data>;
export type Remote = Record<string, Data | null>;

export const SETTINGS_KEY = 'settings:profile';
export const SETTINGS_FIELDS = ['daily_goal', 'accessibility', 'onboarding', 'study_plan', 'nav_order'] as const;
export const SCHEDULE_FIELDS = ['interval', 'repetitions', 'ease', 'lapses', 'last_score', 'last_result', 'next_review', 'buried_until'];
const COUNT_KINDS = ['activity', 'practiced'];
const KINDS = ['card', 'capture', 'deck', 'settings', ...COUNT_KINDS];

// Records are keyed by text that comes from the cloud, so every map here has
// no prototype and is read with Object.hasOwn: a key like "__proto__" or
// "constructor" is then just an unknown key, never a built-in property.
const has = (record: object, key: string) => Object.hasOwn(record, key);
const emptyMap = <T>(): Record<string, T> => Object.create(null) as Record<string, T>;

/** Deep equality for JSON values (key order doesn't matter), like Python's ==. */
export function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') {
    // Python treats 1 == 1.0 as equal; JSON numbers already are.
    return false;
  }
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) {
    const other = b as unknown[];
    return a.length === other.length && a.every((item, i) => same(item, other[i]));
  }
  const left = a as Data;
  const right = b as Data;
  const keys = Object.keys(left);
  if (keys.length !== Object.keys(right).length) return false;
  return keys.every((key) => has(right, key) && same(left[key], right[key]));
}

const sortKeys = (keys: Iterable<string>) => [...new Set(keys)].sort();

export function kindOf(key: string): string {
  return key.split(':', 1)[0];
}

/**
 * A record key this app understands (`<kind>:...`). Anything else in the cloud
 * is ignored: kept in the base it would be pushed back on every sync and
 * refused by the database, stopping sync.
 */
export function knownKey(key: unknown): boolean {
  return typeof key === 'string' && key.includes(':') && KINDS.includes(kindOf(key));
}

function knownOnly<T>(records: Record<string, T>): Record<string, T> {
  const result = emptyMap<T>();
  for (const key of Object.keys(records)) if (knownKey(key)) result[key] = records[key];
  return result;
}

export function deviceOf(key: string): string {
  return COUNT_KINDS.includes(kindOf(key)) ? key.slice(key.lastIndexOf(':') + 1) : '';
}

const count = (data: unknown) => Math.max(0, Math.trunc(Number((data as Data | null)?.count ?? 0) || 0));

export function otherDeviceCounts(base: Records, deviceId: string): [Record<string, number>, number] {
  const activity = emptyMap<number>();
  let practiced = 0;
  for (const [key, data] of Object.entries(base)) {
    if (!COUNT_KINDS.includes(kindOf(key)) || deviceOf(key) === deviceId || !data || typeof data !== 'object') continue;
    if (kindOf(key) === 'activity') {
      const day = String(data.day ?? '');
      activity[day] = (activity[day] ?? 0) + count(data);
    } else {
      practiced += count(data);
    }
  }
  return [activity, practiced];
}

interface PayloadLike {
  cards?: Data[];
  captures?: Data[];
  decks?: Data[];
  activity?: Record<string, number>;
  practiced?: number;
  [key: string]: unknown;
}

export function recordsFromPayload(payload: PayloadLike, deviceId: string, base: Records): Records {
  const records = emptyMap<Data>();
  for (const card of payload.cards ?? []) records[`card:${card.id}`] = { ...card };
  for (const capture of payload.captures ?? []) records[`capture:${capture.id}`] = { ...capture };
  for (const info of payload.decks ?? []) records[`deck:${info.id}`] = { ...info };
  records[SETTINGS_KEY] = Object.fromEntries(SETTINGS_FIELDS.map((name) => [name, payload[name] ?? null]));
  const [othersActivity, othersPracticed] = otherDeviceCounts(base, deviceId);
  for (const day of Object.keys(payload.activity ?? {}).sort()) {
    const own = Math.trunc(Number(payload.activity?.[day] ?? 0) || 0) - (othersActivity[day] ?? 0);
    if (own > 0) records[`activity:${day}:${deviceId}`] = { day, count: own };
  }
  records[`practiced:${deviceId}`] = { count: Math.max(0, Math.trunc(Number(payload.practiced ?? 0) || 0) - othersPracticed) };
  for (const [key, data] of Object.entries(base)) {
    if (COUNT_KINDS.includes(kindOf(key)) && deviceOf(key) !== deviceId) records[key] = data;
  }
  return records;
}

function newestFirst(keys: string[], records: Records): string[] {
  return [...keys].sort((a, b) => {
    const left = String(records[a].created_at ?? '');
    const right = String(records[b].created_at ?? '');
    return left < right ? 1 : left > right ? -1 : 0;
  });
}

export function payloadFromRecords<T extends PayloadLike>(payload: T, records: Records): T {
  const result: PayloadLike = { ...payload };
  const cardOrder = (payload.cards ?? []).map((card) => `card:${card.id}`);
  const cardKeys = Object.keys(records).filter((key) => kindOf(key) === 'card');
  const fresh = newestFirst(cardKeys.filter((key) => !cardOrder.includes(key)), records);
  result.cards = [...fresh, ...cardOrder.filter((key) => has(records, key))].map((key) => ({ ...records[key] }));
  const captureOrder = (payload.captures ?? []).map((item) => `capture:${item.id}`);
  const captureKeys = Object.keys(records).filter((key) => kindOf(key) === 'capture');
  const freshCaptures = newestFirst(captureKeys.filter((key) => !captureOrder.includes(key)), records);
  result.captures = [...freshCaptures, ...captureOrder.filter((key) => has(records, key))].map((key) => ({ ...records[key] }));
  const deckOrder = (payload.decks ?? []).map((item) => `deck:${item.id}`);
  const deckKeys = Object.keys(records).filter((key) => kindOf(key) === 'deck' && !deckOrder.includes(key)).sort();
  result.decks = [...deckOrder.filter((key) => has(records, key)), ...deckKeys].map((key) => ({ ...records[key] }));
  const settings = (has(records, SETTINGS_KEY) && records[SETTINGS_KEY]) || {};
  for (const name of SETTINGS_FIELDS) {
    if (has(settings, name) && settings[name] !== null && settings[name] !== undefined) result[name] = settings[name];
  }
  const activity = emptyMap<number>();
  let practiced = 0;
  for (const [key, data] of Object.entries(records)) {
    if (kindOf(key) === 'activity') {
      const day = String(data.day ?? '');
      activity[day] = (activity[day] ?? 0) + count(data);
    } else if (kindOf(key) === 'practiced') {
      practiced += count(data);
    }
  }
  result.activity = Object.fromEntries(Object.keys(activity).sort().filter((day) => activity[day] > 0).map((day) => [day, activity[day]]));
  result.practiced = practiced;
  return result as T;
}

function progress(card: Data): [number, string] {
  return [Math.trunc(Number(card.repetitions ?? 0) || 0) + Math.trunc(Number(card.lapses ?? 0) || 0), String(card.next_review ?? '')];
}

function moreProgress(a: Data, b: Data): boolean {
  const [ra, da] = progress(a);
  const [rb, db] = progress(b);
  return ra !== rb ? ra > rb : da > db;
}

function whole(value: unknown): number {
  return Math.trunc(Number(value ?? 0) || 0);
}

/**
 * Whose review schedule to keep when both devices reviewed the same card.
 * A miss on either side wins, so a forgotten card comes back soon rather than
 * being pushed weeks out; otherwise the side with more reviews wins.
 */
function scheduleWinner(base: Data, local: Data, remote: Data): Data {
  const lapsesBefore = whole(base.lapses);
  const localMissed = whole(local.lapses) > lapsesBefore;
  const remoteMissed = whole(remote.lapses) > lapsesBefore;
  if (localMissed !== remoteMissed) return localMissed ? local : remote;
  return moreProgress(local, remote) ? local : remote;
}

function unreviewed(key: string, data: Data | null): boolean {
  return kindOf(key) === 'card' && !!data && whole(data.repetitions) === 0 && whole(data.lapses) === 0;
}

function isRecord(value: unknown): value is Data {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function mergeRecord(key: string, base: Data | null | undefined, local: Data | null | undefined, remote: Data | null | undefined): Data | null {
  if (!local && !remote) return null;
  if (!local) return remote ?? null; // an edit on the other device beats a delete here
  if (!remote) return local;
  const was = base ?? {};
  // A missing field counts as null, as Python's dict.get() gives None.
  const field = (record: Data, name: string) => (has(record, name) ? (record[name] ?? null) : null);
  let winner: Data | null = null;
  if (kindOf(key) === 'card' && SCHEDULE_FIELDS.some((name) => !same(field(local, name), field(remote, name)) && !same(field(local, name), field(was, name)) && !same(field(remote, name), field(was, name)))) {
    winner = scheduleWinner(was, local, remote);
  }
  const merged = emptyMap<unknown>();
  for (const name of sortKeys([...Object.keys(local), ...Object.keys(remote)])) {
    const mine = field(local, name);
    const theirs = field(remote, name);
    const before = field(was, name);
    let value: unknown;
    if (winner && SCHEDULE_FIELDS.includes(name)) value = field(winner, name);
    else if (same(mine, theirs)) value = mine;
    else if (same(mine, before)) value = theirs;
    else if (same(theirs, before)) value = mine;
    else if (key === SETTINGS_KEY && isRecord(mine) && isRecord(theirs)) {
      // Settings groups (accessibility, the study plan) merge one level
      // deeper, so changing text size on one device and motion on another
      // keeps both.
      value = mergeRecord('settings:group', isRecord(before) ? before : {}, mine, theirs);
    } else value = theirs; // both changed the same field: the cloud copy wins
    merged[name] = value === undefined ? null : value;
  }
  return merged;
}

export interface SyncPlan {
  push: Record<string, Data | null>;
  apply: Record<string, Data | null>;
  final: Records;
}

export function planSync(localIn: Records, baseIn: Records, remoteIn: Remote): SyncPlan {
  const [local, base, remote] = [knownOnly(localIn), knownOnly(baseIn), knownOnly(remoteIn)];
  const push = emptyMap<Data | null>();
  const apply = emptyMap<Data | null>();
  const final = emptyMap<Data>();
  for (const key of sortKeys([...Object.keys(local), ...Object.keys(base), ...Object.keys(remote)])) {
    const mine = local[key] ?? null;
    const was = base[key] ?? null;
    const inRemote = has(remote, key);
    const theirs = inRemote ? remote[key] : was;
    let localChanged = !same(mine, was);
    let remoteChanged = inRemote && !same(theirs, was);
    if (inRemote && theirs === null && was === null && unreviewed(key, mine)) {
      // A card deleted elsewhere that this device never synced or reviewed
      // (a starter card on a new install) stays deleted.
      localChanged = false;
      remoteChanged = true;
    }
    let result: Data | null;
    if (remoteChanged && localChanged) result = mergeRecord(key, was, mine, theirs);
    else if (remoteChanged) result = theirs;
    else result = mine;
    if (!same(result, theirs)) push[key] = result;
    if (!same(result, mine)) apply[key] = result;
    if (result !== null) final[key] = result;
  }
  return { push, apply, final };
}

export function applyPlan<T extends PayloadLike>(payload: T, local: Records, plan: SyncPlan): T {
  const records: Records = Object.assign(emptyMap<Data>(), local);
  for (const [key, data] of Object.entries(plan.apply)) {
    if (data === null) delete records[key];
    else records[key] = data;
  }
  return payloadFromRecords(payload, records);
}

// ------------------------------------------------- syncing through a drive
// Port of the drive section of sync.py: every device writes only its own
// file, with a stamp on each record; "remote" is each record's newest copy
// across the files, and deletions stay in the files as tombstones.

export type Entry = [string, Data | null];
export type Entries = Record<string, Entry>;

export const FILE_PREFIX = 'memorypal-';
export const FILE_FORMAT = 1;
const STAMP_DIGITS = [13, 6];

export function fileName(deviceId: string): string {
  return `${FILE_PREFIX}${deviceId}.json`;
}

/** [milliseconds, counter] of a stamp, or null when it isn't one. */
export function stampParts(stamp: unknown): [number, number] | null {
  if (typeof stamp !== 'string') return null;
  const first = stamp.indexOf(':');
  const second = first < 0 ? -1 : stamp.indexOf(':', first + 1);
  if (second < 0) return null;
  const parts = [stamp.slice(0, first), stamp.slice(first + 1, second), stamp.slice(second + 1)];
  if (!parts[2] || !STAMP_DIGITS.every((size, i) => parts[i].length === size && /^\d+$/.test(parts[i]))) return null;
  return [Number(parts[0]), Number(parts[1])];
}

const pad = (value: number, size: number) => String(value).padStart(size, '0');

/** A stamp newer than `newest` (the newest seen anywhere), normally the clock time. */
export function nextStamp(newest: string, deviceId: string, nowMs: number): string {
  const seen = stampParts(newest) ?? [0, 0];
  const now = Math.trunc(nowMs);
  const [ms, count] = now > seen[0] ? [now, 0] : [seen[0], seen[1] + 1];
  return `${pad(ms, STAMP_DIGITS[0])}:${pad(count, STAMP_DIGITS[1])}:${deviceId}`;
}

/** The records a device file holds; anything malformed is skipped. */
export function entriesOf(content: unknown): Entries {
  const entries = emptyMap<Entry>();
  const records = isRecord(content) ? content.records : null;
  if (!isRecord(records)) return entries;
  for (const key of Object.keys(records)) {
    const entry = records[key];
    if (!knownKey(key) || !Array.isArray(entry) || entry.length !== 2) continue;
    const [stamp, data] = entry;
    if (stampParts(stamp) === null || !(data === null || isRecord(data))) continue;
    entries[key] = [stamp as string, data as Data | null];
  }
  return entries;
}

/** Each record's newest copy across the device files (this device's own included). */
export function remoteFromFiles(files: Entries[]): [Remote, Record<string, string>] {
  const remote = emptyMap<Data | null>();
  const stamps = emptyMap<string>();
  for (const entries of files) {
    for (const key of Object.keys(entries)) {
      const [stamp, data] = entries[key];
      if (!has(stamps, key) || stamp > stamps[key]) {
        stamps[key] = stamp;
        remote[key] = data;
      }
    }
  }
  return [remote, stamps];
}

export function newestStamp(stamps: Record<string, string>): string {
  return Object.values(stamps).reduce((newest, stamp) => (stamp > newest ? stamp : newest), '');
}

/** This device's file after a sync: what it sent gets the new stamp, what it took keeps the sender's. */
export function entriesAfter(own: Entries, plan: SyncPlan, remote: Remote, stamps: Record<string, string>, stamp: string): Entries {
  const entries = emptyMap<Entry>();
  for (const key of Object.keys(own)) if (knownKey(key)) entries[key] = [own[key][0], own[key][1]];
  for (const key of Object.keys(remote)) if (!has(plan.push, key)) entries[key] = [stamps[key], remote[key]];
  for (const key of Object.keys(plan.push)) entries[key] = [stamp, plan.push[key]];
  return entries;
}

export function fileContent(deviceId: string, entries: Entries, stamp: string) {
  return { format: FILE_FORMAT, device: deviceId, written: stamp, records: entries };
}
