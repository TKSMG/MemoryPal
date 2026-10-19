/** Phone AI helpers (consent gating, error text, labels, rows) and quiz screen helpers. */
import { AiError } from '../src/cloud/ai';
import type { AiQuestion } from '../src/cloud/ai';
import { newCard } from '../src/core/models';
import { BLANK, Question } from '../src/core/questions';
import { AI_TAG, aiErrorText, aiGate, aiLabel, aiPage, canSendAi, isOnline, needsAccount, remainingText, reportMailto, rowsFromAiQuestions } from '../src/features/aiHelpers';
import { makeRound, matchBoard, matchDone, nextRecent, promptParts, promptSpeech, RECENT_KEEP, tapMatch } from '../src/features/quizPlay';
import { talkCards } from '../src/features/talkback';

jest.mock('expo-constants', () => ({ __esModule: true, default: { expoConfig: { extra: { supabaseUrl: 'https://proj.supabase.co/', supabasePublishableKey: 'sb_publishable_x' } } } }));

const ready = { allowed: true, signedIn: true, online: true, configured: true };

describe('AI consent gating', () => {
  test('nothing is sent before consent, whatever else is true', () => {
    expect(aiGate({ ...ready, allowed: false })).toBe('consent');
    expect(aiGate({ allowed: false, signedIn: false, online: false, configured: false })).toBe('consent');
    expect(canSendAi({ ...ready, allowed: false })).toBe(false);
  });

  test('then sign-in, then internet', () => {
    expect(aiGate({ ...ready, signedIn: false })).toBe('sign_in');
    expect(aiGate({ ...ready, signedIn: false, online: false })).toBe('sign_in');
    expect(aiGate({ ...ready, online: false })).toBe('offline');
    expect(aiGate({ ...ready, configured: false })).toBe('not_configured');
    expect(aiGate(ready)).toBe('ready');
    expect(canSendAi(ready)).toBe(true);
  });

  test('unknown network state counts as online', () => {
    expect(isOnline(null)).toBe(true);
    expect(isOnline({ isConnected: true, isInternetReachable: null })).toBe(true);
    expect(isOnline({ isConnected: false })).toBe(false);
    expect(isOnline({ isConnected: true, isInternetReachable: false })).toBe(false);
  });
});

describe('AI error text', () => {
  test('every server code has a friendly sentence', () => {
    for (const code of ['not_signed_in', 'second_step', 'limit_reached', 'file_too_large', 'unsupported_file', 'bad_request', 'blocked', 'busy', 'provider_error', 'not_configured', 'offline', 'bad_answer']) {
      const text = aiErrorText(new AiError(code));
      expect(text.length).toBeGreaterThan(10);
      expect(text).not.toMatch(/_/);
    }
    expect(aiErrorText(new AiError('offline'))).toMatch(/Needs internet/);
    expect(aiErrorText(new AiError('limit_reached'))).toMatch(/tomorrow/);
  });

  test('unknown errors stay calm, and sign-in problems offer the account screen', () => {
    expect(aiErrorText(new Error('boom'))).toMatch(/Try again/);
    expect(aiErrorText(new AiError('weird_code'))).toMatch(/problem|Try/);
    expect(needsAccount(new AiError('not_signed_in'))).toBe(true);
    expect(needsAccount(new AiError('second_step'))).toBe(true);
    expect(needsAccount(new AiError('busy'))).toBe(false);
    expect(needsAccount(new Error('x'))).toBe(false);
  });

  test('uses left today', () => {
    expect(remainingText(12)).toBe('12 AI uses left today');
    expect(remainingText(1)).toBe('1 AI use left today');
    expect(remainingText(0)).toMatch(/No AI uses left today/);
    expect(remainingText(null)).toBe('');
    expect(remainingText(undefined)).toBe('');
  });
});

describe('AI card labels and rows', () => {
  const questions: AiQuestion[] = [
    { type: 'short', question: 'What pumps blood?', answer: 'The heart', options: [], page: 3 },
    { type: 'truefalse', question: 'Veins carry blood to the heart.', answer: 'True', options: ['True', 'False'], page: null },
  ];

  test('AI cards carry the tag; the person’s own cards do not', () => {
    expect(aiLabel(newCard({ pathway: 'Made with AI > Biology' }))).toBe(AI_TAG);
    expect(aiLabel(newCard({ pathway: 'Capture > Biology' }))).toBe('');
    expect(aiLabel(null)).toBe('');
  });

  test('rows keep the AI marking and attach the source', () => {
    const fromPdf = rowsFromAiQuestions(questions, 'Biology', 'Heart', { kind: 'pdf', uri: 'file:///doc/a.pdf' });
    expect(fromPdf[0]).toMatchObject({ front: 'What pumps blood?', back: 'The heart', pathway: 'Made with AI > Heart', text_file: 'file:///doc/a.pdf', image: '' });
    expect(aiPage({ association: fromPdf[0].note ?? '' })).toBe(3);
    expect(fromPdf[1].front).toBe('True or false: Veins carry blood to the heart.');
    expect(fromPdf[1].text_file).toBe(''); // no page, nothing to point at
    const fromPhoto = rowsFromAiQuestions(questions, 'Biology', 'Heart', { kind: 'image', uri: 'file:///doc/p.jpg' });
    expect(fromPhoto.every((row) => row.image === 'file:///doc/p.jpg')).toBe(true);
    const fromText = rowsFromAiQuestions(questions, 'Biology', 'Heart', null);
    expect(fromText.every((row) => !row.image && !row.text_file && row.note?.startsWith('Made with AI, check it.'))).toBe(true);
  });

  test('report opens an email with the content', () => {
    const url = reportMailto('card', 'Question: What pumps blood?');
    expect(url.startsWith('mailto:memorypal09@gmail.com?subject=')).toBe(true);
    expect(decodeURIComponent(url)).toContain('Question: What pumps blood?');
    expect(decodeURIComponent(reportMailto('notes', 'x'.repeat(5000))).length).toBeLessThan(1800);
  });
});

describe('quiz screen helpers', () => {
  const cards = [
    newCard({ id: 'a', deck: 'Capitals', front: 'Capital of France', back: 'Paris' }),
    newCard({ id: 'b', deck: 'Capitals', front: 'Capital of Spain', back: 'Madrid' }),
    newCard({ id: 'c', deck: 'Capitals', front: 'Capital of Italy', back: 'Rome' }),
    newCard({ id: 'd', deck: 'Capitals', front: 'Capital of Peru', back: 'Lima' }),
    newCard({ id: 'e', deck: 'Other', front: 'No answer', back: '' }),
  ];

  test('a round uses answered cards of the set only and avoids the last round', () => {
    const round = makeRound(cards, 'Capitals', [], 7);
    expect(round.length).toBe(4);
    expect(round.every((q) => q.deck === 'Capitals')).toBe(true);
    const recent = nextRecent([], round);
    const next = makeRound(cards, 'Capitals', recent, 8);
    // Same cards (there are only four), but not the same question for each.
    expect(next.filter((q) => recent.includes(q.id)).length).toBeLessThan(next.length);
    expect(nextRecent(Array.from({ length: 100 }, (_, i) => `x:${i}`), round).length).toBe(RECENT_KEEP);
  });

  test('blank shown as a gap and read as "blank"', () => {
    const q = { prompt: `Fill in the blank: The ${BLANK} pumps blood.` } as Question;
    expect(promptParts(q.prompt)).toEqual({ before: 'Fill in the blank: The ', after: ' pumps blood.', blank: true });
    expect(promptSpeech(q)).toBe('Fill in the blank: The blank pumps blood.');
    expect(promptParts('No gap').blank).toBe(false);
  });

  test('match board: tap to pair, wrong tries counted', () => {
    const q = { type: 'match', pairs: [['France', 'Paris'], ['Spain', 'Madrid'], ['Italy', 'Rome']], options: ['Rome', 'Paris', 'Madrid'] } as unknown as Question;
    let board = matchBoard(q);
    board = tapMatch(board, q, 'left', 0); // France
    board = tapMatch(board, q, 'right', 0); // Rome: wrong
    expect(board.mistakes).toBe(1);
    expect(board.wrong).toEqual({ left: 0, right: 0 });
    board = tapMatch(board, q, 'right', 1); // Paris first, then France
    board = tapMatch(board, q, 'left', 0);
    expect(board.matched).toEqual({ 0: 1 });
    expect(tapMatch(board, q, 'left', 0)).toBe(board); // a made pair can't be tapped again
    board = tapMatch(tapMatch(board, q, 'left', 1), q, 'right', 2);
    board = tapMatch(tapMatch(board, q, 'left', 2), q, 'right', 0);
    expect(matchDone(board)).toBe(true);
    expect(board.mistakes).toBe(1);
  });

  test('talk-back questions keep the card id and have no underscores', () => {
    const talk = talkCards([...cards.slice(0, 4), newCard({ id: 'f', front: 'Photosynthesis', back: 'Plants turn sunlight water and carbon dioxide into sugar and oxygen' })], 3);
    expect(talk.map((t) => t.id).sort()).toEqual(['a', 'b', 'c', 'd', 'f']);
    expect(talk.every((t) => !t.front.includes('_') && t.back)).toBe(true);
  });
});
