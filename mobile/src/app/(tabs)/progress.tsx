/** Progress: streaks, level, simple charts in plain words, and badges. */
import { useWindowDimensions, View } from 'react-native';

import { WEEKDAYS, achievements, bestStreak, dailySeries, dueForecast, levelInfo, maturityBreakdown } from '../../core/progress';
import { weekday } from '../../core/dates';
import { useStore } from '../../state/AppState';
import { Card, ListGroup, ListRow, ProgressBar, Row, Screen, SectionTitle, Stat, Txt } from '../../ui/components';
import { useTheme } from '../../ui/theme';

function Bars({ values, labels, color, summary }: { values: number[]; labels: string[]; color: string; summary: string }) {
  const theme = useTheme();
  const max = Math.max(1, ...values);
  return (
    <View accessible accessibilityLabel={summary} style={{ gap: 6 }}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', height: 110, gap: 4 }}>
        {values.map((value, i) => (
          <View key={i} style={{ flex: 1, height: '100%', justifyContent: 'flex-end' }}>
            <View style={{ height: `${Math.max(value ? 6 : 2, (value / max) * 100)}%`, backgroundColor: value ? color : theme.colors.line, borderRadius: 4 }} />
          </View>
        ))}
      </View>
      <View style={{ flexDirection: 'row', gap: 4 }}>
        {labels.map((label, i) => (
          <Txt key={i} variant="small" center numberOfLines={1} adjustsFontSizeToFit maxFontSizeMultiplier={1.5} style={{ flex: 1, fontSize: theme.font(11) }}>{label}</Txt>
        ))}
      </View>
    </View>
  );
}

export default function Progress() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const level = levelInfo(store.practiced);
  const streak = store.currentStreak();
  const best = Math.max(bestStreak(store.activity), streak);
  const week = dailySeries(store.activity, 14);
  const weekTotal = week.slice(7).reduce((sum, [, count]) => sum + count, 0);
  const forecast = dueForecast(store.cards, 7);
  const maturity = maturityBreakdown(store.cards);
  const total = Math.max(1, store.cards.length);
  const badges = achievements(store);
  const earned = badges.filter((badge) => badge.done).length;
  // On narrow phones the day labels drop to one letter (M T W…), like Health's
  // charts, instead of being cut short to "M..".
  const { width } = useWindowDimensions();
  const dayLength = width < 400 ? 1 : 2;

  const segments: [string, number, string][] = [
    ['New', maturity.new, c.muted],
    ['Learning', maturity.learning, c.orange],
    ['Young', maturity.young, c.primary],
    ['Mature', maturity.mature, c.green],
  ];

  return (
    <Screen title="Progress">
      <Card>
        <Row wrap style={{ alignItems: 'flex-start' }}>
          <Stat value={streak} label={`day streak${best > streak ? ` (best ${best})` : ''}`} />
          <Stat value={store.practiced} label="reviews in total" />
        </Row>
        <Txt variant="h3">Level {level.level}</Txt>
        <ProgressBar value={level.pct} label={`${level.xp} of ${level.need} XP to the next level`} />
        <Txt variant="small">{`${level.xp} of ${level.need} XP. Each review earns 10.`}</Txt>
      </Card>

      <SectionTitle>Last two weeks</SectionTitle>
      <Card>
        <Bars
          values={week.map(([, count]) => count)}
          labels={week.map(([day], i) => (i % 2 ? '' : WEEKDAYS[weekday(day)].slice(0, dayLength)))}
          color={c.primary}
          summary={`${weekTotal} reviews in the last 7 days.`}
        />
        <Txt variant="muted">{weekTotal ? `${weekTotal} reviews in the last 7 days.` : 'No reviews this week yet. Even five minutes counts.'}</Txt>
      </Card>

      <SectionTitle>Coming up</SectionTitle>
      <Card>
        <Bars
          values={forecast.map(([, count]) => count)}
          labels={forecast.map(([day], i) => (i === 0 ? 'Today' : WEEKDAYS[weekday(day)].slice(0, dayLength)))}
          color={c.primary}
          summary={`Cards due over the next 7 days: ${forecast.map(([, count]) => count).join(', ')}.`}
        />
        <Txt variant="muted">Cards due each day this week. Today includes anything overdue.</Txt>
      </Card>

      <SectionTitle>How settled your cards are</SectionTitle>
      <Card>
        <View style={{ flexDirection: 'row', height: 18, borderRadius: 9, overflow: 'hidden', backgroundColor: c.alt }} accessible accessibilityLabel={segments.map(([name, count]) => `${count} ${name.toLowerCase()}`).join(', ')}>
          {segments.map(([name, count, color]) => (count ? <View key={name} style={{ flex: count / total, backgroundColor: color }} /> : null))}
        </View>
        <Row wrap gap={14}>
          {segments.map(([name, count, color]) => (
            <Row key={name} gap={6}>
              <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: color }} />
              <Txt variant="small">{`${name} ${count}`}</Txt>
            </Row>
          ))}
        </Row>
        <Txt variant="muted">Mature cards come back three weeks or more apart, a good sign they’re in long-term memory.</Txt>
      </Card>

      <SectionTitle>{`Badges · ${earned} of ${badges.length}`}</SectionTitle>
      <ListGroup>
        {badges.map((badge) => (
          <ListRow
            key={badge.key}
            icon={badge.done ? 'ribbon' : 'lock-closed-outline'}
            tint={badge.done ? c.primary : c.muted}
            title={badge.title}
            detail={badge.body}
            value={badge.done ? 'Earned' : `${badge.current} of ${badge.target}`}
            accessibilityLabel={`${badge.title}. ${badge.body}. ${badge.done ? 'Earned' : `${badge.current} of ${badge.target}`}`}
          />
        ))}
      </ListGroup>
    </Screen>
  );
}
