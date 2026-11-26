/**
 * A gate in front of the AI tutor's ears.
 *
 * Gemini Live treats any sound on the microphone as the learner starting to
 * talk: a cough, a door, a TV, or the tutor's own voice leaking back from the
 * loudspeaker stopped it mid-sentence, and it then answered words nobody said
 * (the noise, transcribed) or started its question over and over. The gate
 * sends the microphone as it is only while someone is really talking; the
 * rest of the time it sends silence of the same length, so the stream never
 * pauses and Google still hears when a turn ends.
 *
 * - While the tutor is quiet, speech opens the gate after a short moment.
 * - While the tutor is talking (and just after), only clearly louder speech
 *   that keeps going opens it, so talking over the tutor still works but echo
 *   and short noises don't.
 * - The last half second before the gate opens is sent too, so the first
 *   words aren't lost.
 * - Thresholds follow the room's own noise level.
 *
 * Same numbers as memorypal/speechgate.py on the desktop app.
 */

export const GATE = {
  /** The starting guess for the room's noise, in dBFS. */
  floorStartDb: -60,
  /** The noise estimate never goes above this (a loud room still needs real speech). */
  floorMaxDb: -45,
  floorMinDb: -75,
  /** Speech while the tutor is quiet: this far above the noise, and at least talkMinDb. */
  talkAboveFloorDb: 12,
  // Low enough for someone speaking softly or a little away from the phone.
  talkMinDb: -52,
  /** Talking over the tutor: this far above the noise, and at least bargeMinDb. */
  bargeAboveFloorDb: 22,
  bargeMinDb: -36,
  /** How long speech must last to open the gate. */
  openMs: 150,
  bargeMs: 350,
  /** Stays open through pauses this long (shorter once the tutor talks again). */
  // Long enough that a pause between words never cuts into an answer.
  hangMs: 1200,
  bargeHangMs: 250,
  /** Sent ahead of the speech that opened the gate. */
  prerollMs: 500,
  /** The tutor's voice can still echo this long after it stops. */
  echoTailMs: 500,
} as const;

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const LOOKUP = (() => {
  const table = new Int16Array(128).fill(-1);
  for (let i = 0; i < B64.length; i++) table[B64.charCodeAt(i)] = i;
  table['-'.charCodeAt(0)] = 62;
  table['_'.charCodeAt(0)] = 63;
  return table;
})();

/** Bytes from base64 (no padding needed). */
export function decodeBase64(text: string): Uint8Array {
  const out = new Uint8Array(Math.floor((text.length * 3) / 4));
  let bits = 0;
  let value = 0;
  let n = 0;
  for (let i = 0; i < text.length; i++) {
    const code = text.charCodeAt(i);
    const digit = code < 128 ? LOOKUP[code] : -1;
    if (digit < 0) continue;
    value = (value << 6) | digit;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[n++] = (value >> bits) & 0xff;
    }
  }
  return out.subarray(0, n);
}

const silenceCache = new Map<number, string>();

/** Base64 of `bytes` zero bytes: silence of the same length. */
export function silenceBase64(bytes: number): string {
  let cached = silenceCache.get(bytes);
  if (cached === undefined) {
    const rest = bytes % 3;
    cached = 'AAAA'.repeat(Math.floor(bytes / 3)) + (rest === 1 ? 'AA==' : rest === 2 ? 'AAA=' : '');
    if (silenceCache.size < 64) silenceCache.set(bytes, cached);
  }
  return cached;
}

/** Loudness of 16-bit little-endian mono PCM, in dBFS (-100 for silence). */
export function levelDb(pcm: Uint8Array): number {
  const samples = Math.floor(pcm.length / 2);
  if (!samples) return -100;
  let sum = 0;
  for (let i = 0; i < samples; i++) {
    let value = pcm[2 * i] | (pcm[2 * i + 1] << 8);
    if (value >= 0x8000) value -= 0x10000;
    sum += value * value;
  }
  const rms = Math.sqrt(sum / samples) / 32768;
  return rms > 0 ? Math.max(-100, 20 * Math.log10(rms)) : -100;
}

export class SpeechGate {
  private open = false;
  private floor: number = GATE.floorStartDb;
  private aboveMs = 0;
  private quietMs = 0;
  private preroll: { data: string; ms: number }[] = [];
  private prerollMs = 0;
  /** The last chunk's loudness, and whether it counted as speech (for the picture and the tutor's checks). */
  lastDb = -100;
  lastLoud = false;

  constructor(private rate = 16000) {}

  get isOpen(): boolean {
    return this.open;
  }

  get noiseDb(): number {
    return this.floor;
  }

  /** Back to closed (muted, or a fresh start); the noise estimate is kept. */
  reset() {
    this.open = false;
    this.aboveMs = 0;
    this.quietMs = 0;
    this.preroll = [];
    this.prerollMs = 0;
  }

  /**
   * Takes one base64 chunk from the microphone and returns what to send, in
   * order: the chunk itself, silence of its length, or (as the gate opens)
   * the half second before it and then the chunk.
   */
  process(data: string, tutorTalking: boolean): string[] {
    const pcm = decodeBase64(data);
    const ms = (pcm.length / 2 / this.rate) * 1000;
    if (!ms) return [];
    const db = levelDb(pcm);
    const talk = Math.max(GATE.talkMinDb, this.floor + GATE.talkAboveFloorDb);
    const barge = Math.max(GATE.bargeMinDb, this.floor + GATE.bargeAboveFloorDb);
    const threshold = tutorTalking ? barge : talk;
    this.lastDb = db;
    this.lastLoud = db >= threshold;
    if (this.open) {
      // Once the tutor talks again, only real speech keeps the gate open, so its echo can't.
      if (db >= threshold) this.quietMs = 0;
      else this.quietMs += ms;
      if (this.quietMs >= (tutorTalking ? GATE.bargeHangMs : GATE.hangMs)) this.reset();
      return [data];
    }
    const need = tutorTalking ? GATE.bargeMs : GATE.openMs;
    if (db >= threshold) this.aboveMs += ms;
    else {
      // Short dips between syllables don't start the count again.
      this.aboveMs = Math.max(0, this.aboveMs - ms);
      // Learn the room's noise while nobody is talking (not from the tutor's echo).
      if (!tutorTalking && db < talk) this.learn(db, ms);
    }
    if (this.aboveMs >= need) {
      const out = [...this.preroll.map((chunk) => chunk.data), data];
      this.open = true;
      this.quietMs = 0;
      this.aboveMs = 0;
      this.preroll = [];
      this.prerollMs = 0;
      return out;
    }
    this.preroll.push({ data, ms });
    this.prerollMs += ms;
    while (this.preroll.length > 1 && this.prerollMs - this.preroll[0].ms >= GATE.prerollMs) {
      this.prerollMs -= this.preroll[0].ms;
      this.preroll.shift();
    }
    return [silenceBase64(pcm.length)];
  }

  private learn(db: number, ms: number) {
    // Quick to follow the noise down, slow to follow it up.
    const weight = db < this.floor ? Math.min(1, ms / 300) : Math.min(1, ms / 4000);
    this.floor = Math.min(GATE.floorMaxDb, Math.max(GATE.floorMinDb, this.floor + (db - this.floor) * weight));
  }
}
