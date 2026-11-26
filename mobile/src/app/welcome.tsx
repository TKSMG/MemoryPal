/** First launch: one plain question, then comfort settings, then straight to Today. */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, Stack, useLocalSearchParams, useNavigation } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, View } from 'react-native';

import { MANAGED_SETTINGS, PERSONAS, persona as personaFor } from '../core/personas';
import { defaultAccessibility, PersonaKey, TextSize } from '../core/store';
import { useStore } from '../state/AppState';
import { Button, Card, Pills, Row, Screen, SectionTitle, ToggleRow, Txt } from '../ui/components';
import { speak } from '../ui/feedback';
import { useTheme } from '../ui/theme';

const SIZE_OPTIONS: { value: TextSize; label: string }[] = [
  { value: 'Comfort', label: 'Standard' },
  { value: 'Large', label: 'Large' },
  { value: 'Extra Large', label: 'Extra large' },
];

const ICONS: Record<PersonaKey, keyof typeof Ionicons.glyphMap> = {
  student: 'school-outline',
  everyday: 'leaf-outline',
  caregiver: 'heart-outline',
  general: 'compass-outline',
};

export default function Welcome() {
  const store = useStore();
  const theme = useTheme();
  const navigation = useNavigation();
  // Settings opens this screen with ?again=1 to choose again; then it has a
  // back button and swipe, and leaving without finishing changes nothing.
  const again = !!useLocalSearchParams<{ again?: string }>().again;
  const [chosen, setChosen] = useState<PersonaKey | ''>(store.onboarding.persona);
  // An account signed in on another device brings its answers with it, so
  // leave as soon as onboarding becomes done during this visit (but not when
  // it was already done on arrival, as when choosing again from Settings).
  const done = store.onboarding.done;
  const doneAtOpen = useRef(done);
  useEffect(() => {
    if (done && !doneAtOpen.current) router.replace('/');
    doneAtOpen.current = done;
  }, [done]);

  // Choosing a persona applies its comfort settings straight away; leaving
  // without finishing puts the earlier ones back.
  const before = useRef(store.accessibility);
  const finished = useRef(false);
  useEffect(() => {
    if (!again) return undefined;
    return navigation.addListener('beforeRemove', () => {
      if (!finished.current) store.setAccessibility(before.current);
    });
  }, [again, navigation, store]);

  // Text size applies to the whole app as soon as it changes, so this page
  // grows or shrinks too. Say so, so the jump doesn't look like a fault.
  const [resized, setResized] = useState(false);
  const choose = (key: PersonaKey) => {
    setChosen(key);
    // Choosing again resets only the settings a persona controls.
    const reset = Object.fromEntries(MANAGED_SETTINGS.map((name) => [name, defaultAccessibility()[name]]));
    const next = { ...reset, ...personaFor(key).accessibility };
    if (next.text_size !== store.accessibility.text_size) setResized(true);
    store.setAccessibility(next);
  };
  const sizeName = SIZE_OPTIONS.find((option) => option.value === store.accessibility.text_size)?.label ?? 'Standard';

  const finish = () => {
    finished.current = true;
    store.finishOnboarding(chosen || 'general');
    if (again && router.canGoBack()) router.back();
    else router.replace('/');
  };

  return (
    <Screen>
      {again ? <Stack.Screen options={{ headerShown: true, title: 'Choose again', gestureEnabled: true }} /> : null}
      <Row gap={14} style={{ marginTop: 8 }}>
        <Image source={require('../../assets/icon.png')} style={{ width: 56, height: 56, borderRadius: 14 }} accessibilityIgnoresInvertColors accessible={false} />
        <View style={{ flex: 1 }}>
          <Txt variant="title">Welcome</Txt>
        </View>
      </Row>
      <Txt variant="muted">Three quick questions so MemoryPal fits you. You can change any of this later in Settings.</Txt>

      <SectionTitle>1. Who will be using MemoryPal?</SectionTitle>
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
              // Every choice keeps a 2pt edge (clear until picked) inside the
              // usual 16pt, so picking one doesn't nudge its words.
              style={{ borderWidth: 2, padding: 14, borderColor: selected ? theme.colors.primary : 'transparent' }}
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

      {resized ? (
        <Row gap={10}>
          <Ionicons name="text-outline" size={theme.icon(20)} color={theme.colors.link} />
          <Txt variant="muted" style={{ flex: 1 }} accessibilityLiveRegion="polite">{`Text is now ${sizeName.toLowerCase()} to suit this choice. You can change it just below.`}</Txt>
        </Row>
      ) : null}

      <SectionTitle>2. How big should the text be?</SectionTitle>
      <Card>
        <Txt variant="muted">The whole app changes size as you pick, so you can see it straight away.</Txt>
        <Pills<TextSize>
          label="Text size"
          value={store.accessibility.text_size}
          onChange={(value) => store.setAccessibility({ text_size: value })}
          options={SIZE_OPTIONS}
        />
        <View style={{ backgroundColor: theme.colors.surfaceSoft, borderRadius: 12, padding: 14, gap: 4 }} accessible accessibilityLabel={`Preview at ${sizeName} size: What is the capital of France?`}>
          <Txt variant="label" color={theme.colors.muted}>{`Preview: ${sizeName}`}</Txt>
          <Txt variant="body">What is the capital of France?</Txt>
        </View>
      </Card>

      <SectionTitle>3. Read questions aloud?</SectionTitle>
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
