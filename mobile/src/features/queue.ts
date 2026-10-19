/** Which cards a study session uses, fixed when the session starts. */
import type { Card as CardModel } from '../core/models';
import type { MemoryStore } from '../core/store';

export type Mode = 'due' | 'weak' | 'new' | 'quick' | 'gentle' | 'all';

export function buildQueue(store: MemoryStore, mode: Mode, deck: string | null): CardModel[] {
  const inDeck = (card: CardModel) => !deck || (card.deck || 'General') === deck;
  const due = store.dueCards(deck);
  switch (mode) {
    case 'weak':
      return store.weakCards().filter(inDeck).slice(0, 20);
    case 'new':
      return store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0 && inDeck(card)).slice(0, 20);
    case 'quick': {
      const extra = store.weakCards().filter((card) => inDeck(card) && !due.includes(card));
      return [...due, ...extra].slice(0, 10);
    }
    case 'gentle': {
      const everyday = due.filter((card) => card.deck === 'Everyday Memory');
      return (everyday.length ? everyday : due).slice(0, 8);
    }
    case 'all':
      return store.cards.filter(inDeck);
    default:
      return due;
  }
}

