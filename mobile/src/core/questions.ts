/**
 * Varied quiz questions made from cards and notes, without any AI.
 * Port of latest_app/memorypal/questions.py: for the same seed and cards both
 * give exactly the same questions (checked by __tests__/parity.test.ts).
 *
 * Question types, chosen by what fits each card:
 * - choice     front -> pick the back among similar answers
 * - reverse    short back -> pick the front it belongs to
 * - cloze      a key word blanked out of a sentence-like back (picked or typed)
 * - truefalse  a front shown with its own back or a plausible same-deck one
 * - match      three or four short pairs to match up
 * - order      a back that is a list: which item comes first / next
 * - recall     type the back (only when nothing else fits)
 */
import { todayIso } from './dates';
import type { Card } from './models';
import { newCard } from './models';
import { splitlines, strip } from './py';
import { blankMarked, plain } from './richtext';
import { comparableText, hangmanHint, normalizeSpace, splitStudyBits, STOP_WORDS, stripListMarker, tokenWords } from './text';

const M32 = 0x100000000;

/** mulberry32: tiny, seedable, and identical in Python and TypeScript. */
export class Rng {
  state: number;

  constructor(seed = 0) {
    this.state = ((Math.trunc(seed) % M32) + M32) % M32;
  }

  nextUint(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    const a = this.state;
    let t = Math.imul(a ^ (a >>> 15), 1 | a) >>> 0;
    t = ((t + (Math.imul(t ^ (t >>> 7), 61 | t) >>> 0)) >>> 0) ^ t;
    t >>>= 0;
    return (t ^ (t >>> 14)) >>> 0;
  }

  random(): number {
    return this.nextUint() / M32;
  }

  /** A whole number from 0 to n - 1. */
  below(n: number): number {
    return n > 0 ? Math.floor(this.random() * n) : 0;
  }

  choice<T>(items: T[]): T {
    return items[this.below(items.length)];
  }

  /** Shuffle an array in place (Fisher-Yates) and return it. */
  shuffle<T>(items: T[]): T[] {
    for (let i = items.length - 1; i > 0; i--) {
      const j = this.below(i + 1);
      [items[i], items[j]] = [items[j], items[i]];
    }
    return items;
  }
}

export type QuestionType = 'choice' | 'reverse' | 'cloze' | 'truefalse' | 'match' | 'order' | 'recall';
export const TYPES: QuestionType[] = ['choice', 'reverse', 'cloze', 'truefalse', 'match', 'order', 'recall'];

export interface Question {
  /** "<card id>:<type>", for the recent-history list. */
  id: string;
  card_id: string;
  deck: string;
  type: QuestionType;
  prompt: string;
  answer: string;
  /** Choices to pick from; empty for typed questions. */
  options: string[];
  /** Index of the answer in options, or -1. */
  answer_index: number;
  typed: boolean;
  /** For match: the right [left, right] pairs (options holds the rights shuffled). */
  pairs: [string, string][];
  /** The card front, for questions whose prompt doesn't show it. */
  context: string;
  /** Hangman-style hint for typed questions. */
  hint: string;
}

export interface NoteQuestion {
  prompt: string;
  answer: string;
  type: 'definition' | 'list' | 'date' | 'cloze' | 'hint';
  source: string;
}

export const BLANK = '_____';
const WORD_RE = /[A-Za-z0-9][A-Za-z0-9'-]{2,}/g;
/** Everyday words that make poor blanks and give-away wrong answers ("over", "them"). */
const CLOZE_FILLER = new Set([
  'above', 'across', 'after', 'again', 'against', 'along', 'among', 'around', 'been', 'before',
  'behind', 'being', 'below', 'between', 'both', 'does', 'doing', 'down', 'during', 'each',
  'even', 'ever', 'every', 'here', 'into', 'many', 'more', 'most', 'much', 'must',
  'only', 'onto', 'other', 'over', 'same', 'some', 'such', 'them', 'these', 'they',
  'those', 'through', 'under', 'until', 'upon', 'very', 'well', 'within', 'without',
]);
const YEAR_RE = /(?<![0-9])(1[0-9]{3}|20[0-9]{2})(?![0-9])/;
const NUMBER_RE = /(?<![A-Za-z0-9.,])[0-9](?:[0-9,.:]*[0-9])?%?(?![A-Za-z0-9])/;
const NUMBER_WORD = /^[-+]?[0-9][0-9,.:]*%?$/;
const MONTH_RE = /(?<![a-z])(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)(?![a-z])/;
const TYPED_NEWLINE = /\\n|(?<![A-Za-z0-9])\/n(?![A-Za-z0-9])/g;
const GENERIC_FRONT = /^(?:what should i recall from bit (?:[0-9]+|\{n\})\??|study bit [0-9]+)$/i;
const PRONOUNS = new Set(['it', 'this', 'that', 'these', 'those', 'there', 'he', 'she', 'they', 'we', 'you', 'i', 'which', 'what', 'who', 'its', 'his', 'her', 'their', 'our']);
const DEFINITION_RE = /^(.{1,60}?)\s+(is called|is known as|refers to|stands for|means|is|are|was|were)\s+(.+)$/iu;
const NOT_DEFINING = new Set(['not', 'no', 'very', 'also', 'being', 'been', 'so', 'too', 'still', 'now', 'often', 'usually', 'always', 'never']);
export const AI_PATHWAY = 'Made with AI';
export const AI_NOTE = 'Made with AI, check it.';

/** Length in characters (code points), like Python's len(). */
const len = (text: string) => [...text].length;

export function wordsOf(text: string): string[] {
  const value = normalizeSpace(text);
  return value ? value.split(' ') : [];
}

/** date, number, word, short or long: distractors should share it. */
export function answerKind(raw: string): string {
  const text = normalizeSpace(raw);
  const words = wordsOf(text);
  if (!words.length) return 'empty';
  if (words.length <= 4 && (YEAR_RE.test(text) || (MONTH_RE.test(text.toLowerCase()) && /[0-9]/.test(text)))) return 'date';
  if (words.length <= 3 && NUMBER_WORD.test(words[0])) return 'number';
  if (words.length === 1) return 'word';
  return words.length <= 5 ? 'short' : 'long';
}

export function isShort(text: string): boolean {
  const count = wordsOf(text).length;
  return count > 0 && count <= 5 && len(normalizeSpace(text)) <= 40;
}

/** The items of a back that is a list (three or more), else []. */
export function listItems(text: string): string[] {
  const raw = (text ?? '').replace(TYPED_NEWLINE, '\n');
  const lines = splitlines(raw).map(stripListMarker).filter(Boolean);
  if (lines.length >= 3) return lines.every((line) => wordsOf(line).length <= 12) ? lines : [];
  const semi = raw.split(';').map(strip).filter(Boolean);
  if (semi.length >= 3) return semi.every((part) => wordsOf(part).length <= 12) ? semi : [];
  let flat = normalizeSpace(raw);
  while (flat.endsWith('.')) flat = flat.slice(0, -1);
  const parts = flat.split(',').map(strip);
  if (parts.length < 3 && !flat.includes(' and ')) return [];
  let items: string[] = [];
  parts.forEach((original, index) => {
    let part = original;
    if (index === parts.length - 1) {
      for (const joiner of ['and ', 'or ']) {
        if (part.startsWith(joiner)) part = strip(part.slice(joiner.length));
      }
      items.push(...part.split(/\s+(?:and|or)\s+/).map(strip));
    } else {
      items.push(part);
    }
  });
  items = items.filter(Boolean);
  if (items.length < 3 || items.some((item) => wordsOf(item).length > 3)) return [];
  return items;
}

/** Fronts made for note bits that say nothing about the bit. */
export function isGenericFront(rawFront: string, back = '', deck = ''): boolean {
  const front = normalizeSpace(rawFront);
  if (!front || GENERIC_FRONT.test(front)) return true;
  return Boolean(back) && front === `${normalizeSpace(deck)}: ${hangmanHint(back)}`;
}

export type ClozeCandidate = [word: string, start: number, end: number];

/** Words worth blanking out, best first: [word as written, start, end]. */
export function clozeCandidates(text: string, avoid = ''): ClozeCandidate[] {
  const avoidStems = new Set(tokenWords(avoid).map(([stem]) => stem));
  const ranked: { score: number; index: number; candidate: ClozeCandidate }[] = [];
  const seen = new Set<string>();
  for (const match of text.matchAll(WORD_RE)) {
    const word = match[0];
    const lower = word.toLowerCase();
    const hasDigit = /[0-9]/.test(word);
    if (STOP_WORDS.has(lower) || CLOZE_FILLER.has(lower) || seen.has(lower) || (word.length < 4 && !hasDigit)) continue;
    seen.add(lower);
    const stems = tokenWords(word);
    const stem = stems.length ? stems[0][0] : lower;
    const start = match.index ?? 0;
    let score = (hasDigit ? 30 : 0) + (/^[A-Z]/.test(word) && start > 0 ? 20 : 0);
    score += (avoidStems.has(stem) ? 0 : 20) + Math.min(word.length, 12);
    ranked.push({ score, index: ranked.length, candidate: [word, start, start + word.length] });
  }
  ranked.sort((a, b) => b.score - a.score || a.index - b.index);
  return ranked.map((item) => item.candidate);
}

/**
 * Words in a text that could stand in for the blanked word `like`. A word
 * that starts a sentence takes the blanked word's capitalisation, so a
 * capital letter gives nothing away; other capitals (names) stay.
 */
export function clozeWords(text: string, like: string): string[] {
  const out: string[] = [];
  for (const match of text.matchAll(WORD_RE)) {
    let word = match[0];
    if (STOP_WORDS.has(word.toLowerCase()) || CLOZE_FILLER.has(word.toLowerCase()) || (word.length < 4 && !/[0-9]/.test(word))) continue;
    const start = match.index ?? 0;
    if (start === 0 || /[.!?]\s+$/.test(text.slice(0, start))) {
      word = (/^[A-Z]/.test(like) ? word.slice(0, 1).toUpperCase() : word.slice(0, 1).toLowerCase()) + word.slice(1);
    }
    out.push(word);
  }
  return out;
}

const blankOut = (text: string, start: number, end: number) => text.slice(0, start) + BLANK + text.slice(end);

/** 'The heart' -> 'the heart', so it reads well inside a question. */
function lowerArticle(text: string): string {
  const first = text.split(' ')[0];
  return ['The', 'A', 'An'].includes(first) ? text[0].toLowerCase() + text.slice(1) : text;
}

const capitalize = (text: string) => text.slice(0, 1).toUpperCase() + text.slice(1);

const DEFINITION_PROMPTS: Record<string, (subject: string) => string> = {
  means: (subject) => `What does ${subject} mean?`,
  'refers to': (subject) => `What does ${subject} refer to?`,
  'stands for': (subject) => `What does ${subject} stand for?`,
  'is called': (subject) => `What is ${subject} called?`,
  'is known as': (subject) => `What is ${subject} known as?`,
};

/** A real question from one sentence of notes, or null. Rule-based and conservative. */
export function questionForBit(bit: string): NoteQuestion | null {
  const markedText = normalizeSpace(stripListMarker(normalizeSpace(bit)));
  let text = normalizeSpace(plain(markedText));
  while (text && '.!;'.includes(text[text.length - 1])) text = text.slice(0, -1).replace(/\s+$/, '');
  const words = wordsOf(text);
  if (!words.length || text.endsWith('?')) return null;
  const made = (prompt: string, answer: string, type: NoteQuestion['type']): NoteQuestion => ({ prompt, answer, type, source: normalizeSpace(plain(bit)) });

  // Words the notes made bold or highlighted are the ones to remember.
  const filled = blankMarked(markedText, BLANK);
  if (filled && wordsOf(filled[0].split(BLANK).join(' ')).length) {
    let sentence = filled[0];
    while (sentence && '.!;'.includes(sentence[sentence.length - 1])) sentence = sentence.slice(0, -1).replace(/\s+$/, '');
    return made(`Fill in the blank: ${sentence}`, filled[1], 'cloze');
  }

  const colon = /^([^:]{1,60}):\s+(.+)$/u.exec(text);
  if (colon && wordsOf(colon[1]).length <= 6 && !/[0-9]$/.test(colon[1])) {
    const term = strip(colon[1]);
    const answer = strip(colon[2]);
    const listed = answer.split(',').filter((part) => strip(part)).length >= 2;
    return made(`What ${listed ? 'are' : 'is'} ${lowerArticle(term)}?`, answer, listed ? 'list' : 'definition');
  }

  const year = YEAR_RE.exec(text);
  if (year) {
    const opening = /^In ((?:1[0-9]{3}|20[0-9]{2})),?\s+(.+)$/.exec(text);
    if (opening && wordsOf(opening[2]).length >= 2) return made(`When did this happen? ${capitalize(opening[2])}.`, opening[1], 'date');
    const closing = /^(.+?)\s+(?:in|during|by)\s+((?:1[0-9]{3}|20[0-9]{2}))$/.exec(text);
    if (closing && wordsOf(closing[1]).length >= 2) {
      const head = closing[1];
      const headWords = wordsOf(head);
      const last = headWords[headWords.length - 1].toLowerCase();
      if (['was', 'were', 'is', 'are'].includes(last)) {
        return made(`When ${last} ${lowerArticle(headWords.slice(0, -1).join(' '))}?`, closing[2], 'date');
      }
      return made(`When did this happen? ${capitalize(head)}.`, closing[2], 'date');
    }
    if (words.length >= 3) return made(`Fill in the blank: ${blankOut(text, year.index, year.index + year[0].length)}`, year[0], 'date');
  }

  const definition = DEFINITION_RE.exec(text);
  if (definition) {
    const term = strip(definition[1]);
    const verb = definition[2].toLowerCase();
    const answer = strip(definition[3]);
    const termWords = wordsOf(term);
    const firstAnswer = answer.split(' ')[0].toLowerCase();
    // "was exiled", "is not", "are growing" describe, they don't define.
    const passive = ['is', 'are', 'was', 'were'].includes(verb) && (/(ed|en|ing)$/.test(firstAnswer) || NOT_DEFINING.has(firstAnswer));
    if (termWords.length >= 1 && termWords.length <= 6 && !PRONOUNS.has(termWords[0].toLowerCase()) && answer && !passive) {
      const subject = lowerArticle(term);
      const prompt = DEFINITION_PROMPTS[verb] ? DEFINITION_PROMPTS[verb](subject) : `What ${verb} ${subject}?`;
      return made(prompt, answer, listItems(answer).length ? 'list' : 'definition');
    }
  }

  if (words.length >= 4) {
    const number = NUMBER_RE.exec(text);
    if (number) return made(`Fill in the blank: ${blankOut(text, number.index, number.index + number[0].length)}`, number[0], 'cloze');
  }
  if (words.length >= 5) {
    const candidates = clozeCandidates(text);
    if (candidates.length) {
      const [word, start, end] = candidates[0];
      return made(`Fill in the blank: ${blankOut(text, start, end)}`, word, 'cloze');
    }
  }
  return made(`What is this? ${hangmanHint(text)}`, text, 'hint');
}

/** Questions from pasted notes: one per study bit that gives a question. */
export function noteQuestions(text: string): NoteQuestion[] {
  const out: NoteQuestion[] = [];
  const seen = new Set<string>();
  for (const bit of splitStudyBits(text)) {
    const question = questionForBit(bit);
    if (!question) continue;
    const key = comparableText(question.prompt);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(question);
  }
  return out;
}

// ------------------------------------------------------------- distractors
/**
 * Up to `count` wrong answers from [text, deck] pairs: same deck and same
 * kind first (numbers with numbers, dates with dates, single words with
 * single words), then the same kind from other decks, then the same deck,
 * then anything. Never the answer again (compared without case or
 * punctuation) and never the same text twice.
 */
export function pickDistractors(answer: string, candidates: [string, string][], count: number, rng: Rng, deck = ''): string[] {
  const kind = answerKind(answer);
  const seen = new Set([comparableText(answer)]);
  const tiers: string[][] = [[], [], [], []];
  for (const [raw, sourceDeck] of candidates) {
    const text = normalizeSpace(raw);
    const key = comparableText(text);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const sameKind = answerKind(text) === kind;
    const sameDeck = sourceDeck === deck;
    tiers[sameDeck && sameKind ? 0 : sameKind ? 1 : sameDeck ? 2 : 3].push(text);
  }
  const picked: string[] = [];
  for (const tier of tiers) picked.push(...rng.shuffle(tier));
  return picked.slice(0, count);
}

function withAnswer(answer: string, distractors: string[], rng: Rng): [string[], number] {
  const options = rng.shuffle([answer, ...distractors]);
  return [options, options.indexOf(answer)];
}

// --------------------------------------------------------------- questions
export type QuizCard = Pick<Card, 'id' | 'front' | 'back'> & Partial<Card>;

export interface PoolEntry {
  id: string;
  deck: string;
  front: string;
  back: string;
  raw_back: string;
  front_key: string;
  back_key: string;
  card: QuizCard;
}

/** The cards a round can draw on, cleaned once (fronts, backs, keys). */
export class Pool {
  entries: PoolEntry[] = [];
  backKeys: Set<string>;
  frontKeys: Set<string>;
  pairBackKeys: Set<string>;
  private fitCache = new Map<PoolEntry, QuestionType[]>();

  constructor(cards: QuizCard[]) {
    for (const card of cards) {
      let front = normalizeSpace(String(card.front ?? ''));
      let back = normalizeSpace(String(card.back ?? ''));
      let rawBack = String(card.back ?? '');
      const deck = String(card.deck || 'General');
      if (isGenericFront(front, back, deck) && back) {
        const made = questionForBit(back);
        if (made) [front, back, rawBack] = [made.prompt, made.answer, made.answer];
      }
      if (!front || !back) continue;
      this.entries.push({ id: String(card.id ?? ''), deck, front, back, raw_back: rawBack, front_key: comparableText(front), back_key: comparableText(back), card });
    }
    this.backKeys = new Set(this.entries.map((entry) => entry.back_key));
    this.frontKeys = new Set(this.entries.map((entry) => entry.front_key));
    this.pairBackKeys = new Set(this.entries.filter((entry) => Pool.pairable(entry)).map((entry) => entry.back_key));
  }

  static pairable(entry: PoolEntry): boolean {
    return isShort(entry.back) && wordsOf(entry.front).length <= 8;
  }

  /** The question types this card can make, in TYPES order. */
  fits(entry: PoolEntry): QuestionType[] {
    let out = this.fitCache.get(entry);
    if (!out) {
      out = this.workOutFits(entry);
      this.fitCache.set(entry, out);
    }
    return out;
  }

  private workOutFits(entry: PoolEntry): QuestionType[] {
    const out: QuestionType[] = [];
    // Every entry's own keys are in the sets, so "others" is one fewer.
    if (this.backKeys.size - 1 >= 2) out.push('choice');
    if (isShort(entry.back) && wordsOf(entry.front).length <= 12 && this.frontKeys.size - 1 >= 2) out.push('reverse');
    if (wordsOf(entry.back).length >= 5 && clozeCandidates(entry.back, entry.front).length) out.push('cloze');
    out.push('truefalse');
    if (Pool.pairable(entry) && this.pairBackKeys.size - 1 >= 2) out.push('match');
    if (listItems(entry.raw_back).length >= 3) out.push('order');
    out.push('recall');
    return out;
  }
}

function question(entry: PoolEntry, type: QuestionType, prompt: string, answer: string, extra: Partial<Question> = {}): Question {
  const typed = extra.typed ?? false;
  return {
    id: `${entry.id}:${type}`,
    card_id: entry.id,
    deck: entry.deck,
    type,
    prompt,
    answer,
    options: extra.options ?? [],
    answer_index: extra.answer_index ?? -1,
    typed,
    pairs: extra.pairs ?? [],
    context: extra.context ?? '',
    hint: typed ? hangmanHint(answer) : '',
  };
}

/** One question of `type` for a Pool entry, or null when it doesn't fit. */
export function makeQuestion(entry: PoolEntry, type: QuestionType, pool: Pool, rng: Rng): Question | null {
  const others = pool.entries.filter((other) => other.id !== entry.id);
  if (type === 'choice') {
    const wrong = pickDistractors(entry.back, others.map((o) => [o.back, o.deck]), 3, rng, entry.deck);
    if (wrong.length < 2) return null;
    const [options, index] = withAnswer(entry.back, wrong, rng);
    return question(entry, type, entry.front, entry.back, { options, answer_index: index });
  }
  if (type === 'reverse') {
    const wrong = pickDistractors(entry.front, others.filter((o) => o.back_key !== entry.back_key).map((o) => [o.front, o.deck]), 3, rng, entry.deck);
    if (wrong.length < 2) return null;
    const [options, index] = withAnswer(entry.front, wrong, rng);
    return question(entry, type, `Which one goes with “${entry.back}”?`, entry.front, { options, answer_index: index });
  }
  if (type === 'cloze') {
    const candidates = clozeCandidates(entry.back, entry.front).slice(0, 3);
    if (!candidates.length || wordsOf(entry.back).length < 5) return null;
    const [word, start, end] = rng.choice(candidates);
    const prompt = `Fill in the blank: ${blankOut(entry.back, start, end)}`;
    const sources = [...others.filter((o) => o.deck === entry.deck), ...others.filter((o) => o.deck !== entry.deck), entry];
    const pool2: [string, string][] = [];
    for (const source of sources) for (const found of clozeWords(source.back, word)) pool2.push([found, source.deck]);
    const wrong = pickDistractors(word, pool2, 3, rng, entry.deck);
    if (wrong.length >= 2 && rng.random() >= 0.35) {
      const [options, index] = withAnswer(word, wrong, rng);
      return question(entry, type, prompt, word, { options, answer_index: index, context: entry.front });
    }
    return question(entry, type, prompt, word, { typed: true, context: entry.front });
  }
  if (type === 'truefalse') {
    const sameDeck = others.filter((o) => o.deck === entry.deck).map((o): [string, string] => [o.back, o.deck]);
    const wrong = pickDistractors(entry.back, sameDeck, 1, rng, entry.deck);
    const showFalse = wrong.length > 0 && rng.random() < 0.5;
    const shown = showFalse ? wrong[0] : entry.back;
    const stop = /[.!?]$/.test(shown) ? '' : '.';
    const prompt = `True or false? The answer to “${entry.front}” is “${shown}”${stop}`;
    return question(entry, type, prompt, showFalse ? 'False' : 'True', { options: ['True', 'False'], answer_index: showFalse ? 1 : 0, context: entry.front });
  }
  if (type === 'match') {
    if (!Pool.pairable(entry)) return null;
    const tiers: PoolEntry[][] = [[], []];
    const fronts = new Set([entry.front_key]);
    const backs = new Set([entry.back_key]);
    for (const other of others) if (Pool.pairable(other)) tiers[other.deck === entry.deck ? 0 : 1].push(other);
    const companions: PoolEntry[] = [];
    for (const tier of tiers) {
      rng.shuffle(tier);
      for (const other of tier) {
        if (companions.length < 3 && !fronts.has(other.front_key) && !backs.has(other.back_key)) {
          fronts.add(other.front_key);
          backs.add(other.back_key);
          companions.push(other);
        }
      }
    }
    if (companions.length < 2) return null;
    const pairs = rng.shuffle([entry, ...companions].map((item): [string, string] => [item.front, item.back]));
    const rights = rng.shuffle(pairs.map(([, right]) => right));
    return question(entry, type, 'Match each one with what goes with it.', entry.back, { options: rights, answer_index: rights.indexOf(entry.back), pairs });
  }
  if (type === 'order') {
    const items = listItems(entry.raw_back);
    if (items.length < 3) return null;
    const at = rng.below(items.length);
    const answer = items[at];
    const prompt = at === 0 ? `${entry.front}: which comes first?` : `${entry.front}: what comes after “${items[at - 1]}”?`;
    const before = at ? items[at - 1] : null;
    const wrong = pickDistractors(answer, items.filter((item) => item !== before).map((item) => [item, entry.deck]), 3, rng, entry.deck);
    if (wrong.length < 2) return null;
    const [options, index] = withAnswer(answer, wrong, rng);
    return question(entry, type, prompt, answer, { options, answer_index: index, context: entry.front });
  }
  if (type === 'recall') return question(entry, type, entry.front, entry.back, { typed: true });
  return null;
}

/** makeQuestion for a card among `cards`; null when it doesn't fit. */
export function cardQuestion(card: QuizCard, type: QuestionType, cards: QuizCard[], rng: Rng): Question | null {
  const pool = new Pool(cards.some((c) => c.id === card.id) ? [...cards] : [card, ...cards]);
  const entry = pool.entries.find((e) => e.id === String(card.id));
  return entry ? makeQuestion(entry, type, pool, rng) : null;
}

// ------------------------------------------------------------ whole rounds
function priorityBucket(card: QuizCard, today: string): number {
  const due = String(card.next_review ?? '') <= today;
  const weak = Number(card.lapses ?? 0) > 0 || String(card.last_result ?? '') === 'Again' || (Number(card.repetitions ?? 0) > 0 && Number(card.last_score ?? 0) < 60);
  return due && weak ? 0 : due ? 1 : weak ? 2 : 3;
}

export interface QuizOptions {
  /** The last round's card ids or question ids ("<card id>:<type>"). */
  recentIds?: string[];
  /** Allowed question types (default: all; "recall" only when nothing else fits). */
  types?: QuestionType[];
  /** ISO date for "due" (default today). */
  today?: string;
}

/**
 * A round of up to `count` varied questions: due and weak cards first, the
 * last round's cards last, never the same card twice, and no two questions in
 * a row of the same type when it can be helped (least-used type preferred).
 */
export function buildQuiz(cards: QuizCard[], count: number, rng: Rng, options: QuizOptions = {}): Question[] {
  const today = options.today || todayIso();
  const allowed = TYPES.filter((type) => !options.types || options.types.includes(type));
  const recent = (options.recentIds ?? []).map(String);
  const recentCards = new Set([...recent.map((item) => item.split(':')[0]), ...recent]);
  const recentQuestions = new Set(recent);
  const pool = new Pool(cards.filter((card) => !(String(card.buried_until ?? '') > today)));
  const entries = rng.shuffle([...pool.entries]);
  const keyed = entries.map((entry, index) => ({ bucket: priorityBucket(entry.card, today) + (recentCards.has(entry.id) ? 4 : 0), index, entry }));
  keyed.sort((a, b) => a.bucket - b.bucket || a.index - b.index);
  const chosen = keyed.slice(0, Math.max(0, Math.trunc(count))).map((item) => item.entry);

  const used = Object.fromEntries(TYPES.map((type) => [type, 0])) as Record<QuestionType, number>;
  let previous = '';
  const out: Question[] = [];
  while (chosen.length) {
    const optionsFor = chosen.map((entry) => {
      const fitting = pool.fits(entry).filter((type) => allowed.includes(type));
      const preferred = fitting.filter((type) => type !== 'recall');
      return preferred.length ? preferred : fitting;
    });
    let at = optionsFor.findIndex((kinds) => kinds.some((type) => type !== previous));
    if (at < 0) at = 0;
    const entry = chosen.splice(at, 1)[0];
    let kinds = optionsFor[at];
    if (!kinds.length) continue;
    const fresh = kinds.filter((type) => type !== previous && !recentQuestions.has(`${entry.id}:${type}`));
    const different = kinds.filter((type) => type !== previous);
    kinds = fresh.length ? fresh : different.length ? different : kinds;
    const least = Math.min(...kinds.map((type) => used[type]));
    kinds = kinds.filter((type) => used[type] === least);
    const type = rng.choice(kinds);
    let made = makeQuestion(entry, type, pool, rng);
    if (!made) {
      for (const fallback of ['choice', 'truefalse', 'recall'] as QuestionType[]) {
        if (allowed.includes(fallback) && fallback !== type) {
          made = makeQuestion(entry, fallback, pool, rng);
          if (made) break;
        }
      }
    }
    if (!made) continue;
    used[made.type] += 1;
    previous = made.type;
    out.push(made);
  }
  return out;
}

/** True when a picked option (index or text) is right; typed answers use answerAssessment. */
export function checkAnswer(item: Question, response: number | string): boolean {
  if (typeof response === 'number') return response === item.answer_index;
  return comparableText(String(response)) === comparableText(item.answer);
}

/** Cards from noteQuestions (or the AI's) output. */
export function cardsFromNoteQuestions(items: { prompt?: string; answer?: string }[], deck: string, ai = false): Card[] {
  const cards: Card[] = [];
  for (const item of items) {
    const prompt = normalizeSpace(item.prompt ?? '');
    const answer = normalizeSpace(item.answer ?? '');
    if (prompt && answer) {
      cards.push(newCard({ deck: deck || 'General', front: prompt, back: answer, pathway: ai ? `${AI_PATHWAY} > ${deck}` : `Capture > ${deck}`, association: ai ? AI_NOTE : '' }));
    }
  }
  return cards;
}

export const isAiCard = (card: Pick<Card, 'pathway'>) => String(card.pathway ?? '').startsWith(AI_PATHWAY);
