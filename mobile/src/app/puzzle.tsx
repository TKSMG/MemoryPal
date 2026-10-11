/**
 * Short memory puzzles. Calm by design: a visible countdown, an "I'm ready"
 * button so nobody is rushed or kept waiting, and More time doubles every timer.
 */
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import { useStore } from '../state/AppState';
import { Button, Card, Field, ProgressBar, Row, Screen, Txt } from '../ui/components';
import { useTheme } from '../ui/theme';

const WORDS = ['apple', 'river', 'candle', 'garden', 'pencil', 'window', 'basket', 'violin', 'mountain', 'teacup', 'ladder', 'blanket', 'compass', 'lemon', 'harbour', 'button', 'feather', 'kettle', 'meadow', 'lantern', 'pebble', 'orchard', 'saddle', 'thimble'];
const ROUNDS = 5;

function sample<T>(items: T[], count: number): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, count);
}

type Phase = 'show' | 'answer' | 'result' | 'done';

interface Round {
  shown: string[];
  pairs?: [string, string][];
  /** For pair recall: the partner choices for each question, already shuffled. */
  options?: string[][];
}

function makeRound(kind: string, level: number): Round {
  if (kind === 'sequence') return { shown: Array.from({ length: level }, () => String(Math.floor(Math.random() * 10))) };
  if (kind === 'pairs') {
    const words = sample(WORDS, level * 2);
    const pairs = Array.from({ length: level }, (_, i) => [words[i * 2], words[i * 2 + 1]] as [string, string]);
    const partners = pairs.map(([, b]) => b);
    return { shown: pairs.map(([a, b]) => `${a} — ${b}`), pairs, options: pairs.map(() => sample(partners, partners.length)) };
  }
  return { shown: sample(WORDS, level) };
}

export default function Puzzle() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const { kind = 'sequence' } = useLocalSearchParams<{ kind?: string }>();
  const moreTime = store.accessibility.more_time;
  const firstLevel = kind === 'sequence' ? 4 : kind === 'words' ? 5 : 3;
  const [level, setLevel] = useState(firstLevel);
  const [roundNumber, setRoundNumber] = useState(1);
  const [phase, setPhase] = useState<Phase>('show');
  const [answer, setAnswer] = useState('');
  const [score, setScore] = useState(0);
  const [lastRight, setLastRight] = useState(false);
  const [pairIndex, setPairIndex] = useState(0);
  const [pairRight, setPairRight] = useState(0);
  // Rounds (and their shuffled options) are made in event handlers, never
  // during render, so a re-render can't reshuffle what's on screen.
  const [round, setRound] = useState<Round>(() => makeRound(kind, firstLevel));
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [tick, setTick] = useState(startedAt);

  const size = round.pairs?.length ?? round.shown.length;
  const showMs = (kind === 'sequence' ? 1500 + 600 * size : 2500 + 1200 * size) * (moreTime ? 2 : 1);
  const left = Math.max(0, showMs - (tick - startedAt));

  useEffect(() => {
    if (phase !== 'show') return undefined;
    const timer = setInterval(() => {
      const now = Date.now();
      setTick(now);
      if (now - startedAt >= showMs) {
        clearInterval(timer);
        setPhase('answer');
      }
    }, 200);
    return () => clearInterval(timer);
  }, [phase, startedAt, showMs]);

  const title = kind === 'sequence' ? 'Sequence recall' : kind === 'pairs' ? 'Pair recall' : 'Word recall';

  const startRound = (nextLevel: number) => {
    const now = Date.now();
    setRound(makeRound(kind, nextLevel));
    setStartedAt(now);
    setTick(now);
    setAnswer('');
    setPairIndex(0);
    setPairRight(0);
    setPhase('show');
  };

  const nextRound = (right: boolean) => {
    if (roundNumber >= ROUNDS) {
      store.recordPractice();
      setPhase('done');
      return;
    }
    // Gently adapt: one step harder after a success, one easier after a miss.
    const nextLevel = Math.max(kind === 'sequence' ? 3 : 2, Math.min(kind === 'sequence' ? 10 : 8, level + (right ? 1 : -1)));
    setLevel(nextLevel);
    setRoundNumber((value) => value + 1);
    startRound(nextLevel);
  };

  const check = () => {
    let right = false;
    if (kind === 'sequence') {
      right = answer.replace(/\D/g, '') === round.shown.join('');
    } else {
      const typed = new Set(answer.toLowerCase().split(/[^a-z]+/).filter(Boolean));
      const found = round.shown.filter((word) => typed.has(word)).length;
      right = found >= Math.ceil(round.shown.length * 0.6);
      setPairRight(found);
    }
    if (right) setScore((value) => value + 1);
    setLastRight(right);
    setPhase('result');
  };

  const choosePartner = (choice: string) => {
    const pairs = round.pairs ?? [];
    const right = choice === pairs[pairIndex][1];
    const correct = pairRight + (right ? 1 : 0);
    if (pairIndex + 1 < pairs.length) {
      setPairRight(correct);
      setPairIndex((value) => value + 1);
      return;
    }
    const success = correct >= Math.ceil(pairs.length * 0.6);
    setPairRight(correct);
    if (success) setScore((value) => value + 1);
    setLastRight(success);
    setPhase('result');
  };

  if (phase === 'done') {
    return (
      <Screen title="All done" eyebrow={title}>
        <Stack.Screen options={{ title }} />
        <Card tone="alt">
          <Txt variant="big">{score} / {ROUNDS}</Txt>
          <Txt variant="body">{theme.plain('Rounds completed well. The puzzle adjusts to you, so it stays the right level of challenge.', 'Well done. Come back tomorrow for another round.')}</Txt>
        </Card>
        <Button kind="primary" label="Play again" icon="refresh" onPress={() => { setRoundNumber(1); setScore(0); setLevel(firstLevel); startRound(firstLevel); }} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Stack.Screen options={{ title }} />
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label">{`Round ${roundNumber} of ${ROUNDS}`}</Txt>
        <Txt variant="label">{`Score ${score}`}</Txt>
      </Row>

      {phase === 'show' ? (
        <>
          <Txt variant="h2">{kind === 'sequence' ? 'Remember these numbers' : kind === 'pairs' ? 'Remember which words go together' : 'Remember these words'}</Txt>
          <Card style={{ alignItems: 'center', paddingVertical: 28, gap: 12 }}>
            {kind === 'sequence' ? (
              <Txt variant="big" style={{ letterSpacing: 8 }}>{round.shown.join(' ')}</Txt>
            ) : (
              round.shown.map((item) => <Txt key={item} variant="h2">{item}</Txt>)
            )}
          </Card>
          <ProgressBar value={left / showMs} label={`${Math.ceil(left / 1000)} seconds left`} />
          <Button label="I'm ready" icon="arrow-forward" onPress={() => setPhase('answer')} />
        </>
      ) : null}

      {phase === 'answer' && kind !== 'pairs' ? (
        <>
          <Field
            label={kind === 'sequence' ? 'Type the numbers in order' : 'Type the words you remember'}
            value={answer}
            onChangeText={setAnswer}
            keyboardType={kind === 'sequence' ? 'number-pad' : 'default'}
            autoCapitalize="none"
            autoFocus
            multiline={kind !== 'sequence'}
          />
          <Button kind="primary" label="Check" icon="checkmark" onPress={check} />
        </>
      ) : null}

      {phase === 'answer' && kind === 'pairs' && round.pairs ? (
        <>
          <Txt variant="h2">{`What went with “${round.pairs[pairIndex][0]}”?`}</Txt>
          <View style={{ gap: 10 }}>
            {(round.options?.[pairIndex] ?? []).map((option) => (
              <Pressable
                key={option}
                onPress={() => choosePartner(option)}
                accessibilityRole="button"
                style={({ pressed }) => ({ minHeight: 56, borderRadius: 14, padding: 14, borderWidth: 1.5, borderColor: c.line, backgroundColor: pressed ? c.alt : c.surface, justifyContent: 'center' })}
              >
                <Txt variant="h3">{option}</Txt>
              </Pressable>
            ))}
          </View>
        </>
      ) : null}

      {phase === 'result' ? (
        <>
          <View accessibilityLiveRegion="polite" style={{ backgroundColor: lastRight ? c.good[0] : c.review[0], borderRadius: 14, padding: 16, gap: 6 }}>
            <Txt variant="h3" color={lastRight ? c.good[1] : c.review[1]}>
              {lastRight ? 'Well remembered!' : theme.plain('Nearly — that one was tricky.', 'Good try. Let’s keep going.')}
            </Txt>
            <Txt variant="body" color={lastRight ? c.good[1] : c.review[1]}>
              {kind === 'sequence' ? `It was ${round.shown.join(' ')}.` : kind === 'pairs' ? `${pairRight} of ${round.shown.length} pairs right.` : `You remembered ${pairRight} of ${round.shown.length}: ${round.shown.join(', ')}.`}
            </Txt>
          </View>
          <Button kind="primary" label={roundNumber >= ROUNDS ? 'Finish' : 'Next round'} icon="arrow-forward" onPress={() => nextRound(lastRight)} />
        </>
      ) : null}
    </Screen>
  );
}
