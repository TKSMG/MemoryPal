import { newCard } from '../src/core/models';
import { MemoryAdapter, MemoryStore } from '../src/core/store';
import { deleteDeck, renameDeck } from '../src/features/decks';
import { blankRow, readyRows, rowFromSentence, splitPasted } from '../src/features/setBuilder';

describe('set builder', () => {
  test('a question/answer list keeps its pairs', () => {
    const { rows, fromNotes } = splitPasted('Capital of France :: Paris\nCapital of Spain => Madrid\nhola\thello');
    expect(fromNotes).toBe(false);
    expect(rows.map((row) => [row.front, row.back])).toEqual([
      ['Capital of France', 'Paris'],
      ['Capital of Spain', 'Madrid'],
      ['hola', 'hello'],
    ]);
  });

  test('notes become one editable row per sentence, without repeated hint prompts', () => {
    const { rows, fromNotes } = splitPasted('The heart is a muscle that pumps blood. Osmosis means water moving through a membrane. Plants need light, water and air to grow well.');
    expect(fromNotes).toBe(true);
    expect(rows.map((row) => row.front)).toEqual([
      'What is the heart?',
      'What does “Osmosis” mean?',
      'Finish: “Plants need light, …”',
    ]);
    expect(rows[0].back).toBe('a muscle that pumps blood');
    expect(rows[2].back).toBe('Plants need light, water and air to grow well');
    // Every front is different: no "Notes: P_____ n___" pattern.
    expect(new Set(rows.map((row) => row.front)).size).toBe(rows.length);
  });

  test('a colon definition splits into term and meaning', () => {
    expect(rowFromSentence('Mitosis: cell division')).toEqual({ front: 'Mitosis', back: 'cell division' });
  });

  test('only rows with a question are saved; whitespace is tidied', () => {
    const rows = [blankRow('  What   is 2+2? ', ' 4 '), blankRow('', 'orphan answer'), blankRow('Self check')];
    expect(readyRows(rows).map((row) => [row.front, row.back])).toEqual([['What is 2+2?', '4'], ['Self check', '']]);
  });
});

describe('sets', () => {
  const store = () => {
    const s = new MemoryStore(new MemoryAdapter());
    s.addCards([newCard({ deck: 'Bio', front: 'a', back: '1' }), newCard({ deck: 'Bio', front: 'b', back: '2' }), newCard({ deck: 'Chem', front: 'c', back: '3' })]);
    return s;
  };

  test('rename moves every card in one save and keeps their schedules', () => {
    const s = store();
    const card = s.cards.find((item) => item.front === 'a')!;
    s.schedule(card, 5);
    const version = s.version;
    expect(renameDeck(s, 'Bio', '  Biology ')).toBe(2);
    expect(s.version).toBe(version + 1);
    expect(s.decks()).toContain('Biology');
    expect(s.decks()).not.toContain('Bio');
    expect(card.repetitions).toBe(1);
  });

  test('renaming into an existing set merges them', () => {
    const s = store();
    renameDeck(s, 'Chem', 'Bio');
    expect(s.cards.filter((item) => item.deck === 'Bio')).toHaveLength(3);
  });

  test('delete removes the set and only its cards', () => {
    const s = store();
    const before = s.cards.length;
    expect(deleteDeck(s, 'Bio')).toBe(2);
    expect(s.cards).toHaveLength(before - 2);
    expect(s.decks()).not.toContain('Bio');
  });
});
