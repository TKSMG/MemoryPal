/**
 * Whether a page has been laid out yet, so the launch screen can stay up
 * until there is a real page behind it. Hiding it earlier (when the fonts
 * and saved sign-in were ready, but before the first page had drawn) showed
 * the bare window behind the app for an instant on a cold start: a white
 * flash, since that window is white until the app sets its colour.
 */
let drawn = false;
const listeners = new Set<() => void>();

/** Called from every page's first layout (Screen and ScreenList). */
export function markPageDrawn() {
  if (drawn) return;
  drawn = true;
  listeners.forEach((listener) => listener());
}

export function pageDrawn(): boolean {
  return drawn;
}

export function onPageDrawn(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
