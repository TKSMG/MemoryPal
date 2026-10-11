import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { AppStateProvider } from '../state/AppState';
import { useTheme } from '../ui/theme';

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
          headerTitleStyle: { color: c.ink, fontWeight: '700' },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: c.bg },
          animation: theme.reduceMotion ? 'none' : 'default',
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="welcome" options={{ headerShown: false, gestureEnabled: false }} />
        <Stack.Screen name="review" options={{ title: 'Review' }} />
        <Stack.Screen name="quiz" options={{ title: 'Quick quiz' }} />
        <Stack.Screen name="add" options={{ title: 'Add cards', presentation: 'modal' }} />
        <Stack.Screen name="card/[id]" options={{ title: 'Edit card', presentation: 'modal' }} />
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
      <RootStack />
    </AppStateProvider>
  );
}
