/** Saved notes: everything kept from Make with AI or pasted notes, grouped by set. */
import { Href, router } from 'expo-router';

import { captureDeck } from '../../core/store';
import { useStore } from '../../state/AppState';
import { EmptyState, ListGroup, ListRow, Screen, Txt } from '../../ui/components';

export default function SavedNotes() {
  const store = useStore();
  const sets = store.decks();
  const groups = new Map<string, typeof store.captures>();
  for (const capture of store.captures) {
    const deck = captureDeck(capture, sets);
    groups.set(deck, [...(groups.get(deck) ?? []), capture]);
  }
  const names = [...groups.keys()].sort((a, b) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b)));

  if (!store.captures.length) {
    return (
      <Screen narrow>
        <EmptyState icon="reader-outline" title="No saved notes yet" body="Notes you save from Make with AI, or paste when making a set, appear here." />
      </Screen>
    );
  }

  return (
    <Screen narrow>
      <Txt variant="muted">Notes you saved from Make with AI or pasted into a set. Open one to read it, hear it, or make questions from it.</Txt>
      {names.map((name) => (
        <ListGroup key={name || '-'} header={name || 'Not in a set'}>
          {(groups.get(name) ?? []).map((capture) => (
            <ListRow key={capture.id} icon="reader-outline" title={capture.title} detail={capture.created_at} onPress={() => router.push(`/notes/${capture.id}` as Href)} accessibilityHint="Opens these notes to read" />
          ))}
        </ListGroup>
      ))}
    </Screen>
  );
}
