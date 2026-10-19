/**
 * Helpers for the quick quiz screen around core/questions.ts: which cards a
 * round uses, how a prompt with a blank is shown and read aloud, typed-answer
 * outcomes, the tap-to-pair match board, and the recent-question history.
 */
import type { Card } from '../core/models';
import { BLANK, buildQuiz, Question, Rng } from '../core/questions';
import type { Assessment } from '../core/smartCheck';

export const ROUND_SIZE = 10;
/** Question ids kept so the next round avoids them (one round's worth, plus a little). */
export const RECENT_KEEP = 30;

/** Answered cards in the set (or all sets): a card with no answer has nothing to quiz. */
export function quizCards(cards: Card[], deck: string | null): Card[] {
  return cards.filter((card) => card.back.trim() && (!deck || (card.deck || 'General') === deck));
}

/** A round from the store's cards: due and weak first, the last round's questions avoided. */
export function makeRound(cards: Card[], deck: string | null, recent: string[], seed = Date.now()): Question[] {
  return buildQuiz(quizCards(cards, deck), ROUND_SIZE, new Rng(seed), { recentIds: recent });
}

/** This round's question ids first, then older ones, without repeats. */
export function nextRecent(previous: string[], round: Question[]): string[] {
  const ids = round.map((q) => q.id);
  return [...new Set([...ids, ...previous])].slice(0, RECENT_KEEP);
}

/** The prompt split around its blank, for showing the blank as a gap. */
export function promptParts(prompt: string): { before: string; after: string; blank: boolean } {
  const at = prompt.indexOf(BLANK);
  if (at < 0) return { before: prompt, after: '', blank: false };
  return { before: prompt.slice(0, at), after: prompt.slice(at + BLANK.length), blank: true };
}

/** The prompt as it should be read aloud ("blank" for the gap). */
export function promptSpeech(question: Question): string {
  return question.prompt.split(BLANK).join(' blank ').replace(/\s+/g, ' ').trim();
}

/** The options read aloud as "A: …. B: …". */
export function optionsSpeech(options: string[]): string {
  return options.map((option, i) => `${String.fromCharCode(65 + i)}: ${option}`).join('. ');
}

export type TypedOutcome = 'right' | 'close' | 'wrong';

export function typedOutcome(assessment: Assessment): TypedOutcome {
  if (assessment.bucket === 'Good' || assessment.bucket === 'Easy') return 'right';
  return assessment.bucket === 'Review' ? 'close' : 'wrong';
}

// ------------------------------------------------------------ match board
export interface MatchBoard {
  /** Left side, in the question's order. */
  lefts: string[];
  /** Right side, shuffled (question.options). */
  rights: string[];
  /** left index -> right index, for pairs already made. */
  matched: Record<number, number>;
  selected: { side: 'left' | 'right'; index: number } | null;
  mistakes: number;
  /** The last wrong pair, to show briefly. */
  wrong: { left: number; right: number } | null;
}

export function matchBoard(question: Question): MatchBoard {
  return { lefts: question.pairs.map(([left]) => left), rights: [...question.options], matched: {}, selected: null, mistakes: 0, wrong: null };
}

const rightIsMatched = (board: MatchBoard, right: number) => Object.values(board.matched).includes(right);

/** Tap one item: select it, or pair it with the selected item on the other side. */
export function tapMatch(board: MatchBoard, question: Question, side: 'left' | 'right', index: number): MatchBoard {
  if (side === 'left' ? index in board.matched : rightIsMatched(board, index)) return board;
  const selected = board.selected;
  if (!selected || selected.side === side) return { ...board, selected: { side, index }, wrong: null };
  const left = side === 'left' ? index : selected.index;
  const right = side === 'right' ? index : selected.index;
  const correct = question.pairs[left]?.[1] === board.rights[right];
  if (correct) return { ...board, matched: { ...board.matched, [left]: right }, selected: null, wrong: null };
  return { ...board, selected: null, mistakes: board.mistakes + 1, wrong: { left, right } };
}

export const matchDone = (board: MatchBoard) => Object.keys(board.matched).length >= board.lefts.length;
