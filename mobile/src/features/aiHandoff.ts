/**
 * Passing notes to the Make with AI screen and AI-made rows back to the set
 * builder, in memory (too long for a route parameter, and never saved).
 */
import type { Row } from './setBuilder';

let notesForAi = '';
let rowsForBuilder: Row[] = [];
let builderMessage = '';

export function sendNotesToAi(text: string) {
  notesForAi = text;
}

export function takeNotesForAi(): string {
  const text = notesForAi;
  notesForAi = '';
  return text;
}

export function sendRowsToBuilder(rows: Row[], message = '') {
  rowsForBuilder = [...rowsForBuilder, ...rows];
  builderMessage = message;
}

/** The rows waiting for the set builder and a line to show with them. */
export function takeRowsForBuilder(): { rows: Row[]; message: string } {
  const taken = { rows: rowsForBuilder, message: builderMessage };
  rowsForBuilder = [];
  builderMessage = '';
  return taken;
}
