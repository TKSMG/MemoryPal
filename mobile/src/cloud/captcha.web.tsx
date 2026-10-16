/** The web build (used for store screenshots) has no web view to run the check in; it skips it. */
import type { ReactNode } from 'react';

export function useCaptcha(): { request?: () => Promise<string>; sheet: ReactNode } {
  return { request: undefined, sheet: null };
}
