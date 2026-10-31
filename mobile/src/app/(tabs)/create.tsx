/** Create: start a set, open your sets, and find, edit or delete any card. */
import { Href, router } from 'expo-router';
import { memo, useCallback, useDeferredValue, useMemo, useState } from 'react';
import { View } from 'react-native';

import { todayIso } from '../../core/dates';
import { examCountdown } from '../../features/decks';
import type { Card as CardModel } from '../../core/models';
import { isAiCard } from '../../core/questions';
import { useStore } from '../../state/AppState';
import { AiTag, Button, Card, EmptyState, Field, ListGroup, ListRow, Pills, Row, ScreenList, SectionTitle, Txt } from '../../ui/components';
import { relativeDay } from '../../ui/dates';
import { setTone, useTheme } from '../../ui/theme';

type Filter = 'all' | 'due' | 'weak' | 'new';

export default function Create() {
  const store = useStore();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const summary = store.deckSummary();
  const today = todayIso();

  // Typing in Search re-filters on the next idle moment, not on every key,
  // and nothing is re-filtered unless the cards or the filters changed.
  const deferredQuery = useDeferredValue(query);
  const matches = useMemo(() => {
    const weakIds = new Set(store.weakCards().map((card) => card.id));
    const q = deferredQuery.trim().toLowerCase();
    return store.cards.filter((card) => {
      if (filter === 'due' && !(card.next_review <= today && card.buried_until <= today)) return false;
      if (filter === 'weak' && !weakIds.has(card.id)) return false;
      if (filter === 'new' && card.repetitions !== 0) return false;
      return !q || [card.deck, card.front, card.back, card.association].join(' ').toLowerCase().includes(q);
    });
  }, [store, store.version, deferredQuery, filter, today]); // eslint-disable-line react-hooks/exhaustive-deps

  // Leech status is worked out once per list change rather than once per row render.
  const leeches = useMemo(() => new Set(matches.filter((card) => store.isLeech(card)).map((card) => card.id)), [matches, store]);
  const renderCard = useCallback(
    ({ item }: { item: CardModel }) => <CardRow card={item} leech={leeches.has(item.id)} today={today} stamp={cardStamp(item)} />,
    [leeches, today],
  );

  const header = (
    <>
      <Row style={{ alignItems: 'stretch' }}>
        <Button kind="primary" label="New set" icon="add" onPress={() => router.push('/add')} style={{ flex: 1 }} hint="Name a set, then type or paste its cards" />
        <Button label="Paste notes" icon="clipboard-outline" onPress={() => router.push('/add?mode=paste')} style={{ flex: 1 }} />
      </Row>

      {Object.keys(summary).length ? (
        <ListGroup header="Sets">
          {Object.entries(summary).map(([name, info]) => (
            <ListRow
              key={name}
              icon="albums-outline"
              tone={setTone(name)}
              title={name}
              detail={[`${info.total} card${info.total === 1 ? '' : 's'}${info.due ? `, ${info.due} due` : ''}`, examCountdown(store.deckInfo(name).exam_date)].filter(Boolean).join(' · ')}
              onPress={() => router.push(`/deck/${encodeURIComponent(name)}` as Href)}
              accessibilityHint="Opens the set to study, rename or delete it"
            />
          ))}
        </ListGroup>
      ) : null}

      {store.captures.length ? (
        <ListGroup>
          <ListRow icon="reader-outline" title="Saved notes" value={String(store.captures.length)} onPress={() => router.push('/notes' as Href)} accessibilityHint="Notes you saved from Make with AI or pasted into a set" />
        </ListGroup>
      ) : null}

      <SectionTitle>All cards</SectionTitle>
      <Field label="Search" value={query} onChangeText={setQuery} placeholder="Questions, answers, sets" returnKeyType="search" autoCapitalize="none" />
      <Pills<Filter>
        label="Show"
        value={filter}
        onChange={setFilter}
        options={[{ value: 'all', label: 'All' }, { value: 'due', label: 'Due' }, { value: 'weak', label: 'Weak' }, { value: 'new', label: 'New' }]}
      />
    </>
  );

  return (
    <ScreenList
      title="Create"
      header={header}
      data={matches}
      renderItem={renderCard}
      keyExtractor={(card) => card.id}
      empty={<EmptyState icon="search-outline" title="No cards match" body={store.cards.length ? 'Try another word, or show all cards.' : 'Start a set with New set above.'} />}
    />
  );
}

/**
 * The store edits cards in place, so a changed card is the same object as
 * before. This stamp of everything a row shows changes with it, which lets the
 * memoised row re-render for that card alone.
 */
function cardStamp(card: CardModel): string {
  return [card.deck, card.front, card.back, card.repetitions, card.next_review, card.lapses, card.pathway].join('\u0000');
}

/** One card in the list; skipped on re-render unless what it shows changed. */
const CardRow = memo(function CardRow({ card, leech, today }: { card: CardModel; leech: boolean; today: string; stamp: string }) {
  const c = useTheme().colors;
  return (
    <Card onPress={() => router.push(`/card/${card.id}`)} accessibilityLabel={`${card.front}. Answer: ${card.back || 'none'}.${isAiCard(card) ? ' Made with AI, check it.' : ''} Tap to edit.`}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label" style={{ flexShrink: 1 }}>{card.deck}</Txt>
        <Txt variant="small">{card.repetitions ? `Next ${card.next_review <= today ? 'today' : relativeDay(card.next_review)}` : 'New'}</Txt>
      </Row>
      <Txt variant="h3">{card.front}</Txt>
      {card.back ? <Txt variant="muted" numberOfLines={3}>{card.back}</Txt> : null}
      {isAiCard(card) ? <AiTag /> : null}
      {leech ? (
        <View style={{ backgroundColor: c.again[0], borderRadius: 10, padding: 8 }}>
          <Txt variant="small" color={c.again[1]}>{`Missed ${card.lapses} times. Try rewriting it or adding a memory hook.`}</Txt>
        </View>
      ) : null}
    </Card>
  );
});
