/**
 * Small helpers that reproduce Python behaviour the desktop logic relies on,
 * so the TypeScript port gives exactly the same results (see
 * __tests__/parity.test.ts, which checks against outputs from the Python code).
 */

/** Python's round(): halves go to the nearest even number (banker's rounding). */
export function pyRound(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Python's int() on a float: truncate toward zero. */
export function pyInt(value: number): number {
  return value < 0 ? Math.ceil(value) : Math.floor(value);
}

// CR+LF, or any single character Python treats as a line boundary
// (built from code points so no invisible separators sit in the source).
const CRLF = String.fromCharCode(0x0d, 0x0a);
const LINE_BREAKS = new RegExp(CRLF + '|[' + [0x0a, 0x0d, 0x0b, 0x0c, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029].map((code) => String.fromCharCode(code)).join('') + ']');

/** Python's str.splitlines() (no keepends). */
export function splitlines(text: string): string[] {
  if (!text) return [];
  const parts = text.split(LINE_BREAKS);
  if (parts.length && parts[parts.length - 1] === '') parts.pop();
  return parts;
}

/** Python's str.strip() with no arguments (whitespace, including Unicode). */
export function strip(text: string): string {
  return text.replace(/^\s+|\s+$/g, '');
}

/** Python's x % n for a positive divisor (never negative). */
export function pyMod(value: number, divisor: number): number {
  return ((value % divisor) + divisor) % divisor;
}

export function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

/**
 * difflib.SequenceMatcher(None, a, b).ratio(), including the "autojunk"
 * heuristic Python applies when b has 200 or more characters.
 */
export function sequenceRatio(a: string, b: string): number {
  const total = a.length + b.length;
  if (!total) return 1;
  return (2 * matchingCharacters(a, b)) / total;
}

function matchingCharacters(a: string, b: string): number {
  const b2j = new Map<string, number[]>();
  for (let j = 0; j < b.length; j++) {
    const ch = b[j];
    const list = b2j.get(ch);
    if (list) list.push(j);
    else b2j.set(ch, [j]);
  }
  const n = b.length;
  if (n >= 200) {
    const ntest = Math.floor(n / 100) + 1;
    for (const [ch, indices] of [...b2j.entries()]) {
      if (indices.length > ntest) b2j.delete(ch);
    }
  }

  const findLongestMatch = (alo: number, ahi: number, blo: number, bhi: number): [number, number, number] => {
    let besti = alo;
    let bestj = blo;
    let bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const next = new Map<number, number>();
      for (const j of b2j.get(a[i]) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) ?? 0) + 1;
        next.set(j, k);
        if (k > bestsize) {
          besti = i - k + 1;
          bestj = j - k + 1;
          bestsize = k;
        }
      }
      j2len = next;
    }
    // No junk set (isjunk=None), but popular characters were dropped from
    // b2j; extend the match over equal characters on both sides like difflib.
    while (besti > alo && bestj > blo && a[besti - 1] === b[bestj - 1]) {
      besti--;
      bestj--;
      bestsize++;
    }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && a[besti + bestsize] === b[bestj + bestsize]) {
      bestsize++;
    }
    return [besti, bestj, bestsize];
  };

  let matched = 0;
  const queue: [number, number, number, number][] = [[0, a.length, 0, b.length]];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop()!;
    const [i, j, k] = findLongestMatch(alo, ahi, blo, bhi);
    if (k) {
      matched += k;
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  return matched;
}
