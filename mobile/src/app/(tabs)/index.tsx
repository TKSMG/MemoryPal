/** Today: the one next action first, then today's plan, progress, and study modes. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Platform, Pressable, View } from 'react-native';

import { now } from '../../core/dates';
import { persona } from '../../core/personas';
import { planForToday } from '../../core/planning';
import { levelInfo, nextAchievement } from '../../core/progress';
import { useStore, useSync } from '../../state/AppState';
import { Button, Card, IconButton, IconName, ListGroup, ListRow, ProgressBar, Row, Screen, SectionTitle, SpeakButton, Txt } from '../../ui/components';
import { MODES, openStep } from '../../ui/routes';
import { useTheme } from '../../ui/theme';

function greeting(): string {
  const hour = now().getHours();
  return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

type SyncInfo = ReturnType<typeof useSync>;

/** The account button doubles as a quiet sync status light. */
function syncIcon(sync: SyncInfo): IconName {
  if (!sync.account.signedIn) return 'person-circle-outline';
  if (sync.syncing) return 'sync-outline';
  return sync.error ? 'cloud-offline-outline' : 'cloud-done-outline';
}

function syncLabel(sync: SyncInfo): string {
  if (!sync.account.signedIn) return 'Account: sign in to sync';
  if (sync.syncing) return 'Account & sync: syncing';
  return sync.error ? `Account & sync: ${sync.error}` : 'Account & sync: up to date';
}

export default function Today() {
  const store = useStore();
  const sync = useSync();
  const theme = useTheme();
  const c = theme.colors;
  const android = Platform.OS === 'android';
  const due = store.dueCards();
  const weak = store.weakCards();
  const today = store.todayCount();
  const goal = store.dailyGoal;
  const streak = store.currentStreak();
  const level = levelInfo(store.practiced);
  const plan = planForToday(store);
  const done = store.planStepsDone();
  const badge = nextAchievement(store);

  let hero: { title: string; body: string; action: string; go: () => void };
  if (!store.cards.length) {
    hero = { title: 'Add something to learn', body: 'Type a question and answer, or paste your notes.', action: 'Add cards', go: () => router.push('/add') };
  } else if (due.length) {
    hero = {
      title: theme.plain("Start today's review", 'Practise your cards'),
      body: `${due.length} card${due.length === 1 ? ' is' : 's are'} ready for you.`,
      action: 'Start review',
      go: () => router.push('/review?mode=due'),
    };
  } else if (weak.length) {
    hero = { title: 'Strengthen shaky cards', body: `Nothing is due. ${weak.length} card${weak.length === 1 ? '' : 's'} could use a confidence pass.`, action: 'Practise weak cards', go: () => router.push('/review?mode=weak') };
  } else {
    hero = { title: "You're all caught up", body: 'A short quiz keeps recall fresh.', action: 'Quick quiz', go: () => router.push('/quiz') };
  }

  return (
    <Screen
      subtitle={greeting()}
      title="Today"
      right={
        <Row gap={10}>
          {sync.configured ? <IconButton icon={syncIcon(sync)} label={syncLabel(sync)} onPress={() => router.push('/account')} /> : null}
          <IconButton icon="settings-outline" label="Settings" onPress={() => router.push('/settings')} />
        </Row>
      }
    >
      <Card tone="alt" style={{ gap: 12 }}>
        <Txt variant="h2">{hero.title}</Txt>
        <Txt variant="muted">{hero.body}</Txt>
        <Button kind="primary" label={hero.action} icon="play" onPress={hero.go} />
      </Card>

      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="h3" style={{ flexShrink: 1 }}>Daily goal</Txt>
          <Txt variant="muted">{today >= goal ? 'Goal reached' : `${goal - today} to go`}</Txt>
        </Row>
        <ProgressBar value={today / goal} color={today >= goal ? c.green : c.primary} label={`${today} of ${goal} reviews today`} />
        <Row wrap style={{ justifyContent: 'space-between' }}>
          <Row gap={6}>
            <Ionicons name="flame" size={theme.icon(20)} color={c.orange} />
            <Txt variant="body">{streak} day{streak === 1 ? '' : 's'} in a row</Txt>
          </Row>
          <Txt variant="muted">{`Level ${level.level}, ${level.xp} of ${level.need} XP`}</Txt>
        </Row>
      </Card>

      <SectionTitle
        action={
          <Row gap={4}>
            {plan && !plan.finished ? <SpeakButton text={plan.steps.map((step, i) => `Step ${i + 1}: ${step.title}, ${step.minutes} minutes.`).join(' ')} label="Read today’s plan aloud" /> : null}
            <Button kind="ghost" compact inline label={plan ? 'Edit' : 'Make one'} onPress={() => router.push('/plan')} />
          </Row>
        }
      >
        Today’s plan
      </SectionTitle>
      {plan ? (
        <Card>
          <Txt variant="muted">{plan.title}</Txt>
          {plan.finished ? <Txt variant="body">Well done, the plan is complete. Make a new one when you’re ready.</Txt> : null}
          {plan.steps.map((step, index) => {
            const ticked = done.has(index);
            // A press shows at once: a ripple on Android, a soft fill elsewhere.
            const pressedFill = (pressed: boolean) => pressed && !android && { backgroundColor: c.surfaceSoft };
            return (
              <Row key={`${step.title}-${index}`} style={{ alignItems: 'flex-start' }}>
                <Pressable
                  onPress={() => store.togglePlanStep(index)}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: ticked }}
                  accessibilityLabel={`${step.title}, ${step.minutes} minutes`}
                  hitSlop={10}
                  android_ripple={android ? { color: c.alt, borderless: true, radius: 22 } : undefined}
                  style={({ pressed }) => [{ paddingTop: 2, borderRadius: 22 }, pressedFill(pressed)]}
                >
                  <Ionicons name={ticked ? 'checkmark-circle' : 'ellipse-outline'} size={theme.icon(28)} color={ticked ? c.green : c.muted} />
                </Pressable>
                <Pressable
                  onPress={() => openStep(step)}
                  accessibilityRole="button"
                  accessibilityHint="Opens this step"
                  android_ripple={android ? { color: c.alt } : undefined}
                  style={({ pressed }) => [{ flex: 1, gap: 2, minHeight: 44, paddingHorizontal: 6, marginHorizontal: -6, borderRadius: 10, overflow: 'hidden' }, pressedFill(pressed)]}
                >
                  <Txt variant="h3" style={ticked ? { textDecorationLine: 'line-through', color: c.muted } : undefined}>{step.title}</Txt>
                  <Txt variant="small">{step.minutes} min · {step.blurb}</Txt>
                </Pressable>
              </Row>
            );
          })}
        </Card>
      ) : (
        <Card onPress={() => router.push('/plan')} accessibilityLabel="Make a study plan">
          <Row>
            <Ionicons name="map-outline" size={theme.icon(26)} color={c.link} />
            <View style={{ flex: 1 }}>
              <Txt variant="h3">Make a study plan</Txt>
              <Txt variant="muted">Say how much time you have and what’s coming up; get steps to tick off each day.</Txt>
            </View>
          </Row>
        </Card>
      )}

      <ListGroup header="Study modes">
        {persona(store.onboarding.persona).modes.map((key) => {
          const mode = MODES[key];
          return <ListRow key={key} icon={mode.icon as IconName} title={mode.title} detail={mode.body} onPress={mode.go} />;
        })}
      </ListGroup>

      {badge ? (
        <ListGroup>
          <ListRow
            icon="ribbon-outline"
            title={`Next badge: ${badge.title}`}
            detail={`${badge.body} ${badge.current} of ${badge.target}.`}
            onPress={() => router.push('/progress')}
          />
        </ListGroup>
      ) : null}
    </Screen>
  );
}
