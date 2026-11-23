/**
 * The phone's notification plan must match the desktop's.
 * Fixtures come from tools/parity/make_notification_fixtures.py (the real Python code).
 */
import fixtures from './fixtures/notifications.json';
import { isoDate, setClock } from '../src/core/dates';
import { MemoryAdapter, MemoryStore } from '../src/core/store';
import { planNotifications } from '../src/features/notifications';

const pad = (value: number) => String(value).padStart(2, '0');
const stamp = (at: Date) => `${isoDate(at)}T${pad(at.getHours())}:${pad(at.getMinutes())}`;

function localDate(text: string): Date {
  const [day, time] = text.split('T');
  const [year, month, date] = day.split('-').map(Number);
  const [hour, minute] = time.split(':').map(Number);
  return new Date(year, month - 1, date, hour, minute);
}

describe('notification parity with the desktop', () => {
  afterEach(() => setClock(null));

  for (const item of fixtures.cases) {
    test(item.name, () => {
      const start = localDate(item.start);
      setClock(() => start);
      const store = new MemoryStore(new MemoryAdapter());
      store.applyRaw(JSON.parse(JSON.stringify(item.store)));
      const planned = planNotifications(store, item.settings, start).map((entry) => ({ ...entry, at: stamp(entry.at) }));
      expect(planned).toEqual(item.expected);
    });
  }
});
