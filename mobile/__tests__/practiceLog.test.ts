/** The practice log the study plan learns from (phone side). */
import { setClock } from '../src/core/dates';
import { newCard } from '../src/core/models';
import { bestStudyHour, buildStudyPlan, planInsights } from '../src/core/planning';
import { MemoryStore } from '../src/core/store';

afterEach(() => setClock(null));

function store(): MemoryStore {
  const made = new MemoryStore();
  made.cards = ['Mercury', 'Venus', 'Earth', 'Mars'].map((back, index) => newCard({ id: `c${index}`, deck: 'Planets', front: `Planet ${index}?`, back, association: index === 0 ? 'One rhymes with sun: imagine Mercury stuck to a sun.' : '' }));
  made.practiceLog = [];
  return made;
}

test('ratings log the method, result, hook and time since the last answer', () => {
  const made = store();
  setClock(() => new Date(2026, 10, 23, 9, 0, 0));
  made.schedule(made.cards[0], 4, null, 'quiz');
  setClock(() => new Date(2026, 10, 23, 9, 0, 25));
  made.schedule(made.cards[1], 1);
  expect(made.practiceLog).toEqual([
    { at: '2026-11-23T09:00:00', m: 'quiz', ok: true, sec: 0, hook: 'peg' },
    { at: '2026-11-23T09:00:25', m: 'review', ok: false, sec: 25, hook: '' },
  ]);
  made.undoLast();
  expect(made.practiceLog).toHaveLength(1);
});

test('synced data keeps this device log, and a reset clears it', () => {
  const made = store();
  made.logPractice('talkback', true);
  made.replaceWith({ cards: made.cards });
  expect(made.practiceLog).toHaveLength(1);
  made.reset();
  expect(made.practiceLog).toEqual([]);
});

test('a plan with no log is the same as before and learns nothing', () => {
  const made = store();
  expect(planInsights(made)).toEqual([]);
  expect(bestStudyHour(made)).toBeNull();
  const steps = buildStudyPlan(made, 30, 'All decks', ['mnemonics', 'explain', 'games'], 'long_term');
  expect(steps.map((step) => step.view)).toEqual(expect.arrayContaining(['tools', 'talkback', 'games']));
  expect(steps.find((step) => step.view === 'tools')?.technique).toBeTruthy();
});
