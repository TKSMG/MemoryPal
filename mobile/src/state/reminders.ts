/**
 * Daily study reminders and the due-cards badge, through the phone's own
 * notifications (expo-notifications). Everything is scheduled on the phone:
 * nothing goes through a server, and no push token is ever made.
 *
 * The module is loaded on first use, like speech recognition, so a build
 * without it (web, an old Expo Go) simply has no reminders.
 */
import { Platform } from 'react-native';

import { MemoryStore } from '../core/store';
import { planReminders } from '../features/reminders';

type NotificationsModule = typeof import('expo-notifications');

const CHANNEL = 'study-reminders';
const KIND = 'memorypal-reminder';

function notifications(): NotificationsModule | null {
  if (Platform.OS === 'web') return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-notifications') as NotificationsModule;
  } catch {
    return null;
  }
}

let handlerSet = false;

/** Shows a reminder that arrives while MemoryPal is open as a quiet banner. */
export function setUpNotifications() {
  const module = notifications();
  if (!module || handlerSet) return;
  handlerSet = true;
  module.setNotificationHandler({
    handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: true }),
  });
  if (Platform.OS === 'android') {
    module
      .setNotificationChannelAsync(CHANNEL, {
        name: 'Study reminders',
        description: 'One reminder a day when cards are due.',
        importance: module.AndroidImportance.DEFAULT,
      })
      .catch(() => undefined);
  }
}

export type Permission = 'granted' | 'denied' | 'unavailable';

/** Asks once; afterwards the answer is in the phone's settings. */
export async function askForNotifications(): Promise<Permission> {
  const module = notifications();
  if (!module) return 'unavailable';
  try {
    const current = await module.getPermissionsAsync();
    if (current.granted) return 'granted';
    if (!current.canAskAgain) return 'denied';
    const answer = await module.requestPermissionsAsync({ ios: { allowAlert: true, allowBadge: true, allowSound: true } });
    return answer.granted ? 'granted' : 'denied';
  } catch {
    return 'unavailable';
  }
}

/**
 * Replaces MemoryPal's scheduled reminders with the next week's, and sets
 * the app icon badge to the cards due today. Called when the app goes to
 * the background and when the settings change. Quiet if not allowed.
 */
export async function refreshReminders(store: MemoryStore, options: { reminders: boolean; time: string; badge: boolean }) {
  const module = notifications();
  if (!module) return;
  try {
    const scheduled = await module.getAllScheduledNotificationsAsync();
    await Promise.all(
      scheduled
        .filter((item) => (item.content.data as { kind?: string } | undefined)?.kind === KIND)
        .map((item) => module.cancelScheduledNotificationAsync(item.identifier)),
    );
    const permission = await module.getPermissionsAsync();
    if (!permission.granted) return;
    await module.setBadgeCountAsync(options.badge ? store.dueCards().length : 0);
    if (!options.reminders) return;
    for (const reminder of planReminders(store, options.time)) {
      await module.scheduleNotificationAsync({
        content: {
          title: reminder.title,
          body: reminder.body,
          data: { kind: KIND, url: '/review' },
          badge: options.badge ? reminder.due : undefined,
          sound: false,
        },
        trigger: { type: module.SchedulableTriggerInputTypes.DATE, date: reminder.at, channelId: CHANNEL },
      });
    }
  } catch {
    // Reminders are a convenience: never let them break the app.
  }
}

/** Opens the screen a tapped reminder points at; returns the unsubscribe. */
export function onReminderTapped(open: (url: string) => void): () => void {
  const module = notifications();
  if (!module) return () => undefined;
  const take = (response: { notification: { request: { content: { data?: unknown } } } } | null | undefined) => {
    const data = response?.notification.request.content.data as { kind?: string; url?: string } | undefined;
    if (data?.kind === KIND && typeof data.url === 'string') open(data.url);
  };
  try {
    module.getLastNotificationResponseAsync().then(take).catch(() => undefined);
    const subscription = module.addNotificationResponseReceivedListener(take);
    return () => subscription.remove();
  } catch {
    return () => undefined;
  }
}
