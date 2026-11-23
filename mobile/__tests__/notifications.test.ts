import { isoDate, setClock } from '../src/core/dates';
import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';
import { clock, normalizeSettings, planNotifications, quietLabel, routeFor } from '../src/features/notifications';

const MORNING = new Date(2026, 9, 24, 9, 0);
const ON = { enabled: true, quiet: 'off' };

function storeWith(dueOffsets: number[]) {
  const store = new MemoryStore(new MemoryAdapter());
  store.cards = dueOffsets.map((offset, index) => {
    const card = newCard({ deck: 'Biology', front: `Question ${index}`, back: 'Answer' });
    card.next_review = isoDate(new Date(2026, 9, 24 + offset));
    return card;
  });
  return store;
}

describe('study notifications', () => {
  beforeEach(() => setClock(() => MORNING));
  afterEach(() => setClock(null));

  test('reads the time, falling back to the evening', () => {
    expect(clock('08:00')).toEqual([8, 0]);
    expect(clock('nonsense')).toEqual([19, 0]);
    expect(clock('25:00')).toEqual([19, 0]);
  });

  test('settings start off and keep only known values', () => {
    expect(normalizeSettings(undefined).enabled).toBe(false);
    const settings = normalizeSettings({ enabled: true, time: '03:00', kinds: ['streak', 'nope'], quiet: 'always' });
    expect(settings).toEqual({ enabled: true, time: '19:00', kinds: ['streak'], quiet: '22:00-07:00', one_a_day: false });
    expect(normalizeSettings({ time: 'best' }).time).toBe('best');
  });

  test('nothing when switched off', () => {
    expect(planNotifications(storeWith([0]), { enabled: false }, MORNING)).toEqual([]);
  });

  test('cards due each day, counting the ones still waiting', () => {
    const plan = planNotifications(storeWith([-2, 0, 2]), { ...ON, kinds: ['cards_due'] }, MORNING);
    expect(plan.slice(0, 3).map((item) => [isoDate(item.at), item.at.getHours(), item.due])).toEqual([
      ['2026-10-24', 19, 2],
      ['2026-10-25', 19, 2],
      ['2026-10-26', 19, 3],
    ]);
    expect(plan[0].title).toBe('2 cards are ready to review');
  });

  test('skips today once studied', () => {
    const store = storeWith([0]);
    store.activity[isoDate(MORNING)] = 4;
    expect(planNotifications(store, { ...ON, kinds: ['cards_due'] }, MORNING)[0].at.getDate()).toBe(25);
  });

  test('a streak gets a late-evening saver', () => {
    const store = storeWith([]);
    store.activity['2026-10-22'] = 3;
    store.activity['2026-10-23'] = 5;
    const plan = planNotifications(store, { ...ON, kinds: ['streak'] }, MORNING);
    expect(plan.map((item) => [item.title, item.at.getHours()])).toEqual([['Keep your 2-day streak', 21]]);
  });

  test('taps open the right screen', () => {
    expect(routeFor('plan')).toBe('/plan');
    expect(routeFor('deck:Year 9 French')).toBe('/review?mode=weak&deck=Year%209%20French');
    expect(routeFor('anything')).toBe('/review');
  });

  test('quiet hours read as times', () => {
    expect(quietLabel('off')).toBe('Off');
    expect(quietLabel('22:00-07:00')).toContain(' to ');
  });
});
