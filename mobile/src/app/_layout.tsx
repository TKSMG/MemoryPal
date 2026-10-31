import { Href, router, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { AppState as RNAppState, Platform, Pressable, Text } from 'react-native';

import { AppStateProvider, usePrefs, useStore } from '../state/AppState';
import { onReminderTapped, refreshReminders, setUpNotifications } from '../state/reminders';
import { ThemeProvider, useTheme } from '../ui/theme';

/** iOS sheets get a way out in the bar; Android has its back button and arrow. */
function SheetButton({ label, bold }: { label: string; bold?: boolean }) {
  const theme = useTheme();
  if (Platform.OS !== 'ios') return null;
  return (
    <Pressable onPress={() => router.back()} accessibilityRole="button" hitSlop={12}>
      <Text maxFontSizeMultiplier={1.6} style={{ color: theme.colors.link, fontSize: 17, fontWeight: bold ? '600' : '400' }}>{label}</Text>
    </Pressable>
  );
}

/**
 * Keeps the next week of study reminders and the icon badge up to date:
 * rescheduled whenever MemoryPal goes to the background (after studying)
 * and when the reminder settings change. A tapped reminder opens Review.
 */
function Reminders() {
  const store = useStore();
  const [prefs] = usePrefs();
  const { reminders, reminder_time: time, badge } = prefs;
  useEffect(() => {
    setUpNotifications();
    return onReminderTapped((url) => router.push(url as Href));
  }, []);
  useEffect(() => {
    const refresh = () => refreshReminders(store, { reminders, time, badge });
    refresh();
    const subscription = RNAppState.addEventListener('change', (state) => {
      if (state !== 'active') refresh();
    });
    return () => subscription.remove();
  }, [store, reminders, time, badge]);
  return null;
}

function RootStack() {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />
      <Reminders />
      <Stack
        screenOptions={{
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
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="start" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="review" options={{ title: 'Review' }} />
        <Stack.Screen name="talkback" options={{ title: 'Talk-back study' }} />
        <Stack.Screen name="talk-live" options={{ title: 'Live tutor' }} />
        <Stack.Screen name="quiz" options={{ title: 'Quick quiz' }} />
        <Stack.Screen name="add" options={{ title: 'New set', presentation: 'modal', headerRight: () => <SheetButton label="Done" bold /> }} />
        <Stack.Screen name="card/[id]" options={{ title: 'Edit card', presentation: 'modal', headerLeft: () => <SheetButton label="Cancel" /> }} />
        <Stack.Screen name="deck/[name]" options={{ title: 'Set' }} />
        <Stack.Screen name="notes/index" options={{ title: 'Saved notes' }} />
        <Stack.Screen name="notes/[id]" options={{ title: 'Notes' }} />
        <Stack.Screen name="plan" options={{ title: 'Study plan' }} />
        <Stack.Screen name="puzzle" options={{ title: 'Puzzle' }} />
        <Stack.Screen name="settings" options={{ title: 'Settings' }} />
        <Stack.Screen name="ai" options={{ title: 'Make with AI' }} />
        <Stack.Screen name="ai-consent" options={{ title: 'AI features', presentation: 'modal', headerLeft: () => <SheetButton label="Cancel" /> }} />
        <Stack.Screen name="account" options={{ title: 'Account & sync' }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <AppStateProvider>
      <ThemeProvider>
        <RootStack />
      </ThemeProvider>
    </AppStateProvider>
  );
}
