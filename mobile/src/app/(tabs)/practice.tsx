/** Practice: memory techniques for lists, plus short memory puzzles. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Href, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { parseIdeas, TECHNIQUES } from '../../core/techniques';
import { Button, Card, Field, Pills, Row, Screen, SectionTitle, Txt } from '../../ui/components';
import { speak } from '../../ui/feedback';
import { useTheme } from '../../ui/theme';
import { useStore } from '../../state/AppState';

const PUZZLES: { kind: string; icon: keyof typeof Ionicons.glyphMap; title: string; body: string }[] = [
  { kind: 'sequence', icon: 'keypad-outline', title: 'Sequence recall', body: 'See a short run of numbers, then type it back.' },
  { kind: 'words', icon: 'reader-outline', title: 'Word recall', body: 'Look at a few words, then list as many as you can.' },
  { kind: 'pairs', icon: 'swap-horizontal-outline', title: 'Pair recall', body: 'See a word pair, then remember the partner.' },
];

export default function Practice() {
  const theme = useTheme();
  const store = useStore();
  const c = theme.colors;
  const [ideas, setIdeas] = useState('');
  const [technique, setTechnique] = useState(TECHNIQUES[0].key);
  const items = parseIdeas(ideas);
  const chosen = TECHNIQUES.find((item) => item.key === technique) ?? TECHNIQUES[0];
  const output = items.length ? chosen.make(items) : '';

  return (
    <Screen eyebrow="Practice" title="Memory gym">
      <SectionTitle>Make a list memorable</SectionTitle>
      <Card>
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
            <Row>
              <Button compact label="Read aloud" icon="volume-high-outline" onPress={() => speak(output, store.accessibility.more_time)} style={{ flex: 1 }} />
            </Row>
          </View>
        ) : null}
      </Card>

      <SectionTitle>Puzzles</SectionTitle>
      {PUZZLES.map((puzzle) => (
        <Card key={puzzle.kind} onPress={() => router.push(`/puzzle?kind=${puzzle.kind}` as Href)} accessibilityLabel={`${puzzle.title}. ${puzzle.body}`}>
          <Row>
            <Ionicons name={puzzle.icon} size={theme.icon(26)} color={c.link} />
            <View style={{ flex: 1, gap: 2 }}>
              <Txt variant="h3">{puzzle.title}</Txt>
              <Txt variant="muted">{puzzle.body}</Txt>
            </View>
            <Ionicons name="chevron-forward" size={theme.icon(20)} color={c.muted} />
          </Row>
        </Card>
      ))}

      <SectionTitle>Why these work</SectionTitle>
      {[
        ['Spaced practice', 'Reviewing just as something starts to fade makes it last much longer than cramming.'],
        ['Retrieval practice', 'Trying to recall, even and especially when it is hard, is what builds memory.'],
        ['Elaboration', 'Ask why and how. Linking a fact to things you know gives it more hooks.'],
        ['Dual coding', 'Pair words with a picture or a sound for a second route back to the memory.'],
      ].map(([title, body]) => (
        <Card key={title} tone="alt">
          <Txt variant="h3">{title}</Txt>
          <Txt variant="muted">{body}</Txt>
        </Card>
      ))}
    </Screen>
  );
}
