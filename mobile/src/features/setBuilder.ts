/**
 * Building a set on the phone: rows of question and answer, filled by typing
 * or by pasting notes or a list. Phone-only helpers; the shared parsing lives
 * in core/text.ts and is used unchanged.
 */
import { BLANK } from '../core/questions';
import { blankMarked, plain } from '../core/richtext';
import { normalizeSpace, parsePromptAnswerLines, splitStudyBits } from '../core/text';

export interface Row {
  key: string;
  front: string;
  back: string;
  hook: string;
  /** Saves to this set instead of the one being built (everyday cards). */
  deck?: string;
  /** AI-made rows: the card's pathway ("Made with AI > …") and note ("Made with AI, check it."). */
  pathway?: string;
  note?: string;
  /** Attachments kept on this phone (a photo, or the PDF a question came from). */
  image?: string;
  text_file?: string;
}

let counter = 0;
export function blankRow(front = '', back = '', hook = ''): Row {
  counter += 1;
  return { key: `row-${Date.now().toString(36)}-${counter}`, front, back, hook };
}

/** A row that will become a card: it needs a question (an empty answer makes a self-check card). */
export function isReady(row: Row): boolean {
  return Boolean(normalizeSpace(row.front));
}

export function hasContent(row: Row): boolean {
  return Boolean(normalizeSpace(row.front) || row.back.trim() || row.hook.trim());
}

// "X is Y", "X are Y", "X means Y", "X: Y", "X = Y": the left side becomes the
// question, the right side the answer. The left side must be short, so a long
// sentence that merely contains "is" isn't cut in an odd place.
const DEFINITION = /^(.{2,60}?)(\s*[:=]\s*|\s+(?:is|are|was|were|means|refers to)\s+)(.{2,})$/i;

/** One sentence of notes as a question and answer the person can edit. */
export function rowFromSentence(sentence: string): Pick<Row, 'front' | 'back'> {
  // Bold or highlighted words are the ones to remember: blank them out.
  const filled = blankMarked(normalizeSpace(sentence), BLANK);
  if (filled && normalizeSpace(filled[0].split(BLANK).join(' '))) return { front: `Fill in the blank: ${filled[0].replace(/[.;]+$/, '')}`, back: filled[1] };
  const text = normalizeSpace(plain(sentence)).replace(/[.;]+$/, '');
  const match = DEFINITION.exec(text);
  if (match) {
    // "The heart is…" reads "What is the heart?"; names keep their capitals.
    const left = match[1].trim().replace(/^(The|A|An)\s/, (word) => word.toLowerCase());
    const verb = match[2].trim().toLowerCase();
    const back = match[3].trim();
    if (verb === 'means' || verb === 'refers to') return { front: `What does “${left}” mean?`, back };
    if (verb === ':' || verb === '=') return { front: match[1].trim(), back };
    return { front: `What ${verb} ${left}?`, back };
  }
  // No definition to split on: ask to finish the sentence from its opening words.
  const words = text.split(/\s+/);
  const lead = words.slice(0, Math.min(4, Math.max(1, Math.floor(words.length / 3)))).join(' ');
  return { front: words.length > 3 ? `Finish: “${lead} …”` : text, back: words.length > 3 ? text : '' };
}

export interface Split {
  rows: Row[];
  /** True when the text read as notes (sentences), not a question/answer list. */
  fromNotes: boolean;
}

/**
 * Pasted text as rows: a "question :: answer" list (also "=>", " - " or a tab)
 * keeps its pairs; anything else is notes, split into sentences or lines.
 */
export function splitPasted(raw: string): Split {
  const pairs = parsePromptAnswerLines(plain(raw));
  const lines = raw.split(/\r?\n/).filter((line) => line.trim()).length;
  const delimited = raw.split(/\r?\n/).filter((line) => /\t|::|=>|\s-\s/.test(line)).length;
  if (pairs.length && delimited >= Math.max(1, Math.ceil(lines / 2))) {
    return { rows: pairs.map((pair) => blankRow(pair.prompt, pair.answer)), fromNotes: false };
  }
  const bits = splitStudyBits(raw);
  return { rows: bits.map((bit) => { const row = rowFromSentence(bit); return blankRow(row.front, row.back); }), fromNotes: true };
}

/** Rows ready to save, with whitespace tidied. */
export function readyRows(rows: Row[]): Row[] {
  return rows.filter(isReady).map((row) => ({ ...row, front: normalizeSpace(row.front), back: row.back.trim(), hook: row.hook.trim() }));
}
