/**
 * How often a password appears in known data breaches (Pwned Passwords),
 * like security.pwned_count on the desktop. k-anonymity: only the first five
 * characters of the password's SHA-1 hash leave the phone. Returns null when
 * the service can't be reached, so the check never blocks signing up.
 */
import * as Crypto from 'expo-crypto';

export async function pwnedCount(password: string, fetcher: typeof fetch = (...args) => fetch(...args)): Promise<number | null> {
  try {
    const digest = (await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA1, password ?? '')).toUpperCase();
    const prefix = digest.slice(0, 5);
    const suffix = digest.slice(5);
    const response = await fetcher(`https://api.pwnedpasswords.com/range/${prefix}`, { headers: { 'Add-Padding': 'true' } });
    if (!response.ok) return null;
    for (const line of (await response.text()).split(/\r?\n/)) {
      const [candidate, count] = line.trim().split(':');
      if (candidate === suffix) return Number(count) || 0;
    }
    return 0;
  } catch {
    return null;
  }
}

export function leakedMessage(count: number): string {
  return `This password has appeared in data breaches ${count.toLocaleString('en-US')} times, so attackers try it first. Please choose a different one.`;
}
