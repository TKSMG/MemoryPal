import { applyPlan, planSync, Records, Remote } from '../src/core/sync';

const card = { id: 'victim', front: 'secret', repetitions: 3, lapses: 0 };

describe('sync with hostile records from the cloud', () => {
  test('a row keyed "__proto__" cannot delete cards', () => {
    // How the account builds `remote` from pulled rows: a plain object, so this
    // assignment swaps its prototype instead of adding a key.
    const remote: Remote = {};
    remote['__proto__'] = { 'card:victim': null };
    const local: Records = { 'card:victim': card };
    const plan = planSync(local, { 'card:victim': card }, remote);
    expect([plan.apply, plan.push, plan.final]).toEqual([{}, {}, { 'card:victim': card }]);
    expect(applyPlan({ cards: [card] }, local, plan).cards).toEqual([card]);
  });

  test('unknown kinds never reach the base, and ones already there are dropped', () => {
    const local: Records = { 'card:victim': card };
    const plan = planSync(local, { ...local, 'evil:x': { a: 1 }, constructor: { b: 2 } }, { 'evil:y': { a: 1 }, toString: { c: 3 } });
    expect([plan.apply, plan.push, Object.keys(plan.final)]).toEqual([{}, {}, ['card:victim']]);
  });
});
