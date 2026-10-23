import { newCard } from '../src/core/models';
import { enoughFor, materialFrom } from '../src/features/puzzleMaterial';

describe('puzzles from a set', () => {
  test('short cards become pairs and words; long ones are left out', () => {
    const cards = [
      newCard({ front: 'Largest heart chamber?', back: 'Left ventricle' }),
      newCard({ front: 'Largest heart chamber?', back: 'Left ventricle' }),
      newCard({ front: 'Pacemaker of the heart?', back: 'SA node' }),
      newCard({ front: 'Explain the cardiac cycle', back: 'A long answer that goes on for many words and would never fit a puzzle round' }),
      newCard({ front: 'Self-check only', back: '' }),
    ];
    const material = materialFrom(cards);
    expect(material.pairs).toEqual([['Largest heart chamber?', 'Left ventricle'], ['Pacemaker of the heart?', 'SA node']]);
    expect(material.words).toEqual(['Left ventricle', 'SA node']);
    expect(enoughFor('pairs', material)).toBe(false);
    expect(enoughFor('pairs', materialFrom([...cards, newCard({ front: 'Valve between LA and LV?', back: 'Mitral' })]))).toBe(true);
    expect(enoughFor('sequence', material)).toBe(false);
    expect(enoughFor('words', null)).toBe(false);
  });
});
