/**
 * Five destinations, like Duolingo and Khan Academy, instead of the
 * desktop's 17-page rail: Today, Study, Create, Practice, Progress.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';
import { Platform, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useStore, useSync } from '../../state/AppState';
import { useTheme } from '../../ui/theme';

type IconName = keyof typeof Ionicons.glyphMap;

const TABS: { name: string; title: string; icon: IconName; active: IconName }[] = [
  { name: 'index', title: 'Today', icon: 'sunny-outline', active: 'sunny' },
  { name: 'study', title: 'Study', icon: 'school-outline', active: 'school' },
  { name: 'create', title: 'Create', icon: 'add-circle-outline', active: 'add-circle' },
  { name: 'practice', title: 'Practice', icon: 'extension-puzzle-outline', active: 'extension-puzzle' },
  { name: 'progress', title: 'Progress', icon: 'stats-chart-outline', active: 'stats-chart' },
];

export default function TabLayout() {
  const store = useStore();
  const sync = useSync();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  // A new install opens on sign-in, then the setup questions, then Today.
  // Wait for the remembered sign-in to load so a signed-in person never sees
  // the sign-in page flash past.
  if (sync.configured && !sync.account.restored) return null;
  if (sync.needsSignInPrompt) return <Redirect href="/start" />;
  if (!store.onboarding.done) return <Redirect href="/welcome" />;
  const due = store.dueCards().length;
  // Tab labels stay at the system tab-bar size whatever the in-app text size,
  // like iOS and Android's own tab bars, so all five names always fit. On
  // Android the bar sits above the gesture handle or the system buttons with
  // a little air, instead of touching them.
  const wide = width >= 600;
  const bottom = Platform.OS === 'android' ? insets.bottom + 6 : Math.max(insets.bottom, 6);
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.link,
        tabBarInactiveTintColor: theme.colors.muted,
        tabBarAllowFontScaling: false,
        tabBarStyle: {
          backgroundColor: theme.colors.tabBar,
          borderTopColor: theme.colors.line,
          height: 56 + bottom,
          paddingTop: 4,
          paddingBottom: bottom,
        },
        tabBarLabelStyle: { fontSize: wide ? 13 : 11, fontWeight: '600', letterSpacing: 0.1 },
        tabBarLabelPosition: wide ? 'beside-icon' : 'below-icon',
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? tab.active : tab.icon} size={24} color={color} />,
            tabBarBadge: tab.name === 'study' && due ? due : undefined,
            // With the label beside the icon (iPad), the default spot sits the
            // badge on top of the icon; lift it to the icon's top-right corner instead.
            tabBarBadgeStyle: [{ backgroundColor: theme.colors.primary, color: theme.colors.onPrimary }, wide && { top: -10, end: undefined, start: 18 }],
            tabBarAccessibilityLabel: tab.name === 'study' && due ? `${tab.title}, ${due} cards due` : tab.title,
          }}
        />
      ))}
    </Tabs>
  );
}
