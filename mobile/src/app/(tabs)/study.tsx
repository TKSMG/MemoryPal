/** Study: every way to practise cards, with what's waiting in each. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Href, router } from 'expo-router';
import { View } from 'react-native';

import { useStore } from '../../state/AppState';
import { Button, Card, Row, Screen, SectionTitle, Txt } from '../../ui/components';
import { useTheme } from '../../ui/theme';

export default function Study() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const due = store.dueCards().length;
  const weak = store.weakCards().length;
  const fresh = store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0).length;

  const options: { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; count?: number; href: Href }[] = [
    { icon: 'flash-outline', title: 'Quick 10', body: 'Ten cards: due ones first, then shaky ones. About five minutes.', href: '/review?mode=quick' },
    { icon: 'fitness-outline', title: theme.plain('Weak cards', 'Cards to practise more'), body: 'Cards you have missed or found hard, hardest first.', count: weak, href: '/review?mode=weak' },
    { icon: 'sparkles-outline', title: 'New cards', body: 'Meet cards you haven’t studied yet (up to 20).', count: fresh, href: '/review?mode=new' },
    { icon: 'chatbubbles-outline', title: 'Talk-back study', body: 'Hands free: hear each question, say the answer, hear how you did.', href: '/talkback?mode=quick' },
    { icon: 'list-circle-outline', title: 'Multiple-choice quiz', body: 'Pick the answer from four. A fast confidence check.', href: '/quiz' },
    { icon: 'map-outline', title: 'Study plan', body: 'Tell MemoryPal your time and goal; get steps for each day.', href: '/plan' },
  ];

  return (
    <Screen eyebrow="Study" title="Review and quiz">
      <Card tone="alt" style={{ gap: 12 }}>
        <Row>
          <Ionicons name="calendar-outline" size={theme.icon(28)} color={c.link} />
          <View style={{ flex: 1 }}>
            <Txt variant="h2">{due ? `${due} card${due === 1 ? '' : 's'} due` : 'Nothing due right now'}</Txt>
            <Txt variant="muted">
              {theme.plain(
                'Answer from memory, then rate how it went. Easy cards come back later; hard ones sooner.',
                'Try to remember each answer, then say how it went.',
              )}
            </Txt>
          </View>
        </Row>
        <Button kind="primary" label={due ? 'Start review' : 'Practise anyway'} icon="play" onPress={() => router.push(due ? '/review?mode=due' : '/review?mode=quick')} />
      </Card>

      <SectionTitle>Other ways to practise</SectionTitle>
      {options.map((option) => (
        <Card key={option.title} onPress={() => router.push(option.href)} accessibilityLabel={`${option.title}. ${option.body}${option.count !== undefined ? ` ${option.count} cards.` : ''}`}>
          <Row style={{ alignItems: 'flex-start' }}>
            <Ionicons name={option.icon} size={theme.icon(26)} color={c.link} />
            <View style={{ flex: 1, gap: 2 }}>
              <Row style={{ justifyContent: 'space-between' }}>
                <Txt variant="h3" style={{ flexShrink: 1 }}>{option.title}</Txt>
                {option.count !== undefined ? <Txt variant="label">{String(option.count)}</Txt> : null}
              </Row>
              <Txt variant="muted">{option.body}</Txt>
            </View>
            <Ionicons name="chevron-forward" size={theme.icon(20)} color={c.muted} style={{ alignSelf: 'center' }} />
          </Row>
        </Card>
      ))}

      <Card tone="warm">
        <Txt variant="h3" color={c.warmText}>Why answer before you look?</Txt>
        <Txt variant="body" color={c.warmText}>
          Pulling an answer out of memory strengthens it far more than rereading. Getting it wrong first still helps — the card simply comes back sooner.
        </Txt>
      </Card>
    </Screen>
  );
}
