import { addDays, todayIso } from '../src/core/dates';
import { Capture, newCard } from '../src/core/models';
import { addTechniqueHooks, deleteDeck, renameDeck, techniqueItems } from '../src/features/decks';
import { buildMultiDayPlan, MAX_PLAN_DAYS, planForToday } from '../src/core/planning';
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

  test('a synced card with a huge interval is cut down and can still be rated', () => {
    const { store } = fresh();
    store.replaceWith({ cards: [JSON.parse(`{"id": "big", "front": "q", "back": "a", "repetitions": 3, "next_review": "2020-01-01", "interval": ${'9'.repeat(300)}}`)] });
    const card = store.cards[0];
    expect(card.interval).toBe(36500);
    store.schedule(card, 4);
    expect(card.interval).toBeLessThanOrEqual(365);
    expect(card.next_review).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  test('a huge or odd plan synced from another device stays quick', () => {
    const { store } = fresh();
    const payload = store.payload();
    payload.study_plan = { settings: { unit: 'days', amount: '1000000', deck: 'All decks', goal_label: 'Cram', habits: [{}] as unknown as string[] }, created: todayIso(), done: {} };
    store.replaceWith(payload as unknown as Record<string, unknown>);
    expect(store.studyPlan).toMatchObject({ settings: { unit: 'days', amount: '365', habits: [] } });
    expect(planForToday(store)?.totalDays).toBe(365);
    // Even an unchecked plan is capped.
    const raw = { settings: { unit: 'weeks', amount: '99999', deck: 'All decks', goal_label: 'Cram', habits: [] }, created: todayIso(), done: {} };
    expect(planForToday(store, raw)?.totalDays).toBe(MAX_PLAN_DAYS);
    expect(buildMultiDayPlan(store, 1e9, 'All decks', [], 'long_term')).toHaveLength(MAX_PLAN_DAYS);
  });
});

describe('set details and notes', () => {
  const capture = (fields: Partial<Capture>): Capture => ({ id: Math.random().toString(36).slice(2), title: 'Notes', notes: '', chunks: [], text_file: '', image: '', audio: '', video: '', created_at: '', deck: '', ...fields });

  test('details save cleaned, persist, and vanish when emptied', () => {
    const { store, reload } = fresh();
    store.setDeckInfo(' Cardio ', { exam_date: '2026-11-02', ai_style: 'clinical cases', ai_examples: 'Why aspirin?' });
    const info = reload().deckInfo('Cardio');
    expect([info.exam_date, info.ai_style, info.ai_examples]).toEqual(['2026-11-02', 'clinical cases', 'Why aspirin?']);
    store.setDeckInfo('Cardio', { exam_date: '2026-02-30' });
    expect(store.deckInfo('Cardio').exam_date).toBe('');
    store.setDeckInfo('Cardio', { ai_style: '', ai_examples: '' });
    expect(reload().deckInfos).toEqual([]);
  });

  test('renaming a set moves its details and notes; deleting keeps the notes', () => {
    const { store, reload } = fresh();
    store.cards = [];
    store.addCards([newCard({ deck: 'Bio', front: 'a' }), newCard({ deck: 'Art', front: 'b' })]);
    store.setDeckInfo('Bio', { exam_date: '2026-11-02', about: 'Year 1' });
    store.setDeckInfo('Biology', { about: 'kept' });
    store.addCapture(capture({ title: 'Bio: Cells' }));
    store.addCapture(capture({ title: 'Plants', deck: 'Bio' }));
    store.addCapture(capture({ title: 'Art: Colour' }));
    renameDeck(store, 'Bio', 'Biology');
    let again = reload();
    expect([again.deckInfo('Biology').about, again.deckInfo('Biology').exam_date, again.deckInfo('Bio').about]).toEqual(['kept', '2026-11-02', '']);
    expect(again.notesForDeck('Biology').map((c) => [c.title, c.deck]).sort()).toEqual([['Cells', 'Biology'], ['Plants', 'Biology']]);
    expect(deleteDeck(store, 'Biology')).toBe(1);
    again = reload();
    expect(again.cards.map((card) => card.deck)).toEqual(['Art']);
    expect(again.deckInfos).toEqual([]);
    expect(again.captures.filter((c) => c.title !== 'Art: Colour').map((c) => c.deck)).toEqual(['', '']);
  });

  test('damaged details are skipped', () => {
    const { store } = fresh();
    store.applyRaw({ decks: [{ id: '  ' }, 'nope', { name: 'A', about: 'x'.repeat(2000) }, { id: 'B' }, { id: 'A', about: 'second' }] });
    expect(store.deckInfos.map((info) => [info.id, info.about])).toEqual([['A', 'second']]);
  });

  test('AI cards find the notes they came from', () => {
    const { store } = fresh();
    const heart = capture({ title: 'Heart', deck: 'Cardio', notes: 'x', chunks: ['The heart has four chambers.', 'Aspirin stops platelets sticking together.'] });
    const lungs = capture({ title: 'Lungs', deck: 'Resp', notes: 'Aspirin stops platelets sticking together.' });
    store.captures = [lungs, heart];
    const card = newCard({ deck: 'Cardio', pathway: 'Made with AI > Heart', association: 'Made with AI, check it. Source: "aspirin stops platelets sticking-together"' });
    expect(store.sourceNotes(card)).toEqual({ capture: heart, bit: 1 });
    expect(store.sourceNotes(newCard({ deck: 'Cardio', pathway: 'Made with AI > Heart' }))).toEqual({ capture: heart, bit: -1 });
    expect(store.sourceNotes(newCard({ deck: 'Cardio' }))).toBeNull();
  });

  test('technique hooks go onto each card of a set once', () => {
    const { store, reload } = fresh();
    store.cards = [];
    store.addCards([newCard({ deck: 'Heart', front: 'Pacemaker?', back: 'SA node' }), newCard({ deck: 'Heart', front: 'Biggest chamber?', back: 'Left ventricle', association: 'Thick wall' })]);
    store.addCards([newCard({ deck: 'Other', front: 'x', back: 'y' })]);
    expect(techniqueItems(store, 'Heart').items).toEqual(['SA node', 'Left ventricle']);
    expect(addTechniqueHooks(store, 'Heart', 'acronym')).toBe(2);
    const hooks = Object.fromEntries(reload().cards.map((card) => [card.front, card.association]));
    expect(hooks).toEqual({ 'Pacemaker?': 'Acronym SL: S is for SA node.', 'Biggest chamber?': 'Thick wall\nAcronym SL: L is for Left ventricle.', x: '' });
    expect(addTechniqueHooks(store, 'Heart', 'acronym')).toBe(0);
  });
});
