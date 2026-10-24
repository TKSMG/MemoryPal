import { isoDate, setClock } from '../src/core/dates';
import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';
import { planReminders, reminderClock } from '../src/features/reminders';

const MORNING = new Date(2026, 9, 24, 9, 0);

function storeWith(dueOffsets: number[]) {
  const store = new MemoryStore(new MemoryAdapter());
  store.cards = dueOffsets.map((offset, index) => {
    const card = newCard({ deck: 'Biology', front: `Question ${index}`, back: 'Answer' });
    card.next_review = isoDate(new Date(2026, 9, 24 + offset));
    return card;
  });
  return store;
}

describe('study reminders', () => {
  beforeEach(() => setClock(() => MORNING));
  afterEach(() => setClock(null));

  test('reads the time, falling back to the evening', () => {
    expect(reminderClock('08:00')).toEqual([8, 0]);
    expect(reminderClock('nonsense')).toEqual([19, 0]);
    expect(reminderClock('25:00')).toEqual([19, 0]);
  });

  test('one reminder on each day cards are due, counting the ones still waiting', () => {
    const plan = planReminders(storeWith([-2, 0, 2]), '19:00');
    expect(plan.map((item) => [isoDate(item.at), item.at.getHours(), item.due])).toEqual([
      ['2026-10-24', 19, 2],
      ['2026-10-25', 19, 2],
      ['2026-10-26', 19, 3],
      ['2026-10-27', 19, 3],
      ['2026-10-28', 19, 3],
      ['2026-10-29', 19, 3],
      ['2026-10-30', 19, 3],
    ]);
    expect(plan[0].title).toBe('2 cards are ready to review');
  });

  test('nothing due and no streak means no reminders at all', () => {
    expect(planReminders(storeWith([5, 9]), '19:00').map((item) => isoDate(item.at))).toEqual(['2026-10-29', '2026-10-30']);
  });

  test('skips today once studied, and a time already gone', () => {
    const store = storeWith([0]);
    store.activity[isoDate(MORNING)] = 4;
    expect(planReminders(store, '19:00')[0].at.getDate()).toBe(25);
    expect(planReminders(storeWith([0]), '08:00')[0].at.getDate()).toBe(25);
  });

  test('a streak gets a nudge even when nothing is due', () => {
    const store = storeWith([]);
    store.activity['2026-10-22'] = 3;
    store.activity['2026-10-23'] = 5;
    const plan = planReminders(store, '19:00');
    expect(plan).toHaveLength(1);
    expect(plan[0].title).toBe('Keep your 2-day streak');
  });
});
