/** Welcome choices: who is using MemoryPal, and the comfort defaults each sets. */
import { Accessibility, PersonaKey } from './store';

export interface Persona {
  key: PersonaKey;
  title: string;
  body: string;
  accessibility: Partial<Accessibility>;
  /** Study modes shown first on Today. */
  modes: string[];
}

export const PERSONAS: Persona[] = [
  {
    key: 'student',
    title: "I'm studying",
    body: 'School, university, exams, or learning a language. Turn notes into cards and practise on a schedule.',
    accessibility: {},
    modes: ['quick10', 'deep', 'cram', 'notes'],
  },
  {
    key: 'everyday',
    title: 'Help with everyday memory',
    body: 'Names, routines, where things are kept, and gentle daily practice. Larger text and a calmer pace.',
    accessibility: { text_size: 'Large', simple_language: true, more_time: true, reduce_motion: true },
    modes: ['gentle', 'puzzles', 'listen', 'everyday'],
  },
  {
    key: 'caregiver',
    title: "I'm helping someone else",
    body: 'Set up cards and reminders for a family member or someone you care for.',
    accessibility: { text_size: 'Large', simple_language: true, more_time: true, caregiver_mode: true },
    modes: ['everyday', 'gentle', 'progress', 'puzzles'],
  },
  {
    key: 'general',
    title: 'Just exploring',
    body: 'Curious about memory training. See the main tools and try a few puzzles.',
    accessibility: {},
    modes: ['quick10', 'technique', 'puzzles', 'plan'],
  },
];

/** Settings any persona changes; choosing again resets these before applying. */
export const MANAGED_SETTINGS = [...new Set(PERSONAS.flatMap((persona) => Object.keys(persona.accessibility)))] as (keyof Accessibility)[];

export function persona(key: string | null | undefined): Persona {
  return PERSONAS.find((item) => item.key === key) ?? PERSONAS[3];
}
