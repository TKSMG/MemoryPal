/** Edit a card's words, start it over, or delete it. Its schedule is kept on edit. */
import { router, Stack, useLocalSearchParams, useNavigation } from 'expo-router';
import { useEffect, useRef, useState } from 'react';

import { useStore } from '../../state/AppState';
import { Button, Card, EmptyState, Field, Row, Screen, Txt } from '../../ui/components';
import { confirm, notify } from '../../ui/feedback';

export default function EditCard() {
  const store = useStore();
  const { id } = useLocalSearchParams<{ id: string }>();
  const card = store.findCard(String(id));
  const [deck, setDeck] = useState(card?.deck ?? '');
  const [front, setFront] = useState(card?.front ?? '');
  const [back, setBack] = useState(card?.back ?? '');
  const [hook, setHook] = useState(card?.association ?? '');
  const navigation = useNavigation();

  // With unsaved edits the sheet can't be swiped away, and Cancel or the
  // back button asks before throwing the edits away.
  const dirty = !!card && (deck !== (card.deck ?? '') || front !== (card.front ?? '') || back !== (card.back ?? '') || hook !== (card.association ?? ''));
  const leaving = useRef(false);
  useEffect(() => {
    if (!dirty) return undefined;
    return navigation.addListener('beforeRemove', (event) => {
      if (leaving.current) return;
      event.preventDefault();
      confirm('Discard your changes?', 'Your edits to this card haven’t been saved.', 'Discard', true).then((ok) => {
        if (!ok) return;
        leaving.current = true;
        navigation.dispatch(event.data.action);
      });
    });
  }, [dirty, navigation]);
  const leave = () => {
    leaving.current = true;
    router.back();
  };

  if (!card) {
    return (
      <Screen>
        <EmptyState icon="alert-circle-outline" title="This card is gone" body="It may have been deleted." action={<Button label="Go back" onPress={() => router.back()} />} />
      </Screen>
    );
  }

  const save = () => {
    if (!front.trim()) return notify('A card needs a question', 'Type the question or prompt.');
    store.updateCard(card, { deck, front, back, association: hook });
    leave();
  };

  const remove = async () => {
    if (await confirm('Delete this card?', `“${card.front.slice(0, 80)}” and its review history will be removed. This can't be undone.`, 'Delete', true)) {
      store.deleteCards([card.id]);
      leave();
    }
  };

  const learnAgain = async () => {
    if (await confirm('Learn this card again?', 'Its progress is reset and it comes back as a new card today.', 'Learn again')) {
      store.resetProgress([card.id]);
      leave();
    }
  };

  return (
    <Screen>
      <Stack.Screen options={{ gestureEnabled: !dirty }} />
      <Card tone="alt">
        <Txt variant="small">
          {card.repetitions
            ? `Next review ${card.next_review} · every ${card.interval} day${card.interval === 1 ? '' : 's'} · last result: ${card.last_result}${card.lapses ? ` · missed ${card.lapses}×` : ''}`
            : 'New card — not reviewed yet.'}
        </Txt>
      </Card>
      <Field label="Deck" value={deck} onChangeText={setDeck} autoCapitalize="words" />
      <Field label="Question or prompt" value={front} onChangeText={setFront} multiline />
      <Field label="Answer" hint="Leave it empty for a self-check card." value={back} onChangeText={setBack} multiline />
      <Field label="Memory hook (optional)" value={hook} onChangeText={setHook} multiline />
      {store.isLeech(card) ? (
        <Txt variant="muted">Tip: a card missed this often is usually too big or too vague. Split it into two, make the question more specific, or add a memory hook.</Txt>
      ) : null}
      <Button kind="primary" label="Save changes" icon="checkmark" onPress={save} />
      <Row>
        <Button label="Learn again" icon="refresh" onPress={learnAgain} style={{ flex: 1 }} />
        <Button kind="danger" label="Delete" icon="trash-outline" onPress={remove} style={{ flex: 1 }} />
      </Row>
    </Screen>
  );
}
