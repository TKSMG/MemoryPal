/**
 * Memory-technique generators (port of memorypal/techniques.py). Every idea
 * gets its own peg, place, or scene: two ideas sharing a hook interfere.
 */
export const EMPTY = 'Add ideas first.';

const PEGS: [string, string, string][] = [
  ['one', 'sun', 'sun'], ['two', 'shoe', 'shoe'], ['three', 'tree', 'tree'], ['four', 'door', 'door'],
  ['five', 'hive', 'hive'], ['six', 'sticks', 'bundle of sticks'], ['seven', 'heaven', 'cloud in heaven'],
  ['eight', 'gate', 'gate'], ['nine', 'line', 'washing line'], ['ten', 'hen', 'hen'],
];
const PEG_ROUNDS = ['', 'giant golden ', 'tiny frozen ', 'noisy rainbow '];

const PALACE_ROUTE = [
  'front door', 'doormat', 'hallway', 'coat hook', 'kitchen', 'fridge', 'table', 'window',
  'sofa', 'television', 'bookshelf', 'stairs', 'landing', 'bathroom', 'bath', 'bedroom',
  'bed', 'wardrobe', 'desk', 'back door',
];
const PALACE_ROUNDS = ['', 'garden ', 'garage '];

const STORY_SCENES = [
  'at the front door', 'on the kitchen table', 'beside a bright window', 'inside a small notebook',
  'under a glowing lamp', 'on a busy bus', 'in a quiet park', 'on top of a tall ladder',
  'inside a lift', 'at a market stall', 'on a sandy beach', 'next to the final doorway',
];
const STORY_ACTIONS = ['shines', 'speaks', 'spins', 'points', 'opens', 'locks', 'sings', 'bounces', 'whistles', 'waves'];

const ACROSTIC_WORDS: Record<string, [string, string]> = {
  a: ['Angry', 'Apples'], b: ['Brave', 'Bears'], c: ['Clever', 'Cats'], d: ['Dancing', 'Dogs'],
  e: ['Eager', 'Eagles'], f: ['Funny', 'Frogs'], g: ['Giant', 'Goats'], h: ['Happy', 'Horses'],
  i: ['Icy', 'Islands'], j: ['Jolly', 'Jugglers'], k: ['Kind', 'Kings'], l: ['Lazy', 'Lions'],
  m: ['Merry', 'Monkeys'], n: ['Noisy', 'Neighbours'], o: ['Orange', 'Owls'], p: ['Purple', 'Penguins'],
  q: ['Quiet', 'Queens'], r: ['Red', 'Rabbits'], s: ['Silly', 'Snakes'], t: ['Tiny', 'Tigers'],
  u: ['Upside-down', 'Umbrellas'], v: ['Very', 'Violins'], w: ['Wild', 'Wolves'], x: ['Extra', 'X-rays'],
  y: ['Yellow', 'Yaks'], z: ['Zany', 'Zebras'],
};

export function parseIdeas(raw: string): string[] {
  const text = (raw ?? '').replace(/\\n|(?<![A-Za-z0-9])\/n(?![A-Za-z0-9])/g, '\n');
  return text.split(/[,\n;|/]+/).map((item) => item.trim()).filter(Boolean);
}

const withArticle = (phrase: string) => ('aeiou'.includes(phrase.charAt(0).toLowerCase()) && phrase ? 'an ' : 'a ') + phrase;
const title = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

export function acronym(items: string[]): string {
  if (!items.length) return EMPTY;
  const letters = items.map((item) => item.charAt(0).toUpperCase()).join('');
  const words = items.map((item, index) => {
    const options = ACROSTIC_WORDS[item.charAt(0).toLowerCase()];
    // Alternate describing words and nouns so it reads like a phrase.
    return options ? options[index % 2] : item.split(/\s+/)[0];
  });
  return `${letters}\n\nConnect each letter back to: ${items.join(', ')}\n\nOr as a sentence (acrostic): ${words.join(' ')}.\nSwap in your own words; a silly sentence you made yourself sticks best.`;
}

export function story(items: string[]): string {
  if (!items.length) return EMPTY;
  const lines = items.map((item, index) => {
    const lap = Math.floor(index / STORY_SCENES.length);
    const scene = STORY_SCENES[index % STORY_SCENES.length] + (lap ? ` (walk ${lap + 1})` : '');
    const action = STORY_ACTIONS[index % STORY_ACTIONS.length];
    return `${index + 1}. Picture ${item} ${scene}. It ${action} so you notice it before moving on.`;
  });
  return 'Mini-story:\n\n' + lines.join('\n') + '\n\nWalk through the scenes in order and let each image cue the next idea.';
}

export function pegList(items: string[]): string {
  if (!items.length) return EMPTY;
  const lines = items.map((item, index) => {
    const lap = Math.floor(index / PEGS.length);
    const [numberWord, rhyme, picture] = PEGS[index % PEGS.length];
    const twist = lap < PEG_ROUNDS.length ? PEG_ROUNDS[lap] : `round-${lap + 1} `;
    return `${index + 1}. ${title(numberWord)} rhymes with ${rhyme}: imagine ${item} stuck to ${withArticle(twist + picture)}.`;
  });
  let tip = '\n\nSay the number, hear the rhyme, see the picture.';
  if (items.length > PEGS.length) tip += ' Past ten, the same rhymes return with a twist (golden, frozen) so each peg stays unique.';
  return 'Peg list:\n\n' + lines.join('\n') + tip;
}

export function palace(items: string[]): string {
  if (!items.length) return EMPTY;
  const lines = items.map((item, index) => {
    const lap = Math.floor(index / PALACE_ROUTE.length);
    const area = lap < PALACE_ROUNDS.length ? PALACE_ROUNDS[lap] : `extra room ${lap + 1} `;
    return `${index + 1}. Put ${item} at the ${area}${PALACE_ROUTE[index % PALACE_ROUTE.length]}. Make it oversized or moving.`;
  });
  return 'Memory palace route:\n\n' + lines.join('\n') + '\n\nReview by walking through the route in the same order. Use a home you know well.';
}

export function chunkMap(items: string[], size = 3): string {
  if (!items.length) return EMPTY;
  const lines: string[] = [];
  for (let index = 0; index < items.length; index += size) {
    lines.push(`Group ${index / size + 1}: ` + items.slice(index, index + size).join(', '));
  }
  return 'Chunk map:\n\n' + lines.join('\n') + '\n\nStudy one group at a time, then connect the groups.';
}

export function linkChain(items: string[]): string {
  if (!items.length) return EMPTY;
  if (items.length === 1) return `Link chain:\n\nStart with ${items[0]} and add more ideas to build a chain.`;
  const lines = items.slice(1).map((second, index) => `${items[index]} leads to ${second}: imagine ${items[index]} handing a bright clue to ${second}.`);
  return 'Link chain:\n\n' + lines.join('\n');
}

export const TECHNIQUES: { key: string; title: string; blurb: string; make: (items: string[]) => string }[] = [
  { key: 'acronym', title: 'Acronym', blurb: 'First letters into one word or a silly sentence.', make: acronym },
  { key: 'story', title: 'Mini-story', blurb: 'Each idea becomes a scene in a little story.', make: story },
  { key: 'peg', title: 'Peg list', blurb: 'One-sun, two-shoe: hang each idea on a rhyme.', make: pegList },
  { key: 'palace', title: 'Memory palace', blurb: 'Place each idea somewhere along a walk through home.', make: palace },
  { key: 'chunk', title: 'Chunk map', blurb: 'Small groups are easier than one long list.', make: (items) => chunkMap(items) },
  { key: 'chain', title: 'Link chain', blurb: 'Each idea hands a clue to the next.', make: linkChain },
];
