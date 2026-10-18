/** Quick quiz: pick the right answer from four. A fast confidence check. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import { Card as CardModel } from '../core/models';
import { useStore, usePrefs } from '../state/AppState';
import { Button, Card, EmptyState, ProgressBar, Row, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../ui/components';
import { speak, stopSpeaking, tap } from '../ui/feedback';
import { useTheme } from '../ui/theme';

function shuffle<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

interface Question {
  card: CardModel;
  choices: string[];
}

export default function Quiz() {
  const store = useStore();
  const theme = useTheme();
  const [prefs] = usePrefs();
  const c = theme.colors;
  const params = useLocalSearchParams<{ deck?: string }>();
  const deck = params.deck || null;

  const questions = useMemo<Question[]>(() => {
    const answered = store.cards.filter((card) => card.back.trim() && (!deck || (card.deck || 'General') === deck));
    const pool = [...store.dueCards(deck), ...store.weakCards()].filter((card, i, all) => card.back.trim() && all.indexOf(card) === i);
    const picked = [...pool, ...shuffle(answered.filter((card) => !pool.includes(card)))].slice(0, 10);
    return shuffle(picked).map((card) => {
      // Wrong choices from the same deck first: answers from another subject
      // ("Paris" next to a biology definition) give the answer away.
      const candidates = answered.filter((other) => other.id !== card.id && other.back !== card.back);
      const sameDeck = shuffle(candidates.filter((other) => other.deck === card.deck).map((other) => other.back));
      const elsewhere = shuffle(candidates.filter((other) => other.deck !== card.deck).map((other) => other.back));
      const others = [...new Set([...sameDeck, ...elsewhere])].slice(0, 3);
      return { card, choices: shuffle([card.back, ...others]) };
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const question = questions[index];

  useEffect(() => {
    if (question && store.accessibility.read_aloud) speak(question.card.front, store.accessibility.more_time);
    return stopSpeaking;
  }, [index]); // eslint-disable-line react-hooks/exhaustive-deps
  useStopSpeechOnLeave();

  if (questions.length < 2 || questions.some((q) => q.choices.length < 2)) {
    return (
      <Screen>
        <EmptyState icon="help-circle-outline" title="Add a few more cards" body="A multiple-choice quiz needs at least four cards with answers, so there are wrong choices to pick from." action={<Button kind="primary" label="Add cards" onPress={() => router.replace('/add')} />} />
      </Screen>
    );
  }

  if (index >= questions.length) {
    return (
      <Screen title="Quiz done" eyebrow="Nice work">
        <Card tone="alt">
          <Txt variant="big">{score} / {questions.length}</Txt>
          <Txt variant="body">{score === questions.length ? 'Every one right!' : 'Cards you missed are worth a proper review — typing the answer from memory works better than picking it.'}</Txt>
        </Card>
        <Button kind="primary" label="Done" onPress={() => router.back()} />
        <Button label="Review weaker cards" onPress={() => router.replace('/review?mode=weak')} />
      </Screen>
    );
  }

  const choose = (choice: string) => {
    if (picked) return;
    tap(prefs.haptics);
    setPicked(choice);
    const right = choice === question.card.back;
    if (right) setScore((value) => value + 1);
    store.recordPractice();
    if (store.accessibility.read_aloud) speak(right ? 'Correct.' : `The answer is ${question.card.back}`, store.accessibility.more_time);
  };

  return (
    <Screen>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label" style={{ flex: 1 }}>{`Question ${index + 1} of ${questions.length}`}</Txt>
        <SpeakButton text={question.card.front} label="Read the question aloud" />
        <SpeakButton text={question.choices.map((choice, i) => `${String.fromCharCode(65 + i)}: ${choice}`).join('. ')} label="Read the choices aloud" />
      </Row>
      <ProgressBar value={index / questions.length} />
      <Card style={{ minHeight: 120, justifyContent: 'center' }}>
        <Txt variant="h2">{question.card.front}</Txt>
      </Card>
      <View accessibilityRole="radiogroup" style={{ gap: 10 }}>
        {question.choices.map((choice) => {
          const isAnswer = choice === question.card.back;
          const state = !picked ? 'idle' : isAnswer ? 'right' : choice === picked ? 'wrong' : 'idle';
          const colors = state === 'right' ? c.good : state === 'wrong' ? c.again : null;
          return (
            <Pressable
              key={choice}
              onPress={() => choose(choice)}
              accessibilityRole="radio"
              accessibilityState={{ selected: choice === picked, disabled: !!picked }}
              accessibilityHint={state === 'right' ? 'Correct answer' : state === 'wrong' ? 'Not the answer' : undefined}
              style={({ pressed }) => ({
                minHeight: 56,
                borderRadius: 14,
                padding: 14,
                borderWidth: 1.5,
                borderColor: colors ? colors[1] : c.line,
                backgroundColor: colors ? colors[0] : pressed ? c.alt : c.surface,
                flexDirection: 'row',
                alignItems: 'center',
                gap: 10,
              })}
            >
              <Txt variant="body" style={{ flex: 1 }} color={colors ? colors[1] : c.ink}>{choice}</Txt>
              {state === 'right' ? <Ionicons name="checkmark-circle" size={theme.icon(24)} color={c.good[1]} /> : null}
              {state === 'wrong' ? <Ionicons name="close-circle" size={theme.icon(24)} color={c.again[1]} /> : null}
            </Pressable>
          );
        })}
      </View>
      {picked ? (
        <Row>
          <Button kind="primary" label={index + 1 === questions.length ? 'See results' : 'Next question'} icon="arrow-forward" onPress={() => { setPicked(null); setIndex((value) => value + 1); }} style={{ flex: 1 }} />
        </Row>
      ) : null}
    </Screen>
  );
}
