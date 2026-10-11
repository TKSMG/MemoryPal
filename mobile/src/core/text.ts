/** Text parsing, ported from memorypal/core.py. */
import { splitlines, strip } from './py';

export function normalizeSpace(value: string | null | undefined): string {
  return strip((value ?? '').replace(/\s+/g, ' '));
}

// A typed line break: a literal "\n", or "/n" standing on its own (so words
// such as "and/nor" or "salt/nitrogen" are left alone).
const TYPED_NEWLINE = /\\n|(?<![A-Za-z0-9])\/n(?![A-Za-z0-9])/g;
// A list marker at the start of a line: "-", "*", "•", or "1." / "2)" (up to
// three digits, so a year such as "1945 ..." stays part of the text).
const LIST_MARKER = /^\s*(?:[-*•]+|\d{1,3}[.)])\s+/;

export function stripListMarker(line: string): string {
  return strip(line.replace(LIST_MARKER, ''));
}

export function splitStudyBits(raw: string | null | undefined): string[] {
  let text = (raw ?? '').replace(TYPED_NEWLINE, '\n');
  if (/(?:^|\s)1[.)]\s/.test(text) && /\s2[.)]\s/.test(text)) {
    // An inline numbered list ("1. foo 2. bar") becomes one item per line.
    text = text.replace(/\s+(?=\d{1,3}[.)]\s+)/g, '\n');
  }
  text = text.replace(/\s*[|;]\s*/g, '\n');
  const lines = splitlines(text).map(stripListMarker).filter(Boolean);
  if (lines.length >= 2) return lines;
  // Sentence ends only: a full stop followed by a space or the end, so
  // "3.14" and "v2.0" stay whole.
  const sentences = text.split(/[.!?]+(?=\s|$)/).map(strip).filter(Boolean);
  if (sentences.length > 1) return sentences;
  const commaBits = text.split(',').map(strip).filter(Boolean);
  if (commaBits.length > 1) return commaBits;
  return strip(text) ? [strip(text)] : [];
}

export interface PromptAnswer {
  prompt: string;
  answer: string;
}

/** Lines of "question :: answer" (also "=>", " - ", or a tab, as Quizlet exports). */
export function parsePromptAnswerLines(raw: string | null | undefined): PromptAnswer[] {
  const items: PromptAnswer[] = [];
  splitlines((raw ?? '').replace(TYPED_NEWLINE, '\n')).forEach((original, offset) => {
    const index = offset + 1;
    const stripped = strip(original);
    if (stripped.includes('\t')) {
      const tab = stripped.indexOf('\t');
      const prompt = normalizeSpace(stripped.slice(0, tab));
      const answer = normalizeSpace(stripped.slice(tab + 1));
      if (answer) items.push({ prompt: prompt || `Study bit ${index}`, answer });
      return;
    }
    let line = normalizeSpace(original);
    if (!line) return;
    line = stripListMarker(line);
    let prompt = '';
    let answer = line;
    for (const delimiter of ['=>', '::', ' - ']) {
      const at = line.indexOf(delimiter);
      if (at >= 0) {
        prompt = normalizeSpace(line.slice(0, at));
        answer = normalizeSpace(line.slice(at + delimiter.length));
        break;
      }
    }
    if (answer) items.push({ prompt: prompt || `Study bit ${index}`, answer });
  });
  return items;
}

export const STOP_WORDS = new Set([
  'the', 'and', 'for', 'with', 'into', 'that', 'this', 'what', 'should',
  'remember', 'image', 'audio', 'video', 'cue', 'about', 'from', 'your',
  'their', 'there', 'then', 'than', 'when', 'where', 'which', 'while',
  'because', 'have', 'has', 'had', 'are', 'was', 'were', 'will', 'would',
  'could', 'also', 'just', 'like', 'make', 'made',
]);

export function textTokens(value: string | null | undefined): string[] {
  return tokenWords(value).map(([stem]) => stem);
}

/**
 * [stem, word as written in lower case] for each scorable word. Scoring
 * compares stems ("increas"); hints shown to people use the real word.
 */
export function tokenWords(value: string | null | undefined): [string, string][] {
  const tokens: [string, string][] = [];
  for (const match of (value ?? '').matchAll(/[A-Za-z0-9][A-Za-z0-9'-]{2,}/g)) {
    const word = match[0].toLowerCase();
    let token = word;
    if (STOP_WORDS.has(token)) continue;
    let stemmed = false;
    for (const suffix of ['ingly', 'edly', 'ing', 'ed', 'es']) {
      if (token.endsWith(suffix) && token.length > suffix.length + 3) {
        token = token.slice(0, -suffix.length);
        stemmed = true;
        break;
      }
    }
    if (!stemmed && token.endsWith('s') && !/(ss|us|is)$/.test(token) && token.length > 4) {
      token = token.slice(0, -1);
    }
    tokens.push([token, word]);
  }
  return tokens;
}

/** Lower-case text with punctuation and extra spaces removed. */
export function comparableText(value: string | null | undefined): string {
  return normalizeSpace((value ?? '').toLowerCase().replace(/[^a-z0-9\s]/g, ' '));
}

/** Counter(...).most_common(n): by count, ties in first-seen order. */
export function mostCommon(tokens: string[], count?: number): [string, number][] {
  const counts = new Map<string, number>();
  for (const token of tokens) counts.set(token, (counts.get(token) ?? 0) + 1);
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return count === undefined ? ranked : ranked.slice(0, count);
}

export function hangmanHint(text: string | null | undefined): string {
  return (text ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => (word.length <= 1 || !/^[\p{L}\p{N}]/u.test(word) ? word : word[0] + word.slice(1).replace(/[A-Za-z0-9]/g, '_')))
    .join(' ');
}

export function salientKeywords(text: string, count = 5): string[] {
  return mostCommon(textTokens(text), count).map(([word]) => word.charAt(0).toUpperCase() + word.slice(1));
}
