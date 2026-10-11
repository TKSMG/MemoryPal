/**
 * Design tokens, shared with the desktop design system (DESIGN_NOTES.md):
 * every text/background pair meets WCAG AA, filled controls pick their text
 * colour by contrast, and sizes respect both the in-app text size and the
 * phone's own font-size setting.
 */
import { useColorScheme } from 'react-native';

import { useStore, usePrefs } from '../state/AppState';

export interface Palette {
  bg: string;
  surface: string;
  surfaceSoft: string;
  alt: string;
  ink: string;
  muted: string;
  line: string;
  primary: string;
  primaryPressed: string;
  onPrimary: string;
  link: string;
  green: string;
  orange: string;
  violet: string;
  danger: string;
  onDanger: string;
  warm: string;
  warmText: string;
  again: [string, string];
  review: [string, string];
  good: [string, string];
  easy: [string, string];
  focus: string;
  tabBar: string;
}

const LIGHT: Palette = {
  bg: '#f6f8fc',
  surface: '#ffffff',
  surfaceSoft: '#eef3fb',
  alt: '#e9f1fb',
  ink: '#172033',
  muted: '#56657d',
  line: '#d8e2ef',
  primary: '#2563eb',
  primaryPressed: '#1d4ed8',
  onPrimary: '#ffffff',
  link: '#2563eb',
  green: '#15803d',
  orange: '#c2410c',
  violet: '#7c3aed',
  danger: '#c62828',
  onDanger: '#ffffff',
  warm: '#fff4e5',
  warmText: '#a45b09',
  again: ['#ffe7e3', '#b42318'],
  review: ['#fff0cc', '#8f5600'],
  good: ['#e4f7ed', '#157a45'],
  easy: ['#e4efff', '#2467b7'],
  focus: '#f59e0b',
  tabBar: '#ffffff',
};

const DARK: Palette = {
  bg: '#111827',
  surface: '#192338',
  surfaceSoft: '#22304a',
  alt: '#273852',
  ink: '#edf2fb',
  muted: '#aeb8cb',
  line: '#33445f',
  primary: '#65afff',
  primaryPressed: '#3f8ee6',
  onPrimary: '#0b1020',
  link: '#8cc4ff',
  green: '#37d67a',
  orange: '#ffab3d',
  violet: '#c084fc',
  danger: '#dc2626',
  onDanger: '#ffffff',
  warm: '#2a1f14',
  warmText: '#ffb572',
  again: ['#3a1a1a', '#ff8a80'],
  review: ['#3a2c10', '#ffcf5c'],
  good: ['#123423', '#5be08c'],
  easy: ['#12233f', '#7fbfff'],
  focus: '#fbbf24',
  tabBar: '#0f1729',
};

const HIGH_CONTRAST_LIGHT: Partial<Palette> = { bg: '#eef3fb', muted: '#25324a', line: '#8da4bf', primary: '#005fcc', primaryPressed: '#004b9f', link: '#004b9f' };
const HIGH_CONTRAST_DARK: Partial<Palette> = { bg: '#0b1220', surface: '#101b2d', muted: '#d5dfef', line: '#74859f', primary: '#8dccff', link: '#a9d8ff' };

const TEXT_SCALE = { Comfort: 1, Large: 1.15, 'Extra Large': 1.3 } as const;

export interface Theme {
  dark: boolean;
  colors: Palette;
  /** In-app text size multiplier (the phone's font setting applies on top). */
  scale: number;
  font: (size: number) => number;
  space: (units: number) => number;
  radius: number;
  reduceMotion: boolean;
  simple: boolean;
  /** Plain-language variant when "simple language" is on. */
  plain: (normal: string, simple: string) => string;
}

export function makeTheme(dark: boolean, textSize: keyof typeof TEXT_SCALE, highContrast: boolean, reduceMotion: boolean, simple: boolean): Theme {
  const colors = { ...(dark ? DARK : LIGHT), ...(highContrast ? (dark ? HIGH_CONTRAST_DARK : HIGH_CONTRAST_LIGHT) : {}) };
  const scale = TEXT_SCALE[textSize] ?? 1;
  return {
    dark,
    colors,
    scale,
    font: (size) => Math.round(size * scale),
    space: (units) => units * 4,
    radius: 14,
    reduceMotion,
    simple,
    plain: (normal, simpleText) => (simple ? simpleText : normal),
  };
}

export function useTheme(): Theme {
  const store = useStore();
  const [prefs] = usePrefs();
  const system = useColorScheme();
  const dark = prefs.theme === 'dark' || (prefs.theme === 'system' && system === 'dark');
  const a = store.accessibility;
  return makeTheme(dark, a.text_size, a.high_contrast, a.reduce_motion, a.simple_language);
}
