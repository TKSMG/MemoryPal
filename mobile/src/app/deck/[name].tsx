/** One set: study it, add to it, rename it, delete it, and see its cards. */
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { normalizeSpace } from '../../core/text';
import { isAiCard } from '../../core/questions';
import { deckCards, deleteDeck, renameDeck } from '../../features/decks';
import { AI_TAG } from '../../features/aiHelpers';
import { useStore } from '../../state/AppState';
import { AiTag, Button, EmptyState, Field, ListGroup, ListRow, Screen, Txt } from '../../ui/components';
import { confirm } from '../../ui/feedback';

const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

export default function Deck() {
  const store = useStore();
  const params = useLocalSearchParams<{ name: string }>();
  const [name, setName] = useState(String(params.name ?? ''));
  const [draft, setDraft] = useState(name);
  const cards = deckCards(store, name);
  const info = store.deckSummary()[name];
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

  const remove = async () => {
    if (await confirm(`Delete “${name}”?`, `All ${plural(cards.length, 'card')} in this set and their review history will be removed. This can’t be undone.`, 'Delete set', true)) {
      deleteDeck(store, name);
      router.back();
    }
  };

  return (
    <Screen narrow>
      <Stack.Screen options={{ title: name }} />
      <Txt variant="muted">{`${plural(info.total, 'card')}, ${info.due} due, ${info.mastery}% mastered`}</Txt>

      <ListGroup>
        <ListRow icon="play-circle-outline" title={info.due ? `Review ${plural(info.due, 'due card')}` : 'Practise this set'} onPress={() => router.push(`/review?mode=${info.due ? 'due' : 'all'}&deck=${q}` as Href)} />
        <ListRow icon="chatbubbles-outline" title="Talk-back study" detail="Hear each question, say the answer" onPress={() => router.push(`/talkback?mode=all&deck=${q}` as Href)} />
        <ListRow icon="list-circle-outline" title="Quick quiz" detail="Mixed questions: pick, match, fill in" onPress={() => router.push(`/quiz?deck=${q}` as Href)} />
        <ListRow icon="add-circle-outline" title="Add cards" onPress={() => router.push(`/add?deck=${q}` as Href)} />
        <ListRow icon="sparkles-outline" title="Make with AI" detail="Notes or questions from notes, a PDF or a photo" onPress={() => router.push(`/ai?deck=${q}` as Href)} />
      </ListGroup>

      <View style={{ gap: 10 }}>
        <Field label="Set name" value={draft} onChangeText={setDraft} autoCapitalize="words" returnKeyType="done" onSubmitEditing={rename} />
        <Button label="Rename set" icon="pencil-outline" onPress={rename} disabled={!normalizeSpace(draft) || normalizeSpace(draft) === name} />
      </View>

      <ListGroup header="Cards">
        {cards.slice(0, 200).map((card) => (
          <ListRow
            key={card.id}
            title={card.front}
            detail={card.back || 'No answer (self-check)'}
            below={isAiCard(card) ? <AiTag /> : null}
            accessibilityLabel={[card.front, card.back || 'No answer (self-check)', isAiCard(card) ? AI_TAG : ''].filter(Boolean).join(', ')}
            onPress={() => router.push(`/card/${card.id}`)}
            accessibilityHint="Opens the card to edit"
          />
        ))}
      </ListGroup>
      {cards.length > 200 ? <Txt variant="small">{`Showing the first 200 of ${cards.length}. Search in Create to find the rest.`}</Txt> : null}

      <Button kind="dangerGhost" label="Delete set" icon="trash-outline" onPress={remove} />
    </Screen>
  );
}
