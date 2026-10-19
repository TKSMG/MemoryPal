/**
 * Renaming and deleting a whole set (deck) with a single save. Phone-only:
 * the store's own card edit saves once per card, which is slow for big sets.
 * Sync compares records, so the changed decks and the deleted cards travel
 * as ordinary edits and tombstones.
 */
import { normalizeSpace } from '../core/text';
import type { MemoryStore } from '../core/store';

const deckOf = (deck: string) => deck || 'General';

export function deckCards(store: MemoryStore, deck: string) {
  return store.cards.filter((card) => deckOf(card.deck) === deck);
}

/** Moves every card of `from` into `to` (merging when `to` already exists). Returns how many moved. */
export function renameDeck(store: MemoryStore, from: string, to: string): number {
  const name = normalizeSpace(to) || 'General';
  if (name === from) return 0;
  const cards = deckCards(store, from);
  for (const card of cards) card.deck = name;
  if (cards.length) store.save();
  return cards.length;
}

/** Deletes a set and its cards. Returns how many cards were removed. */
export function deleteDeck(store: MemoryStore, deck: string): number {
  return store.deleteCards(deckCards(store, deck).map((card) => card.id));
}
