/**
 * Renaming and deleting a whole set (deck) with a single save. Phone-only:
 * the store's own card edit saves once per card, which is slow for big sets.
 * Sync compares records, so the changed decks and the deleted cards travel
 * as ordinary edits and tombstones.
 */
import { Card, DECK_INFO_FIELDS } from '../core/models';
import { moveCapture } from '../core/store';
import type { MemoryStore } from '../core/store';
import { hooksFor } from '../core/techniques';
import { normalizeSpace } from '../core/text';

import { daysBetween, parseIso } from '../core/dates';

const deckOf = (deck: string) => deck || 'General';

/** Days from today to a YYYY-MM-DD exam date (negative once past), or null. */
export function daysUntil(examDate: string, today: Date = new Date()): number | null {
  const day = parseIso(examDate);
  return day ? daysBetween(today, day) : null;
}

/** "Exam in 12 days", "Exam tomorrow", "Exam today", "Exam was 3 days ago", or ''. */
export function examCountdown(examDate: string, today: Date = new Date()): string {
  const days = daysUntil(examDate, today);
  if (days === null) return '';
  if (days === 0) return 'Exam today';
  if (days === 1) return 'Exam tomorrow';
  if (days > 1) return `Exam in ${days} days`;
  return `Exam was ${-days} day${days === -1 ? '' : 's'} ago`;
}

export function deckCards(store: MemoryStore, deck: string) {
  return store.cards.filter((card) => deckOf(card.deck) === deck);
}

/**
 * Moves every card of `from` into `to` (merging when `to` already exists),
 * with the set's details and notes. Details already on `to` win; any it
 * lacks come from `from`. Returns how many cards moved.
 */
export function renameDeck(store: MemoryStore, from: string, to: string): number {
  const name = normalizeSpace(to) || 'General';
  if (name === from) return 0;
  const cards = deckCards(store, from);
  for (const card of cards) card.deck = name;
  const info = store.deckInfo(from);
  const target = store.deckInfo(name);
  for (const field of DECK_INFO_FIELDS) if (!target[field]) target[field] = info[field];
  let changed = store.storeDeckInfo(target);
  changed = store.dropDeckInfo(from) || changed;
  for (const capture of store.notesForDeck(from)) {
    moveCapture(capture, from, name);
    changed = true;
  }
  if (cards.length || changed) store.save();
  return cards.length;
}

/** Deletes a set, its cards and details; its notes stay, unlinked. Returns how many cards were removed. */
export function deleteDeck(store: MemoryStore, deck: string): number {
  const ids = new Set(deckCards(store, deck).map((card) => card.id));
  store.cards = store.cards.filter((card) => !ids.has(card.id));
  if (store.lastAction && ids.has(store.lastAction.cardId)) store.lastAction = null;
  let changed = store.dropDeckInfo(deck);
  for (const capture of store.notesForDeck(deck)) {
    moveCapture(capture, deck, '');
    changed = true;
  }
  if (ids.size || changed) store.save();
  return ids.size;
}

/** What a card is remembered by in a memory technique: its answer when short, else its question. */
export function techniqueItem(card: Card): string {
  const back = String(card.back || '').split(/\s+/).filter(Boolean).join(' ');
  return back && back.split(' ').length <= 8 ? back : String(card.front || '').split(/\s+/).filter(Boolean).join(' ');
}

/** A set's cards, oldest first, and the item each is remembered by. */
export function techniqueItems(store: MemoryStore, deck: string): { cards: Card[]; items: string[] } {
  const cards = [...deckCards(store, deck)].reverse();
  return { cards, items: cards.map(techniqueItem) };
}

/** Give each card in a set its line from a memory technique, added to its hook. Returns how many changed. */
export function addTechniqueHooks(store: MemoryStore, deck: string, kind: string): number {
  const { cards, items } = techniqueItems(store, deck);
  const hooks = hooksFor(kind, items);
  let changed = 0;
  if (hooks.length === cards.length) {
    cards.forEach((card, i) => {
      if (card.association.includes(hooks[i])) return;
      card.association = card.association.trim() ? `${card.association}\n${hooks[i]}` : hooks[i];
      changed += 1;
    });
  }
  if (changed) store.save();
  return changed;
}
