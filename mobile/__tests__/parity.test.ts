/**
 * The TypeScript core must give exactly the desktop's answers.
 * Fixtures come from tools/parity/make_fixtures.py (the real Python code).
 */
import fixtures from './fixtures/parity.json';
import { addDays } from '../src/core/dates';
import { cardFromDict, newCard } from '../src/core/models';
import { buildMultiDayPlan, buildStudyPlan, PlanStep } from '../src/core/planning';
import { achievements, bestStreak, dueForecast, levelInfo, maturityBreakdown, ratingMix } from '../src/core/progress';
import { sequenceRatio } from '../src/core/py';
import { AttemptLimiter, accountAgeCheck, characterClasses, passwordProblems, passwordStrength, predictable, waitMessage } from '../src/core/security';
import { answerAssessment } from '../src/core/smartCheck';
import { MemoryStore, normalizeStudyPlan } from '../src/core/store';
import { Entries, entriesAfter, entriesOf, newestStamp, nextStamp, payloadFromRecords, planSync, recordsFromPayload, Records, Remote, remoteFromFiles } from '../src/core/sync';
import { acronym, chunkMap, hooksFor, linkChain, palace, parseIdeas, pegList, story } from '../src/core/techniques';
import { answerKind, buildQuiz, cardQuestion, clozeCandidates, isGenericFront, listItems, noteQuestions, questionForBit, QuestionType, QuizCard, Rng } from '../src/core/questions';
import { parsePromptAnswerLines, splitStudyBits, textTokens } from '../src/core/text';

type Spec = (typeof fixtures.plan_cards)[number];

function storeFrom(specs: Spec[]): MemoryStore {
  const store = new MemoryStore();
  store.cards = specs.map((spec) =>
    newCard({ id: spec.id, deck: spec.deck, front: spec.front, back: spec.back, repetitions: spec.repetitions, lapses: spec.lapses, last_score: spec.last_score, interval: spec.interval, next_review: addDays(spec.due) }),
  );
  return store;
}

const strip = (step: PlanStep) => ({
  title: step.title,
  view: step.view,
  minutes: step.minutes,
  blurb: step.blurb,
  ...(step.quiz_mode ? { quiz_mode: step.quiz_mode } : {}),
});

describe('parity with the desktop logic', () => {
  test('Smart Check scores every case the same', () => {
    for (const item of fixtures.smart_check) {
      expect({ case: [item.response, item.expected], result: answerAssessment(item.response, item.expected, item.context) }).toEqual({ case: [item.response, item.expected], result: item.result });
    }
  });

  test('SequenceMatcher ratio matches difflib', () => {
    for (const item of fixtures.sequence) {
      expect(sequenceRatio(item.a, item.b)).toBeCloseTo(item.ratio, 12);
    }
  });

  test('text splitting, Q/A parsing and tokens match', () => {
    for (const item of fixtures.split) expect(splitStudyBits(item.raw)).toEqual(item.bits);
    for (const item of fixtures.prompt_answer) expect(parsePromptAnswerLines(item.raw)).toEqual(item.items);
    for (const item of fixtures.tokens) expect(textTokens(item.raw)).toEqual(item.tokens);
  });

  test('the scheduler gives the same interval, ease and result', () => {
    for (const item of fixtures.schedule) {
      const store = new MemoryStore();
      const card = newCard({ id: item.card.id, front: 'Q', back: 'A', repetitions: item.card.repetitions, interval: item.card.interval, ease: item.card.ease, lapses: item.card.lapses, next_review: addDays(-item.card.overdue) });
      store.cards = [card];
      store.schedule(card, item.quality);
      expect({ id: item.card.id, q: item.quality, interval: card.interval, repetitions: card.repetitions, lapses: card.lapses, last_score: card.last_score, last_result: card.last_result, next_review: card.next_review })
        .toEqual({ id: item.card.id, q: item.quality, interval: item.interval, repetitions: item.repetitions, lapses: item.lapses, last_score: item.last_score, last_result: item.last_result, next_review: addDays(item.due_in) });
      expect(card.ease).toBeCloseTo(item.ease, 12);
    }
  });

  test('session plans match step for step', () => {
    const store = storeFrom(fixtures.plan_cards);
    const empty = new MemoryStore();
    empty.cards = [];
    for (const item of fixtures.sessions) {
      const steps = buildStudyPlan(item.store === 'empty' ? empty : store, item.minutes, item.deck, item.habits, item.goal);
      expect({ params: [item.minutes, item.deck, item.goal, item.habits], steps: steps.map(strip) }).toEqual({ params: [item.minutes, item.deck, item.goal, item.habits], steps: item.steps });
    }
  });

  test('multi-day plans match day for day', () => {
    const store = storeFrom(fixtures.plan_cards);
    for (const item of fixtures.multi_day) {
      const plan = buildMultiDayPlan(store, item.days, item.deck, item.habits, item.goal);
      const got = plan.map((day) => ({ day: day.day, offset: day.day - 1, kind: day.kind, due: day.due, minutes: day.minutes, steps: day.steps.map(strip) }));
      expect({ params: [item.days, item.deck, item.goal, item.habits], plan: got }).toEqual({ params: [item.days, item.deck, item.goal, item.habits], plan: item.plan });
    }
  });

  test('memory technique text matches', () => {
    for (const item of fixtures.techniques) {
      expect({ acronym: acronym(item.items), story: story(item.items), peg: pegList(item.items), palace: palace(item.items), chunk: chunkMap(item.items), chain: linkChain(item.items) })
        .toEqual({ acronym: item.acronym, story: item.story, peg: item.peg, palace: item.palace, chunk: item.chunk, chain: item.chain });
      for (const [kind, hooks] of Object.entries(item.hooks)) expect(hooksFor(kind, [...item.items, '  two\nlines '])).toEqual(hooks);
    }
    for (const item of fixtures.parse_ideas) expect(parseIdeas(item.raw)).toEqual(item.ideas);
  });

  test('sync plans (what to send, apply and keep) match for every case', () => {
    for (const [i, item] of fixtures.sync_plans.entries()) {
      const plan = planSync(item.local as Records, item.base as Records, item.remote as Remote);
      expect({ case: i, push: plan.push, apply: plan.apply, final: plan.final }).toEqual({ case: i, push: item.push, apply: item.apply, final: item.final });
    }
  });

  test('drive files are read, combined, stamped and written back the same way', () => {
    const d = fixtures.drive;
    for (const [i, item] of d.cases.entries()) {
      const [own, ...others] = (item.files as unknown[]).map((content) => entriesOf(content));
      const [remote, stamps] = remoteFromFiles([own, ...others]);
      const plan = planSync(item.local as Records, item.base as Records, remote);
      const stamp = nextStamp(newestStamp(stamps), 'laptop', item.now_ms);
      expect({ i, remote, stamps, push: plan.push, stamp, after: entriesAfter(own, plan, remote, stamps, stamp) })
        .toEqual({ i, remote: item.remote, stamps: item.stamps, push: item.push, stamp: item.stamp, after: item.entries_after as unknown as Entries });
    }
    for (const [i, item] of d.hostile.entries()) expect({ i, entries: entriesOf(item.content) }).toEqual({ i, entries: item.entries });
    for (const item of d.stamps) expect(nextStamp(item.newest, item.device, item.now_ms)).toBe(item.stamp);
  });

  test('password checks and strength scores match', () => {
    for (const item of fixtures.security.passwords) {
      const ours = { problems: passwordProblems(item.password, item.email), strength: passwordStrength(item.password, item.email), predictable: predictable(item.password), classes: characterClasses(item.password) };
      expect({ password: item.password, email: item.email, ...ours }).toEqual(item);
    }
  });

  test('the sign-in attempt limiter waits the same way', () => {
    let now = 1000;
    const limiter = new AttemptLimiter(() => now);
    for (const [i, step] of fixtures.security.limiter.entries()) {
      now += step.advance;
      if (step.action === 'fail') limiter.failed(' Pat@Example.com');
      else if (step.action === 'ok') limiter.succeeded('pat@example.com');
      const wait = limiter.waitSeconds('pat@example.com ');
      expect({ i, wait, message: wait ? waitMessage(wait) : '' }).toEqual({ i, wait: step.wait, message: step.message });
    }
    for (const item of fixtures.security.waits) expect(waitMessage(item.seconds)).toBe(item.message);
  });

  test('the account age check agrees', () => {
    for (const item of fixtures.security.ages) {
      const [message, under] = accountAgeCheck(item.month, item.year, 2026, 10);
      expect({ ...item, message, under }).toEqual(item);
    }
  });

  test('damaged or hostile records from sync are handled the same way', () => {
    for (const [i, item] of fixtures.hostile.plans.entries()) expect({ i, plan: normalizeStudyPlan(item.raw) }).toEqual({ i, plan: item.plan });
    for (const item of fixtures.hostile.cards) expect(cardFromDict(item.raw)).toEqual(item.card);
    for (const [i, item] of fixtures.hostile.sync.entries()) {
      const plan = planSync(item.local as unknown as Records, item.base as unknown as Records, item.remote as unknown as Remote);
      expect({ i, push: plan.push, apply: plan.apply, final: plan.final }).toEqual({ i, push: item.push, apply: item.apply, final: item.final });
    }
  });

  test('profile data converts to sync records and back the same way', () => {
    const c = fixtures.sync_conversion;
    expect(recordsFromPayload(c.payload, 'laptop', c.base as Records)).toEqual(c.records);
    expect(payloadFromRecords(c.payload, c.records_more as Records)).toEqual(c.payload_back);
  });

  test('progress, streaks, weak cards, deck summary and badges match', () => {
    const p = fixtures.progress;
    for (const level of p.levels) expect(levelInfo(level.practiced)).toEqual(level.info);
    const store = storeFrom(fixtures.plan_cards);
    store.activity = Object.fromEntries(Object.entries(p.activity_offsets).map(([offset, count]) => [addDays(-Number(offset)), count]));
    store.practiced = p.practiced;
    store.dailyGoal = p.daily_goal;
    expect(store.currentStreak()).toBe(p.streak);
    expect(bestStreak(store.activity)).toBe(p.best_streak);
    expect(maturityBreakdown(store.cards)).toEqual(p.maturity);
    expect(ratingMix(store.cards)).toEqual(p.rating_mix);
    expect(dueForecast(store.cards, 14).map(([, count]) => count)).toEqual(p.forecast);
    expect(store.weakCards().map((card) => card.id)).toEqual(p.weak_order);
    expect(store.deckSummary()).toEqual(p.deck_summary);
    expect(achievements(store).map((badge) => [badge.key, badge.current, badge.done])).toEqual(p.badges);
  });
  test('quiz questions: same generator, same questions for the same seed', () => {
    const q = fixtures.questions;
    for (const item of q.rng) {
      const r = new Rng(item.seed);
      expect(item.uints.map(() => r.nextUint())).toEqual(item.uints);
      const r2 = new Rng(item.seed);
      expect([1, 2, 3, 7, 10, 100, 1000].map((n) => r2.below(n))).toEqual(item.below);
      expect(new Rng(item.seed).shuffle([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])).toEqual(item.shuffle);
    }
    const cards = q.cards as unknown as QuizCard[];
    for (const [i, item] of q.quizzes.entries()) {
      const pool = (item as { cards?: string }).cards === 'small' ? cards.slice(0, 2) : cards;
      const quiz = buildQuiz(pool, item.count, new Rng(item.seed), { recentIds: item.recent, types: (item.types ?? undefined) as QuestionType[] | undefined, today: q.today });
      expect({ i, quiz }).toEqual({ i, quiz: item.quiz });
    }
    for (const item of q.singles) {
      const card = cards.find((c) => c.id === item.card)!;
      const index = cards.indexOf(card);
      expect({ ...item, question: cardQuestion(card, item.type as QuestionType, cards, new Rng(index * 7 + item.type.length)) }).toEqual(item);
    }
    for (const item of q.notes) expect(noteQuestions(item.text)).toEqual(item.questions);
    for (const item of q.bits) expect({ bit: item.bit, question: questionForBit(item.bit) }).toEqual(item);
    for (const item of q.lists) expect(listItems(item.text)).toEqual(item.items);
    for (const item of q.kinds) expect(answerKind(item.text)).toBe(item.kind);
    for (const item of q.cloze) expect(clozeCandidates(item.text, 'What is photosynthesis?')).toEqual(item.candidates);
    for (const item of q.generic) expect(isGenericFront(item.front, item.back, item.deck)).toBe(item.generic);
  });
});
