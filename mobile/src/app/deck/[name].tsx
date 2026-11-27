/** One set: study it, add to it, describe it (exam date, AI style), read its notes, rename or delete it, and see its cards. */
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import { memo, useMemo, useState } from 'react';
import { View } from 'react-native';

import { isoDay } from '../../core/models';
import { normalizeSpace } from '../../core/text';
import { isAiCard } from '../../core/questions';
import { daysUntil, deckCards, deleteDeck, examCountdown, renameDeck } from '../../features/decks';
import { AI_TAG } from '../../features/aiHelpers';
import { useStore } from '../../state/AppState';
import { AiTag, Button, EmptyState, Field, ListGroup, ListRow, ProgressBar, Screen, SectionTitle, Txt } from '../../ui/components';
import { confirm, notify } from '../../ui/feedback';
import { useTheme } from '../../ui/theme';
import { savedLabel } from '../../ui/dates';

/** Cards the page opens with, how many each "Show more" adds, and the most it lists. */
const CARDS_AT_FIRST = 30;
const MORE_CARDS = 50;
const MAX_CARDS = 200;

/** One card in the set's list; skipped on re-render (typing in the fields above) unless what it shows changed. */
const DeckCardRow = memo(function DeckCardRow({ id, front, back, ai }: { id: string; front: string; back: string; ai: boolean }) {
  const answer = back || 'No answer (self-check)';
  return (
    <ListRow
      title={front}
      detail={answer}
      below={ai ? <AiTag /> : null}
      accessibilityLabel={[front, answer, ai ? AI_TAG : ''].filter(Boolean).join(', ')}
      onPress={() => router.push(`/card/${id}`)}
      accessibilityHint="Opens the card to edit"
    />
  );
});

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

export default function Deck() {
  const store = useStore();
  const theme = useTheme();
  const params = useLocalSearchParams<{ name: string }>();
  const [name, setName] = useState(String(params.name ?? ''));
  const [draft, setDraft] = useState(name);
  const details = store.deckInfo(name);
  const [about, setAbout] = useState(details.about);
  const [examDate, setExamDate] = useState(details.exam_date);
  const [style, setStyle] = useState(details.ai_style);
  const [examples, setExamples] = useState(details.ai_examples);
  // Worked out once per change to the cards, not on every key typed in the
  // fields below (the counts walk every card of every set).
  const cards = useMemo(() => deckCards(store, name), [store, store.version, name]); // eslint-disable-line react-hooks/exhaustive-deps
  const notes = useMemo(() => store.notesForDeck(name), [store, store.version, name]); // eslint-disable-line react-hooks/exhaustive-deps
  const info = useMemo(() => store.deckSummary()[name], [store, store.version, name]); // eslint-disable-line react-hooks/exhaustive-deps
  // A long set opens with its first cards; the rest come in on request, so
  // the page is ready to slide in without building hundreds of rows first.
  const [shown, setShown] = useState(CARDS_AT_FIRST);
  const q = encodeURIComponent(name);

  if (!cards.length || !info) {
    return (
      <Screen narrow>
        <Stack.Screen options={{ title: 'Set' }} />
        <EmptyState icon="albums-outline" title="This set is empty" body="Its cards may have been moved or deleted." action={<Button label="Go back" onPress={() => router.back()} />} />
      </Screen>
    );
  }

  const rename = async () => {
    const next = normalizeSpace(draft);
    if (!next || next === name) return;
    const merging = store.decks().includes(next);
    if (merging && !(await confirm(`Move into “${next}”?`, `You already have a set called “${next}”. The ${plural(cards.length, 'card')} from “${name}” will join it.`, 'Move cards'))) return;
    renameDeck(store, name, next);
    setName(next);
    setDraft(next);
    router.setParams({ name: next });
  };

  const detailsChanged = about !== details.about || examDate !== details.exam_date || style !== details.ai_style || examples !== details.ai_examples;
  const saveDetails = () => {
    if (examDate.trim() && !isoDay(examDate)) return notify('Check the exam date', 'Type it as year-month-day, for example 2026-12-05.');
    const saved = store.setDeckInfo(name, { about, exam_date: examDate, ai_style: style, ai_examples: examples });
    setAbout(saved.about);
    setExamDate(saved.exam_date);
    setStyle(saved.ai_style);
    setExamples(saved.ai_examples);
  };
  const countdown = examCountdown(details.exam_date);
  const daysLeft = daysUntil(details.exam_date);

  const remove = async () => {
    const kept = notes.length ? ` Its ${plural(notes.length, 'saved note')} will stay in Saved notes.` : '';
    if (await confirm(`Delete “${name}”?`, `All ${plural(cards.length, 'card')} in this set and their review history will be removed. This can’t be undone.${kept}`, 'Delete set', true)) {
      deleteDeck(store, name);
      router.back();
    }
  };

  return (
    <Screen narrow>
      <Stack.Screen options={{ title: name }} />
      <Txt variant="muted">{[`${plural(info.total, 'card')}, ${info.due} due, ${info.mastery}% mastered`, countdown && countdown.charAt(0).toLowerCase() + countdown.slice(1)].filter(Boolean).join(', ')}</Txt>
      {/* The set's own tone, the same as on its tile in Create. */}
      <ProgressBar value={info.mastery / 100} color={theme.colors.primary} height={8} label={`${info.mastery}% mastered`} />
      {details.about ? <Txt variant="body">{details.about}</Txt> : null}

      <ListGroup>
        <ListRow icon="play-circle-outline" title={info.due ? `Review ${plural(info.due, 'due card')}` : 'Practise this set'} onPress={() => router.push(`/review?mode=${info.due ? 'due' : 'all'}&deck=${q}` as Href)} />
        <ListRow icon="chatbubbles-outline" title="Talk-back study" detail="AI tutor, or questions read aloud" onPress={() => router.push(`/talkback?mode=all&deck=${q}` as Href)} />
        <ListRow icon="list-circle-outline" title="Quick quiz" detail="Mixed questions: pick, match, fill in" onPress={() => router.push(`/quiz?deck=${q}` as Href)} />
        <ListRow icon="add-circle-outline" title="Add cards" onPress={() => router.push(`/add?deck=${q}` as Href)} />
        <ListRow icon="sparkles-outline" title="Make with AI" detail="Notes or questions from notes, a PDF or a photo" onPress={() => router.push(`/ai?deck=${q}` as Href)} />
        <ListRow icon="extension-puzzle-outline" title="Puzzles with these cards" detail="Pairs, words and lists from this set" onPress={() => router.push(`/puzzle?deck=${q}` as Href)} />
        {daysLeft !== null && daysLeft > 0 ? (
          <ListRow icon="calendar-outline" title="Plan for the exam" detail={`A day-by-day plan for the next ${plural(daysLeft, 'day')}`} onPress={() => router.push(`/plan?deck=${q}&days=${daysLeft}` as Href)} />
        ) : null}
      </ListGroup>

      {notes.length ? (
        <ListGroup header="Saved notes">
          {notes.map((capture) => (
            <ListRow key={capture.id} icon="reader-outline" title={capture.title} detail={savedLabel(capture.created_at)} onPress={() => router.push(`/notes/${capture.id}` as Href)} accessibilityHint="Opens these notes to read" />
          ))}
        </ListGroup>
      ) : null}

      <View style={{ gap: 10 }}>
        <SectionTitle detail="Saved with the set and synced to your other devices.">About this set</SectionTitle>
        <Field label="About (optional)" value={about} onChangeText={setAbout} placeholder="Year 2 cardiology, Dr Shah’s lectures" maxLength={1000} />
        <Field label="Exam date (optional)" hint="Year-month-day, for example 2026-12-05. The set shows a countdown and can plan up to it." value={examDate} onChangeText={setExamDate} placeholder="2026-12-05" keyboardType="numbers-and-punctuation" maxLength={10} />
        <Field label="How should AI notes look? (optional)" value={style} onChangeText={setStyle} placeholder="One line per drug: class, use, side effect" maxLength={500} />
        <Field label="Questions your teacher has asked (optional)" hint="One per line. Make with AI writes new questions in the same style." value={examples} onChangeText={setExamples} multiline maxLength={8000} style={{ minHeight: 90 }} />
        <Button label="Save details" icon="checkmark" onPress={saveDetails} disabled={!detailsChanged} />
      </View>

      <View style={{ gap: 10 }}>
        <Field label="Set name" value={draft} onChangeText={setDraft} autoCapitalize="words" returnKeyType="done" onSubmitEditing={rename} />
        <Button label="Rename set" icon="pencil-outline" onPress={rename} disabled={!normalizeSpace(draft) || normalizeSpace(draft) === name} />
      </View>

      <ListGroup header="Cards">
        {cards.slice(0, Math.min(shown, MAX_CARDS)).map((card) => (
          <DeckCardRow key={card.id} id={card.id} front={card.front} back={card.back} ai={isAiCard(card)} />
        ))}
      </ListGroup>
      {cards.length > shown && shown < MAX_CARDS ? (
        <Button label={`Show ${Math.min(MORE_CARDS, cards.length - shown, MAX_CARDS - shown)} more cards`} icon="chevron-down" onPress={() => setShown((count) => count + MORE_CARDS)} />
      ) : null}
      {cards.length > MAX_CARDS && shown >= MAX_CARDS ? <Txt variant="small">{`Showing the first ${MAX_CARDS} of ${cards.length}. Search in Create to find the rest.`}</Txt> : null}

      <Button kind="dangerGhost" label="Delete set" icon="trash-outline" onPress={remove} />
    </Screen>
  );
}
