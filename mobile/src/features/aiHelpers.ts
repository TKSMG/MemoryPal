/**
 * Phone-side helpers for AI notes and questions: whether a request may be
 * made yet (consent, sign-in, internet), friendly error text, the "uses left"
 * line, AI labels, the Report message, and turning AI questions into set
 * builder rows. Pure functions, so they are tested without a phone.
 */
import { AiError, FRIENDLY, questionsToCards } from '../cloud/ai';
import type { AiNotes, AiQuestion } from '../cloud/ai';
import type { Card } from '../core/models';
import { isAiCard } from '../core/questions';
import { blankRow, Row } from './setBuilder';

/** Matches the server's default AI_DAILY_LIMIT (supabase/functions/ai). */
export const AI_DAILY_LIMIT = 20;
export const AI_TAG = 'Made with AI, check it';
export const REPORT_EMAIL = 'memorypal09@gmail.com';

export type AiGate = 'consent' | 'not_configured' | 'sign_in' | 'offline' | 'ready';

export interface GateInput {
  /** Allowed on the one-time AI screen (and not withdrawn in Settings). */
  allowed: boolean;
  signedIn: boolean;
  /** False only when the phone knows it has no internet; unknown counts as online. */
  online: boolean;
  /** The app has a MemoryPal cloud address. */
  configured: boolean;
}

/**
 * What stands between the person and an AI request, first thing first: the
 * consent screen always comes before anything is sent.
 */
export function aiGate({ allowed, signedIn, online, configured }: GateInput): AiGate {
  if (!allowed) return 'consent';
  if (!configured) return 'not_configured';
  if (!signedIn) return 'sign_in';
  if (!online) return 'offline';
  return 'ready';
}

/** True when an AI request may be sent now. */
export const canSendAi = (input: GateInput) => aiGate(input) === 'ready';

/** Unknown network state (null/undefined) counts as online, so a slow check never blocks. */
export function isOnline(state: { isConnected?: boolean | null; isInternetReachable?: boolean | null } | null | undefined): boolean {
  if (!state) return true;
  return state.isConnected !== false && state.isInternetReachable !== false;
}

const PHONE_TEXT: Record<string, string> = {
  not_signed_in: 'Sign in to your MemoryPal account to use AI. Everything else works without an account.',
  signed_out: 'Sign in to your MemoryPal account to use AI. Everything else works without an account.',
  not_configured: "AI isn't switched on for MemoryPal yet. Try again later; everything else keeps working.",
  offline: 'Needs internet. Connect to Wi-Fi or mobile data and try again.',
  bad_request: 'Type or paste some notes, or choose a PDF or photo first.',
  unsupported_file: 'AI can read PDFs and PNG, JPEG, WEBP or HEIC photos.',
};

/** A friendly sentence for anything a request can throw. */
export function aiErrorText(error: unknown): string {
  if (error instanceof AiError) return PHONE_TEXT[error.code] ?? FRIENDLY[error.code] ?? error.message ?? FRIENDLY.provider_error;
  return 'Something went wrong making that. Try again in a moment.';
}

/** The error needs the account screen (sign in, or finish two-step sign-in). */
export function needsAccount(error: unknown): boolean {
  return error instanceof AiError && ['not_signed_in', 'signed_out', 'second_step'].includes(error.code);
}

/** "12 AI uses left today", or '' when the server didn't say. */
export function remainingText(remaining: number | null | undefined): string {
  if (typeof remaining !== 'number' || !Number.isFinite(remaining)) return '';
  const left = Math.max(0, Math.trunc(remaining));
  if (left === 0) return 'No AI uses left today. They reset tomorrow.';
  return `${left} AI use${left === 1 ? '' : 's'} left today`;
}

/** The visible tag for an AI-made card, or '' for the person's own. */
export function aiLabel(card: Pick<Card, 'pathway'> | null | undefined): string {
  return card && isAiCard(card) ? AI_TAG : '';
}

/** The page a card's AI question came from ("From page 3." in its note), or null. */
export function aiPage(card: Pick<Card, 'association'>): number | null {
  const match = /From page (\d+)\./.exec(card.association ?? '');
  return match ? Number(match[1]) : null;
}

const clipText = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text);

/**
 * A mailto: link for reporting a bad AI result. There is no feedback sender
 * on the phone, so the report opens in the person's own email app, where
 * they can see and change everything before sending.
 */
export function reportMailto(what: 'card' | 'notes', content: string): string {
  const subject = what === 'card' ? 'MemoryPal: report an AI card' : 'MemoryPal: report AI notes';
  const body = [
    'What is wrong with this AI result? (for example: wrong, harmful, offensive)',
    '',
    '',
    '---',
    clipText(content.trim(), 1500),
  ].join('\n');
  return `mailto:${REPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/** A card's words for a report. */
export function cardReportText(card: Pick<Card, 'deck' | 'front' | 'back'>): string {
  return `Set: ${card.deck}\nQuestion: ${card.front}\nAnswer: ${card.back}`;
}

/** Where AI questions came from, for attaching it to the cards. */
export interface AiSourceRef {
  kind: 'text' | 'pdf' | 'image';
  /** A kept copy on this phone (file:// URI), or '' when it couldn't be kept. */
  uri: string;
}

/**
 * Set builder rows from AI questions, marked as AI-made. A photo is attached
 * to every card made from it (a photo is one page). A PDF page can't be drawn
 * as a picture on the phone, so the PDF itself is attached as the card's
 * text file and the note says which page ("From page 3.").
 */
export function rowsFromAiQuestions(questions: AiQuestion[], deck: string, title: string, source: AiSourceRef | null): Row[] {
  return questionsToCards(questions, deck, title).map(({ card, page }) => ({
    ...blankRow(card.front, card.back),
    pathway: card.pathway,
    note: card.association,
    image: source?.kind === 'image' && source.uri ? source.uri : '',
    text_file: source?.kind === 'pdf' && source.uri && page ? source.uri : '',
  }));
}


/** Notes as text for reading aloud: a section heading and its points. */
export function sectionSpeech(section: AiNotes['sections'][number]): string {
  return [section.heading, ...section.bullets].filter(Boolean).join('. ');
}
