/**
 * Design tokens, shared with the desktop design system (docs/DESIGN_NOTES.md):
 * every text/background pair meets WCAG AA, filled controls pick their text
 * colour by contrast, and sizes respect both the in-app text size and the
 * phone's own font-size setting.
 */
import { createContext, createElement, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AccessibilityInfo, useColorScheme } from 'react-native';

import { useStore, usePrefs } from '../state/AppState';

export interface Palette {
  bg: string;
  surface: string;
  surfaceSoft: string;
  alt: string;
  ink: string;
  muted: string;
  line: string;
  /** Text-field outline: meets the 3:1 non-text contrast that `line` (a divider) doesn't. */
  inputBorder: string;
  primary: string;
  primaryPressed: string;
  onPrimary: string;
  link: string;
  green: string;
  orange: string;
  violet: string;
  danger: string;
  dangerPressed: string;
  /** Destructive text on the page or a card (a quiet Delete). */
  dangerText: string;
  onDanger: string;
  warm: string;
  warmText: string;
  again: [string, string];
  review: [string, string];
  good: [string, string];
  easy: [string, string];
  focus: string;
  /** Outline marking Smart Check's suggested rating: at least 3:1 against the page and every rating fill. */
  suggested: string;
  tabBar: string;
}

const LIGHT: Palette = {
  // Grouped-list grey: white groups sit on it without needing borders.
  bg: '#f2f4f7',
  surface: '#ffffff',
  surfaceSoft: '#e7ebf1',
  alt: '#e9f1fb',
  ink: '#172033',
  muted: '#56657d',
  line: '#d8e2ef',
  inputBorder: '#7d8ca3',
  primary: '#2563eb',
  primaryPressed: '#1d4ed8',
  onPrimary: '#ffffff',
  link: '#2563eb',
  green: '#15803d',
  orange: '#c2410c',
  violet: '#7c3aed',
  danger: '#c62828',
  dangerPressed: '#a82020',
  dangerText: '#c62828',
  onDanger: '#ffffff',
  warm: '#fff4e5',
  warmText: '#a45b09',
  again: ['#ffe7e3', '#b42318'],
  review: ['#fff0cc', '#8f5600'],
  good: ['#e4f7ed', '#157a45'],
  easy: ['#e4efff', '#2467b7'],
  focus: '#f59e0b',
  suggested: '#b45309',
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
  inputBorder: '#6f84a3',
  primary: '#65afff',
  primaryPressed: '#3f8ee6',
  onPrimary: '#0b1020',
  link: '#8cc4ff',
  green: '#37d67a',
  orange: '#ffab3d',
  violet: '#c084fc',
  danger: '#dc2626',
  dangerPressed: '#b91c1c',
  dangerText: '#ff8a80',
  onDanger: '#ffffff',
  warm: '#2a1f14',
  warmText: '#ffb572',
  again: ['#3a1a1a', '#ff8a80'],
  review: ['#3a2c10', '#ffcf5c'],
  good: ['#123423', '#5be08c'],
  easy: ['#12233f', '#7fbfff'],
  focus: '#fbbf24',
  suggested: '#fbbf24',
  tabBar: '#0f1729',
};

const HIGH_CONTRAST_LIGHT: Partial<Palette> = { bg: '#eef3fb', muted: '#25324a', line: '#8da4bf', primary: '#005fcc', primaryPressed: '#004b9f', link: '#004b9f' };
const HIGH_CONTRAST_DARK: Partial<Palette> = { bg: '#0b1220', surface: '#101b2d', muted: '#d5dfef', line: '#74859f', primary: '#8dccff', link: '#a9d8ff' };

/**
 * The pressed look of a filled control: about 8% darker in light mode and 8%
 * lighter in dark mode, so a press shows even with Reduce Motion's scale off.
 */
export function pressedShade(hex: string, dark: boolean, amount = 0.08): string {
  const match = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!match) return hex;
  const value = parseInt(match[1], 16);
  const target = dark ? 255 : 0;
  const channel = (shift: number) => {
    const c = (value >> shift) & 255;
    return Math.round(c + (target - c) * amount).toString(16).padStart(2, '0');
  };
  return `#${channel(16)}${channel(8)}${channel(0)}`;
}

const TEXT_SCALE = { Comfort: 1, Large: 1.15, 'Extra Large': 1.3 } as const;

export interface Theme {
  dark: boolean;
  colors: Palette;
  /** In-app text size multiplier (the phone's font setting applies on top). */
  scale: number;
  font: (size: number) => number;
  /** Icon size that grows with the in-app text size, so symbols stay in step with their labels. */
  icon: (size: number) => number;
  space: (units: number) => number;
  /** Controls (buttons, fields, banners). */
  radius: number;
  /** Groups and cards. */
  radiusLarge: number;
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
    icon: (size) => Math.round(size * scale),
    space: (units) => units * 4,
    radius: 12,
    radiusLarge: 16,
    reduceMotion,
    simple,
    plain: (normal, simpleText) => (simple ? simpleText : normal),
  };
}

const ThemeContext = createContext<Theme | null>(null);

/** Follows the phone's own Reduce Motion setting as well as the in-app one. */
function useSystemReduceMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    let live = true;
    AccessibilityInfo.isReduceMotionEnabled().then((value) => live && setReduce(value)).catch(() => undefined);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduce);
    return () => {
      live = false;
      subscription.remove();
    };
  }, []);
  return reduce;
}

/**
 * Works the theme out once for the whole app. Every label and button reads it
 * from context, so a store change (a sync, a rating) re-renders only the
 * screens that show store data, not every leaf component on all five tabs.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const store = useStore();
  const [prefs] = usePrefs();
  const system = useColorScheme();
  const systemReduceMotion = useSystemReduceMotion();
  const dark = prefs.theme === 'dark' || (prefs.theme === 'system' && system === 'dark');
  const a = store.accessibility;
  const reduceMotion = a.reduce_motion || systemReduceMotion;
  const theme = useMemo(
    () => makeTheme(dark, a.text_size, a.high_contrast, reduceMotion, a.simple_language),
    [dark, a.text_size, a.high_contrast, reduceMotion, a.simple_language],
  );
  return createElement(ThemeContext.Provider, { value: theme }, children);
}

export function useTheme(): Theme {
  const theme = useContext(ThemeContext);
  if (!theme) throw new Error('useTheme must be used inside ThemeProvider');
  return theme;
}
