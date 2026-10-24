/** Study: every way to practise cards, with what's waiting in each. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Href, router } from 'expo-router';
import { View } from 'react-native';

import { useStore } from '../../state/AppState';
import { Button, Card, ListGroup, ListRow, Row, Screen, Txt } from '../../ui/components';
import { useTheme } from '../../ui/theme';

export default function Study() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const due = store.dueCards().length;
  const weak = store.weakCards().length;
  const fresh = store.cards.filter((card) => card.repetitions === 0 && card.lapses === 0).length;

  const options: { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; count?: number; href: Href }[] = [
    { icon: 'flash-outline', title: 'Quick 10', body: 'Due cards first, then shaky ones. About five minutes.', href: '/review?mode=quick' },
    { icon: 'fitness-outline', title: theme.plain('Weak cards', 'Cards to practise more'), body: 'Cards you have missed, found hard or not studied yet, hardest first.', count: weak, href: '/review?mode=weak' },
    { icon: 'sparkles-outline', title: 'New cards', body: 'Cards you haven’t studied yet, up to 20.', count: fresh, href: '/review?mode=new' },
    { icon: 'chatbubbles-outline', title: 'Talk-back study', body: 'Hands free: hear each question, say the answer, hear how you did.', href: '/talkback?mode=quick' },
    { icon: 'list-circle-outline', title: 'Quick quiz', body: 'Mixed questions: pick, match, fill in the blank, true or false.', href: '/quiz' },
    { icon: 'map-outline', title: 'Study plan', body: 'Your time and goal become steps for each day.', href: '/plan' },
  ];

  return (
    <Screen title="Study">
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

      <ListGroup header="More ways to practise" footer="Answering from memory before you look builds recall far better than rereading. A miss still helps: the card simply comes back sooner.">
        {options.map((option) => (
          <ListRow
            key={option.title}
            icon={option.icon}
            title={option.title}
            detail={option.body}
            value={option.count !== undefined ? String(option.count) : undefined}
            onPress={() => router.push(option.href)}
            accessibilityLabel={`${option.title}. ${option.body}${option.count !== undefined ? ` ${option.count} cards.` : ''}`}
          />
        ))}
      </ListGroup>
    </Screen>
  );
}
