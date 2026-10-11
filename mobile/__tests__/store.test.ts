import { addDays, todayIso } from '../src/core/dates';
import { newCard } from '../src/core/models';
import { planForToday } from '../src/core/planning';
import { MemoryAdapter, MemoryStore } from '../src/core/store';

function fresh() {
  const adapter = new MemoryAdapter();
  const store = new MemoryStore(adapter);
  return { adapter, store, reload: () => new MemoryStore(adapter) };
}

describe('MemoryStore', () => {
  test('a new profile gets sample cards and the welcome screen', () => {
    const { store } = fresh();
    expect(store.cards.length).toBe(4);
    expect(store.onboarding.done).toBe(false);
  });

  test('ratings and progress persist', () => {
    const { store, reload } = fresh();
    const card = store.cards[0];
    store.schedule(card, 5);
    const saved = reload();
    expect(saved.findCard(card.id)?.repetitions).toBe(1);
    expect(saved.practiced).toBe(1);
    expect(saved.todayCount()).toBe(1);
  });

  test('undo takes back the card, the review count and today', () => {
    const { store, reload } = fresh();
    const card = store.cards[0];
    store.schedule(card, 4);
    expect(store.undoLast()).toBe(true);
    expect([card.repetitions, card.interval, store.practiced, store.todayCount()]).toEqual([0, 0, 0, 0]);
    expect(reload().practiced).toBe(0);
  });

  test('editing keeps the schedule; deleting removes the card', () => {
    const { store, reload } = fresh();
    const card = store.cards[0];
    store.schedule(card, 4);
    const before = [card.interval, card.next_review];
    store.updateCard(card, { front: 'New question', deck: '   ' });
    expect([card.front, card.deck]).toEqual(['New question', 'General']);
    expect([card.interval, card.next_review]).toEqual(before);
    expect(store.deleteCards([card.id])).toBe(1);
    expect(reload().findCard(card.id)).toBeUndefined();
  });

  test('learn again makes a card new and due today', () => {
    const { store } = fresh();
    const card = store.cards[0];
    store.schedule(card, 1);
    store.resetProgress([card.id]);
    expect([card.repetitions, card.lapses, card.last_result, card.next_review]).toEqual([0, 0, 'New', todayIso()]);
  });

  test('skip for today hides a due card until tomorrow', () => {
    const { store } = fresh();
    const card = store.cards[0];
    expect(store.dueCards().map((c) => c.id)).toContain(card.id);
    store.buryCard(card);
    expect(store.dueCards().map((c) => c.id)).not.toContain(card.id);
    expect(store.dueCards(null, addDays(1)).map((c) => c.id)).toContain(card.id);
  });

  test('a desktop backup imports, with damaged fields tolerated', () => {
    const { store } = fresh();
    store.importBackup({
      cards: [{ id: 'x1', front: 'From desktop', back: 'Yes', nextReview: '2020-01-01', ease: 'oops', interval: null }, 'not a card'],
      activity: [1, 2],
      daily_goal: 0,
      accessibility: { text_size: 'Huge', read_aloud: 1 },
    });
    expect(store.cards.map((c) => c.front)).toEqual(['From desktop']);
    expect(store.cards[0]).toMatchObject({ next_review: '2020-01-01', ease: 2.5, interval: 0 });
    expect(store.activity).toEqual({});
    expect(store.dailyGoal).toBe(1);
    expect(store.accessibility).toMatchObject({ text_size: 'Comfort', read_aloud: true });
    expect(store.onboarding.done).toBe(true);
  });

  test('export then import round-trips everything', () => {
    const { store } = fresh();
    store.addCard(newCard({ front: 'Round trip', back: 'OK', deck: 'Travel' }));
    store.schedule(store.cards[0], 4);
    const copy = fresh().store;
    copy.importBackup(JSON.parse(store.exportBackup()));
    expect(copy.payload()).toEqual({ ...store.payload(), onboarding: { done: true, persona: store.onboarding.persona } });
  });

  test('unreadable saved data is not overwritten until something changes', () => {
    const adapter = new MemoryAdapter();
    adapter.text = '{ broken';
    const store = new MemoryStore(adapter);
    expect(store.loadProblem).not.toBe('');
    expect(adapter.text).toBe('{ broken');
  });

  test('a saved plan gives today’s steps and ticks persist', () => {
    const { store, reload } = fresh();
    store.setStudyPlan({ unit: 'minutes', amount: '30', deck: 'All decks', goal_label: 'Exam prep', habits: [] });
    const today = planForToday(store);
    expect(today?.steps.reduce((sum, step) => sum + step.minutes, 0)).toBe(30);
    expect(store.togglePlanStep(1)).toBe(true);
    expect([...reload().planStepsDone()]).toEqual([1]);
  });
});
