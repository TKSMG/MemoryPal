/** Where plan steps and study modes lead on the phone. */
import { Href, router } from 'expo-router';

import { PlanStep } from '../core/planning';
import { notify } from './feedback';

export function openStep(step: PlanStep) {
  const deck = step.deck ? `&deck=${encodeURIComponent(step.deck)}` : '';
  switch (step.view) {
    case 'review':
      return router.push(`/review?mode=due${deck}` as Href);
    case 'focus':
    case 'shuffle':
    case 'testing':
      return router.push(`/review?mode=weak${deck}` as Href);
    case 'quiz':
      return router.push(`/quiz?${step.quiz_mode === 'self' ? 'mode=self' : 'mode=choices'}${deck}` as Href);
    case 'capture':
      return router.push('/add');
    case 'tools':
      return router.push('/practice');
    case 'games':
      return router.push('/puzzle?kind=sequence');
    case 'stats':
      return router.push('/progress');
    case 'break':
      return notify('Rest break', step.blurb);
  }
}

export interface Mode {
  key: string;
  icon: string;
  title: string;
  body: string;
  go: () => void;
}

export const MODES: Record<string, Omit<Mode, 'key'>> = {
  quick10: { icon: 'flash-outline', title: 'Quick 10', body: 'Ten cards: due first, then shaky ones.', go: () => router.push('/review?mode=quick') },
  deep: { icon: 'library-outline', title: 'Deep study', body: 'Plan a full hour with breaks.', go: () => router.push('/plan?minutes=60&goal=Long-term%20retention') },
  cram: { icon: 'timer-outline', title: 'Exam cram', body: 'Weak cards first, aimed at the test.', go: () => router.push('/plan?minutes=45&goal=Cram') },
  notes: { icon: 'document-text-outline', title: 'Add notes', body: "Turn today's notes into cards.", go: () => router.push('/add?mode=notes') },
  gentle: { icon: 'leaf-outline', title: 'Gentle review', body: 'People, routines and places, calmly.', go: () => router.push('/review?mode=gentle') },
  puzzles: { icon: 'extension-puzzle-outline', title: 'Daily puzzle', body: 'A short, friendly memory game.', go: () => router.push('/puzzle?kind=sequence') },
  listen: { icon: 'volume-high-outline', title: 'Listen and practise', body: 'Each question is read aloud.', go: () => router.push('/review?mode=due&read=1') },
  everyday: { icon: 'people-outline', title: 'Add a memory card', body: 'A person, routine, place or reminder.', go: () => router.push('/add?mode=everyday') },
  progress: { icon: 'stats-chart-outline', title: 'Check progress', body: 'How practice is going this week.', go: () => router.push('/progress') },
  technique: { icon: 'bulb-outline', title: 'Try a technique', body: 'Memory palaces, stories, peg lists.', go: () => router.push('/practice') },
  plan: { icon: 'map-outline', title: 'Build a plan', body: 'Your time and goal become a path.', go: () => router.push('/plan') },
};
