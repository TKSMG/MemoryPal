/** A set's cards as material for the memory puzzles (pair and word recall). */
import type { Card } from '../core/models';

export interface Material {
  /** Short question and answer pairs. */
  pairs: [string, string][];
  /** Short answers, used as the words to remember. */
  words: string[];
}

const short = (text: string, words: number, chars: number) => !!text.trim() && text.trim().split(/\s+/).length <= words && text.trim().length <= chars;

export function materialFrom(cards: Card[]): Material {
  const pairs = cards.filter((card) => short(card.front, 12, 80) && short(card.back, 4, 40)).map((card) => [card.front.trim(), card.back.trim()] as [string, string]);
  const words = [...new Set(cards.filter((card) => short(card.back, 3, 30)).map((card) => card.back.trim()))];
  return { pairs: [...new Map(pairs.map((pair) => [pair[0], pair])).values()], words };
}

/** Enough of a set's material for this puzzle (otherwise the built-in words are used). */
export const enoughFor = (kind: string, material: Material | null) =>
  !!material && (kind === 'pairs' ? material.pairs.length >= 3 : kind === 'words' ? material.words.length >= 5 : false);
