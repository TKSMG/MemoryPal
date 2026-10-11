/** Browsers have no secure keychain; the web build keeps the sign-in for this tab session only. */
export async function readSecret(key: string): Promise<string | null> {
  try {
    return globalThis.sessionStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export async function writeSecret(key: string, value: string | null): Promise<void> {
  try {
    if (value === null) globalThis.sessionStorage?.removeItem(key);
    else globalThis.sessionStorage?.setItem(key, value);
  } catch {
    // private browsing: stay signed in until the page closes
  }
}
