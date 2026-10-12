/** First launch: one plain question, then comfort settings, then straight to Today. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, View } from 'react-native';

import { MANAGED_SETTINGS, PERSONAS, persona as personaFor } from '../core/personas';
import { defaultAccessibility, PersonaKey, TextSize } from '../core/store';
import { useStore } from '../state/AppState';
import { Button, Card, Pills, Row, Screen, ToggleRow, Txt } from '../ui/components';
import { speak } from '../ui/feedback';
import { useTheme } from '../ui/theme';

const ICONS: Record<PersonaKey, keyof typeof Ionicons.glyphMap> = {
  student: 'school-outline',
  everyday: 'leaf-outline',
  caregiver: 'heart-outline',
  general: 'compass-outline',
};

export default function Welcome() {
  const store = useStore();
  const theme = useTheme();
  const [chosen, setChosen] = useState<PersonaKey | ''>(store.onboarding.persona);
  // An account signed in on another device brings its answers with it.
  const done = store.onboarding.done;
  useEffect(() => {
    if (done) router.replace('/');
  }, [done]);

  const choose = (key: PersonaKey) => {
    setChosen(key);
    // Choosing again resets only the settings a persona controls.
    const reset = Object.fromEntries(MANAGED_SETTINGS.map((name) => [name, defaultAccessibility()[name]]));
    store.setAccessibility({ ...reset, ...personaFor(key).accessibility });
  };

  const finish = () => {
    store.finishOnboarding(chosen || 'general');
    router.replace('/');
  };

  return (
    <Screen>
      <Row gap={14} style={{ marginTop: 8 }}>
        <Image source={require('../../assets/icon.png')} style={{ width: 56, height: 56, borderRadius: 14 }} accessibilityIgnoresInvertColors accessible={false} />
        <View style={{ flex: 1 }}>
          <Txt variant="label" color={theme.colors.link}>Welcome to MemoryPal</Txt>
          <Txt variant="title">Let’s set things up</Txt>
        </View>
      </Row>
      <Txt variant="muted">Three quick questions so the app fits you. You can change any of this later in Settings.</Txt>

      <Txt variant="h2">1. Who will be using MemoryPal?</Txt>
      <View accessibilityRole="radiogroup" accessibilityLabel="Who will be using MemoryPal?" style={{ gap: 16 }}>
        {PERSONAS.map((item) => {
          const selected = chosen === item.key;
          return (
            <Card
              key={item.key}
              onPress={() => choose(item.key)}
              accessibilityLabel={`${item.title}. ${item.body}`}
              accessibilityRole="radio"
              accessibilityState={{ selected, checked: selected }}
              style={selected ? { borderColor: theme.colors.primary, borderWidth: 2 } : undefined}
            >
              <Row>
                <Ionicons name={ICONS[item.key]} size={theme.icon(28)} color={selected ? theme.colors.link : theme.colors.muted} />
                <View style={{ flex: 1, gap: 2 }}>
                  <Txt variant="h3">{item.title}</Txt>
                  <Txt variant="muted">{item.body}</Txt>
                </View>
                {selected ? <Ionicons name="checkmark-circle" size={theme.icon(26)} color={theme.colors.link} /> : null}
              </Row>
            </Card>
          );
        })}
      </View>

      <Txt variant="h2">2. How big should the text be?</Txt>
      <Card>
        <Pills<TextSize>
          label="Text size"
          value={store.accessibility.text_size}
          onChange={(value) => store.setAccessibility({ text_size: value })}
          options={[{ value: 'Comfort', label: 'Standard' }, { value: 'Large', label: 'Large' }, { value: 'Extra Large', label: 'Extra large' }]}
        />
        <Txt variant="body">This is how cards will look.</Txt>
      </Card>

      <Txt variant="h2">3. Read questions aloud?</Txt>
      <Card>
        <ToggleRow
          label="Read questions and answers aloud"
          description="Uses your phone's own voice. Works offline."
          value={store.accessibility.read_aloud}
          onChange={(value) => {
            store.setAccessibility({ read_aloud: value });
            if (value) speak('Questions and answers will be read aloud.', store.accessibility.more_time);
          }}
        />
        <ToggleRow
          label="Give me more time"
          description="Slower voice and longer timers in puzzles."
          value={store.accessibility.more_time}
          onChange={(value) => store.setAccessibility({ more_time: value })}
        />
      </Card>

      <Button kind="primary" label={chosen ? 'Start using MemoryPal' : 'Skip and start'} icon="arrow-forward" onPress={finish} />
    </Screen>
  );
}
