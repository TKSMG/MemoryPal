import { newCard } from '../src/core/models';
import { BLANK, buildQuiz, cardQuestion, cardsFromNoteQuestions, checkAnswer, isAiCard, isGenericFront, noteQuestions, pickDistractors, questionForBit, Rng, TYPES } from '../src/core/questions';
import { comparableText } from '../src/core/text';

const TODAY = '2026-10-18';
const later = '2026-10-30';

function deck() {
  return [
    newCard({ id: 'fr', deck: 'Geo', front: 'Capital of France', back: 'Paris', next_review: '2026-10-01', lapses: 2 }),
    newCard({ id: 'es', deck: 'Geo', front: 'Capital of Spain', back: 'Madrid', next_review: later }),
    newCard({ id: 'it', deck: 'Geo', front: 'Capital of Italy', back: 'Rome', next_review: later }),
    newCard({ id: 'de', deck: 'Geo', front: 'Capital of Germany', back: 'Berlin', next_review: later }),
    newCard({ id: 'pl', deck: 'Geo', front: 'Inner planets', back: 'Mercury, Venus, Earth and Mars', next_review: later }),
    newCard({ id: 'ww2', deck: 'History', front: 'End of World War II', back: '1945', next_review: later }),
    newCard({ id: 'hast', deck: 'History', front: 'Battle of Hastings', back: '1066', next_review: later }),
    newCard({ id: 'bit', deck: 'History', front: 'Study bit 3', back: 'The Treaty of Versailles was signed in 1919', next_review: later }),
    newCard({ id: 'ps', deck: 'Bio', front: 'What is photosynthesis?', back: 'The process plants use to turn light and water into food.', next_review: later }),
    newCard({ id: 'sr', deck: 'Bio', front: 'What is spaced repetition?', back: 'Reviewing information at increasing intervals so recall strengthens over time.', next_review: later }),
  ];
}

const ask = (text: string) => {
  const made = questionForBit(text);
  return made ? [made.prompt, made.answer] : null;
};

describe('seeded generator', () => {
  test('mulberry32 reference values', () => {
    const rng = new Rng(1);
    expect([rng.nextUint(), rng.nextUint(), rng.nextUint()]).toEqual([2693262067, 11749833, 2265367787]);
  });
});

describe('questions from notes', () => {
  test('definitions and dates become real questions', () => {
    expect(ask('The capital of Peru is Lima')).toEqual(['What is the capital of Peru?', 'Lima']);
    expect(ask('DNA stands for deoxyribonucleic acid')).toEqual(['What does DNA stand for?', 'deoxyribonucleic acid']);
    expect(ask('In 1492, Columbus sailed the ocean blue.')).toEqual(['When did this happen? Columbus sailed the ocean blue.', '1492']);
    expect(ask('The Battle of Hastings was in 1066')).toEqual(['When was the Battle of Hastings?', '1066']);
  });

  test('stays conservative', () => {
    expect(ask('Is this already a question?')).toBeNull();
    const [prompt, answer] = ask('Napoleon was exiled to the island of Elba')!;
    expect(prompt).toContain(BLANK);
    expect(prompt).not.toContain(answer);
    for (const item of noteQuestions('Mitochondria means powerhouse. In 1066 the Normans invaded England. Paris')) {
      expect(item.prompt.toLowerCase()).not.toContain('bit');
    }
  });

  test('generic fronts are recognised', () => {
    expect(isGenericFront('What should I recall from bit 3?')).toBe(true);
    expect(isGenericFront('Notes: P____', 'Paris', 'Notes')).toBe(true);
    expect(isGenericFront('Capital of France', 'Paris', 'Geo')).toBe(false);
  });
});

describe('questions from cards', () => {
  test('distractors: same deck and kind first, never the answer', () => {
    const picked = pickDistractors('1945', [['1066', 'History'], ['Paris', 'History'], ['1945', 'History'], ['1945.', 'Geo'], ['1789', 'Geo']], 3, new Rng(1), 'History');
    expect(picked.slice(0, 2)).toEqual(['1066', '1789']);
    expect(picked.map(comparableText)).not.toContain('1945');
  });

  test('every type appears and is well formed', () => {
    const cards = deck();
    const seen = new Set<string>();
    for (const card of cards) {
      for (const type of TYPES) {
        const made = cardQuestion(card, type, cards, new Rng(3));
        if (!made) continue;
        seen.add(made.type);
        if (made.options.length) {
          expect(made.options[made.answer_index]).toBe(made.answer);
          expect(new Set(made.options.map(comparableText)).size).toBe(made.options.length);
        } else {
          expect(made.typed).toBe(true);
        }
        expect(checkAnswer(made, made.answer)).toBe(true);
      }
    }
    expect([...seen].sort()).toEqual([...TYPES].sort());
  });
});

describe('quiz rounds', () => {
  test('no card twice, no type twice in a row, weak due cards first', () => {
    for (let seed = 0; seed < 20; seed++) {
      const quiz = buildQuiz(deck(), 8, new Rng(seed), { today: TODAY });
      expect(quiz).toHaveLength(8);
      expect(new Set(quiz.map((item) => item.card_id)).size).toBe(8);
      for (let i = 1; i < quiz.length; i++) expect(quiz[i].type).not.toBe(quiz[i - 1].type);
    }
    expect(buildQuiz(deck(), 1, new Rng(4), { today: TODAY })[0].card_id).toBe('fr');
  });

  test('the last round is avoided and type filters apply', () => {
    const first = buildQuiz(deck(), 5, new Rng(1), { today: TODAY });
    const second = buildQuiz(deck(), 5, new Rng(2), { today: TODAY, recentIds: first.map((item) => item.id) });
    const firstIds = new Set(first.map((item) => item.card_id));
    expect(second.some((item) => firstIds.has(item.card_id))).toBe(false);
    expect(buildQuiz(deck(), 6, new Rng(1), { today: TODAY, types: ['choice', 'truefalse'] }).every((item) => ['choice', 'truefalse'].includes(item.type))).toBe(true);
    expect(buildQuiz([], 3, new Rng(1))).toEqual([]);
  });

  test('note cards marked as AI-made', () => {
    const cards = cardsFromNoteQuestions(noteQuestions('Gold is Au. Iron is Fe.'), 'Chemistry', true);
    expect(cards.map((card) => [card.front, card.back])).toEqual([['What is Gold?', 'Au'], ['What is Iron?', 'Fe']]);
    expect(cards.every(isAiCard)).toBe(true);
  });
});
