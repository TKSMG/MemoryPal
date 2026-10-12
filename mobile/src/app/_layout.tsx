import { router, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, Pressable, Text } from 'react-native';

import { AppStateProvider } from '../state/AppState';
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

function RootStack() {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <>
      <StatusBar style={theme.dark ? 'light' : 'dark'} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: c.bg },
          headerTintColor: c.link,
          headerTitleStyle: { color: c.ink, fontWeight: '600' },
          headerShadowVisible: false,
          // The tab group has no title, so a back label would read "(tabs)".
          headerBackButtonDisplayMode: 'minimal',
          contentStyle: { backgroundColor: c.bg },
          // Reduce Motion swaps the slide for a cross-fade, so a change of
          // screen is still visible without the movement.
          animation: theme.reduceMotion ? 'fade' : 'default',
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="review" options={{ title: 'Review' }} />
        <Stack.Screen name="quiz" options={{ title: 'Quick quiz' }} />
        <Stack.Screen name="add" options={{ title: 'Add cards', presentation: 'modal', headerRight: () => <SheetButton label="Done" bold /> }} />
        <Stack.Screen name="card/[id]" options={{ title: 'Edit card', presentation: 'modal', headerLeft: () => <SheetButton label="Cancel" /> }} />
        <Stack.Screen name="plan" options={{ title: 'Study plan' }} />
        <Stack.Screen name="puzzle" options={{ title: 'Puzzle' }} />
        <Stack.Screen name="settings" options={{ title: 'Settings' }} />
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
