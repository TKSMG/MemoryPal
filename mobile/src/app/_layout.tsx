import Ionicons from '@expo/vector-icons/Ionicons';
import { DarkTheme, DefaultTheme, Href, router, Stack, ThemeProvider as NavigationTheme } from 'expo-router';
import { useFonts } from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as SystemUI from 'expo-system-ui';
import { useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { AppState as RNAppState, Platform, Pressable, Text } from 'react-native';

import { normalizeSettings } from '../features/notifications';
import { AppStateProvider, usePrefs, useStore, useSync } from '../state/AppState';
import { onReminderTapped, refreshReminders, setUpNotifications } from '../state/reminders';
import { StackHeader } from '../ui/StackHeader';
import { onPageDrawn, pageDrawn } from '../ui/launch';
import { ThemeProvider, useTheme } from '../ui/theme';

// The launch screen stays up until the first page can be drawn whole (see
// RootLayout), instead of the page appearing and then rearranging itself.
SplashScreen.preventAutoHideAsync().catch(() => undefined);

/** iOS sheets get a way out in the bar; Android has its back button and arrow. */
function SheetButton({ label, bold }: { label: string; bold?: boolean }) {
  const theme = useTheme();
  return (
    <Pressable onPress={() => router.back()} accessibilityRole="button" hitSlop={12}>
      <Text maxFontSizeMultiplier={1.6} style={{ color: theme.colors.link, fontSize: 17, fontWeight: bold ? '600' : '400' }}>{label}</Text>
    </Pressable>
  );
}

/**
 * The sheet's Cancel or Done, on iOS only. iOS 26 puts a grey glass pill
 * behind any custom bar button, which looked like a stray white background
 * behind the teal text; `hidesSharedBackground` leaves plain text, as on
 * earlier iOS and everywhere else in the app.
 */
function sheetButton(label: string, bold?: boolean) {
  if (Platform.OS !== 'ios') return undefined;
  return () => [{ type: 'custom' as const, element: <SheetButton label={label} bold={bold} />, hidesSharedBackground: true }];
}

/** Pages shown as sheets keep the phone's own bar (see StackHeader). */
const SHEETS = new Set(['add', 'card/[id]', 'ai-consent']);

/**
 * Today's tabs sit under every page, even one opened straight from a reminder
 * or a link, so its bar always has a way back instead of a dead end.
 */
export const unstable_settings = { anchor: '(tabs)' };

/**
 * Keeps the next week of study reminders and the icon badge up to date:
 * rescheduled whenever MemoryPal goes to the background (after studying)
 * and when the notification settings change. A tapped one opens its screen.
 */
function Reminders() {
  const store = useStore();
  const [prefs] = usePrefs();
  const { reminders, reminder_time: time, badge, notify_kinds: kinds, quiet_hours: quiet, one_a_day: oneADay } = prefs;
  const kindsKey = kinds.join(',');
  useEffect(() => {
    setUpNotifications();
    return onReminderTapped((url) => router.push(url as Href));
  }, []);
  useEffect(() => {
    const settings = normalizeSettings({ enabled: reminders, time, kinds: kindsKey.split(','), quiet, one_a_day: oneADay });
    const refresh = () => refreshReminders(store, { settings, badge });
    refresh();
    const subscription = RNAppState.addEventListener('change', (state) => {
      if (state !== 'active') refresh();
    });
    return () => subscription.remove();
  }, [store, reminders, time, badge, kindsKey, quiet, oneADay]);
  return null;
}

function RootStack() {
  const theme = useTheme();
  const c = theme.colors;
  // Everything behind the screens takes the page colour too: the phone's own
  // root view and the navigator's theme (it fills the edges while a page
  // slides in or a sheet opens, and was white).
  useEffect(() => {
    SystemUI.setBackgroundColorAsync(c.bg).catch(() => undefined);
  }, [c.bg]);
  const navigationTheme = useMemo(() => {
    const base = theme.dark ? DarkTheme : DefaultTheme;
    return { ...base, dark: theme.dark, colors: { ...base.colors, background: c.bg, card: c.bg, text: c.ink, border: c.line, primary: c.link, notification: c.primary } };
  }, [theme.dark, c.bg, c.ink, c.line, c.link, c.primary]);
  return (
    <NavigationTheme value={navigationTheme}>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />
      <Reminders />
      <Stack
        screenOptions={({ route }) => ({
          // Pushed pages get the app's own bar, laid out with the page before
          // it slides in, instead of the phone's bar settling into place
          // after the slide (see StackHeader).
          header: SHEETS.has(route.name) ? undefined : StackHeader,
          headerStyle: { backgroundColor: c.bg },
          headerTintColor: c.link,
          headerTitleStyle: { color: c.ink, fontWeight: '600' },
          headerShadowVisible: false,
          // The tab group has no title, so a back label would read "(tabs)".
          headerBackButtonDisplayMode: 'minimal',
          contentStyle: { backgroundColor: c.bg },
          // Screens underneath the one on top stop redrawing until they're
          // back in front.
          freezeOnBlur: true,
          // Reduce Motion swaps the slide for a cross-fade, so a change of
          // screen is still visible without the movement.
          animation: theme.reduceMotion ? 'fade' : 'default',
        })}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="start" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="review" options={{ title: 'Review' }} />
        <Stack.Screen name="talkback" options={{ title: 'Talk-back study' }} />
        <Stack.Screen name="talk-live" options={{ title: 'Live tutor' }} />
        <Stack.Screen name="quiz" options={{ title: 'Quick quiz' }} />
        <Stack.Screen name="add" options={{ title: 'New set', presentation: 'modal', unstable_headerRightItems: sheetButton('Done', true) }} />
        <Stack.Screen name="card/[id]" options={{ title: 'Edit card', presentation: 'modal', unstable_headerLeftItems: sheetButton('Cancel') }} />
        <Stack.Screen name="deck/[name]" options={{ title: 'Set' }} />
        <Stack.Screen name="notes/index" options={{ title: 'Saved notes' }} />
        <Stack.Screen name="notes/[id]" options={{ title: 'Notes' }} />
        <Stack.Screen name="plan" options={{ title: 'Study plan' }} />
        <Stack.Screen name="puzzle" options={{ title: 'Puzzle' }} />
        <Stack.Screen name="repetition" options={{ title: 'Repetition path' }} />
        <Stack.Screen name="settings" options={{ title: 'Settings' }} />
        <Stack.Screen name="ai" options={{ title: 'Make with AI' }} />
        <Stack.Screen name="ai-consent" options={{ title: 'AI features', presentation: 'modal', unstable_headerLeftItems: sheetButton('Cancel') }} />
        <Stack.Screen name="account" options={{ title: 'Account & sync' }} />
      </Stack>
    </NavigationTheme>
  );
}

/** Longest the launch screen waits, so a slow phone never looks stuck. */
const SPLASH_LIMIT_MS = 2500;

/**
 * Hides the launch screen once the first page is on screen as it will stay:
 * the icon font is loaded (until then every icon drew as nothing and popped
 * in a moment later, pushing titles and rows sideways), the remembered
 * sign-in is read (until then the tabs show a blank page), and a page has
 * been laid out behind it (before that, the bare window showed through for
 * an instant on a cold start, as a white flash).
 */
function LaunchScreen({ fontsReady, late }: { fontsReady: boolean; late: boolean }) {
  const sync = useSync();
  const drawn = useSyncExternalStore(onPageDrawn, pageDrawn);
  const ready = late || (fontsReady && drawn && (!sync.configured || sync.account.restored));
  useEffect(() => {
    if (!ready) return;
    // One frame later, so the page is on screen before the launch screen goes.
    const frame = requestAnimationFrame(() => {
      SplashScreen.hideAsync().catch(() => undefined);
    });
    return () => cancelAnimationFrame(frame);
  }, [ready]);
  return null;
}

export default function RootLayout() {
  const [fontsLoaded, fontError] = useFonts(Ionicons.font);
  const [late, setLate] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setLate(true), SPLASH_LIMIT_MS);
    return () => clearTimeout(timer);
  }, []);
  // A font that can't load still lets the app open (icons then load on their own).
  const fontsReady = fontsLoaded || !!fontError || late;
  return (
    <AppStateProvider>
      <ThemeProvider>
        <LaunchScreen fontsReady={fontsReady} late={late} />
        {fontsReady ? <RootStack /> : null}
      </ThemeProvider>
    </AppStateProvider>
  );
}
