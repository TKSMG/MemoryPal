/**
 * AI study notes and questions through the MemoryPal cloud (port of
 * latest_app/memorypal/ai.py). The app never holds an AI key: it calls the
 * Supabase Edge Function "ai" (supabase/functions/ai) with the signed-in
 * person's access token, and the function calls Google Gemini.
 *
 *   const notes = await makeNotes(account, { text, file: fileFromBase64(base64, 'application/pdf') });
 *   const { questions } = await makeQuestions(account, { text: notesText(notes), count: 10, avoid: cards.map((c) => c.front) });
 *   const made = questionsToCards(questions, 'Biology'); // [{ card, page }]
 */
import type { Card } from '../core/models';
import { newCard } from '../core/models';
import { AI_NOTE, AI_PATHWAY } from '../core/questions';
import { cloudConfig, CloudError } from './client';
import type { Session } from './client';

export const MAX_FILE_BYTES = 8 * 1024 * 1024;
export const MAX_QUESTIONS = 30;
export const MAX_STYLE_CHARS = 500;
export const MAX_EXAMPLES = 20;
const MAX_QUESTION_CHARS = 600;
const MAX_CONTEXT_CHARS = 240;
const TIMEOUT_MS = 120000; // a PDF can take Gemini a while
export const QUESTION_TYPES = ['short', 'choice', 'truefalse', 'cloze'] as const;
export type AiQuestionType = (typeof QUESTION_TYPES)[number];

export const MIME_BY_EXTENSION: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  heic: 'image/heic',
  heif: 'image/heic',
};
const MIME_TYPES = new Set(Object.values(MIME_BY_EXTENSION));

export const FRIENDLY: Record<string, string> = {
  not_signed_in: 'Sign in to your MemoryPal account to use AI notes.',
  signed_out: 'Sign in to your MemoryPal account to use AI notes.',
  second_step: 'Finish two-step sign-in first: enter the code from your authenticator app.',
  limit_reached: "You've used today's AI requests. They reset tomorrow, and everything else keeps working.",
  file_too_large: 'That file is larger than 8 MB. Try a smaller file, or a few pages at a time.',
  unsupported_file: 'AI notes can read PDFs and PNG, JPEG, WEBP or HEIC pictures.',
  bad_request: 'Add some notes or choose a file first.',
  blocked: "This material can't be used for AI study notes.",
  busy: 'The AI is busy right now. Wait a minute and try again.',
  busy_today: 'The AI has had a lot of requests today and is paused until tomorrow. Everything else keeps working.',
  provider_error: 'The AI service had a problem. Try again later.',
  not_configured: "AI notes aren't set up for this copy of MemoryPal yet.",
  offline: "Couldn't reach the MemoryPal cloud. Check the internet connection and try again.",
  bad_answer: "The AI's answer couldn't be read. Try again.",
};

export class AiError extends Error {
  constructor(public code: string, message?: string) {
    super(message ?? FRIENDLY[code] ?? FRIENDLY.provider_error);
  }
}

export interface AiFile {
  data: string; // base64
  mime_type: string;
}

export interface AiNotes {
  title: string;
  sections: { heading: string; bullets: string[] }[];
  key_terms: { term: string; definition: string }[];
}

export interface AiQuestion {
  type: AiQuestionType;
  question: string;
  answer: string;
  /** For choice: the answer first, then 3 wrong options (shuffle before showing). */
  options: string[];
  /** The sentence from the material the answer comes from, or ''. */
  context: string;
  /** The PDF page it came from, or null. */
  page: number | null;
}

/** An access token, a Session, or the CloudAccount (which refreshes the sign-in). */
export type AiAuth = string | Session | { activeSession(): Promise<Session> };

export interface AiOptions {
  fetcher?: typeof fetch;
  url?: string;
  key?: string;
  timeoutMs?: number;
}

/** Bytes a base64 string decodes to (without decoding it). */
export function base64Bytes(data: string): number {
  const clean = data.replace(/\s+/g, '');
  const padding = clean.endsWith('==') ? 2 : clean.endsWith('=') ? 1 : 0;
  return Math.floor((clean.length * 3) / 4) - padding;
}

/**
 * Check a picked file before sending it: `type` is a MIME type or a file
 * name ("lecture.pdf"). Throws AiError unsupported_file / file_too_large.
 */
export function fileFromBase64(data: string, type: string): AiFile {
  const lower = (type ?? '').toLowerCase().trim();
  const mime = MIME_TYPES.has(lower) ? lower : lower === 'image/heif' ? 'image/heic' : MIME_BY_EXTENSION[lower.split('.').pop() ?? ''] ?? '';
  if (!mime) throw new AiError('unsupported_file');
  const clean = (data ?? '').replace(/^data:[^,]*,/, '').replace(/\s+/g, '');
  if (!clean) throw new AiError('bad_request', "That file couldn't be opened.");
  if (base64Bytes(clean) > MAX_FILE_BYTES) throw new AiError('file_too_large');
  return { data: clean, mime_type: mime };
}

async function accessToken(auth: AiAuth): Promise<string> {
  let token = '';
  if (typeof auth === 'string') token = auth;
  else if (auth && 'accessToken' in auth) token = auth.accessToken;
  else if (auth && 'activeSession' in auth) {
    try {
      token = (await auth.activeSession()).accessToken;
    } catch (error) {
      if (error instanceof CloudError) throw new AiError(FRIENDLY[error.code] ? error.code : 'not_signed_in', error.message);
      throw error;
    }
  }
  if (!token) throw new AiError('not_signed_in');
  return token;
}

export function errorFrom(status: number, detail: unknown): AiError {
  const code = detail && typeof detail === 'object' ? String((detail as Record<string, unknown>).error ?? '') : '';
  if (FRIENDLY[code]) return new AiError(code);
  if (status === 401) return new AiError('not_signed_in');
  if (status === 413) return new AiError('file_too_large');
  if (status === 429) return new AiError('limit_reached');
  if (status === 404) return new AiError('not_configured');
  return new AiError('provider_error');
}

/** POST to the "ai" function; its decoded JSON, or AiError. */
export async function callAi(auth: AiAuth, body: Record<string, unknown>, options: AiOptions = {}): Promise<Record<string, unknown>> {
  const config = cloudConfig();
  const url = (options.url ?? config.url).replace(/\/+$/, '');
  const key = options.key ?? config.key;
  if (!url || !key) throw new AiError('not_configured');
  const token = await accessToken(auth);
  const fetcher = options.fetcher ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetcher(`${url}/functions/v1/ai`, {
      method: 'POST',
      headers: { apikey: key, Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch {
    throw new AiError('offline');
  } finally {
    clearTimeout(timer);
  }
  const text = await response.text().catch(() => '');
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!response.ok) throw errorFrom(response.status, data);
  if (!data || typeof data !== 'object') throw new AiError('bad_answer');
  if ((data as Record<string, unknown>).ok !== true) throw errorFrom(response.status, data);
  return data as Record<string, unknown>;
}

// --------------------------------------------------------------- validation
const clip = (value: unknown, max: number) => (typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, max) : '');
const asList = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const asObject = (value: unknown): Record<string, unknown> => (value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {});

export function parseNotes(raw: unknown): AiNotes {
  const data = asObject(raw);
  const sections = asList(data.sections)
    .map((section) => {
      const s = asObject(section);
      return { heading: clip(s.heading, 120), bullets: asList(s.bullets).map((b) => clip(b, 300)).filter(Boolean).slice(0, 12) };
    })
    .filter((section) => section.heading || section.bullets.length)
    .slice(0, 12);
  const keyTerms = asList(data.key_terms)
    .map((item) => {
      const t = asObject(item);
      return { term: clip(t.term, 80), definition: clip(t.definition, 300) };
    })
    .filter((item) => item.term && item.definition)
    .slice(0, 30);
  return { title: clip(data.title, 120) || 'Study notes', sections, key_terms: keyTerms };
}

const questionKey = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

export function parseQuestions(raw: unknown, count = MAX_QUESTIONS, avoid: string[] = []): AiQuestion[] {
  const items = Array.isArray(raw) ? raw : asList(asObject(raw).questions);
  const seen = new Set(avoid.map((text) => questionKey(String(text))));
  const out: AiQuestion[] = [];
  for (const entry of items) {
    if (out.length >= Math.min(count, MAX_QUESTIONS)) break;
    const item = asObject(entry);
    const type = String(item.type ?? '').toLowerCase() as AiQuestionType;
    let question = clip(item.question, MAX_QUESTION_CHARS);
    let answer = clip(item.answer, 300);
    if (!QUESTION_TYPES.includes(type) || !question || !answer) continue;
    let options: string[] = [];
    if (type === 'choice') {
      const keys = new Set([questionKey(answer)]);
      const wrong: string[] = [];
      for (const option of asList(item.options)) {
        const text = clip(option, 200);
        if (text && !keys.has(questionKey(text))) {
          keys.add(questionKey(text));
          wrong.push(text);
        }
      }
      if (wrong.length < 3) continue;
      options = [answer, ...wrong.slice(0, 3)];
    } else if (type === 'truefalse') {
      const verdict = answer.toLowerCase().replace(/[^a-z]/g, '');
      if (verdict !== 'true' && verdict !== 'false') continue;
      answer = verdict === 'true' ? 'True' : 'False';
      options = ['True', 'False'];
    } else if (type === 'cloze') {
      question = question.replace(/_{3,}/g, '_____');
      if (!question.includes('_____')) {
        const at = question.toLowerCase().indexOf(answer.toLowerCase());
        if (at < 0) continue;
        question = question.slice(0, at) + '_____' + question.slice(at + answer.length);
      }
    }
    const key = questionKey(question);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const page = typeof item.page === 'number' && Number.isFinite(item.page) && item.page >= 1 && item.page <= 10000 ? Math.trunc(item.page) : null;
    out.push({ type, question, answer, options, context: clip(item.context, MAX_CONTEXT_CHARS), page });
  }
  return out;
}

// ---------------------------------------------------------------- the calls
export interface AiInput {
  text?: string;
  file?: AiFile | null;
  title?: string;
  /** How the learner wants it laid out, in their words ("one line per date"); empty for the usual. */
  style?: string;
  /** Questions the learner's teacher has asked before: one per line, or a list. Questions only. */
  examples?: string | string[];
}

/** Teacher's past questions, cleaned (bullets stripped, clipped) and capped. */
export function exampleLines(examples: string | string[] | undefined): string[] {
  const items = typeof examples === 'string' ? examples.split(/\r?\n/) : (examples ?? []);
  return items
    .map((item) => clip(String(item).replace(/^[-•*\s]+/, ''), 400))
    .filter(Boolean)
    .slice(0, MAX_EXAMPLES);
}

function requestBody(action: 'notes' | 'questions', input: AiInput & { count?: number; avoid?: string[] }): Record<string, unknown> {
  const body: Record<string, unknown> = { action, text: (input.text ?? '').trim() };
  if (input.file) body.file = { data: input.file.data, mime_type: input.file.mime_type };
  if (!body.text && !body.file) throw new AiError('bad_request');
  if (action === 'questions') {
    body.count = Math.max(1, Math.min(MAX_QUESTIONS, Math.trunc(input.count ?? 10) || 10));
    body.avoid = (input.avoid ?? []).map(String).filter((front) => front.trim()).slice(0, 300);
    const examples = exampleLines(input.examples);
    if (examples.length) body.examples = examples;
  }
  if (input.title) body.title = input.title.slice(0, 120);
  const style = clip(input.style, MAX_STYLE_CHARS);
  if (style) body.style = style;
  return body;
}

const remainingOf = (data: Record<string, unknown>) => (typeof data.remaining === 'number' ? data.remaining : null);

/** Study notes from text and/or a file, plus requests left today. */
export async function makeNotes(auth: AiAuth, input: AiInput, options: AiOptions = {}): Promise<AiNotes & { remaining: number | null }> {
  const data = await callAi(auth, requestBody('notes', input), options);
  return { ...parseNotes(data.result), remaining: remainingOf(data) };
}

/** Varied practice questions (none repeating `avoid`), plus requests left today. */
export async function makeQuestions(
  auth: AiAuth,
  input: AiInput & { count?: number; avoid?: string[] },
  options: AiOptions = {},
): Promise<{ questions: AiQuestion[]; remaining: number | null }> {
  const data = await callAi(auth, requestBody('questions', input), options);
  return { questions: parseQuestions(data.result, input.count ?? 10, input.avoid ?? []), remaining: remainingOf(data) };
}

// -------------------------------------------------------------- conversions
/** Notes as plain text, for a capture's notes or as input to makeQuestions. */
export function notesText(notes: AiNotes): string {
  const lines = [notes.title];
  for (const section of notes.sections) {
    lines.push('');
    if (section.heading) lines.push(section.heading);
    lines.push(...section.bullets.map((bullet) => `- ${bullet}`));
  }
  if (notes.key_terms.length) {
    lines.push('', 'Key terms', ...notes.key_terms.map((item) => `- ${item.term} :: ${item.definition}`));
  }
  return lines.join('\n').trim();
}

export function questionCardFields(question: AiQuestion): [front: string, back: string] {
  if (question.type === 'truefalse') return [`True or false: ${question.question}`, question.answer];
  // Multiple-choice options aren't stored: the quiz makes its own from the deck.
  return [question.question, question.answer];
}

/**
 * Cards from AI questions, marked as AI-made (pathway "Made with AI > ...",
 * association asks the person to check it; no new card field, so sync is
 * unchanged). When `page` is set, attach that PDF page's image to the card.
 */
export function questionsToCards(questions: AiQuestion[], deck: string, title = ''): { card: Card; page: number | null }[] {
  return questions.map((question) => {
    const [front, back] = questionCardFields(question);
    const association = cardNote(question);
    return { card: newCard({ deck: deck || 'General', front, back, pathway: `${AI_PATHWAY} > ${title || deck || 'Notes'}`, association }), page: question.page };
  });
}

/** The hook text for an AI card: check it, which page, and the source sentence. */
export function cardNote(question: Pick<AiQuestion, 'page' | 'context'>): string {
  const note = AI_NOTE + (question.page ? ` From page ${question.page}.` : '');
  return question.context ? `${note} Source: "${question.context}"` : note;
}

// ------------------------------------------------------------ live talk-back
export const MAX_LIVE_CARDS = 40;

export interface LiveStart {
  token: string;
  setup: Record<string, unknown>;
  minutes: number;
  remaining: number | null;
}

/**
 * A one-use token for a spoken conversation with the AI tutor about these
 * cards (counts as one AI request). The cards go by short keys, c1, c2...,
 * in the order given; the tutor saves results by those keys.
 */
export async function startLive(auth: AiAuth, cards: { front: string; back: string }[], deck = '', options: AiOptions = {}): Promise<LiveStart> {
  const list = cards.slice(0, MAX_LIVE_CARDS).map((card, i) => ({ key: `c${i + 1}`, front: clip(card.front, 300), back: clip(card.back, 300) }));
  if (!list.length) throw new AiError('bad_request', 'Talk-back needs cards with answers.');
  const data = await callAi(auth, { action: 'live', cards: list, deck: clip(deck, 120) }, { timeoutMs: 30000, ...options });
  const result = asObject(data.result);
  const token = typeof result.token === 'string' ? result.token : '';
  const setup = asObject(result.setup);
  if (!token || !setup.model) throw new AiError('bad_answer');
  const minutes = typeof result.minutes === 'number' && result.minutes > 0 ? Math.min(15, result.minutes) : 10;
  return { token, setup, minutes, remaining: remainingOf(data) };
}
