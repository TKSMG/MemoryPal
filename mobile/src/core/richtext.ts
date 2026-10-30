/**
 * Bold, italics and highlighting in notes, kept as plain text with marks,
 * ported from memorypal/richtext.py (see that file for the rules).
 *
 * **bold**, _italic_ (or *italic*) and ==highlighted== live in the text
 * itself, so notes save, sync and export exactly as before.
 */
import { strip } from './py';

export type Style = 'bold' | 'italic' | 'highlight';
export interface Span {
  text: string;
  bold: boolean;
  italic: boolean;
  highlight: boolean;
}

export const MARKS: Record<Style, string> = { bold: '**', italic: '*', highlight: '==' };
// Longest first, so "**" is read before "*".
const TOKENS: [string, Style][] = [['**', 'bold'], ['==', 'highlight'], ['*', 'italic'], ['_', 'italic']];

const isSpace = (char: string) => /\s/.test(char);
const wordChar = (char: string) => /[\p{L}\p{N}]/u.test(char);

type Piece = [number, number, Style | 'text', string];

/** [pieces, unclosed openers, unopened closers] for one piece of text. */
function scan(value: string | null | undefined): [Piece[], string[], string[]] {
  const text = String(value ?? '');
  const pieces: Piece[] = [];
  const openAt = new Map<Style, [number, string]>();
  const closers: string[] = [];
  let i = 0;
  while (i < text.length) {
    const found = TOKENS.find(([raw]) => text.startsWith(raw, i));
    if (!found) {
      pieces.push([i, i + 1, 'text', text[i]]);
      i += 1;
      continue;
    }
    const [raw, style] = found;
    const end = i + raw.length;
    const before = i ? text[i - 1] : '';
    const after = end < text.length ? text[end] : '';
    const edge = raw !== '**'; // these need a word edge on the outside
    const canOpen = Boolean(after) && !isSpace(after) && !(edge && wordChar(before));
    const canClose = Boolean(before) && !isSpace(before) && !(edge && wordChar(after));
    const opened = openAt.get(style);
    if (canClose && opened && opened[1] === raw) {
      pieces[opened[0]][2] = style;
      openAt.delete(style);
      pieces.push([i, end, style, raw]);
    } else if (canOpen && !opened) {
      openAt.set(style, [pieces.length, raw]);
      pieces.push([i, end, 'text', raw]);
    } else {
      if (canClose) closers.push(raw);
      pieces.push([i, end, 'text', raw]);
    }
    i = end;
  }
  const unclosed = [...openAt.values()].sort((a, b) => a[0] - b[0]).map(([, raw]) => raw);
  return [pieces, unclosed, closers];
}

/** The text as [start, end, kind, raw] pieces, kind "text" or the style a (paired) mark toggles. */
export function tokens(text: string | null | undefined): Piece[] {
  const merged: Piece[] = [];
  for (const [start, end, kind, raw] of scan(text)[0]) {
    const last = merged[merged.length - 1];
    if (kind === 'text' && last && last[2] === 'text') merged[merged.length - 1] = [last[0], end, 'text', last[3] + raw];
    else merged.push([start, end, kind, raw]);
  }
  return merged;
}

/** Runs of text with their styles. */
export function spans(text: string | null | undefined): Span[] {
  const active = { bold: false, italic: false, highlight: false };
  const result: Span[] = [];
  for (const [, , kind, raw] of tokens(text)) {
    if (kind !== 'text') {
      active[kind] = !active[kind];
      continue;
    }
    const last = result[result.length - 1];
    if (last && last.bold === active.bold && last.italic === active.italic && last.highlight === active.highlight) last.text += raw;
    else result.push({ text: raw, ...active });
  }
  return result;
}

/** The words without the marks, for reading aloud, searching and cards. */
export function plain(text: string | null | undefined): string {
  return spans(text).map((span) => span.text).join('');
}

export function hasMarks(text: string | null | undefined): boolean {
  return tokens(text).some(([, , kind]) => kind !== 'text');
}

/** The bold or highlighted words, in order: what the notes say matters most. */
export function marked(text: string | null | undefined): string[] {
  return spans(text).filter((span) => (span.bold || span.highlight) && strip(span.text)).map((span) => strip(span.text));
}

/** [the plain sentence with bold or highlighted words blanked, those words] or null. */
export function blankMarked(text: string | null | undefined, blank = '_____'): [string, string] | null {
  const found = marked(text);
  if (!found.length) return null;
  const out: string[] = [];
  for (const span of spans(text)) {
    if ((span.bold || span.highlight) && strip(span.text)) {
      if (out[out.length - 1] !== blank) out.push(blank);
    } else out.push(span.text);
  }
  return [out.join(''), found.join(', ')];
}

/** Close marks a split cut through, and reopen them in the next bit (only when the next bit closes them). */
export function balanceBits(bits: string[]): string[] {
  const result: string[] = [];
  let carry: string[] = [];
  bits.forEach((original, index) => {
    const bit = carry.join('') + original;
    const unclosed = scan(bit)[1];
    const following = index + 1 < bits.length ? scan(bits[index + 1])[2] : [];
    carry = unclosed.filter((raw) => following.includes(raw));
    result.push(bit + [...carry].reverse().join(''));
  });
  return result;
}

function run(text: string, index: number, step: number): number {
  let count = 0;
  let i = step < 0 ? index - 1 : index;
  while (i >= 0 && i < text.length && text[i] === '*') {
    count += 1;
    i += step;
  }
  return count;
}

function around(text: string, start: number, end: number, style: Style): number {
  if (style === 'highlight') return text.slice(Math.max(0, start - 2), start) === '==' && text.slice(end, end + 2) === '==' ? 2 : 0;
  if (style === 'italic' && start && end < text.length && text[start - 1] === '_' && text[end] === '_') return 1;
  const stars = Math.min(run(text, start, -1), run(text, end, 1));
  if (style === 'bold') return stars >= 2 ? 2 : 0;
  return stars % 2 ? 1 : 0;
}

/**
 * Add or remove a style on text[start:end], like a B or I button. Returns
 * [new text, new start, new end] with the same words selected; with nothing
 * selected it puts an empty pair at the cursor, cursor inside.
 */
export function toggle(value: string | null | undefined, from: number, to: number, style: Style): [string, number, number] {
  const text = String(value ?? '');
  const mark = MARKS[style];
  const clamp = (n: number) => Math.max(0, Math.min(n, text.length));
  let [start, end] = [clamp(from), clamp(to)].sort((a, b) => a - b);
  const chosen = text.slice(start, end);
  let size: number;
  if (style === 'italic' && chosen.length > 2 && chosen[0] === '_' && chosen[chosen.length - 1] === '_') size = 1;
  else if (style === 'highlight') size = chosen.length > 4 && chosen.startsWith('==') && chosen.endsWith('==') ? 2 : 0;
  else {
    const stars = Math.min(chosen.length - chosen.replace(/^\*+/, '').length, chosen.length - chosen.replace(/\*+$/, '').length);
    size = style === 'bold' ? (stars >= 2 ? 2 : 0) : stars % 2 ? 1 : 0;
    if (2 * stars >= chosen.length) size = 0;
  }
  if (size) {
    const inner = chosen.slice(size, -size);
    return [text.slice(0, start) + inner + text.slice(end), start, start + inner.length];
  }
  while (start < end && isSpace(text[start])) start += 1;
  while (end > start && isSpace(text[end - 1])) end -= 1;
  size = around(text, start, end, style);
  if (size && start < end) return [text.slice(0, start - size) + text.slice(start, end) + text.slice(end + size), start - size, end - size];
  size = mark.length;
  if (start === end) return [text.slice(0, start) + mark + mark + text.slice(start), start + size, start + size];
  return [text.slice(0, start) + mark + text.slice(start, end) + mark + text.slice(end), start + size, end + size];
}
