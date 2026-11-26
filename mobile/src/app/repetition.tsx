/**
 * Repetition path: recall a list in growing runs, such as 5, 5-4, 5-4-3,
 * then 3-2-1 back to the first item. The items come from a set, the weakest
 * cards, or a typed list (kept only on this screen). Practice only: rounds
 * never change when cards are due. Same rounds as the desktop page.
 */
import { useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { View } from 'react-native';

import { defaultStart, itemsFromCards, itemsFromText, PathItem, PathStep, repetitionSteps, roundExpected, WEAK_LIMIT } from '../core/repetition';
import { answerAssessment, Assessment, describeSimply } from '../core/smartCheck';
import { deckCards } from '../features/decks';
import { useStore } from '../state/AppState';
import { Button, Card, Field, Pills, ProgressBar, Row, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../ui/components';
import { notify } from '../ui/feedback';
import { useTheme } from '../ui/theme';

const WEAK = '__weak__';
const OWN = '__own__';

/** A whole number from a box, or null when it is empty. NaN when it isn't a number. */
function numberFrom(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  return /^-?\d+$/.test(trimmed) ? Number(trimmed) : NaN;
}

export default function RepetitionPath() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  useStopSpeechOnLeave();
  const params = useLocalSearchParams<{ source?: string; deck?: string }>();
  const sets = store.decks();
  const [source, setSource] = useState<string>(() => {
    if (params.source === 'weak') return WEAK;
    if (params.deck && sets.includes(params.deck)) return params.deck;
    return sets.length ? sets[0] : OWN;
  });
  // A plan step can ask for the weakest cards of one set.
  const weakDeck = params.source === 'weak' && params.deck ? params.deck : null;
  const [ownList, setOwnList] = useState('');
  const [start, setStart] = useState('');
  const [range, setRange] = useState('');
  const [path, setPath] = useState<{ items: PathItem[]; steps: PathStep[] } | null>(null);
  const [round, setRound] = useState(0);
  const [recall, setRecall] = useState('');
  const [revealed, setRevealed] = useState(false);
  const [checked, setChecked] = useState<Assessment | null>(null);

  const items = useMemo(() => {
    if (source === OWN) return itemsFromText(ownList);
    if (source === WEAK) return itemsFromCards(store.weakCards().filter((card) => !weakDeck || (card.deck || 'General') === weakDeck).slice(0, WEAK_LIMIT));
    return itemsFromCards([...deckCards(store, source)].reverse());
  }, [source, ownList, store, weakDeck]);

  const startNumber = numberFrom(start);
  const rangeNumber = numberFrom(range);
  const preview = Number.isNaN(startNumber) || Number.isNaN(rangeNumber) ? [] : repetitionSteps(items.length, startNumber, rangeNumber);

  const resetRound = () => {
    setRecall('');
    setRevealed(false);
    setChecked(null);
  };

  const build = () => {
    if (!items.length) {
      notify('Nothing to practise yet', source === OWN ? 'Type a few things to remember, one per line.' : 'This choice has no cards with answers yet.');
      return;
    }
    if (Number.isNaN(startNumber) || Number.isNaN(rangeNumber)) {
      notify('Check the numbers', 'Start and loop range must be whole numbers.');
      return;
    }
    setPath({ items, steps: repetitionSteps(items.length, startNumber, rangeNumber) });
    setRound(0);
    resetRound();
  };

  if (path) {
    const [label, indexes] = path.steps[round];
    const expected = roundExpected(path.items, indexes);
    const last = round === path.steps.length - 1;
    const check = () => {
      setRevealed(true);
      if (recall.trim()) {
        const assessment = answerAssessment(recall, expected);
        setChecked(assessment);
        store.logPractice('repetition', assessment.bucket === 'Good' || assessment.bucket === 'Easy', null, undefined, true);
      }
    };
    const move = (delta: number) => {
      setRound((value) => Math.min(Math.max(value + delta, 0), path.steps.length - 1));
      resetRound();
    };
    const bucketColors = checked ? c[({ Again: 'again', Review: 'review', Good: 'good', Easy: 'easy' } as const)[checked.bucket]] : null;
    return (
      <Screen>
        <Txt variant="label">{`Round ${round + 1} of ${path.steps.length}`}</Txt>
        <ProgressBar value={(round + 1) / path.steps.length} label={`Round ${round + 1} of ${path.steps.length}`} />
        <Card>
          <Txt variant="h2" accessibilityRole="header">{`Repeat ${label}`}</Txt>
          <Txt variant="label">Recall these, in this order</Txt>
          {indexes.map((index) => (
            <Txt key={index} variant="body">{`${index + 1}. ${path.items[index].prompt}`}</Txt>
          ))}
        </Card>
        <Field
          label="Your recall (optional)"
          hint={theme.simple ? undefined : 'One answer per line. Type them to have Smart Check compare, or just say them and show the answers.'}
          value={recall}
          onChangeText={setRecall}
          multiline
          placeholder="Type what you remember…"
        />
        {!revealed ? (
          <Button kind="primary" label={recall.trim() ? 'Check my recall' : 'Show answers'} icon={recall.trim() ? 'checkmark-done' : 'eye-outline'} onPress={check} />
        ) : (
          <>
            <Card tone="alt">
              <Row style={{ justifyContent: 'space-between' }}>
                <Txt variant="label">Answers</Txt>
                <SpeakButton text={indexes.map((index) => path.items[index].answer).join('. ')} label="Read the answers aloud" />
              </Row>
              {indexes.map((index) => (
                <Txt key={index} variant="h3">{`${index + 1}. ${path.items[index].answer}`}</Txt>
              ))}
            </Card>
            {checked && bucketColors ? (
              <View accessibilityLiveRegion="polite" style={{ backgroundColor: bucketColors[0], borderRadius: 14, padding: 14, gap: 4 }}>
                <Txt variant="h3" color={bucketColors[1]}>{theme.simple ? describeSimply(checked) : `${checked.label} · ${checked.score}%`}</Txt>
                {!theme.simple && checked.detail ? <Txt variant="small" color={bucketColors[1]}>{checked.detail}</Txt> : null}
              </View>
            ) : null}
          </>
        )}
        <Row style={{ alignItems: 'stretch' }}>
          <Button compact label="Previous" icon="chevron-back" onPress={() => move(-1)} disabled={round === 0} style={{ flex: 1 }} />
          {last ? (
            <Button compact kind="primary" label="Finish" icon="checkmark" onPress={() => setPath(null)} style={{ flex: 1 }} />
          ) : (
            <Button compact kind={revealed ? 'primary' : 'secondary'} label="Next round" icon="chevron-forward" onPress={() => move(1)} style={{ flex: 1 }} />
          )}
        </Row>
        <Button compact kind="ghost" label="Change the path" icon="options-outline" onPress={() => setPath(null)} />
      </Screen>
    );
  }

  const sources = [
    ...sets.map((name) => ({ value: name, label: name })),
    { value: WEAK, label: weakDeck ? `Weakest in ${weakDeck}` : 'Weakest cards' },
    { value: OWN, label: 'My own list' },
  ];
  const fallbackStart = defaultStart(items.length);

  return (
    <Screen>
      <Txt variant="muted">Recall a list in growing runs: 5, then 5‑4, then 5‑4‑3, then back down to 1. Saying a run in order, again and again, makes it stick.</Txt>
      <Card>
        <Pills label="Practise" value={source} onChange={setSource} options={sources} />
        {source === OWN ? (
          <Field
            label="Things to remember"
            hint='One per line. Write "prompt - answer" to give an item its own question.'
            value={ownList}
            onChangeText={setOwnList}
            multiline
            placeholder={'Mercury\nVenus\nEarth\nMars\nJupiter'}
          />
        ) : null}
        <Txt variant="muted">{items.length ? `${items.length} item${items.length === 1 ? '' : 's'}, in order.` : source === OWN ? 'Nothing typed yet.' : 'No cards with answers here yet.'}</Txt>
        <Row style={{ alignItems: 'flex-start' }}>
          <View style={{ flex: 1 }}>
            <Field label="Start at item" value={start} onChangeText={setStart} keyboardType="number-pad" placeholder={fallbackStart ? String(fallbackStart) : '5'} />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Loop range (optional)" value={range} onChangeText={setRange} keyboardType="number-pad" placeholder="All the way" />
          </View>
        </Row>
        <Txt variant="muted">Example: start 5 with range 3 gives 5, 5‑4, 5‑4‑3, then 3‑2‑1.</Txt>
        {preview.length ? <Txt variant="small">{`Rounds: ${preview.map(([label]) => label).join(', ')}`}</Txt> : null}
        <Button kind="primary" label="Start the path" icon="play" onPress={build} disabled={!items.length} />
      </Card>
    </Screen>
  );
}
