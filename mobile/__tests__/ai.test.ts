/** AI notes and questions: requests, validation and error messages (network mocked). */
import { AiError, FRIENDLY, fileFromBase64, makeNotes, makeQuestions, MAX_FILE_BYTES, notesText, parseQuestions, questionsToCards } from '../src/cloud/ai';
import { CloudError } from '../src/cloud/client';
import type { Session } from '../src/cloud/client';
import { isAiCard } from '../src/core/questions';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { supabaseUrl: 'https://proj.supabase.co/', supabasePublishableKey: 'sb_publishable_x' } } } }));

function fakeFetch(status: number, body: unknown) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetcher = jest.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const text = typeof body === 'string' ? body : JSON.stringify(body);
    return { ok: status >= 200 && status < 300, status, text: async () => text } as Response;
  });
  return { calls, fetcher: fetcher as unknown as typeof fetch };
}

async function codeOf(promise: Promise<unknown>): Promise<string> {
  try {
    await promise;
  } catch (error) {
    if (error instanceof AiError) return error.code;
    throw error;
  }
  return 'none';
}

describe('AI requests', () => {
  test('notes: request shape and cleaned result', async () => {
    const { calls, fetcher } = fakeFetch(200, {
      ok: true,
      remaining: 19,
      result: { title: ' Cells ', sections: [{ heading: 'Parts', bullets: ['Nucleus', '', 4] }, { heading: '', bullets: [] }], key_terms: [{ term: 'Cell', definition: 'Unit of life' }, { term: 'Lonely' }] },
    });
    const notes = await makeNotes('token-1', { text: ' Cells are small. ', title: 'Bio' }, { fetcher });
    expect(calls[0].url).toBe('https://proj.supabase.co/functions/v1/ai');
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer token-1');
    expect(headers.apikey).toBe('sb_publishable_x');
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ action: 'notes', text: 'Cells are small.', title: 'Bio' });
    expect(notes).toEqual({ title: 'Cells', sections: [{ heading: 'Parts', bullets: ['Nucleus'] }], key_terms: [{ term: 'Cell', definition: 'Unit of life' }], remaining: 19 });
    expect(notesText(notes)).toContain('- Cell :: Unit of life');
  });

  test('questions: file, count and avoid are sent; bad questions are dropped', async () => {
    const { calls, fetcher } = fakeFetch(200, {
      ok: true,
      remaining: 3,
      result: {
        questions: [
          { type: 'short', question: 'What is a cell?', answer: 'Unit of life', page: 2 },
          { type: 'choice', question: 'Powerhouse?', answer: 'Mitochondria', options: ['Nucleus', 'mitochondria', 'Ribosome', 'Golgi', 'Wall'] },
          { type: 'choice', question: 'Too few?', answer: 'A', options: ['B'] },
          { type: 'truefalse', question: 'Cells have walls', answer: 'FALSE' },
          { type: 'cloze', question: 'The nucleus holds DNA', answer: 'DNA' },
          { type: 'essay', question: 'Write', answer: 'No' },
          { type: 'short', question: 'Existing front', answer: 'x' },
        ],
      },
    });
    const session = { accessToken: 'abc' } as Session;
    const result = await makeQuestions(session, { file: fileFromBase64('JVBERi0=', 'lecture.PDF'), count: 50, avoid: ['existing FRONT'] }, { fetcher });
    const sent = JSON.parse(String(calls[0].init.body));
    expect(sent.file).toEqual({ data: 'JVBERi0=', mime_type: 'application/pdf' });
    expect(sent.count).toBe(30);
    expect(result.questions.map((q) => q.type)).toEqual(['short', 'choice', 'truefalse', 'cloze']);
    expect(result.questions[1].options).toEqual(['Mitochondria', 'Nucleus', 'Ribosome', 'Golgi']);
    expect(result.questions[2].answer).toBe('False');
    expect(result.questions[3].question).toBe('The nucleus holds _____');
    expect(result.remaining).toBe(3);

    const made = questionsToCards(result.questions, 'Biology', 'Lecture 1');
    expect(made[0].page).toBe(2);
    expect([made[0].card.front, made[0].card.back, made[0].card.deck]).toEqual(['What is a cell?', 'Unit of life', 'Biology']);
    expect(isAiCard(made[0].card)).toBe(true);
    expect(made[0].card.association).toContain('page 2');
    expect(made[2].card.front).toBe('True or false: Cells have walls');
  });

  test('error codes become friendly messages', async () => {
    const cases: [number, unknown, string][] = [
      [401, { ok: false, error: 'not_signed_in' }, 'not_signed_in'],
      [429, { ok: false, error: 'limit_reached' }, 'limit_reached'],
      [503, { ok: false, error: 'busy' }, 'busy'],
      [413, 'not json', 'file_too_large'],
      [415, { ok: false, error: 'unsupported_file' }, 'unsupported_file'],
      [502, { ok: false, error: 'provider_error' }, 'provider_error'],
      [422, { ok: false, error: 'blocked' }, 'blocked'],
      [500, { error: 'something new' }, 'provider_error'],
      [200, '<html>', 'bad_answer'],
    ];
    for (const [status, body, code] of cases) {
      const { fetcher } = fakeFetch(status, body);
      let error: unknown;
      try {
        await makeNotes('t', { text: 'x' }, { fetcher });
      } catch (caught) {
        error = caught;
      }
      expect([status, (error as AiError).code, (error as AiError).message]).toEqual([status, code, FRIENDLY[code]]);
    }
    const offline = jest.fn(async () => {
      throw new TypeError('Network request failed');
    }) as unknown as typeof fetch;
    expect(await codeOf(makeNotes('t', { text: 'x' }, { fetcher: offline }))).toBe('offline');
  });

  test('checks before sending', async () => {
    const { calls, fetcher } = fakeFetch(200, { ok: true });
    expect(await codeOf(makeNotes('', { text: 'x' }, { fetcher }))).toBe('not_signed_in');
    expect(await codeOf(makeNotes('t', { text: '  ' }, { fetcher }))).toBe('bad_request');
    const signedOut = { activeSession: async () => Promise.reject(new CloudError('Sign in to sync your cards.', 'signed_out')) };
    expect(await codeOf(makeNotes(signedOut, { text: 'x' }, { fetcher }))).toBe('signed_out');
    expect(await codeOf(makeNotes('t', { text: 'x' }, { fetcher, url: '' }))).toBe('not_configured');
    expect(calls).toHaveLength(0);
    expect(() => fileFromBase64('AAAA', 'notes.docx')).toThrow(AiError);
    expect(() => fileFromBase64('A'.repeat(Math.ceil((MAX_FILE_BYTES + 3) / 3) * 4), 'image/png')).toThrow(FRIENDLY.file_too_large);
    expect(fileFromBase64('data:image/heif;base64,AAAA', 'image/heif')).toEqual({ data: 'AAAA', mime_type: 'image/heic' });
  });

  test('parseQuestions tolerates junk', () => {
    expect(parseQuestions(null)).toEqual([]);
    expect(parseQuestions({ questions: 'nope' })).toEqual([]);
    expect(parseQuestions([{ type: 'short', question: 'Q', answer: 'A', page: 0 }])).toEqual([{ type: 'short', question: 'Q', answer: 'A', options: [], page: null }]);
  });
});
