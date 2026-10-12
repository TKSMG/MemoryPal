/**
 * A review session: answer first, then check or reveal, then rate.
 * Ends with a summary of what was remembered and what comes back when.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import { addDays } from '../core/dates';
import { Card as CardModel } from '../core/models';
import { answerAssessment, Assessment, Bucket, describeSimply } from '../core/smartCheck';
import { MemoryStore } from '../core/store';
import { useStore, usePrefs } from '../state/AppState';
import { Button, ButtonKind, Card, EmptyState, Field, IconButton, ProgressBar, Row, Screen, Txt } from '../ui/components';
import { speak, stopSpeaking, tap } from '../ui/feedback';
import { useTheme } from '../ui/theme';

type Mode = 'due' | 'weak' | 'new' | 'quick' | 'gentle' | 'all';

function buildQueue(store: MemoryStore, mode: Mode, deck: string | null): CardModel[] {
  const inDeck = (card: CardModel) => !deck || (card.deck || 'General') === deck;
  const due = store.dueCards(deck);
  switch (mode) {
    case 'weak':
      return store.weakCards().filter(inDeck).slice(0, 20);
    case 'new':
      return store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0 && inDeck(card)).slice(0, 20);
    case 'quick': {
      const extra = store.weakCards().filter((card) => inDeck(card) && !due.includes(card));
      return [...due, ...extra].slice(0, 10);
    }
    case 'gentle': {
      const everyday = due.filter((card) => card.deck === 'Everyday Memory');
      return (everyday.length ? everyday : due).slice(0, 8);
    }
    case 'all':
      return store.cards.filter(inDeck);
    default:
      return due;
  }
}

const RATINGS: { bucket: Bucket; quality: number; kind: ButtonKind; label: string; simple: string }[] = [
  { bucket: 'Again', quality: 1, kind: 'again', label: 'Again', simple: 'Not yet' },
  { bucket: 'Review', quality: 3, kind: 'review', label: 'Hard', simple: 'Hard' },
  { bucket: 'Good', quality: 4, kind: 'good', label: 'Good', simple: 'Got it' },
  { bucket: 'Easy', quality: 5, kind: 'easy', label: 'Easy', simple: 'Easy' },
];

function whenLabel(days: number): string {
  if (days <= 1) return 'tomorrow';
  if (days < 30) return `in ${days} days`;
  const months = Math.round(days / 30);
  return months < 12 ? `in ${months} month${months === 1 ? '' : 's'}` : 'in a year';
}

interface Result {
  card: CardModel;
  quality: number;
  position: number; // where it sat in the queue, for Undo
}

export default function Review() {
  const store = useStore();
  const theme = useTheme();
  const [prefs] = usePrefs();
  const c = theme.colors;
  const params = useLocalSearchParams<{ mode?: string; deck?: string; read?: string }>();
  const mode = (params.mode as Mode) || 'due';
  const deck = params.deck || null;
  const readAloud = store.accessibility.read_aloud || params.read === '1';
  const slow = store.accessibility.more_time;

  // The queue is fixed when the session starts, so rating a card doesn't reshuffle it.
  const queue = useMemo(() => buildQueue(store, mode, deck), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [checked, setChecked] = useState<Assessment | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const card = queue[index];
  const finished = index >= queue.length;

  useEffect(() => {
    if (card && readAloud) speak(card.front, slow);
    return stopSpeaking;
  }, [card?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!queue.length) {
    return (
      <Screen>
        <EmptyState
          icon="checkmark-done-circle-outline"
          title={mode === 'due' ? 'Nothing is due right now' : 'No cards here yet'}
          body={mode === 'due' ? 'Everything is scheduled for later. A quick quiz or your weaker cards are good extra practice.' : 'Add a few cards first, then come back.'}
          action={
            <View style={{ gap: 10, alignSelf: 'stretch' }}>
              {mode === 'due' && store.weakCards().length ? <Button kind="primary" label="Practise weaker cards" onPress={() => router.replace('/review?mode=weak')} /> : null}
              <Button label="Add cards" onPress={() => router.replace('/add')} />
            </View>
          }
        />
      </Screen>
    );
  }

  if (finished) {
    const remembered = results.filter((r) => r.quality >= 4).length;
    const missed = results.filter((r) => r.quality < 3);
    const tomorrow = store.dueCards(null, addDays(1)).length;
    return (
      <Screen title="Session done" eyebrow="Well done">
        <Card tone="alt">
          {/* One row per number: three narrow columns broke words apart at large text sizes. */}
          {([
            [results.length, 'cards reviewed', c.ink],
            [remembered, 'remembered well', c.green],
            [missed.length, 'to practise again', missed.length ? c.again[1] : c.muted],
          ] as [number, string, string][]).map(([value, label, color]) => (
            <Row key={label} gap={14} style={{ alignItems: 'baseline' }}>
              <Txt variant="big" color={color} style={{ minWidth: 56 }}>{String(value)}</Txt>
              <Txt variant="body" style={{ flex: 1 }}>{label}</Txt>
            </Row>
          ))}
          <Txt variant="body">
            {theme.plain(
              `Missed cards come back tomorrow, so they get extra practice. About ${tomorrow} card${tomorrow === 1 ? ' is' : 's are'} due tomorrow.`,
              'Cards you missed will come back tomorrow. That is how they stick.',
            )}
          </Txt>
        </Card>
        {missed.length ? (
          <Card>
            <Txt variant="h3">Worth another look</Txt>
            {missed.map(({ card: item }) => (
              <View key={item.id} style={{ gap: 2 }}>
                <Txt variant="body">{item.front}</Txt>
                <Txt variant="small">{item.back}</Txt>
              </View>
            ))}
          </Card>
        ) : null}
        <Button kind="primary" label="Done" icon="checkmark" onPress={() => router.back()} />
        {missed.length ? <Button label="Practise the missed ones now" onPress={() => router.replace('/review?mode=weak')} /> : null}
      </Screen>
    );
  }

  const hasAnswer = Boolean(card.back.trim());
  const reveal = () => {
    setRevealed(true);
    if (answer.trim()) setChecked(answerAssessment(answer, card.back, card.front));
    if (readAloud) speak(hasAnswer ? card.back : 'No saved answer. Rate how well you remembered.', slow);
  };

  const rate = (quality: number, bucket: Bucket) => {
    tap(prefs.haptics);
    store.schedule(card, quality, checked && checked.bucket === bucket ? checked : null);
    setResults((list) => [...list, { card, quality, position: index }]);
    setIndex((value) => value + 1);
    setAnswer('');
    setRevealed(false);
    setChecked(null);
  };

  const undo = () => {
    if (!results.length || !store.undoLast()) return;
    // Go back to the rated card itself, even if cards were skipped since.
    const last = results[results.length - 1];
    setResults((list) => list.slice(0, -1));
    setIndex(last.position);
    setRevealed(false);
    setChecked(null);
    setAnswer('');
  };

  const skip = () => {
    store.buryCard(card);
    setIndex((value) => value + 1);
    setAnswer('');
    setRevealed(false);
    setChecked(null);
  };

  const preview = (quality: number) => (quality < 3 ? 1 : store.nextInterval({ ...card }, quality));
  const bucketColors = checked ? c[({ Again: 'again', Review: 'review', Good: 'good', Easy: 'easy' } as const)[checked.bucket]] : null;

  return (
    <Screen>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label">{`Card ${index + 1} of ${queue.length}${card.deck ? ` · ${card.deck}` : ''}`}</Txt>
        <Row gap={8}>
          <IconButton icon="volume-high-outline" label="Read the question aloud" onPress={() => speak(card.front, slow)} />
          <IconButton icon="create-outline" label="Edit this card" onPress={() => router.push(`/card/${card.id}`)} />
        </Row>
      </Row>
      <ProgressBar value={index / queue.length} label={`${index} of ${queue.length} done`} />

      <Card style={{ minHeight: 140, justifyContent: 'center' }}>
        <Txt variant="label">{theme.plain('Question', 'Try to remember')}</Txt>
        <Txt variant="h2" accessibilityRole="header">{card.front}</Txt>
      </Card>

      {!revealed ? (
        <>
          <Field
            label={theme.plain('Your answer (optional)', 'Type what you remember (optional)')}
            hint={theme.simple ? undefined : 'Type it to have Smart Check compare it, or just think of it and show the answer.'}
            value={answer}
            onChangeText={setAnswer}
            multiline
            placeholder="Type what you remember…"
            returnKeyType="done"
            submitBehavior="blurAndSubmit"
            onSubmitEditing={reveal}
          />
          <Button kind="primary" label={answer.trim() ? 'Check my answer' : 'Show answer'} icon={answer.trim() ? 'checkmark-done' : 'eye-outline'} onPress={reveal} />
          <Row>
            <Button compact label="Skip for today" icon="time-outline" onPress={skip} style={{ flex: 1 }} hint="The card comes back tomorrow without counting as a miss." />
            <Button compact label="Undo" icon="arrow-undo-outline" onPress={undo} disabled={!results.length} style={{ flex: 1 }} hint="Take back the last rating." />
          </Row>
        </>
      ) : (
        <>
          <Card tone="alt">
            <Row style={{ justifyContent: 'space-between' }}>
              <Txt variant="label">{theme.plain('Answer', 'The answer')}</Txt>
              {hasAnswer ? <IconButton icon="volume-high-outline" label="Read the answer aloud" onPress={() => speak(card.back, slow)} /> : null}
            </Row>
            <Txt variant="h3">{hasAnswer ? card.back : 'No saved answer. Use this as a self-check, then rate yourself.'}</Txt>
            {card.association ? (
              <Row style={{ alignItems: 'flex-start' }}>
                <Ionicons name="bulb-outline" size={20} color={c.link} />
                <Txt variant="muted" style={{ flex: 1 }}>{card.association}</Txt>
              </Row>
            ) : null}
          </Card>
          {checked && bucketColors ? (
            <View accessibilityLiveRegion="polite" style={{ backgroundColor: bucketColors[0], borderRadius: 14, padding: 14, gap: 4 }}>
              <Txt variant="h3" color={bucketColors[1]}>{theme.simple ? describeSimply(checked) : `${checked.label} · ${checked.score}%`}</Txt>
              {!theme.simple ? <Txt variant="small" color={bucketColors[1]}>{checked.detail} Suggested: {RATINGS.find((r) => r.bucket === checked.bucket)?.label}.</Txt> : null}
            </View>
          ) : null}
          <Txt variant="h3">{theme.plain('How well did you remember it?', 'How did it go?')}</Txt>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
            {RATINGS.map((rating) => {
              const suggested = checked?.bucket === rating.bucket;
              return (
                <Button
                  key={rating.bucket}
                  kind={rating.kind}
                  label={theme.simple ? rating.simple : rating.label}
                  sublabel={whenLabel(preview(rating.quality))}
                  onPress={() => rate(rating.quality, rating.bucket)}
                  hint={`Shows this card again ${whenLabel(preview(rating.quality))}`}
                  style={[{ flexBasis: '46%', flexGrow: 1 }, suggested && { borderWidth: 3, borderColor: c.focus }]}
                />
              );
            })}
          </View>
          <Button compact kind="ghost" label="Undo last rating" icon="arrow-undo-outline" onPress={undo} disabled={!results.length} />
        </>
      )}
    </Screen>
  );
}
