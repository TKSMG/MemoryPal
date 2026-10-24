/**
 * Data shapes shared with the desktop app. Field names are the desktop's
 * snake_case JSON names, so a desktop backup opens on the phone and back,
 * and the same records can later be synced.
 */
import { nowLabel, todayIso } from './dates';
import { splitStudyBits } from './text';

export interface Card {
  id: string;
  deck: string;
  front: string;
  back: string;
  pathway: string;
  association: string;
  text_file: string;
  image: string;
  audio: string;
  video: string;
  next_review: string;
  interval: number;
  repetitions: number;
  ease: number;
  lapses: number;
  last_score: number;
  last_result: string;
  created_at: string;
  buried_until: string;
}

export interface Capture {
  id: string;
  title: string;
  notes: string;
  chunks: string[];
  text_file: string;
  image: string;
  audio: string;
  video: string;
  created_at: string;
  /** The set these notes belong to ('' for none). */
  deck: string;
}

/**
 * What a set knows about itself: cards name their set, this holds the rest.
 * `id` is the set's name, so two devices describing one set share a record.
 * A set with no details has no DeckInfo at all.
 */
export interface DeckInfo {
  id: string;
  /** YYYY-MM-DD, or ''. */
  exam_date: string;
  /** A line about the set, shown on its page. */
  about: string;
  /** "How should it look?" for Make with AI. */
  ai_style: string;
  /** Questions the teacher has asked, one per line. */
  ai_examples: string;
}

export const DECK_INFO_FIELDS = ['exam_date', 'about', 'ai_style', 'ai_examples'] as const;
export type DeckInfoField = (typeof DECK_INFO_FIELDS)[number];
export const MAX_DECK_NAME = 120;
const MAX_ABOUT = 1000;
const MAX_AI_STYLE = 500;
const MAX_AI_EXAMPLES = 8000;

/** A set name as stored: single spaces, at most MAX_DECK_NAME characters. */
export function deckName(value: unknown): string {
  return String(value ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, MAX_DECK_NAME);
}

/** value if it is a real YYYY-MM-DD date, else ''. */
export function isoDay(value: unknown): string {
  const text = String(value ?? '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (!match) return '';
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const date = new Date(Date.UTC(year, month - 1, day));
  return year >= 1 && date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day ? text : '';
}

export function deckInfoFromDict(raw: Raw): DeckInfo {
  const name = deckName(firstText(raw, ['id', 'name'], ''));
  if (!name) throw new Error('a set needs a name');
  const text = (field: string, limit: number) => String(raw[field] || '').trim().slice(0, limit);
  return {
    id: name,
    exam_date: isoDay(raw.exam_date),
    about: text('about', MAX_ABOUT),
    ai_style: text('ai_style', MAX_AI_STYLE),
    ai_examples: text('ai_examples', MAX_AI_EXAMPLES),
  };
}

export function deckInfoEmpty(info: DeckInfo): boolean {
  return !DECK_INFO_FIELDS.some((name) => info[name]);
}

export interface FeedbackEntry {
  id: string;
  rating: number;
  category: string;
  page: string;
  note: string;
  created_at: string;
  sent_at: string;
}

export function uid(): string {
  const cryptoApi = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const random = (Math.random() * 16) | 0;
    return (char === 'x' ? random : (random & 0x3) | 0x8).toString(16);
  });
}

export function newCard(fields: Partial<Card> = {}): Card {
  return {
    id: uid(),
    deck: 'General',
    front: '',
    back: '',
    pathway: '',
    association: '',
    text_file: '',
    image: '',
    audio: '',
    video: '',
    next_review: todayIso(),
    interval: 0,
    repetitions: 0,
    ease: 2.5,
    lapses: 0,
    last_score: 0,
    last_result: 'New',
    created_at: nowLabel(),
    buried_until: '',
    ...fields,
  };
}

type Raw = Record<string, unknown>;

/** First non-empty value among names (field name, then legacy camelCase aliases). */
function firstText(raw: Raw, names: string[], fallback: string): string {
  for (const name of names) {
    const value = raw[name];
    if (value !== null && value !== undefined && String(value) !== '') return String(value);
  }
  return fallback;
}

const MAX_ID_LENGTH = 150; // the cloud refuses record keys over 200 characters
// A hundred years between reviews, and more reviews than anyone makes of one
// card: anything bigger is damaged (or hostile) synced data.
export const MAX_INTERVAL_DAYS = 36500;
export const MAX_REVIEW_COUNT = 10000;

function recordId(value: string): string {
  return value.length > 0 && value.length <= MAX_ID_LENGTH ? value : uid();
}

function toNumber(value: unknown, integer: boolean, fallback: number): number {
  if (typeof value === 'boolean') return Number(value);
  if (typeof value === 'number' && Number.isFinite(value)) return integer ? Math.trunc(value) : value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = integer ? (/^\s*[-+]?\d+\s*$/.test(value) ? parseInt(value, 10) : NaN) : Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return fallback;
}

/** Same tolerance as the desktop's Card.from_dict: bad fields fall back one by one. */
export function cardFromDict(raw: Raw): Card {
  const defaults = newCard();
  const text = (...names: string[]) => firstText(raw, names, String((defaults as unknown as Raw)[names[0]] ?? ''));
  return {
    id: recordId(text('id')),
    deck: text('deck') || 'General',
    front: text('front'),
    back: text('back'),
    pathway: text('pathway'),
    association: text('association'),
    text_file: text('text_file', 'textFile'),
    image: text('image'),
    audio: text('audio'),
    video: text('video'),
    next_review: text('next_review', 'nextReview'),
    interval: Math.max(0, Math.min(MAX_INTERVAL_DAYS, toNumber(raw.interval, true, 0))),
    repetitions: Math.max(0, Math.min(MAX_REVIEW_COUNT, toNumber(raw.repetitions, true, 0))),
    ease: Math.min(3.5, Math.max(1.3, toNumber(raw.ease, false, 2.5))),
    lapses: Math.max(0, Math.min(MAX_REVIEW_COUNT, toNumber(raw.lapses, true, 0))),
    last_score: Math.max(0, Math.min(100, toNumber(raw.last_score ?? raw.lastScore, true, 0))),
    last_result: text('last_result', 'lastResult'),
    created_at: text('created_at', 'createdAt'),
    buried_until: text('buried_until'),
  };
}

export function captureFromDict(raw: Raw): Capture {
  const text = (name: string, fallback = '') => firstText(raw, [name], fallback);
  const notes = text('notes');
  const chunks = Array.isArray(raw.chunks)
    ? raw.chunks.filter((chunk) => chunk !== null && chunk !== undefined && String(chunk).trim()).map(String)
    : [];
  return {
    id: recordId(text('id', uid())),
    title: text('title') || 'Captured memory material',
    notes,
    chunks: chunks.length ? chunks : splitStudyBits(notes),
    text_file: firstText(raw, ['text_file', 'textFile'], ''),
    image: text('image'),
    audio: text('audio'),
    video: text('video'),
    created_at: firstText(raw, ['created_at', 'createdAt'], nowLabel()),
    deck: deckName(text('deck')),
  };
}

export function feedbackFromDict(raw: Raw): FeedbackEntry {
  const rating = toNumber(raw.rating, true, 0);
  return {
    id: String(raw.id ?? uid()),
    rating: Math.max(0, Math.min(5, rating)),
    category: String(raw.category || 'General'),
    page: String(raw.page || 'Overall app'),
    note: String(raw.note ?? ''),
    created_at: String(raw.created_at ?? raw.createdAt ?? nowLabel()),
    sent_at: String(raw.sent_at || ''),
  };
}

export function sampleCards(): Card[] {
  // Fixed ids: every device starts with the same four cards, so syncing
  // merges them instead of showing each starter card once per device.
  return [
    newCard({
      id: 'sample-spaced-repetition',
      deck: 'Memory Techniques',
      front: 'What is spaced repetition?',
      back: 'Reviewing information at increasing intervals so recall strengthens over time.',
      pathway: 'Dashboard > Review > due cards',
      association: 'The space between reviews grows like stepping stones.',
    }),
    newCard({
      id: 'sample-retrieval-practice',
      deck: 'Memory Techniques',
      front: 'What is retrieval practice?',
      back: 'Trying to recall the answer before rereading or revealing it.',
      pathway: 'Quiz > Self Check',
      association: 'Pull the memory out instead of looking it up first.',
    }),
    newCard({
      id: 'sample-chunking',
      deck: 'Memory Techniques',
      front: 'What is chunking?',
      back: 'Breaking information into smaller meaningful pieces so each part is easier to practise.',
      pathway: 'Capture > study bits',
      association: 'One shelf per idea.',
    }),
    newCard({
      id: 'sample-media-cues',
      deck: 'Memory Techniques',
      front: 'Why use media cues?',
      back: 'Images, audio, video, and text notes can make a memory more familiar and easier to retrieve.',
      pathway: 'Capture > attach cues',
      association: 'A cue gives the memory a handle.',
    }),
  ];
}
