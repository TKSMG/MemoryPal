/**
 * What the live tutor's picture shows: who is talking and how loud, right now.
 *
 * Gemini sends the tutor's speech faster than it plays (a whole sentence can
 * arrive in a fraction of a second), so measuring each piece as it arrived
 * made the circle swell ahead of the voice and then sit still while the
 * sentence was still playing. Instead each piece is measured in 20 ms steps
 * and laid on a timeline from the moment it will actually play, so the circle
 * moves with the syllables you hear. The microphone is measured as it comes
 * in, and counts as "you" only while the speech gate (speechGate.ts) lets it
 * through, which is what the tutor actually hears.
 *
 * The desktop app measures the tutor as each frame reaches the speakers
 * (memorypal/liveaudio.py), which lines up with the voice the same way.
 */
import { decodeBase64, levelDb } from './speechGate';

export const METER = {
  /** Length of one loudness step on the timeline. */
  stepMs: 20,
  /** dBFS that shows as an empty circle; 0 dBFS is a full one. */
  quietDb: -60,
  /** How long a microphone reading stays current. */
  micHoldMs: 200,
} as const;

/** 0..1 for the picture: quiet speech still shows, loud speech doesn't pin it. */
export function loudness(db: number): number {
  const level = Math.max(0, Math.min(1, (db - METER.quietDb) / -METER.quietDb));
  return level * level;
}

interface Piece {
  start: number;
  levels: number[];
}

export type Voice = { who: 'tutor' | 'you' | null; level: number };

export class VoiceMeter {
  private pieces: Piece[] = [];
  private until = 0;
  private micLevel = 0;
  private micAt = -Infinity;
  private micOpen = false;

  constructor(private rate = 24000) {}

  /** The tutor's speech, handed to the player now; returns when it will finish (ms). */
  speech(base64: string, now: number): number {
    return this.speechPcm(decodeBase64(base64), now);
  }

  speechPcm(pcm: Uint8Array, now: number): number {
    const stepBytes = Math.max(2, Math.round((this.rate * METER.stepMs) / 1000) * 2);
    const levels: number[] = [];
    for (let at = 0; at + 1 < pcm.length; at += stepBytes) levels.push(loudness(levelDb(pcm.subarray(at, Math.min(pcm.length, at + stepBytes)))));
    const start = Math.max(now, this.until);
    this.until = start + ((pcm.length / 2) * 1000) / this.rate;
    if (levels.length) this.pieces.push({ start, levels });
    // Pieces that finished playing a while ago aren't needed any more.
    while (this.pieces.length && this.pieces[0].start + this.pieces[0].levels.length * METER.stepMs < now - 1000) this.pieces.shift();
    return this.until;
  }

  /** The learner talked over the tutor: speech not yet played is dropped. */
  clearSpeech(now: number) {
    this.until = Math.min(this.until, now);
    this.pieces = this.pieces.filter((piece) => piece.start <= now);
  }

  /** When the speech handed over so far will have finished playing. */
  get speechUntil(): number {
    return this.until;
  }

  /** A microphone reading; `open` is whether the gate let it through. */
  mic(db: number, open: boolean, now: number) {
    this.micLevel = loudness(db);
    this.micAt = now;
    this.micOpen = open;
  }

  micOff() {
    this.micLevel = 0;
    this.micOpen = false;
  }

  /** The tutor's loudness at `now` on the timeline (0 when it isn't speaking). */
  tutorLevel(now: number): number {
    if (now >= this.until) return 0;
    for (let i = this.pieces.length - 1; i >= 0; i--) {
      const piece = this.pieces[i];
      if (piece.start > now) continue;
      const step = Math.floor((now - piece.start) / METER.stepMs);
      return step < piece.levels.length ? piece.levels[step] : 0;
    }
    return 0;
  }

  /** Who the picture shows now, and how big. */
  voice(now: number): Voice {
    if (now < this.until) return { who: 'tutor', level: this.tutorLevel(now) };
    const fresh = now - this.micAt < METER.micHoldMs;
    if (fresh && this.micOpen) return { who: 'you', level: this.micLevel };
    return { who: null, level: 0 };
  }
}
