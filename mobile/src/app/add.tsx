/**
 * Build a set: name it (or pick one), then add cards in one place. Type
 * question and answer rows, or paste notes or a list and edit the rows it
 * makes before saving. Memory hooks and everyday cards sit under More options.
 */
import { Href, router, useFocusEffect, useLocalSearchParams, useNavigation } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { nowLabel } from '../core/dates';
import { newCard, uid } from '../core/models';
import { normalizeSpace, splitStudyBits } from '../core/text';
import { sendNotesToAi, takeRowsForBuilder } from '../features/aiHandoff';
import { aiPage } from '../features/aiHelpers';
import { blankRow, hasContent, readyRows, Row, splitPasted } from '../features/setBuilder';
import { useStore } from '../state/AppState';
import { AiTag, Button, Card, Disclosure, Field, IconButton, ListGroup, ListRow, MIN_TOUCH, Pills, RichField, Row as HRow, Screen, SectionTitle, ToggleRow, Txt } from '../ui/components';
import { confirm, notify } from '../ui/feedback';
import { useTheme } from '../ui/theme';

type Everyday = 'person' | 'routine' | 'place' | 'reminder';

const EVERYDAY_DECK = 'Everyday Memory';

const EVERYDAY: Record<Everyday, { a: string; b: string; aHint: string; bHint: string; make: (a: string, b: string) => [string, string] }> = {
  person: { a: 'Their name', b: 'Who they are to you', aHint: 'e.g. Priya', bHint: 'e.g. My granddaughter. She visits on Sundays.', make: (a, b) => [`Who is ${normalizeSpace(a)}?`, b.trim()] },
  routine: { a: 'Routine', b: 'The steps, one per line', aHint: 'e.g. Morning', bHint: 'e.g. Tablets with water\nBreakfast\nCheck the calendar', make: (a, b) => [`What are my ${normalizeSpace(a).toLowerCase()} steps?`, splitStudyBits(b).map((step, i) => `${i + 1}. ${step}`).join('\n')] },
  place: { a: 'The item', b: 'Where it is kept', aHint: 'e.g. glasses', bHint: 'e.g. On the hall table, in the blue case', make: (a, b) => [`Where do I keep my ${normalizeSpace(a)}?`, b.trim()] },
  reminder: { a: 'What to remember', b: 'The detail', aHint: 'e.g. Dentist appointment', bHint: 'e.g. Tuesday at 10am, Dr Lee, bring the blue card', make: (a, b) => [`What should I remember about ${normalizeSpace(a)}?`, b.trim()] },
};

const STARTERS: [string, string, string][] = [
  ['What day is it today?', 'Check the calendar or the phone’s lock screen.', 'The calendar is by the kettle.'],
  ['Where do I keep my keys?', 'In the bowl by the front door.', ''],
  ['Who can I call if I need help?', 'Add the name and number of someone you trust here.', ''],
  ['What helps me feel calm?', 'A cup of tea, some music, and a short walk.', ''],
];

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

export default function Add() {
  const store = useStore();
  const theme = useTheme();
  const navigation = useNavigation();
  const params = useLocalSearchParams<{ mode?: string; deck?: string }>();
  const everydayStart = params.mode === 'everyday';
  const [deck, setDeck] = useState(params.deck || (everydayStart ? EVERYDAY_DECK : ''));
  const [rows, setRows] = useState<Row[]>(() => [blankRow()]);
  const [pasteOpen, setPasteOpen] = useState(params.mode === 'paste' || params.mode === 'notes');
  const [pasted, setPasted] = useState('');
  // Notes that were split into rows, kept with the set as a capture (as before).
  const [notes, setNotes] = useState('');
  const [moreOpen, setMoreOpen] = useState(everydayStart);
  const [showHooks, setShowHooks] = useState(false);
  const [kind, setKind] = useState<Everyday>('person');
  const [a, setA] = useState('');
  const [b, setB] = useState('');
  const [saved, setSaved] = useState('');
  const [aiMessage, setAiMessage] = useState('');

  const decks = store.decks();
  const ready = readyRows(rows);
  const name = normalizeSpace(deck);

  // Leaving with unsaved rows asks first, like editing a card.
  const dirty = rows.some(hasContent) || !!pasted.trim();
  const leaving = useRef(false);
  useEffect(() => {
    if (!dirty) return undefined;
    return navigation.addListener('beforeRemove', (event) => {
      if (leaving.current) return;
      event.preventDefault();
      confirm('Discard these cards?', 'The cards you typed haven’t been saved.', 'Discard', true).then((ok) => {
        if (!ok) return;
        leaving.current = true;
        navigation.dispatch(event.data.action);
      });
    });
  }, [dirty, navigation]);

  const update = (key: string, changes: Partial<Row>) => {
    setSaved('');
    setRows((list) => list.map((row) => (row.key === key ? { ...row, ...changes } : row)));
  };
  const remove = (key: string) => setRows((list) => (list.length > 1 ? list.filter((row) => row.key !== key) : [blankRow()]));
  // New rows replace a lone empty row instead of sitting under it.
  const append = (extra: Row[]) => {
    setSaved('');
    setRows((list) => [...list.filter(hasContent), ...extra]);
  };

  // Rows made on the Make with AI screen arrive when this screen is shown again.
  useFocusEffect(
    useCallback(() => {
      const { rows: made, message } = takeRowsForBuilder();
      if (!made.length) return;
      setSaved('');
      setRows((list) => [...list.filter(hasContent), ...made]);
      setAiMessage(message);
    }, []),
  );

  const openAi = () => {
    sendNotesToAi([pasted.trim(), notes.trim()].filter(Boolean).join('\n\n'));
    router.push(`/ai?from=add&deck=${encodeURIComponent(name)}` as Href);
  };

  const split = () => {
    const result = splitPasted(pasted);
    if (!result.rows.length) return notify('Nothing to split yet', 'Paste notes, or one card per line like “Capital of France :: Paris”.');
    append(result.rows);
    if (result.fromNotes) setNotes((value) => [value, pasted.trim()].filter(Boolean).join('\n\n'));
    setPasted('');
    setPasteOpen(false);
  };

  // Everyday cards always live in their own set, which Gentle review reads.
  const everyday = (row: Row): Row => (name && name !== EVERYDAY_DECK ? { ...row, deck: EVERYDAY_DECK } : row);

  const addEveryday = () => {
    if (!normalizeSpace(a) || !b.trim()) return notify('Fill in both boxes', 'Both parts are needed to make a helpful card.');
    const [front, back] = EVERYDAY[kind].make(a, b);
    if (!name) setDeck(EVERYDAY_DECK);
    append([everyday(blankRow(front, back))]);
    setA('');
    setB('');
  };

  const addStarters = () => {
    if (!name) setDeck(EVERYDAY_DECK);
    append(STARTERS.map(([front, back, hook]) => everyday(blankRow(front, back, hook))));
    if (STARTERS.some(([, , hook]) => hook)) setShowHooks(true);
  };

  const save = () => {
    if (!name) return notify('Name your set first', 'Type a name at the top, or pick one of your sets.');
    if (!ready.length) return notify('Add a question', 'Each card needs a question. The answer can be left empty for a self-check card.');
    const fromNotes = !!notes.trim();
    if (fromNotes) {
      store.addCapture({ id: uid(), title: name, notes: notes.trim(), chunks: splitStudyBits(notes), text_file: '', image: '', audio: '', video: '', created_at: nowLabel(), deck: name });
    }
    store.addCards(
      ready.map((row) =>
        newCard({
          deck: row.deck || name,
          front: row.front,
          back: row.back,
          association: row.hook || row.note || '',
          // AI rows keep their "Made with AI > …" pathway (it labels the card); the set name follows any rename.
          pathway: row.pathway ? row.pathway.replace(/ > .*$/, ` > ${name}`) : fromNotes ? `Capture > ${name}` : '',
          image: row.image || '',
          text_file: row.text_file || '',
        }),
      ),
    );
    leaving.current = false;
    setAiMessage('');
    setSaved(`${plural(ready.length, 'card')} saved to ${name}.`);
    setRows([blankRow()]);
    setNotes('');
  };

  return (
    <Screen narrow>
      <View style={{ gap: 8 }}>
        <Field label="Set name" value={deck} onChangeText={(value) => { setDeck(value); setSaved(''); }} placeholder="e.g. Spanish verbs" autoCapitalize="words" returnKeyType="next" />
        {decks.length ? <Pills label="Your sets" value={deck} onChange={(value) => { setDeck(value); setSaved(''); }} options={decks.slice(0, 8).map((item) => ({ value: item, label: item }))} /> : null}
      </View>

      {saved ? (
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: theme.colors.good[0], borderRadius: theme.radius, padding: 14 }}>
          <Txt variant="body" color={theme.colors.good[1]}>{saved}</Txt>
        </View>
      ) : null}

      {aiMessage ? (
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: theme.colors.review[0], borderRadius: theme.radius, padding: 14 }}>
          <Txt variant="body" color={theme.colors.review[1]}>{aiMessage}</Txt>
        </View>
      ) : null}

      <SectionTitle action={<Txt variant="muted" accessibilityLiveRegion="polite">{ready.length ? `${plural(ready.length, 'card')} ready` : 'No cards yet'}</Txt>}>Cards</SectionTitle>

      {rows.map((row, i) => (
        <Card key={row.key}>
          <HRow style={{ justifyContent: 'space-between', minHeight: MIN_TOUCH }}>
            <View style={{ flex: 1, gap: 4 }}>
              <Txt variant="label">{row.deck ? `Card ${i + 1}, goes to ${row.deck}` : `Card ${i + 1}`}</Txt>
              {row.pathway ? <AiTag /> : null}
              {row.image ? <Txt variant="small">The photo is attached to this card.</Txt> : null}
              {row.text_file ? <Txt variant="small">{aiPage({ association: row.note ?? '' }) ? `The PDF is attached, page ${aiPage({ association: row.note ?? '' })}.` : 'The PDF is attached.'}</Txt> : null}
            </View>
            {rows.length > 1 || hasContent(row) ? <IconButton icon="trash-outline" label={`Remove card ${i + 1}`} onPress={() => remove(row.key)} /> : null}
          </HRow>
          <Field label="Question" value={row.front} onChangeText={(value) => update(row.key, { front: value })} multiline placeholder="What is photosynthesis?" style={{ minHeight: 52 }} />
          <Field label="Answer" value={row.back} onChangeText={(value) => update(row.key, { back: value })} multiline placeholder="How plants turn light into food" style={{ minHeight: 52 }} />
          {showHooks || row.hook ? (
            <Field label="Memory hook" value={row.hook} onChangeText={(value) => update(row.key, { hook: value })} multiline placeholder="A picture, rhyme or story" style={{ minHeight: 52 }} />
          ) : null}
        </Card>
      ))}

      <Button label="Add a card" icon="add" onPress={() => append([blankRow()])} />

      <ListGroup footer="Make notes or questions from your notes, a PDF or a photo. AI can be wrong, so check what it makes.">
        <ListRow icon="sparkles-outline" title="Make with AI" detail="From notes, a PDF or a photo" onPress={openAi} />
      </ListGroup>

      <Disclosure title="Paste notes or a list" open={pasteOpen} onToggle={() => setPasteOpen((value) => !value)}>
        <RichField
          label="Notes or list"
          hint="A list like “Question :: Answer” keeps its pairs. Notes become one card per sentence, which you can edit before saving. Bold or highlighted words become the blank to fill in."
          value={pasted}
          onChangeText={setPasted}
          placeholder={'Capital of France :: Paris\nThe heart is a muscle that pumps blood.'}
          style={{ minHeight: 140 }}
        />
        <Button label="Split into cards" icon="git-branch-outline" onPress={split} disabled={!pasted.trim()} />
      </Disclosure>

      <Disclosure title="More options" open={moreOpen} onToggle={() => setMoreOpen((value) => !value)}>
        <ToggleRow label="Memory hooks" description="Add a picture, rhyme or story to each card." value={showHooks} onChange={setShowHooks} />
        <View style={{ gap: 10 }}>
          <Txt variant="h3">Everyday card</Txt>
          <Txt variant="muted">A person, routine, place or reminder. These go in {EVERYDAY_DECK} for Gentle review.</Txt>
          <Pills<Everyday>
            label="Kind of everyday card"
            value={kind}
            onChange={(value) => { setKind(value); setA(''); setB(''); }}
            options={[{ value: 'person', label: 'Person' }, { value: 'routine', label: 'Routine' }, { value: 'place', label: 'Where things are' }, { value: 'reminder', label: 'Reminder' }]}
          />
          <Field label={EVERYDAY[kind].a} value={a} onChangeText={setA} placeholder={EVERYDAY[kind].aHint} />
          <Field label={EVERYDAY[kind].b} value={b} onChangeText={setB} multiline placeholder={EVERYDAY[kind].bHint} />
          <Button label="Add to the cards" icon="add" onPress={addEveryday} />
          <Button kind="ghost" label="Add four starter cards" onPress={addStarters} hint="Gentle everyday cards you can edit to fit." />
        </View>
      </Disclosure>

      <Button
        kind="primary"
        icon="checkmark"
        label={ready.length ? `Save ${plural(ready.length, 'card')}` : 'Save'}
        onPress={save}
        disabled={!ready.length}
        hint={name ? `Saves to ${name}` : 'Name the set first'}
      />
      {saved ? <Button kind="ghost" label="Done" onPress={() => { leaving.current = true; router.back(); }} /> : null}
    </Screen>
  );
}
