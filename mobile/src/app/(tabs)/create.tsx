/** Create: add cards, see decks, and find, edit or delete any card. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { memo, useCallback, useDeferredValue, useMemo, useState } from 'react';
import { Pressable, useWindowDimensions, View } from 'react-native';

import { todayIso } from '../../core/dates';
import type { Card as CardModel } from '../../core/models';
import { useStore } from '../../state/AppState';
import { Button, Card, EmptyState, Field, Pills, Row, ScreenList, SectionTitle, Txt } from '../../ui/components';
import { relativeDay } from '../../ui/dates';
import { useTheme } from '../../ui/theme';

type Filter = 'all' | 'due' | 'weak' | 'new';

export default function Create() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [deck, setDeck] = useState<string | null>(null);
  const { fontScale } = useWindowDimensions();
  // At the largest text sizes the icon goes above the label, so a two-word
  // label keeps the tile's full width instead of breaking mid-word.
  const stackTiles = theme.scale * fontScale >= 1.3;
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

  // Leech status is worked out once per list change rather than once per row render.
  const leeches = useMemo(() => new Set(matches.filter((card) => store.isLeech(card)).map((card) => card.id)), [matches, store]);
  const renderCard = useCallback(
    ({ item }: { item: CardModel }) => <CardRow card={item} leech={leeches.has(item.id)} today={today} stamp={cardStamp(item)} />,
    [leeches, today],
  );

  const header = (
    <>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
        {tiles.map((tile) => (
          <Card key={tile.mode} onPress={() => router.push(`/add?mode=${tile.mode}`)} accessibilityLabel={`Add cards: ${tile.title}`} style={{ flexBasis: '46%', flexGrow: 1, paddingVertical: 14 }}>
            <View style={stackTiles ? { gap: 6 } : { flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name={tile.icon} size={theme.icon(24)} color={c.link} />
              <Txt variant="h3" style={{ flexShrink: 1 }}>{tile.title}</Txt>
            </View>
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
                    onPress={() => setDeck(selected ? null : name)}
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
      <Field label="Search" value={query} onChangeText={setQuery} placeholder="Search questions, answers, decks" returnKeyType="search" autoCapitalize="none" />
      <Pills<Filter>
        label="Show"
        value={filter}
        onChange={setFilter}
        options={[{ value: 'all', label: 'All' }, { value: 'due', label: 'Due' }, { value: 'weak', label: 'Weak' }, { value: 'new', label: 'New' }]}
      />
      {deck ? <Button compact kind="ghost" label={`Showing ${deck} only — show all decks`} onPress={() => setDeck(null)} /> : null}
    </>
  );

  return (
    <ScreenList
      eyebrow="Create"
      title="Your cards"
      header={header}
      data={matches}
      renderItem={renderCard}
      keyExtractor={(card) => card.id}
      empty={<EmptyState icon="search-outline" title="No cards match" body={store.cards.length ? 'Try another word, or show all cards.' : 'Add your first card with one of the buttons above.'} />}
    />
  );
}

/**
 * The store edits cards in place, so a changed card is the same object as
 * before. This stamp of everything a row shows changes with it, which lets the
 * memoised row re-render for that card alone.
 */
function cardStamp(card: CardModel): string {
  return [card.deck, card.front, card.back, card.repetitions, card.next_review, card.lapses].join('\u0000');
}

/** One card in the list; skipped on re-render unless what it shows changed. */
const CardRow = memo(function CardRow({ card, leech, today }: { card: CardModel; leech: boolean; today: string; stamp: string }) {
  const c = useTheme().colors;
  return (
    <Card onPress={() => router.push(`/card/${card.id}`)} accessibilityLabel={`${card.front}. Answer: ${card.back || 'none'}. Tap to edit.`}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label" style={{ flexShrink: 1 }}>{card.deck}</Txt>
        <Txt variant="small">{card.repetitions ? `Next ${card.next_review <= today ? 'today' : relativeDay(card.next_review)}` : 'New'}</Txt>
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
