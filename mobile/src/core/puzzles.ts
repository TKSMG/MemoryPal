/**
 * The memory puzzles: rounds, scoring, levels, saved results and today's mix.
 * A port of latest_app/memorypal/puzzles.py (checked by the parity fixtures),
 * so a puzzle plays the same on the phone and the desktop.
 *
 * Made with older players in mind: every answer can be tapped (typing is
 * optional), each game is a few short rounds that gently follow the player's
 * level, and a "Help me" clue is always there. Results stay on this phone
 * (device prefs `puzzles`), never synced.
 */
import { Rng } from './questions';

export const ROUNDS = 4;
export const DAILY_ROUNDS = 2;
const RECENT_MAX = 12;
const DAYS_MAX = 60;
/** A round counts as remembered when at least this share is right. */
const PASS_SHARE = 0.6;

export type PuzzleKind = 'sequence' | 'words' | 'pairs' | 'missing' | 'names' | 'places' | 'story' | 'routine' | 'sort' | 'search' | 'nback';
export type Skill = 'memory' | 'attention' | 'thinking' | 'everyday';

export interface PuzzleInfo {
  kind: PuzzleKind;
  title: string;
  skill: Skill;
  first: number;
  low: number;
  high: number;
  body: string;
  tip: string;
}

export const PUZZLES: PuzzleInfo[] = [
  { kind: 'sequence', title: 'Number run', skill: 'memory', first: 4, low: 3, high: 10, body: 'See a short run of numbers, then tap them back.', tip: 'Say the numbers in little groups, like a phone number.' },
  { kind: 'words', title: 'Word recall', skill: 'memory', first: 4, low: 3, high: 9, body: 'Look at a few words, then pick out the ones you saw.', tip: 'Picture the words together in one silly scene.' },
  { kind: 'pairs', title: 'Pair recall', skill: 'memory', first: 3, low: 2, high: 7, body: 'See word pairs, then remember each partner.', tip: 'Imagine the two things touching or talking to each other.' },
  { kind: 'missing', title: "What's missing?", skill: 'memory', first: 4, low: 3, high: 9, body: 'Remember a list, then spot the one that has gone.', tip: 'Read the list once as a little sentence.' },
  { kind: 'names', title: 'Names and faces', skill: 'everyday', first: 2, low: 2, high: 6, body: 'Meet a few people, then remember who is who.', tip: 'Link the name to the detail: Rose grows roses.' },
  { kind: 'places', title: 'Where did I put it?', skill: 'everyday', first: 2, low: 2, high: 7, body: 'See where things were put down, then find them again.', tip: 'Picture yourself walking into the room and putting it down.' },
  { kind: 'story', title: 'Story recall', skill: 'everyday', first: 3, low: 3, high: 6, body: 'Read a short story, then answer a few questions about it.', tip: 'Ask yourself who, where, when and what as you read.' },
  { kind: 'routine', title: 'Put it in order', skill: 'thinking', first: 3, low: 3, high: 7, body: 'See the steps of an everyday task, then put them back in order.', tip: 'Walk through the task in your head, step by step.' },
  { kind: 'sort', title: 'Sort it out', skill: 'thinking', first: 4, low: 4, high: 10, body: 'Put each thing into the group where it belongs.', tip: 'Ask yourself where you would find it at home.' },
  { kind: 'search', title: 'Spot them all', skill: 'attention', first: 3, low: 2, high: 7, body: 'Find every copy of one word in a grid.', tip: 'Scan slowly, one row at a time, left to right.' },
  { kind: 'nback', title: 'Same as before?', skill: 'attention', first: 6, low: 5, high: 14, body: 'Words appear one at a time. Say if each matches the one before.', tip: 'Keep saying the last word quietly to yourself.' },
];
export const KINDS = PUZZLES.map((item) => item.kind);
export const SKILLS: Record<Skill, string> = { memory: 'Memory', attention: 'Attention', thinking: 'Thinking', everyday: 'Everyday memory' };

export const WORDS = [
  'apple', 'river', 'candle', 'garden', 'pencil', 'window', 'basket', 'violin', 'mountain', 'teacup',
  'ladder', 'blanket', 'compass', 'lemon', 'harbour', 'button', 'feather', 'kettle', 'meadow', 'lantern',
  'pebble', 'orchard', 'saddle', 'thimble', 'piano', 'carrot', 'bridge', 'clock', 'honey', 'jacket',
  'mirror', 'parrot', 'rocket', 'tulip', 'wagon', 'anchor', 'biscuit', 'castle', 'daisy', 'engine',
];
const CATEGORIES: [string, string[]][] = [
  ['Fruit', ['apple', 'banana', 'pear', 'cherry', 'plum', 'grape', 'orange', 'lemon', 'peach', 'mango']],
  ['Animals', ['dog', 'horse', 'rabbit', 'sheep', 'goat', 'duck', 'fox', 'owl', 'cow', 'mouse']],
  ['In the kitchen', ['kettle', 'teapot', 'saucepan', 'fork', 'toaster', 'ladle', 'colander', 'bread bin', 'oven glove', 'whisk']],
  ['Clothes', ['scarf', 'coat', 'slippers', 'cardigan', 'hat', 'gloves', 'socks', 'jumper', 'boots', 'shirt']],
  ['In the garden', ['rose', 'spade', 'hose', 'bench', 'tulip', 'rake', 'hedge', 'watering can', 'daisy', 'bird table']],
  ['Getting about', ['bus', 'train', 'bicycle', 'taxi', 'car', 'ferry', 'tram', 'scooter', 'van', 'aeroplane']],
];
const ROUTINES = [
  ['Fill the kettle', 'Switch the kettle on', 'Put a tea bag in the cup', 'Pour in the hot water', 'Wait for it to brew', 'Take out the tea bag', 'Add a splash of milk'],
  ['Put on your coat', 'Check you have your keys', 'Turn off the lights', 'Step outside', 'Close the front door', 'Lock the door', 'Check the handle'],
  ['Write the card', 'Put it in the envelope', 'Seal the envelope', 'Write the address', 'Stick on a stamp', 'Walk to the post box', 'Post the letter'],
  ['Fill the watering can', 'Carry it to the plants', 'Water the roots gently', 'Check the soil is damp', 'Pick off dead leaves', 'Empty the can', 'Put the can away'],
  ['Brush your teeth', 'Wash your face', 'Put on your pyjamas', 'Take your evening tablets', 'Set the alarm', 'Get into bed', 'Turn off the lamp'],
  ['Write a shopping list', 'Take your bags', 'Walk to the shop', 'Find each thing on the list', 'Pay at the till', 'Carry the bags home', 'Put the food away'],
];
const NAMES = ['Margaret', 'Arthur', 'Joan', 'Frank', 'Rose', 'Harold', 'Betty', 'Walter', 'Irene', 'George',
  'Dorothy', 'Albert', 'Priya', 'Ahmed', 'Mei', 'Carlos', 'Amara', 'Kenji', 'Nora', 'Samuel'];
const DETAILS = ['grows roses', 'plays the piano', 'has a dog called Max', 'bakes bread', 'was a teacher', 'loves crosswords',
  'lives by the sea', 'sings in a choir', 'collects stamps', 'walks every morning', 'is learning to paint',
  'fixes old clocks', 'keeps bees', 'knits scarves', 'was a nurse', 'likes jazz'];
const ITEMS = ['glasses', 'keys', 'wallet', 'phone', 'watch', 'umbrella', 'library book', 'pill box', 'purse', 'remote control', 'address book', 'hat'];
export const ROOMS = ['Kitchen', 'Bedroom', 'Hallway', 'Living room', 'Bathroom', 'Garden shed'];
const STORY_FACTS: [string, string, string[]][] = [
  ['day', 'Which day was it?', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']],
  ['place', 'Where did {name} go?', ['the market', 'the library', 'the park', 'the bakery', 'the post office', 'the garden centre']],
  ['item', 'What did {name} buy?', ['a blue scarf', 'fresh bread', 'a birthday card', 'tomato seeds', 'a jar of honey', 'a new teapot']],
  ['friend', 'Who was it for?', ['Joan', 'Frank', 'Betty', 'Walter', 'Irene', 'Albert']],
  ['weather', 'What was the weather like?', ['raining', 'sunny', 'windy', 'foggy', 'snowing', 'cloudy']],
  ['travel', 'How did {name} get there?', ['by bus', 'by taxi', 'by train', 'by bicycle', 'on foot', 'by car']],
];
const STORY_NAMES = ['Margaret', 'Arthur', 'Rose', 'Harold', 'Dorothy', 'George', 'Priya', 'Samuel'];

const PRAISE = ['Well remembered!', 'Lovely work!', "That's the way!", 'Spot on!', 'Brilliant!'];
const GENTLE = ['Nearly. That one was tricky.', "Good try. Let's keep going.", 'That was a hard one.', "Not quite, and that's fine."];

export interface ChoiceQuestion {
  prompt: string;
  options: string[];
  answer: string;
}

export interface PuzzleRound {
  kind: PuzzleKind;
  level: number;
  /** Lines to remember (empty: no show step). */
  show: string[];
  /** Choice questions (pairs, missing, names, places, story, sort, nback). */
  questions: ChoiceQuestion[];
  /** sequence: the digits; words / routine: the words or steps in order; search: how many to find. */
  answer?: string | string[] | number;
  /** words: the words to pick from; routine: the steps shuffled. */
  options?: string[];
  /** missing: the list again without the one that went. */
  remaining?: string[];
  people?: [string, string][];
  groups?: string[];
  target?: string;
  tiles?: string[];
  items?: string[];
}

export interface Material {
  pairs: [string, string][];
  words: string[];
}

export function puzzle(kind: string): PuzzleInfo {
  return PUZZLES.find((item) => item.kind === kind) ?? PUZZLES[0];
}

export function clampLevel(kind: string, level: unknown): number {
  const info = puzzle(kind);
  const value = typeof level === 'number' && Number.isInteger(level) ? level : info.first;
  return Math.max(info.low, Math.min(info.high, value));
}

function unique(items: unknown[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of items) {
    const text = String(item).trim();
    const key = text.toLowerCase();
    if (text && !seen.has(key)) {
      seen.add(key);
      out.push(text);
    }
  }
  return out;
}

function short(text: string, words: number, chars: number): boolean {
  const trimmed = String(text ?? '').trim();
  return !!trimmed && trimmed.split(/\s+/).length <= words && trimmed.length <= chars;
}

/** A set's cards ([front, back]) as puzzle material: short question/answer pairs and short answers. */
export function materialFrom(cards: [string, string][]): Material {
  const pairs: [string, string][] = [];
  const seen = new Set<string>();
  for (const [front, back] of cards) {
    if (short(front, 12, 80) && short(back, 4, 40) && !seen.has(front.trim())) {
      seen.add(front.trim());
      pairs.push([front.trim(), back.trim()]);
    }
  }
  const words = unique(cards.filter(([, back]) => short(back, 3, 30)).map(([, back]) => back));
  return { pairs, words };
}

/** Enough of a set's material for this puzzle (otherwise the built-in words are used). */
export function enoughFor(kind: string, material: Material | null | undefined): boolean {
  if (!material) return false;
  if (kind === 'pairs') return (material.pairs ?? []).length >= 3;
  if (['words', 'missing', 'search', 'nback'].includes(kind)) return (material.words ?? []).length >= 6;
  return false;
}

export const usesMaterial = (kind: string) => ['pairs', 'words', 'missing', 'search', 'nback'].includes(kind);

const wordPool = (kind: string, material: Material | null | undefined) => (enoughFor(kind, material) ? [...material!.words] : [...WORDS]);

function choiceOptions(answer: string, pool: string[], count: number, rng: Rng): string[] {
  const others = rng.shuffle(unique(pool).filter((item) => item.toLowerCase() !== answer.toLowerCase()));
  return rng.shuffle([answer, ...others.slice(0, count - 1)]);
}

export function makeRound(kind: string, level: number, seed: number, material: Material | null = null): PuzzleRound {
  const rng = new Rng(seed);
  const lv = clampLevel(kind, level);
  const base = { kind: kind as PuzzleKind, level: lv, show: [] as string[], questions: [] as ChoiceQuestion[] };
  if (kind === 'sequence') {
    const digits: string[] = [];
    for (let i = 0; i < lv; i++) {
      let digit = String(rng.below(10));
      // Never three of the same in a row: it reads as a typo.
      while (digits.length >= 2 && digits[digits.length - 1] === digit && digits[digits.length - 2] === digit) digit = String(rng.below(10));
      digits.push(digit);
    }
    return { ...base, show: [digitGroups(digits.join('')).join(' ')], answer: digits.join('') };
  }
  if (kind === 'words') {
    const pool = wordPool(kind, material);
    const shown = rng.shuffle([...pool]).slice(0, lv);
    let rest = pool.filter((word) => !shown.includes(word));
    if (rest.length < lv) rest = [...rest, ...WORDS.filter((word) => !shown.includes(word) && !rest.includes(word))];
    const options = rng.shuffle([...shown, ...rng.shuffle(rest).slice(0, lv)]);
    return { ...base, show: shown, options, answer: [...shown] };
  }
  if (kind === 'pairs') {
    let pairs: [string, string][];
    if (enoughFor(kind, material)) {
      pairs = rng.shuffle(material!.pairs.map((pair) => [...pair] as [string, string])).slice(0, lv);
    } else {
      const words = rng.shuffle([...WORDS]).slice(0, lv * 2);
      pairs = Array.from({ length: lv }, (_, i) => [words[i * 2], words[i * 2 + 1]] as [string, string]);
    }
    const partners = pairs.map(([, b]) => b);
    const questions = rng.shuffle(pairs.map((pair) => [...pair] as [string, string])).map(([a, b]) => ({ prompt: `What went with “${a}”?`, options: rng.shuffle([...partners]), answer: b }));
    const joiner = enoughFor(kind, material) ? ' → ' : ' and ';
    return { ...base, show: pairs.map(([a, b]) => `${a}${joiner}${b}`), questions };
  }
  if (kind === 'missing') {
    const pool = wordPool(kind, material);
    const shown = rng.shuffle([...pool]).slice(0, lv);
    const gone = rng.below(shown.length);
    const remaining = rng.shuffle(shown.filter((_, index) => index !== gone));
    const others = rng.shuffle(shown.filter((_, index) => index !== gone)).slice(0, 3);
    const options = rng.shuffle([shown[gone], ...others]);
    return { ...base, show: shown, remaining, questions: [{ prompt: 'Which one has gone?', options, answer: shown[gone] }] };
  }
  if (kind === 'names') {
    const names = rng.shuffle([...NAMES]).slice(0, lv);
    const details = rng.shuffle([...DETAILS]).slice(0, lv);
    const people = names.map((name, i) => [name, details[i]] as [string, string]);
    const questions: ChoiceQuestion[] = [];
    for (const [name, detail] of rng.shuffle(people.map((person) => [...person] as [string, string]))) {
      const extra = rng.shuffle(NAMES.filter((n) => !names.includes(n))).slice(0, 2);
      const options = choiceOptions(name, [...names, ...extra], Math.min(4, lv + 1), rng);
      questions.push({ prompt: `Who ${detail}?`, options, answer: name });
    }
    return { ...base, show: people.map(([name, detail]) => `${name}: ${detail}`), people, questions };
  }
  if (kind === 'places') {
    const items = rng.shuffle([...ITEMS]).slice(0, lv);
    const rooms = items.map(() => rng.choice(ROOMS));
    const questions: ChoiceQuestion[] = [];
    for (const index of rng.shuffle(Array.from({ length: lv }, (_, i) => i))) {
      const options = choiceOptions(rooms[index], ROOMS, 4, rng);
      questions.push({ prompt: `Where did you put the ${items[index]}?`, options, answer: rooms[index] });
    }
    return { ...base, show: items.map((item, i) => `The ${item} in the ${rooms[i].toLowerCase()}`), questions };
  }
  if (kind === 'story') {
    const name = rng.choice(STORY_NAMES);
    const facts: Record<string, string> = {};
    for (const [key, , options] of STORY_FACTS) facts[key] = rng.choice(options);
    const text = [`On ${facts.day}, ${name} went to ${facts.place} ${facts.travel}.`, `It was ${facts.weather}.`, `${name} bought ${facts.item} for ${facts.friend}.`];
    const asked = rng.shuffle(STORY_FACTS.map((fact) => [...fact] as [string, string, string[]])).slice(0, lv);
    const questions = asked.map(([key, question, options]) => ({ prompt: question.split('{name}').join(name), options: choiceOptions(facts[key], options, 4, rng), answer: facts[key] }));
    return { ...base, show: [text.join(' ')], questions };
  }
  if (kind === 'routine') {
    const steps = [...rng.choice(ROUTINES).slice(0, lv)];
    const options = [...steps];
    while (options.every((step, i) => step === steps[i])) rng.shuffle(options);
    return { ...base, show: steps.map((step, i) => `${i + 1}. ${step}`), options, answer: steps };
  }
  if (kind === 'sort') {
    const groups = rng.shuffle(CATEGORIES.map(([name, items]) => [name, [...items]] as [string, string[]])).slice(0, lv <= 6 ? 2 : 3);
    const names = groups.map(([name]) => name);
    const picked: string[] = [];
    const questions: ChoiceQuestion[] = [];
    for (let index = 0; index < lv; index++) {
      const [name, items] = groups[index % groups.length];
      const item = rng.choice(items.filter((entry) => !picked.includes(entry)));
      picked.push(item);
      questions.push({ prompt: item, options: [...names], answer: name });
    }
    return { ...base, groups: names, questions: rng.shuffle(questions) };
  }
  if (kind === 'search') {
    let pool = wordPool(kind, material).filter((word) => word.length <= 14);
    if (pool.length < 6) pool = [...WORDS];
    const target = rng.choice(pool);
    const others = pool.filter((word) => word !== target);
    const size = Math.min(20, 8 + lv * 2);
    const tiles = [...Array.from({ length: lv }, () => target), ...Array.from({ length: size - lv }, () => rng.choice(others))];
    return { ...base, target, tiles: rng.shuffle(tiles), answer: lv };
  }
  if (kind === 'nback') {
    const pool = wordPool(kind, material);
    const items: string[] = [];
    for (let index = 0; index < lv; index++) {
      if (index > 0 && rng.random() < 0.35) items.push(items[items.length - 1]);
      else items.push(rng.choice(pool.filter((word) => !items.length || word !== items[items.length - 1])));
    }
    const questions = items.slice(1).map((item, i) => ({ prompt: item, options: ['Same', 'Different'], answer: item === items[i] ? 'Same' : 'Different' }));
    return { ...base, items, questions };
  }
  return makeRound('sequence', level, seed);
}

/** Digits in twos and threes, never a lone digit: 4 -> 2+2, 7 -> 3+2+2. */
export function digitGroups(digits: string): string[] {
  const groups: string[] = [];
  let rest = digits;
  while (rest) {
    let size = rest.length === 2 || rest.length === 4 ? 2 : 3;
    if (rest.length === 1) size = 1;
    groups.push(rest.slice(0, size));
    rest = rest.slice(size);
  }
  return groups;
}

/** How long the things to remember stay up before the answer screen (0: no show step). */
export function showMs(round: PuzzleRound, moreTime = false): number {
  const size = round.level;
  const table: Record<string, number> = {
    sequence: 1500 + 700 * size, words: 2500 + 1300 * size, pairs: 2500 + 2000 * size,
    missing: 2500 + 1300 * size, names: 3000 + 3000 * size, places: 3000 + 2200 * size,
    story: 12000, routine: 3000 + 2000 * size,
  };
  return (table[round.kind] ?? 0) * (moreTime ? 2 : 1);
}

export const norm = (text: unknown) => String(text).toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(/\s+/).filter(Boolean).join(' ');

export interface RoundScore {
  correct: number;
  total: number;
  right: boolean;
}

export type Response = string | string[] | { found: number; wrong: number };

/**
 * One round's score. response: sequence -> the digits; words -> the words
 * picked (or typed text); routine -> the steps in the order tapped; search ->
 * {found, wrong}; the rest -> one chosen option per question.
 */
export function score(round: PuzzleRound, response: Response | null | undefined): RoundScore {
  const kind = round.kind;
  if (kind === 'sequence') {
    const typed = String(response ?? '').replace(/\D/g, '');
    const answer = String(round.answer);
    let correct = 0;
    for (let i = 0; i < Math.min(typed.length, answer.length); i++) if (typed[i] === answer[i]) correct += 1;
    return { correct, total: answer.length, right: typed === answer };
  }
  if (kind === 'words') {
    const shown = round.answer as string[];
    let hits: number;
    let wrong = 0;
    if (typeof response === 'string') {
      const typed = ` ${norm(response)} `;
      hits = shown.filter((word) => typed.includes(` ${norm(word)} `)).length;
    } else {
      const picked = unique((response as string[] | null) ?? []);
      hits = picked.filter((word) => shown.includes(word)).length;
      wrong = picked.length - hits;
    }
    const correct = Math.max(0, hits - wrong);
    return { correct, total: shown.length, right: correct >= shown.length * PASS_SHARE };
  }
  if (kind === 'routine') {
    const order = (response as string[] | null) ?? [];
    const answer = round.answer as string[];
    let correct = 0;
    for (let i = 0; i < Math.min(order.length, answer.length); i++) if (order[i] === answer[i]) correct += 1;
    return { correct, total: answer.length, right: correct >= answer.length * PASS_SHARE };
  }
  if (kind === 'search') {
    const value = (response ?? {}) as { found?: number; wrong?: number };
    const found = Math.trunc(Number(value.found ?? 0));
    const wrong = Math.trunc(Number(value.wrong ?? 0));
    const total = round.answer as number;
    return { correct: found, total, right: found >= total && wrong <= 2 };
  }
  const picks = (response as string[] | null) ?? [];
  const questions = round.questions;
  let correct = 0;
  for (let i = 0; i < Math.min(questions.length, picks.length); i++) if (picks[i] === questions[i].answer) correct += 1;
  return { correct, total: questions.length, right: questions.length > 0 && correct >= questions.length * PASS_SHARE };
}

/** One step harder after a success, one easier after a miss; a helped success stays put. */
export function nextLevel(kind: string, level: number, right: boolean, helped = false): number {
  if (right && helped) return clampLevel(kind, level);
  return clampLevel(kind, level + (right ? 1 : -1));
}

/** Help me: the question with all but one wrong option taken away. */
export function clue(question: ChoiceQuestion, seed: number): string[] {
  const rng = new Rng(seed);
  const options = question.options;
  const wrong = options.filter((option) => option !== question.answer);
  if (options.length <= 2 || !wrong.length) return [...options];
  const keep = rng.choice(wrong);
  return options.filter((option) => option === question.answer || option === keep);
}

export function feedback(right: boolean, seed: number, simple = false): string {
  const rng = new Rng(seed);
  if (right) return rng.choice(PRAISE);
  return simple ? GENTLE[1] : rng.choice(GENTLE);
}

// ------------------------------------------------------------------ results
export interface KindResult {
  level: number;
  best: number;
  plays: number;
  last: string;
  recent: number[];
}

export interface PuzzleResults {
  kinds: Partial<Record<PuzzleKind, KindResult>>;
  days: string[];
}

const int = (value: unknown) => (typeof value === 'number' && Number.isInteger(value) ? value : 0);

/** Saved puzzle results: {kinds: {kind: {...}}, days: [ISO dates played]}. */
export function normalizeResults(raw: unknown): PuzzleResults {
  const out: PuzzleResults = { kinds: {}, days: [] };
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return out;
  const source = raw as Record<string, unknown>;
  const kinds = source.kinds && typeof source.kinds === 'object' && !Array.isArray(source.kinds) ? (source.kinds as Record<string, unknown>) : {};
  for (const kind of KINDS) {
    const item = Object.prototype.hasOwnProperty.call(kinds, kind) ? kinds[kind] : undefined;
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const entry = item as Record<string, unknown>;
    const recent = Array.isArray(entry.recent) ? entry.recent : [];
    out.kinds[kind] = {
      level: clampLevel(kind, entry.level),
      best: int(entry.best) > 0 ? clampLevel(kind, entry.best) : 0,
      plays: Math.max(0, int(entry.plays)),
      last: String(entry.last || '').slice(0, 10),
      recent: recent.map((value) => (value === 1 || value === true ? 1 : 0)).slice(-RECENT_MAX),
    };
  }
  const days = Array.isArray(source.days) ? source.days : [];
  out.days = [...new Set(days.filter((day): day is string => typeof day === 'string' && day.length >= 10).map((day) => day.slice(0, 10)))].sort().slice(-DAYS_MAX);
  return out;
}

/** Where a game starts: the level reached last time, else the first level. */
export function startLevel(results: unknown, kind: string): number {
  const item = normalizeResults(results).kinds[kind as PuzzleKind];
  return item ? item.level : puzzle(kind).first;
}

export interface PlayedRound {
  level: number;
  right: boolean;
  helped?: boolean;
}

/** Add a finished game. rounds: [{level, right}] in the order played. */
export function recordGame(results: unknown, kind: string, rounds: PlayedRound[], day: string): PuzzleResults {
  const updated = normalizeResults(results);
  if (!KINDS.includes(kind as PuzzleKind) || !rounds.length) return updated;
  const key = kind as PuzzleKind;
  const item: KindResult = updated.kinds[key] ?? { level: puzzle(kind).first, best: 0, plays: 0, last: '', recent: [] };
  const passed = rounds.filter((entry) => entry.right).map((entry) => clampLevel(kind, entry.level));
  const last = rounds[rounds.length - 1];
  item.level = nextLevel(kind, clampLevel(kind, last.level), !!last.right, !!last.helped);
  item.best = Math.max(item.best, ...passed);
  item.plays += 1;
  item.last = day;
  item.recent = [...item.recent, ...rounds.map((entry) => (entry.right ? 1 : 0))].slice(-RECENT_MAX);
  updated.kinds[key] = item;
  updated.days = [...new Set([...updated.days, day])].sort().slice(-DAYS_MAX);
  return updated;
}

/** Share of recent rounds remembered (null before any are played). */
export function accuracy(results: unknown, kind: string): number | null {
  const item = normalizeResults(results).kinds[kind as PuzzleKind];
  if (!item || !item.recent.length) return null;
  return item.recent.reduce((a, b) => a + b, 0) / item.recent.length;
}

function shiftDay(iso: string, days: number): string {
  const [y, m, d] = iso.split('-').map(Number);
  const when = new Date(Date.UTC(y, m - 1, d + days));
  return when.toISOString().slice(0, 10);
}

function daysSince(last: string, today: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(last) || !/^\d{4}-\d{2}-\d{2}$/.test(today)) return 99;
  const parse = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number);
    return Date.UTC(y, m - 1, d);
  };
  const value = Math.round((parse(today) - parse(last)) / 86400000);
  return Number.isNaN(value) ? 99 : value;
}

/** Days in a row with a puzzle, counting back from today (or yesterday: the day isn't over). */
export function streak(results: unknown, today: string): number {
  const days = new Set(normalizeResults(results).days);
  let current = days.has(today) ? today : shiftDay(today, -1);
  let count = 0;
  while (days.has(current)) {
    count += 1;
    current = shiftDay(current, -1);
  }
  return count;
}

/** A friendly line that never scolds for a missed day. */
export function streakText(results: unknown, today: string): string {
  const count = streak(results, today);
  const saved = normalizeResults(results);
  if (count >= 2) return `${count} days in a row. Lovely.`;
  if (saved.days.includes(today)) return "You've played today. Well done.";
  if (saved.days.length) return 'Welcome back. A few minutes is all it takes.';
  return 'A few minutes a day keeps the mind busy.';
}

/**
 * Today's mix: the puzzles most worth playing, from different skills.
 * Unplayed puzzles first, then the ones played longest ago or going worst.
 * With `everyday` (the everyday-memory or caregiver profile) the everyday
 * puzzles count a little more. The same day always gives the same mix.
 * Story recall, when picked, goes first so its questions can come back at
 * the end (remembering after a delay is what trains memory most).
 */
export function todaysPuzzles(results: unknown, today: string, everyday = false, count = 3): PuzzleKind[] {
  const saved = normalizeResults(results);
  const order = new Rng(Number(today.replace(/-/g, ''))).shuffle([...KINDS]);
  const scored: [number, PuzzleKind][] = order.map((kind) => {
    const item = saved.kinds[kind];
    let priority: number;
    if (!item) priority = 100;
    else {
      const share = item.recent.length ? item.recent.reduce((a, b) => a + b, 0) / item.recent.length : 0.5;
      priority = Math.min(30, daysSince(item.last, today)) * 2 + Math.trunc((1 - share) * 10);
    }
    if (everyday && puzzle(kind).skill === 'everyday') priority += 6;
    return [priority, kind];
  });
  const ranked = [...scored].sort((a, b) => b[0] - a[0]).map(([, kind]) => kind);
  const picked: PuzzleKind[] = [];
  const skills = new Set<Skill>();
  for (const kind of ranked) {
    const skill = puzzle(kind).skill;
    // Different skills each day; the everyday profile may get two everyday puzzles.
    const everydayCount = picked.filter((chosen) => puzzle(chosen).skill === 'everyday').length;
    if (picked.length < count && (!skills.has(skill) || (everyday && skill === 'everyday' && everydayCount < 2))) {
      picked.push(kind);
      skills.add(skill);
    }
  }
  for (const kind of ranked) if (picked.length < count && !picked.includes(kind)) picked.push(kind);
  const story = picked.indexOf('story');
  if (story >= 0) {
    picked.splice(story, 1);
    picked.unshift('story');
  }
  return picked;
}

/** The one puzzle most worth a round now (for a study plan step). */
export const weakestPuzzle = (results: unknown, today: string, everyday = false) => todaysPuzzles(results, today, everyday, 1)[0];

export interface PuzzleSummary {
  kind: PuzzleKind;
  title: string;
  skill: Skill;
  level: number;
  best: number;
  plays: number;
  accuracy: number | null;
  days_since: number | null;
}

/** For progress screens and the study plan: per kind level, best, plays, accuracy, days since played. */
export function summary(results: unknown, today: string): PuzzleSummary[] {
  const saved = normalizeResults(results);
  return PUZZLES.map((info) => {
    const item = saved.kinds[info.kind];
    const share = item && item.recent.length ? item.recent.reduce((a, b) => a + b, 0) / item.recent.length : null;
    return {
      kind: info.kind, title: info.title, skill: info.skill,
      level: item ? item.level : info.first, best: item ? item.best : 0, plays: item ? item.plays : 0,
      accuracy: share, days_since: item && item.last ? daysSince(item.last, today) : null,
    };
  });
}
