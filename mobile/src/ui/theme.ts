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
  /** Highlighted words in notes, under ink text. */
  mark: string;
  again: [string, string];
  review: [string, string];
  good: [string, string];
  easy: [string, string];
  focus: string;
  /** Outline marking Smart Check's suggested rating: at least 3:1 against the page and every rating fill. */
  suggested: string;
  tabBar: string;
}

// Shared with the desktop palette (latest_app/memorypal/constants.py): warm
// paper and ink in light mode, neutral graphite in dark mode, one pine accent.
const LIGHT: Palette = {
  // Grouped-list paper: white groups sit on it without needing borders.
  bg: '#f2efe9',
  surface: '#fffdf9',
  surfaceSoft: '#ece7de',
  alt: '#e4ded2',
  ink: '#1e1d1a',
  muted: '#5c574e',
  line: '#e2ddd2',
  inputBorder: '#8a8476',
  primary: '#146b5a',
  primaryPressed: '#0e5547',
  onPrimary: '#ffffff',
  link: '#146b5a',
  green: '#2f7323',
  orange: '#b5541a',
  violet: '#7d4a72',
  danger: '#b42a22',
  dangerPressed: '#97231c',
  dangerText: '#b42a22',
  onDanger: '#ffffff',
  warm: '#fbf0de',
  warmText: '#94500e',
  mark: '#fae38a',
  again: ['#fbe6e1', '#a52a1d'],
  review: ['#f9edcf', '#7f5100'],
  good: ['#e3f1df', '#2b6a21'],
  easy: ['#e2ecf2', '#2a5c7d'],
  focus: '#d9821f',
  suggested: '#a8530c',
  tabBar: '#fffdf9',
};

const DARK: Palette = {
  bg: '#141413',
  surface: '#1d1d1b',
  surfaceSoft: '#2d2c29',
  alt: '#363531',
  ink: '#eeebe4',
  muted: '#aaa59b',
  line: '#34332f',
  inputBorder: '#7c786e',
  primary: '#63c9ae',
  primaryPressed: '#48b496',
  onPrimary: '#14130f',
  link: '#7fd6bf',
  green: '#86d27a',
  orange: '#f0a456',
  violet: '#d0a2c6',
  danger: '#d0453a',
  dangerPressed: '#b23a30',
  dangerText: '#ff9585',
  onDanger: '#ffffff',
  warm: '#2c2317',
  warmText: '#f2b872',
  mark: '#5c4a12',
  again: ['#3a1d1a', '#ff9585'],
  review: ['#372b13', '#f2c560'],
  good: ['#1c3320', '#8cdb80'],
  easy: ['#1a2a35', '#8fc4e6'],
  focus: '#f2c14e',
  suggested: '#f2c14e',
  tabBar: '#181817',
};

const HIGH_CONTRAST_LIGHT: Partial<Palette> = { bg: '#f1eee7', muted: '#35322c', line: '#9c9584', primary: '#0b5446', primaryPressed: '#073f34', link: '#073f34' };
const HIGH_CONTRAST_DARK: Partial<Palette> = { bg: '#0b0b0a', surface: '#151514', muted: '#dcd8cf', line: '#838076', primary: '#8be0c8', link: '#a6ebd8' };

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
