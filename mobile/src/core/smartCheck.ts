/** Smart Check: score a typed answer against the saved one (port of core.answer_assessment). */
import { pyRound, sequenceRatio } from './py';
import { comparableText, mostCommon, normalizeSpace, textTokens, tokenWords } from './text';

export type Bucket = 'Again' | 'Review' | 'Good' | 'Easy';

export interface Assessment {
  score: number;
  quality: number;
  label: string;
  bucket: Bucket;
  repetitions: number;
  detail: string;
}

const NUMBER_RE = /\d+(?:[.,:]\d+)*/g;
const NEGATIONS = new Set(['not', 'no', 'never', 'none', 'neither', 'nor', 'cannot', "can't", "don't", "doesn't", "isn't", "aren't", "wasn't", "weren't", "won't", 'without']);

function negationCount(tokens: string[]): number {
  return tokens.filter((token) => NEGATIONS.has(token) || token.endsWith("n't")).length;
}

/** Equal, a clear abbreviation ("info"/"information"), or a small typo. Numbers must match exactly. */
export function tokensMatch(expected: string, response: string): boolean {
  if (expected === response) return true;
  if (/\d/.test(expected + response)) return false;
  const [shorter, longer] = response.length < expected.length ? [response, expected] : [expected, response];
  if (shorter.length >= 4 && longer.startsWith(shorter)) return true;
  return shorter.length >= 5 && sequenceRatio(expected, response) >= 0.8;
}

export function answerAssessment(responseRaw: string, expected: string, context = ''): Assessment {
  // Score against the saved answer only; context (the question) is used only
  // when there is no saved answer to compare with.
  const response = normalizeSpace(responseRaw);
  const expectedText = normalizeSpace(expected) || normalizeSpace(context);
  if (!response) {
    return {
      score: 0,
      quality: 1,
      label: 'Needs response',
      bucket: 'Again',
      repetitions: 5,
      detail: 'Type an answer, transcript, caption, or media description first.',
    };
  }

  const responsePlain = comparableText(response);
  const expectedPlain = comparableText(expectedText);
  const expectedTokens = textTokens(expectedText);
  const responseTokens = textTokens(response);
  const expectedCounts = mostCommon(expectedTokens);
  const sequence = expectedPlain ? sequenceRatio(responsePlain, expectedPlain) : 0;

  let score: number;
  let missing: string[] = [];
  if (expectedPlain && responsePlain === expectedPlain) {
    score = 100;
  } else if (!expectedTokens.length) {
    // Very short answers (numbers, initials, "yes") must match closely as a whole.
    score = sequence >= 0.9 ? pyRound(100 * sequence) : pyRound(40 * sequence);
  } else {
    const unmatched = [...responseTokens];
    let hits = 0;
    const matchedWords = new Set<string>();
    for (const word of expectedTokens) {
      const at = unmatched.findIndex((token) => tokensMatch(word, token));
      if (at >= 0) {
        unmatched.splice(at, 1);
        hits += 1;
        matchedWords.add(word);
      }
    }
    const weighted = hits / expectedTokens.length;
    const coverage = matchedWords.size / expectedCounts.length;
    score = expectedCounts.length <= 2
      ? pyRound(100 * (0.5 * sequence + 0.5 * coverage))
      : pyRound(100 * (0.28 * sequence + 0.52 * coverage + 0.2 * weighted));
    score = Math.min(100, score);
    const written = new Map<string, string>();
    for (const [stem, word] of tokenWords(expectedText)) if (!written.has(stem)) written.set(stem, word);
    missing = expectedCounts.slice(0, 6).map(([word]) => word).filter((word) => !matchedWords.has(word)).map((word) => written.get(word) ?? word);
    if (negationCount(expectedTokens) % 2 !== negationCount(responseTokens) % 2) {
      // "reversible" for "not reversible" shares almost every word but means the opposite.
      score = Math.min(score, 41);
      if (!missing.length) missing = ['the answer says the opposite (check for "not")'];
    }
  }
  const given = new Set((response.match(NUMBER_RE) ?? []).map((number) => number.replace(/,/g, '')));
  const wrongNumbers = (expectedText.match(NUMBER_RE) ?? []).filter((number) => !given.has(number.replace(/,/g, '')));
  if (wrongNumbers.length && score < 100) {
    // Dates, amounts and doses are usually the point of the card.
    score = Math.min(score, 41);
    missing = [...wrongNumbers, ...missing.filter((word) => !wrongNumbers.includes(word))];
  }

  let quality: number, label: string, repetitions: number, bucket: Bucket;
  if (score >= 82) [quality, label, repetitions, bucket] = [5, 'Strong match', 1, 'Easy'];
  else if (score >= 64) [quality, label, repetitions, bucket] = [4, 'Close enough', 2, 'Good'];
  else if (score >= 42) [quality, label, repetitions, bucket] = [3, 'Partial match', 3, 'Review'];
  else if (score >= 24) [quality, label, repetitions, bucket] = [2, 'Weak match', 4, 'Again'];
  else [quality, label, repetitions, bucket] = [1, 'Missed context', 5, 'Again'];

  const detail = missing.length ? 'Missing key cues: ' + missing.slice(0, 4).join(', ') : 'Main cues are covered.';
  return { score, quality, label, bucket, repetitions, detail };
}

/** Plain-language result, the desktop's "simple language" wording. */
export function describeSimply(result: Assessment): string {
  const message = {
    Easy: 'Well done — you remembered it.',
    Good: 'Nearly all there.',
    Review: 'You remembered part of it.',
    Again: "Not quite yet — that's okay, it will come back soon.",
  }[result.bucket];
  if (result.detail.startsWith('Missing key cues:')) {
    return `${message} Words that would help: ${result.detail.split(':').slice(1).join(':').trim()}.`;
  }
  return message;
}
