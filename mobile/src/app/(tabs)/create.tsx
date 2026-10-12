/** Create: add cards, see decks, and find, edit or delete any card. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { memo, useDeferredValue, useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';

import { todayIso } from '../../core/dates';
import type { Card as CardModel } from '../../core/models';
import { useStore } from '../../state/AppState';
import { Button, Card, EmptyState, Field, Pills, Row, Screen, SectionTitle, Txt } from '../../ui/components';
import { useTheme } from '../../ui/theme';

type Filter = 'all' | 'due' | 'weak' | 'new';
const PAGE = 40;

export default function Create() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [deck, setDeck] = useState<string | null>(null);
  const [limit, setLimit] = useState(PAGE);
  const summary = store.deckSummary();
  const today = todayIso();

  // Typing in Search re-filters on the next idle moment, not on every key,
  // and nothing is re-filtered unless the cards or the filters changed.
  const deferredQuery = useDeferredValue(query);
  const matches = useMemo(() => {
    const weakIds = new Set(store.weakCards().map((card) => card.id));
    const q = deferredQuery.trim().toLowerCase();
    return store.cards.filter((card) => {
      if (deck && (card.deck || 'General') !== deck) return false;
      if (filter === 'due' && !(card.next_review <= today && card.buried_until <= today)) return false;
      if (filter === 'weak' && !weakIds.has(card.id)) return false;
      if (filter === 'new' && card.repetitions !== 0) return false;
      return !q || [card.deck, card.front, card.back, card.association].join(' ').toLowerCase().includes(q);
    });
  }, [store, store.version, deferredQuery, deck, filter, today]); // eslint-disable-line react-hooks/exhaustive-deps

  const tiles: { icon: keyof typeof Ionicons.glyphMap; title: string; mode: string }[] = [
    { icon: 'create-outline', title: 'One card', mode: 'single' },
    { icon: 'list-outline', title: 'Paste a list', mode: 'paste' },
    { icon: 'document-text-outline', title: 'From notes', mode: 'notes' },
    { icon: 'people-outline', title: 'Everyday', mode: 'everyday' },
  ];

  return (
    <Screen eyebrow="Create" title="Your cards">
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {tiles.map((tile) => (
          <Card key={tile.mode} onPress={() => router.push(`/add?mode=${tile.mode}`)} accessibilityLabel={`Add cards: ${tile.title}`} style={{ flexBasis: '46%', flexGrow: 1, paddingVertical: 14 }}>
            <Row gap={10}>
              <Ionicons name={tile.icon} size={theme.icon(24)} color={c.link} />
              <Txt variant="h3">{tile.title}</Txt>
            </Row>
          </Card>
        ))}
      </View>

      {Object.keys(summary).length ? (
        <>
          <SectionTitle>Decks</SectionTitle>
          <Card style={{ gap: 0, paddingVertical: 6 }}>
            {Object.entries(summary).map(([name, info], i) => {
              const selected = deck === name;
              return (
                <View key={name} style={{ minHeight: 56, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', gap: 12, borderTopWidth: i ? 1 : 0, borderTopColor: c.line }}>
                  {/* Two separate targets side by side: nesting a button inside
                      another confuses screen readers (and is invalid on web). */}
                  <Pressable
                    onPress={() => { setDeck(selected ? null : name); setLimit(PAGE); }}
                    accessibilityRole="button"
                    accessibilityState={{ selected }}
                    accessibilityLabel={`${name}: ${info.total} cards, ${info.due} due, ${info.mastery} percent mastered`}
                    accessibilityHint={selected ? 'Shows all decks again' : 'Shows only this deck below'}
                    style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 44 }}
                  >
                    <View style={{ flex: 1 }}>
                      <Txt variant="h3" color={selected ? c.link : c.ink}>{name}</Txt>
                      <Txt variant="small">{info.total} cards · {info.due} due · {info.mastery}% mastered</Txt>
                    </View>
                    <Ionicons name={selected ? 'funnel' : 'chevron-forward'} size={theme.icon(20)} color={selected ? c.link : c.muted} />
                  </Pressable>
                  {info.due ? <Button compact kind="primary" label="Study" hint={`Review the ${info.due} due cards in ${name}`} onPress={() => router.push(`/review?mode=due&deck=${encodeURIComponent(name)}`)} /> : null}
                </View>
              );
            })}
          </Card>
        </>
      ) : null}

      <SectionTitle>{deck ? `Cards in ${deck}` : 'All cards'}</SectionTitle>
      <Field label="Search" value={query} onChangeText={(text) => { setQuery(text); setLimit(PAGE); }} placeholder="Search questions, answers, decks" returnKeyType="search" autoCapitalize="none" />
      <Pills<Filter>
        label="Show"
        value={filter}
        onChange={(value) => { setFilter(value); setLimit(PAGE); }}
        options={[{ value: 'all', label: 'All' }, { value: 'due', label: 'Due' }, { value: 'weak', label: 'Weak' }, { value: 'new', label: 'New' }]}
      />
      {deck ? <Button compact kind="ghost" label={`Showing ${deck} only — show all decks`} onPress={() => setDeck(null)} /> : null}

      {!matches.length ? (
        <EmptyState icon="search-outline" title="No cards match" body={store.cards.length ? 'Try another word, or show all cards.' : 'Add your first card with one of the buttons above.'} />
      ) : (
        matches.slice(0, limit).map((card) => (
          <CardRow key={card.id} card={card} leech={store.isLeech(card)} today={today} version={store.version} />
        ))
      )}
      {matches.length > limit ? (
        <Button label={`Show ${Math.min(PAGE, matches.length - limit)} more (${matches.length - limit} left)`} onPress={() => setLimit((value) => value + PAGE)} />
      ) : null}
    </Screen>
  );
}

/** One card in the list; skipped on re-render unless that card or the store changed. */
const CardRow = memo(function CardRow({ card, leech, today }: { card: CardModel; leech: boolean; today: string; version: number }) {
  const c = useTheme().colors;
  return (
    <Card onPress={() => router.push(`/card/${card.id}`)} accessibilityLabel={`${card.front}. Answer: ${card.back || 'none'}. Tap to edit.`}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label">{card.deck}</Txt>
        <Txt variant="small">{card.repetitions ? `Next ${card.next_review <= today ? 'today' : card.next_review}` : 'New'}</Txt>
      </Row>
      <Txt variant="h3">{card.front}</Txt>
      {card.back ? <Txt variant="muted" numberOfLines={3}>{card.back}</Txt> : null}
      {leech ? (
        <View style={{ backgroundColor: c.again[0], borderRadius: 10, padding: 8 }}>
          <Txt variant="small" color={c.again[1]}>{`Missed ${card.lapses} times — try rewriting it or adding a memory hook.`}</Txt>
        </View>
      ) : null}
    </Card>
  );
});
