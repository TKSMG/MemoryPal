/** Study plan: time, material, goal and habits become steps (or a day-by-day plan). */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { buildMultiDayPlan, buildStudyPlan, GOAL_KEYS, planMinutes, PlanStep, STUDY_HABIT_OPTIONS, TIME_UNIT_OPTIONS, TIME_UNIT_ORDER } from '../core/planning';
import { StudyPlan } from '../core/store';
import { useStore } from '../state/AppState';
import { Button, Card, Pills, Row, Screen, SectionTitle, SpeakButton, ToggleRow, Txt, useStopSpeechOnLeave } from '../ui/components';
import { confirm } from '../ui/feedback';
import { useTheme } from '../ui/theme';

/** The steps as one paragraph to read aloud. */
function stepsText(steps: PlanStep[]): string {
  return steps.map((step, i) => `Step ${i + 1}: ${step.title}, ${step.minutes} minutes. ${step.blurb}`).join(' ');
}

const KIND_LABEL: Record<string, string> = { learn: 'Learn day', review: 'Spaced review day', maintenance: 'Short maintenance', light: 'Light day', study: 'Study day' };

function StepList({ steps }: { steps: PlanStep[] }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 10 }}>
      {steps.map((step, i) => (
        <Row key={`${step.title}-${i}`} style={{ alignItems: 'flex-start' }}>
          <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: step.view === 'break' ? theme.colors.alt : theme.colors.primary, alignItems: 'center', justifyContent: 'center' }}>
            {step.view === 'break'
              ? <Ionicons name="cafe-outline" size={theme.icon(16)} color={theme.colors.ink} />
              : <Txt variant="small" color={theme.colors.onPrimary}>{String(i + 1)}</Txt>}
          </View>
          <View style={{ flex: 1, gap: 2 }}>
            <Txt variant="h3">{`${step.title} · ${step.minutes} min`}</Txt>
            <Txt variant="small">{step.blurb}</Txt>
          </View>
        </Row>
      ))}
    </View>
  );
}

export default function Plan() {
  const store = useStore();
  const theme = useTheme();
  useStopSpeechOnLeave();
  const params = useLocalSearchParams<{ minutes?: string; goal?: string }>();
  const saved = (store.studyPlan as StudyPlan).settings;
  const [unit, setUnit] = useState<string>(params.minutes ? 'minutes' : String(saved?.unit ?? 'minutes'));
  const [amount, setAmount] = useState<string>(params.minutes ?? String(saved?.amount ?? '30'));
  const [deck, setDeck] = useState<string>(String(saved?.deck ?? 'All decks'));
  const [goal, setGoal] = useState<string>(params.goal ?? String(saved?.goal_label ?? 'Long-term retention'));
  const [habits, setHabits] = useState<string[]>(Array.isArray(saved?.habits) ? (saved.habits as string[]) : []);

  const settings = { unit, amount, deck, goal_label: goal, habits };
  const minutes = planMinutes(settings);
  const goalKey = GOAL_KEYS[goal] ?? 'long_term';
  const totalDays = Number(amount) * (unit === 'weeks' ? 7 : 1);
  const session = minutes !== null ? buildStudyPlan(store, minutes, deck, habits, goalKey) : null;
  const days = minutes === null ? buildMultiDayPlan(store, totalDays, deck, habits, goalKey) : null;

  const changeUnit = (value: string) => {
    setUnit(value);
    setAmount(TIME_UNIT_OPTIONS[value][value === 'minutes' ? 1 : 0]);
  };

  const save = () => {
    store.setStudyPlan(settings);
    router.back();
  };

  const remove = async () => {
    if (await confirm('Remove your plan?', 'Today will go back to suggesting what to study next.', 'Remove')) {
      store.setStudyPlan(null);
      router.back();
    }
  };

  return (
    <Screen>
      <Card>
        <Txt variant="h3">How much time do you have?</Txt>
        <Pills label="Time unit" value={unit} onChange={changeUnit} options={TIME_UNIT_ORDER.map((value) => ({ value, label: value[0].toUpperCase() + value.slice(1) }))} />
        <Pills label="Amount" value={amount} onChange={setAmount} options={TIME_UNIT_OPTIONS[unit].map((value) => ({ value, label: value }))} />
      </Card>
      <Card>
        <Txt variant="h3">What are you studying?</Txt>
        <Pills label="Material" value={deck} onChange={setDeck} options={['All decks', 'New material', ...store.decks()].map((value) => ({ value, label: value }))} />
      </Card>
      <Card>
        <Txt variant="h3">What’s the goal?</Txt>
        <Pills label="Goal" value={goal} onChange={setGoal} options={Object.keys(GOAL_KEYS).map((value) => ({ value, label: value }))} />
      </Card>
      <Card>
        <Txt variant="h3">What helps you study?</Txt>
        {STUDY_HABIT_OPTIONS.map(([key, label]) => (
          <ToggleRow key={key} label={label} value={habits.includes(key)} onChange={(on) => setHabits((list) => (on ? [...list, key] : list.filter((item) => item !== key)))} />
        ))}
      </Card>

      <SectionTitle action={<SpeakButton text={session ? stepsText(session) : days ? days.map((day) => `Day ${day.day}, ${day.minutes} minutes. ${day.steps.map((step) => step.title).join(', ')}.`).join(' ') : ''} label="Read the plan aloud" />}>Your plan</SectionTitle>
      {session ? (
        <Card tone="alt">
          <Txt variant="muted">{`${minutes} minutes · ${goal} · ${deck}`}</Txt>
          <StepList steps={session} />
        </Card>
      ) : null}
      {days?.map((day) => (
        <Card key={day.day} tone={day.day === 1 ? 'alt' : 'default'}>
          <Txt variant="h3">{`Day ${day.day} · ${KIND_LABEL[day.kind] ?? 'Study day'} · ${day.minutes} min`}</Txt>
          <Txt variant="small">{day.due ? `${day.due} card${day.due === 1 ? '' : 's'} coming due` : 'No cards due'}</Txt>
          {day.day === 1 ? <StepList steps={day.steps} /> : <Txt variant="muted">{day.steps.map((step) => step.title).join(' → ')}</Txt>}
        </Card>
      ))}

      <Button kind="primary" label="Make this my plan" icon="checkmark" onPress={save} hint="Today shows the steps for each day, with boxes to tick." />
      {saved ? <Button kind="ghost" label="Remove my current plan" onPress={remove} /> : null}
      <Txt variant="small" center>{theme.plain('Plans look ahead at which cards come due on each day.', 'You can change the plan any time.')}</Txt>
    </Screen>
  );
}
