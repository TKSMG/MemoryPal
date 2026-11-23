/** The phone's memory puzzles must play exactly like the desktop's (fixtures from tools/parity/make_fixtures.py). */
import fixtures from './fixtures/parity.json';
import {
  accuracy, clue, digitGroups, enoughFor, feedback, makeRound, Material, materialFrom, nextLevel, normalizeResults, PlayedRound, PuzzleRound,
  recordGame, Response, score, showMs, startLevel, streak, streakText, summary, todaysPuzzles, weakestPuzzle, KINDS, ChoiceQuestion,
} from '../src/core/puzzles';

const data = fixtures.puzzles as unknown as {
  cards: [string, string][];
  material: Material;
  rounds: { kind: string; level: number; seed: number; material: boolean; round: PuzzleRound; show_ms: [number, number] }[];
  scores: { round: PuzzleRound; response: Response; score: unknown }[];
  clues: { question: ChoiceQuestion; seed: number; clue: string[] }[];
  levels: { kind: string; level: number; right: boolean; helped: boolean; next: number }[];
  games: { kind: string; rounds: PlayedRound[]; day: string; results: unknown }[];
  queries: Record<string, unknown>[];
  groups: { digits: string; groups: string[] }[];
  feedback: { right: boolean; seed: number; simple: boolean; text: string }[];
  enough: { kind: string; material: Material | null; enough: boolean }[];
};

describe('puzzles match the desktop', () => {
  test('material and rounds', () => {
    expect(materialFrom(data.cards)).toEqual(data.material);
    for (const item of data.rounds) {
      const made = makeRound(item.kind, item.level, item.seed, item.material ? data.material : null);
      expect({ case: [item.kind, item.level, item.seed, item.material], round: made }).toEqual({ case: [item.kind, item.level, item.seed, item.material], round: item.round });
      expect([showMs(made), showMs(made, true)]).toEqual(item.show_ms);
    }
    for (const item of data.enough) expect(enoughFor(item.kind, item.material)).toBe(item.enough);
    for (const item of data.groups) expect(digitGroups(item.digits)).toEqual(item.groups);
  });

  test('scores, clues, levels and feedback', () => {
    for (const item of data.scores) expect({ round: item.round.kind, response: item.response, score: score(item.round, item.response) }).toEqual({ round: item.round.kind, response: item.response, score: item.score });
    for (const item of data.clues) expect(clue(item.question, item.seed)).toEqual(item.clue);
    for (const item of data.levels) expect(nextLevel(item.kind, item.level, item.right, item.helped)).toBe(item.next);
    for (const item of data.feedback) expect(feedback(item.right, item.seed, item.simple)).toBe(item.text);
  });

  test('saved results, streaks and today’s mix', () => {
    let state: unknown = {};
    for (const game of data.games) {
      state = recordGame(state, game.kind, game.rounds, game.day);
      expect(state).toEqual(game.results);
    }
    for (const query of data.queries) {
      const { results, today } = query as { results: unknown; today: string };
      expect({
        normalized: normalizeResults(results), streak: streak(results, today), streak_text: streakText(results, today),
        today3: todaysPuzzles(results, today), today_everyday: todaysPuzzles(results, today, true), weakest: weakestPuzzle(results, today),
        summary: summary(results, today),
        start: Object.fromEntries(KINDS.map((kind) => [kind, startLevel(results, kind)])),
        accuracy: Object.fromEntries(KINDS.map((kind) => [kind, accuracy(results, kind)])),
      }).toEqual({
        normalized: query.normalized, streak: query.streak, streak_text: query.streak_text, today3: query.today3, today_everyday: query.today_everyday,
        weakest: query.weakest, summary: query.summary, start: query.start, accuracy: query.accuracy,
      });
    }
  });
});
