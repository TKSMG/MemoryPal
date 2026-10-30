/**
 * Small helpers for raw audio in live Talk-back: how long a base64 chunk of
 * 16-bit PCM plays for, and UTF-8 for binary WebSocket frames.
 */

/** Bytes a base64 string decodes to (without decoding it). */
export function base64Length(text: string): number {
  const clean = text.replace(/[^A-Za-z0-9+/=_-]/g, '');
  const padding = clean.endsWith('==') ? 2 : clean.endsWith('=') ? 1 : 0;
  return Math.max(0, Math.floor((clean.length * 3) / 4) - padding);
}

/** Milliseconds a base64 chunk of 16-bit mono PCM at `rate` plays for. */
export function pcmMs(base64: string, rate: number): number {
  return base64Length(base64) / ((rate * 2) / 1000);
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
