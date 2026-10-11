/**
 * Five destinations, like Duolingo and Khan Academy, instead of the
 * desktop's 17-page rail: Today, Study, Create, Practice, Progress.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Redirect, Tabs } from 'expo-router';

import { useStore } from '../../state/AppState';
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
  const theme = useTheme();
  if (!store.onboarding.done) return <Redirect href="/welcome" />;
  const due = store.dueCards().length;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.colors.link,
        tabBarInactiveTintColor: theme.colors.muted,
        tabBarStyle: { backgroundColor: theme.colors.tabBar, borderTopColor: theme.colors.line, minHeight: 64 },
        tabBarLabelStyle: { fontSize: theme.font(12), fontWeight: '600' },
        tabBarItemStyle: { paddingVertical: 4 },
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color, focused }) => <Ionicons name={focused ? tab.active : tab.icon} size={26} color={color} />,
            tabBarBadge: tab.name === 'study' && due ? due : undefined,
            tabBarBadgeStyle: { backgroundColor: theme.colors.primary, color: theme.colors.onPrimary },
            tabBarAccessibilityLabel: tab.name === 'study' && due ? `${tab.title}, ${due} cards due` : tab.title,
          }}
        />
      ))}
    </Tabs>
  );
}
