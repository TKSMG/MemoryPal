/** Practice: memory techniques for lists, plus short memory puzzles. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Href, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { parseIdeas, TECHNIQUES } from '../../core/techniques';
import { addTechniqueHooks, techniqueItems } from '../../features/decks';
import { useStore } from '../../state/AppState';
import { confirm, notify } from '../../ui/feedback';
import { Button, Card, Field, ListGroup, ListRow, Pills, Row, Screen, SectionTitle, SpeakButton, Txt } from '../../ui/components';
import { useTheme } from '../../ui/theme';

const PUZZLES: { kind: string; icon: keyof typeof Ionicons.glyphMap; title: string; body: string }[] = [
  { kind: 'sequence', icon: 'keypad-outline', title: 'Sequence recall', body: 'See a short run of numbers, then type it back.' },
  { kind: 'words', icon: 'reader-outline', title: 'Word recall', body: 'Look at a few words, then list as many as you can.' },
  { kind: 'pairs', icon: 'swap-horizontal-outline', title: 'Pair recall', body: 'See a word pair, then remember the partner.' },
];

export default function Practice() {
  const theme = useTheme();
  const c = theme.colors;
  const store = useStore();
  const sets = store.decks();
  const [ideas, setIdeas] = useState('');
  // A set chosen here fills the box with its answers; its cards can then keep their lines as hooks.
  const [set, setSet] = useState('');
  const [technique, setTechnique] = useState(TECHNIQUES[0].key);
  const items = parseIdeas(ideas);
  const chosen = TECHNIQUES.find((item) => item.key === technique) ?? TECHNIQUES[0];
  const output = items.length ? chosen.make(items) : '';
  const fromSet = set ? techniqueItems(store, set) : null;
  const unchanged = !!fromSet && fromSet.items.join('\n') === ideas;

  const chooseSet = (name: string) => {
    setSet(name);
    setIdeas(name ? techniqueItems(store, name).items.join('\n') : '');
  };
  const saveHooks = async () => {
    if (!fromSet) return;
    if (!(await confirm('Save as memory hooks?', `Each of the ${fromSet.cards.length} cards in ${set} gets its own line from the ${chosen.title.toLowerCase()}, added to its memory hook.`, 'Save hooks'))) return;
    const changed = addTechniqueHooks(store, set, technique);
    notify(changed ? 'Hooks saved' : 'Nothing to add', changed ? `${changed} card${changed === 1 ? '' : 's'} in ${set} now have the hook. You’ll see it when you review them.` : 'Those cards already have these hooks.');
  };

  return (
    <Screen title="Practice">
      <SectionTitle>Make a list memorable</SectionTitle>
      <Card>
        {sets.length ? (
          <Pills label="Or use a set’s cards" value={set} onChange={chooseSet} options={[{ value: '', label: 'My own list' }, ...sets.map((name) => ({ value: name, label: name }))]} />
        ) : null}
        <Field
          label="Things to remember"
          hint="Separate them with commas or new lines."
          value={ideas}
          onChangeText={setIdeas}
          multiline
          placeholder="milk, eggs, bread, apples"
        />
        <Pills label="Technique" value={technique} onChange={setTechnique} options={TECHNIQUES.map((item) => ({ value: item.key, label: item.title }))} />
        <Txt variant="muted">{chosen.blurb}</Txt>
        {output ? (
          <View style={{ backgroundColor: c.alt, borderRadius: 14, padding: 14, gap: 8 }} accessibilityLiveRegion="polite">
            <Txt variant="body">{output}</Txt>
            <Row style={{ justifyContent: 'flex-end' }}>
              <SpeakButton text={output} label="Read it aloud" />
            </Row>
          </View>
        ) : null}
        {output && unchanged ? (
          <Button icon="bookmark-outline" label={`Save as hooks on ${set}’s cards`} onPress={saveHooks} hint="Each card gets its own line, added to its memory hook" />
        ) : null}
      </Card>

      <ListGroup header="Puzzles">
        {PUZZLES.map((puzzle) => (
          <ListRow key={puzzle.kind} icon={puzzle.icon} title={puzzle.title} detail={puzzle.body} onPress={() => router.push(`/puzzle?kind=${puzzle.kind}` as Href)} />
        ))}
      </ListGroup>

      <ListGroup header="Why these work">
        {[
          ['Spaced practice', 'Reviewing just as something starts to fade makes it last much longer than cramming.'],
          ['Retrieval practice', 'Trying to recall, especially when it is hard, is what builds memory.'],
          ['Elaboration', 'Ask why and how. Linking a fact to what you know gives it more hooks.'],
          ['Dual coding', 'Pair words with a picture or a sound for a second route back.'],
        ].map(([title, body]) => (
          <ListRow key={title} title={title} detail={body} />
        ))}
      </ListGroup>
    </Screen>
  );
}
