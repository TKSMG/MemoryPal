/**
 * Small helpers for raw audio in live Talk-back: base64 for the WebSocket,
 * 24 kHz -> 16 kHz resampling (Gemini speaks at 24 kHz; the phone's
 * echo-cancelling player takes 16 kHz), and UTF-8 for binary frames.
 * All audio is 16-bit little-endian mono PCM.
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
const LOOKUP = (() => {
  const table = new Int16Array(128).fill(-1);
  for (let i = 0; i < ALPHABET.length; i++) table[ALPHABET.charCodeAt(i)] = i;
  table['-'.charCodeAt(0)] = 62; // base64url too
  table['_'.charCodeAt(0)] = 63;
  return table;
})();

export function bytesToBase64(bytes: Uint8Array): string {
  const out: string[] = [];
  let i = 0;
  for (; i + 2 < bytes.length; i += 3) {
    const n = (bytes[i] << 16) | (bytes[i + 1] << 8) | bytes[i + 2];
    out.push(ALPHABET[n >> 18], ALPHABET[(n >> 12) & 63], ALPHABET[(n >> 6) & 63], ALPHABET[n & 63]);
  }
  if (i < bytes.length) {
    const n = (bytes[i] << 16) | ((bytes[i + 1] ?? 0) << 8);
    out.push(ALPHABET[n >> 18], ALPHABET[(n >> 12) & 63], i + 1 < bytes.length ? ALPHABET[(n >> 6) & 63] : '=', '=');
  }
  return out.join('');
}

export function base64ToBytes(text: string): Uint8Array {
  const clean = text.replace(/[^A-Za-z0-9+/\-_]/g, '');
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4));
  let bits = 0;
  let value = 0;
  let at = 0;
  for (let i = 0; i < clean.length; i++) {
    const digit = LOOKUP[clean.charCodeAt(i)];
    if (digit < 0) continue;
    value = (value << 6) | digit;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out[at++] = (value >> bits) & 0xff;
    }
  }
  return out.subarray(0, at);
}

/** Text from a UTF-8 frame (TextDecoder when there is one). */
export function utf8(bytes: Uint8Array): string {
  const Decoder = (globalThis as { TextDecoder?: new () => { decode(input: Uint8Array): string } }).TextDecoder;
  if (Decoder) return new Decoder().decode(bytes);
  let out = '';
  for (let i = 0; i < bytes.length; ) {
    const b = bytes[i++];
    let code = b;
    if (b >= 0xf0) code = ((b & 0x07) << 18) | ((bytes[i++] & 0x3f) << 12) | ((bytes[i++] & 0x3f) << 6) | (bytes[i++] & 0x3f);
    else if (b >= 0xe0) code = ((b & 0x0f) << 12) | ((bytes[i++] & 0x3f) << 6) | (bytes[i++] & 0x3f);
    else if (b >= 0xc0) code = ((b & 0x1f) << 6) | (bytes[i++] & 0x3f);
    out += String.fromCodePoint(code);
  }
  return out;
}

/**
 * Streams 16-bit PCM from one rate to another with linear interpolation,
 * carrying the position across chunks so the joins don't click. A byte left
 * over from an odd-length chunk is kept for the next one.
 */
export class Resampler {
  private position = 0; // where the next output sample falls, in input samples from `last`
  private last: number | null = null;
  private spare: number | null = null;

  constructor(private from: number, private to: number) {}

  reset() {
    this.position = 0;
    this.last = null;
    this.spare = null;
  }

  push(chunk: Uint8Array): Uint8Array {
    let bytes = chunk;
    if (this.spare !== null) {
      bytes = new Uint8Array(chunk.length + 1);
      bytes[0] = this.spare;
      bytes.set(chunk, 1);
      this.spare = null;
    }
    if (bytes.length % 2) {
      this.spare = bytes[bytes.length - 1];
      bytes = bytes.subarray(0, bytes.length - 1);
    }
    const count = bytes.length / 2;
    if (!count) return new Uint8Array(0);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    // Input samples with the previous chunk's last one in front: index 0 is `last`.
    const offset = this.last === null ? 0 : 1;
    const sample = (i: number) => (i < offset ? (this.last as number) : view.getInt16((i - offset) * 2, true));
    const total = count + offset;
    if (this.last === null) this.position = 0;
    const step = this.from / this.to;
    const out: number[] = [];
    let at = this.position;
    while (at <= total - 1) {
      const base = Math.floor(at);
      const frac = at - base;
      const a = sample(base);
      const b = base + 1 < total ? sample(base + 1) : a;
      out.push(Math.round(a + (b - a) * frac));
      at += step;
    }
    // Carry on from the last input sample next time.
    this.position = at - (total - 1);
    this.last = sample(total - 1);
    const result = new Uint8Array(out.length * 2);
    const outView = new DataView(result.buffer);
    out.forEach((value, i) => outView.setInt16(i * 2, Math.max(-32768, Math.min(32767, value)), true));
    return result;
  }
}
