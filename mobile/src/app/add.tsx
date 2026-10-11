/** Four ways to make cards: one at a time, pasted lists, split notes, or everyday cards. */
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { newCard, uid } from '../core/models';
import { nowLabel } from '../core/dates';
import { hangmanHint, normalizeSpace, parsePromptAnswerLines, splitStudyBits } from '../core/text';
import { useStore } from '../state/AppState';
import { Button, Card, Field, Pills, Screen, Txt } from '../ui/components';
import { notify } from '../ui/feedback';
import { useTheme } from '../ui/theme';

type Mode = 'single' | 'paste' | 'notes' | 'everyday';
type Everyday = 'person' | 'routine' | 'place' | 'reminder';

const EVERYDAY_DECK = 'Everyday Memory';

export default function Add() {
  const store = useStore();
  const theme = useTheme();
  const params = useLocalSearchParams<{ mode?: string; deck?: string }>();
  const [mode, setMode] = useState<Mode>((params.mode as Mode) || 'single');
  const [deck, setDeck] = useState(params.deck || store.decks()[0] || 'General');
  const [front, setFront] = useState('');
  const [back, setBack] = useState('');
  const [hook, setHook] = useState('');
  const [bulk, setBulk] = useState('');
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState<Everyday>('person');
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  const [saved, setSaved] = useState('');

  const decks = store.decks();
  const parsed = parsePromptAnswerLines(bulk);
  const bits = splitStudyBits(bulk);

  const done = (message: string) => {
    setSaved(message);
    setFront('');
    setBack('');
    setHook('');
    setBulk('');
    setA('');
    setB('');
  };

  const saveSingle = () => {
    if (!normalizeSpace(front)) return notify('Add a question', 'Type the question or prompt you want to be asked.');
    store.addCard(newCard({ deck: normalizeSpace(deck) || 'General', front: normalizeSpace(front), back: back.trim(), association: hook.trim() }));
    done('Card saved. Add another, or go back when you’re done.');
  };

  const savePaste = () => {
    if (!parsed.length) return notify('Nothing to add yet', 'Put one card per line, like "Capital of France :: Paris".');
    store.addCards(parsed.map((item) => newCard({ deck: normalizeSpace(deck) || 'General', front: item.prompt, back: item.answer })));
    done(`${parsed.length} card${parsed.length === 1 ? '' : 's'} added to ${deck}.`);
  };

  const saveNotes = () => {
    if (!bits.length) return notify('Paste some notes first', 'Each sentence or line becomes a small study bit.');
    const name = normalizeSpace(title) || 'My notes';
    store.addCapture({ id: uid(), title: name, notes: bulk.trim(), chunks: bits, text_file: '', image: '', audio: '', video: '', created_at: nowLabel() });
    // Each bit's prompt shows its first letters: a real cue to recall from.
    store.addCards(bits.map((bit) => newCard({ deck: name, front: `${name}: ${hangmanHint(bit)}`, back: bit, pathway: `Capture > ${name}` })));
    done(`${bits.length} card${bits.length === 1 ? '' : 's'} made from your notes.`);
  };

  const EVERYDAY: Record<Everyday, { a: string; b: string; aHint: string; bHint: string; make: () => [string, string] }> = {
    person: { a: 'Their name', b: 'Who they are to you', aHint: 'e.g. Priya', bHint: 'e.g. My granddaughter. She visits on Sundays.', make: () => [`Who is ${normalizeSpace(a)}?`, b.trim()] },
    routine: { a: 'Routine', b: 'The steps, one per line', aHint: 'e.g. Morning', bHint: 'e.g. Tablets with water\nBreakfast\nCheck the calendar', make: () => [`What are my ${normalizeSpace(a).toLowerCase()} steps?`, splitStudyBits(b).map((step, i) => `${i + 1}. ${step}`).join('\n')] },
    place: { a: 'The item', b: 'Where it is kept', aHint: 'e.g. glasses', bHint: 'e.g. On the hall table, in the blue case', make: () => [`Where do I keep my ${normalizeSpace(a)}?`, b.trim()] },
    reminder: { a: 'What to remember', b: 'The detail', aHint: 'e.g. Dentist appointment', bHint: 'e.g. Tuesday at 10am, Dr Lee, bring the blue card', make: () => [`What should I remember about ${normalizeSpace(a)}?`, b.trim()] },
  };

  const saveEveryday = () => {
    if (!normalizeSpace(a) || !b.trim()) return notify('Fill in both boxes', 'Both parts are needed to make a helpful card.');
    const [question, answer] = EVERYDAY[kind].make();
    store.addCard(newCard({ deck: EVERYDAY_DECK, front: question, back: answer }));
    done('Everyday card saved. It will come up in Gentle review.');
  };

  const addStarterSet = () => {
    store.addCards([
      newCard({ deck: EVERYDAY_DECK, front: 'What day is it today?', back: 'Check the calendar or the phone’s lock screen.', association: 'The calendar is by the kettle.' }),
      newCard({ deck: EVERYDAY_DECK, front: 'Where do I keep my keys?', back: 'In the bowl by the front door.' }),
      newCard({ deck: EVERYDAY_DECK, front: 'Who can I call if I need help?', back: 'Add the name and number of someone you trust here.' }),
      newCard({ deck: EVERYDAY_DECK, front: 'What helps me feel calm?', back: 'A cup of tea, some music, and a short walk.' }),
    ]);
    done('Four starter cards added. Tap any card in Create to change it to fit.');
  };

  const deckPicker = (
    <View style={{ gap: 8 }}>
      <Field label="Deck" value={deck} onChangeText={setDeck} placeholder="e.g. Biology" autoCapitalize="words" />
      {decks.length ? <Pills label="Existing decks" value={deck} onChange={setDeck} options={decks.slice(0, 8).map((name) => ({ value: name, label: name }))} /> : null}
    </View>
  );

  return (
    <Screen>
      <Pills<Mode>
        label="How do you want to add cards?"
        value={mode}
        onChange={(value) => { setMode(value); setSaved(''); }}
        options={[{ value: 'single', label: 'One card' }, { value: 'paste', label: 'Paste a list' }, { value: 'notes', label: 'From notes' }, { value: 'everyday', label: 'Everyday' }]}
      />

      {saved ? (
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: theme.colors.good[0], borderRadius: 14, padding: 14 }}>
          <Txt variant="body" color={theme.colors.good[1]}>{saved}</Txt>
        </View>
      ) : null}

      {mode === 'single' ? (
        <Card>
          {deckPicker}
          <Field label="Question or prompt" value={front} onChangeText={setFront} multiline placeholder="What is photosynthesis?" />
          <Field label="Answer" hint="Leave it empty for a self-check card." value={back} onChangeText={setBack} multiline placeholder="How plants turn light, water and air into food." />
          <Field label="Memory hook (optional)" hint="A picture, rhyme or story that helps it stick." value={hook} onChangeText={setHook} multiline />
          <Button kind="primary" label="Save card" icon="checkmark" onPress={saveSingle} />
        </Card>
      ) : null}

      {mode === 'paste' ? (
        <Card>
          {deckPicker}
          <Field
            label="One card per line"
            hint={'Question :: Answer   (also "=>", " - ", or a tab — Quizlet and spreadsheet copies work).'}
            value={bulk}
            onChangeText={setBulk}
            multiline
            placeholder={'Capital of France :: Paris\nCapital of Spain :: Madrid'}
            autoCapitalize="none"
            style={{ minHeight: 160 }}
          />
          <Txt variant="muted">{parsed.length ? `${parsed.length} card${parsed.length === 1 ? '' : 's'} ready: e.g. “${parsed[0].prompt}” → “${parsed[0].answer}”` : 'Nothing recognised yet.'}</Txt>
          <Button kind="primary" label={parsed.length ? `Add ${parsed.length} card${parsed.length === 1 ? '' : 's'}` : 'Add cards'} icon="add" onPress={savePaste} />
        </Card>
      ) : null}

      {mode === 'notes' ? (
        <Card>
          <Field label="Title" value={title} onChangeText={setTitle} placeholder="Chapter 3 key terms" autoCapitalize="sentences" />
          <Field label="Your notes" hint="Each sentence or line becomes one small card. Smaller pieces are easier to remember." value={bulk} onChangeText={setBulk} multiline style={{ minHeight: 180 }} />
          {bits.length ? (
            <View style={{ gap: 4 }}>
              <Txt variant="muted">{`${bits.length} study bit${bits.length === 1 ? '' : 's'}:`}</Txt>
              {bits.slice(0, 5).map((bit, i) => <Txt key={i} variant="small">{`${i + 1}. ${bit}`}</Txt>)}
              {bits.length > 5 ? <Txt variant="small">…and {bits.length - 5} more</Txt> : null}
            </View>
          ) : null}
          <Button kind="primary" label="Make cards from notes" icon="sparkles-outline" onPress={saveNotes} />
        </Card>
      ) : null}

      {mode === 'everyday' ? (
        <>
          <Card>
            <Pills<Everyday>
              label="Kind of card"
              value={kind}
              onChange={(value) => { setKind(value); setA(''); setB(''); }}
              options={[{ value: 'person', label: 'Person' }, { value: 'routine', label: 'Routine' }, { value: 'place', label: 'Where things are' }, { value: 'reminder', label: 'Reminder' }]}
            />
            <Field label={EVERYDAY[kind].a} value={a} onChangeText={setA} placeholder={EVERYDAY[kind].aHint} />
            <Field label={EVERYDAY[kind].b} value={b} onChangeText={setB} multiline placeholder={EVERYDAY[kind].bHint} />
            <Button kind="primary" label="Save everyday card" icon="checkmark" onPress={saveEveryday} />
          </Card>
          <Card tone="warm">
            <Txt variant="h3" color={theme.colors.warmText}>Starting from scratch?</Txt>
            <Txt variant="body" color={theme.colors.warmText}>Add four gentle starter cards you can edit to fit.</Txt>
            <Button label="Add starter cards" onPress={addStarterSet} />
          </Card>
        </>
      ) : null}

      <Button kind="ghost" label="Done" onPress={() => router.back()} />
    </Screen>
  );
}
