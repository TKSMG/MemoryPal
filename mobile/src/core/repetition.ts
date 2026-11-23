/**
 * Repetition path (port of memorypal/repetition.py): recall a list in
 * growing runs, such as 5, 5-4, 5-4-3, then 3-2-1 back to the first item.
 * The parity fixtures check both apps build the same rounds.
 */
import { normalizeSpace, parsePromptAnswerLines, PromptAnswer } from './text';

/** A start this far into a long set already makes a long path. */
export const DEFAULT_START = 5;
const DEFAULT_PROMPT = /^Study bit \d+$/;

export type PathItem = PromptAnswer;
/** A round: its label ("5-4-3") and the item indexes from 0, in recall order. */
export type PathStep = [string, number[]];

/** The start a new path uses: item 5, or the last item of a shorter list. */
export function defaultStart(count: number): number {
  return Math.min(Math.max(count, 0), DEFAULT_START);
}

/** With start 5 and range 3: 5, 5-4, 5-4-3, then 3-2-1. No range walks all the way back to item 1. */
export function repetitionSteps(count: number, start?: number | null, span?: number | null): PathStep[] {
  if (count <= 0) return [];
  const from = start == null ? defaultStart(count) : start;
  const startIndex = Math.min(Math.max(from, 1), count) - 1;
  const width = span == null ? startIndex + 1 : Math.min(Math.max(span, 1), count);
  const steps: PathStep[] = [];
  const current: number[] = [];
  for (let offset = 0; offset < width; offset += 1) {
    const index = startIndex - offset;
    if (index < 0) break;
    current.push(index);
    steps.push([current.map((item) => item + 1).join('-'), [...current]]);
  }
  const last = current[current.length - 1];
  if (current.length && last > 0) {
    const walk: number[] = [];
    for (let index = last; index >= 0; index -= 1) walk.push(index);
    steps.push([walk.map((item) => item + 1).join('-'), walk]);
  }
  return steps;
}

/** A typed list as path items: "prompt - answer" lines keep their prompt; a plain line is prompted by its place. */
export function itemsFromText(raw: string | null | undefined): PathItem[] {
  const items: PathItem[] = [];
  for (const item of parsePromptAnswerLines(raw)) {
    items.push({ prompt: DEFAULT_PROMPT.test(item.prompt) ? `Item ${items.length + 1}` : item.prompt, answer: item.answer });
  }
  return items;
}

/** Cards as path items: the question is the prompt, the answer is what to recall. */
export function itemsFromCards(cards: { front: string; back: string }[]): PathItem[] {
  const items: PathItem[] = [];
  for (const card of cards) {
    const prompt = normalizeSpace(String(card.front ?? ''));
    const answer = normalizeSpace(String(card.back ?? ''));
    if (answer) items.push({ prompt: prompt || `Item ${items.length + 1}`, answer });
  }
  return items;
}

/** The answers a round asks for, one per line, in the round's order. */
export function roundExpected(items: PathItem[], indexes: number[]): string {
  return indexes.map((index) => items[index].answer).join('\n');
}

/** How many of the weakest cards a path drills: enough for a full 5-4-3-2-1 and a little more. */
export const WEAK_LIMIT = 10;
