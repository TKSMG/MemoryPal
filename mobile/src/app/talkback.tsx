/**
 * Talk-back study, hands free: each question is read aloud, the spoken answer
 * is checked with Smart Check, the result is said, and the next card follows.
 * Pause, repeat, skip or type at any point. With a screen reader on, results
 * are announced and the person moves on with the buttons.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { AccessibilityInfo, Animated, Easing, Platform, View } from 'react-native';

import { answerAssessment } from '../core/smartCheck';
import { buildQueue, Mode } from '../features/queue';
import { liveAudioAvailable } from '../features/liveAudio';
import { makeEars, prepareRecognition } from '../features/recognition';
import { Snapshot, TalkbackSession, talkCards, Voice } from '../features/talkback';
import { usePrefs, useStore, useSync } from '../state/AppState';
import { Button, EmptyState, Field, ProgressBar, Row, Screen, Txt } from '../ui/components';
import { speakAsync, stopSpeaking } from '../ui/feedback';
import { useTheme } from '../ui/theme';

function useScreenReader(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    // react-native-web always reports a screen reader, so the browser preview runs hands free.
    if (Platform.OS === 'web') return undefined;
    let live = true;
    AccessibilityInfo.isScreenReaderEnabled().then((value) => live && setOn(value)).catch(() => undefined);
    const subscription = AccessibilityInfo.addEventListener('screenReaderChanged', setOn);
    return () => {
      live = false;
      subscription.remove();
    };
  }, []);
  return on;
}

const IDLE: Snapshot = { phase: 'idle', index: 0, total: 0, card: null, heard: '', message: '', last: null, results: [] };
const noop = () => () => undefined;

/** The microphone badge: a calm pulse while listening (still with Reduce Motion on). */
function ListeningBadge({ active }: { active: boolean }) {
  const theme = useTheme();
  const c = theme.colors;
  const [pulse] = useState(() => new Animated.Value(1));
  useEffect(() => {
    if (!active || theme.reduceMotion) {
      pulse.setValue(1);
      return undefined;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1.12, duration: 700, easing: Easing.out(Easing.quad), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.in(Easing.quad), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, theme.reduceMotion, pulse]);
  const size = theme.icon(72);
  return (
    <Animated.View
      accessible={false}
      style={{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: active ? c.primary : c.surfaceSoft, transform: [{ scale: pulse }] }}
    >
      <Ionicons name={active ? 'mic' : 'mic-outline'} size={theme.icon(34)} color={active ? c.onPrimary : c.muted} />
    </Animated.View>
  );
}

export default function Talkback() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const params = useLocalSearchParams<{ mode?: string; deck?: string }>();
  const screenReader = useScreenReader();
  // The voice reads this when it speaks, so turning a screen reader on mid-session takes effect.
  const screenReaderNow = useRef(screenReader);
  useEffect(() => {
    screenReaderNow.current = screenReader;
  }, [screenReader]);
  const [session, setSession] = useState<TalkbackSession | null>(null);
  const [notice, setNotice] = useState('');
  const [starting, setStarting] = useState(false);
  // The typed answer belongs to one card, so it starts empty on the next.
  const [draft, setDraft] = useState({ index: -1, text: '' });
  const slow = store.accessibility.more_time;
  const [prefs] = usePrefs();
  const sync = useSync();
  // The live tutor needs AI on, an account, and the full app (not Expo Go or the browser).
  const live = prefs.ai_allowed && sync.configured && sync.account.signedIn && liveAudioAvailable();
  const openLive = () => router.replace(`/talk-live?mode=${encodeURIComponent(params.mode || 'due')}${params.deck ? `&deck=${encodeURIComponent(params.deck)}` : ''}`);

  // Answered cards only: a card with no saved answer has nothing to check against.
  const queue = useMemo(() => talkCards(buildQueue(store, (params.mode as Mode) || 'due', params.deck || null).filter((card) => card.back.trim())), []); // eslint-disable-line react-hooks/exhaustive-deps
  const snap = useSyncExternalStore(session?.subscribe ?? noop, session?.getSnapshot ?? (() => IDLE), session?.getSnapshot ?? (() => IDLE));

  useEffect(() => session?.setScreenReader(screenReader), [session, screenReader]);
  // Leaving the screen stops the voice and the microphone.
  useFocusEffect(useCallback(() => () => session?.stop(), [session]));
  useEffect(() => () => session?.stop(), [session]);

  const start = async () => {
    setStarting(true);
    const readiness = await prepareRecognition();
    setStarting(false);
    if (readiness !== 'ready') {
      setNotice(
        readiness === 'denied'
          ? 'Microphone access is off, so MemoryPal will read each question and you can type the answer. You can allow it in the phone’s Settings.'
          : 'Listening isn’t available on this phone, so MemoryPal will read each question and you can type the answer.',
      );
    }
    const voice: Voice = {
      // With a screen reader on, its own voice announces; ours stays quiet.
      say: (text) => {
        if (screenReaderNow.current) {
          AccessibilityInfo.announceForAccessibility(text);
          return Promise.resolve();
        }
        return speakAsync(text, slow);
      },
      stop: stopSpeaking,
    };
    const next = new TalkbackSession(queue, {
      voice,
      ears: readiness === 'ready' ? makeEars() : null,
      check: answerAssessment,
      screenReader,
      onRate: (talkCard, assessment) => {
        const card = store.findCard(talkCard.id);
        if (card) store.schedule(card, assessment.quality, assessment);
      },
    });
    setSession(next);
    next.start();
  };

  if (!queue.length) {
    return (
      <Screen>
        <EmptyState
          icon="chatbubbles-outline"
          title="No cards to talk through"
          body="Talk-back needs cards with answers. Try all your cards, or add some first."
          action={
            <View style={{ gap: 10, alignSelf: 'stretch' }}>
              {params.mode !== 'all' ? <Button kind="primary" label="Use all my cards" onPress={() => router.replace(`/talkback?mode=all${params.deck ? `&deck=${encodeURIComponent(params.deck)}` : ''}`)} /> : null}
              <Button label="Add cards" onPress={() => router.replace('/add')} />
            </View>
          }
        />
      </Screen>
    );
  }

  if (!session) {
    return (
      <Screen narrow>
        <Txt variant="h2">Study out loud</Txt>
        <Txt variant="body">
          {screenReader
            ? 'Each question is announced. Tap Answer aloud and say your answer, or type it. You move on with Next.'
            : 'Each question is read aloud. Say your answer and MemoryPal checks it, tells you how it went, and moves on.'}
        </Txt>
        <Txt variant="muted">{`${queue.length} card${queue.length === 1 ? '' : 's'}. Pause, repeat, skip or type at any time. Speech is recognised on the phone where it supports it.`}</Txt>
        {live ? (
          <>
            <Button kind="primary" label="Talk with the AI tutor" icon="chatbubble-ellipses-outline" onPress={openLive} sublabel="A real conversation: interrupt, ask why, get hints" />
            <Button label={starting ? 'Starting…' : 'Classic Talk-back'} icon="play" onPress={start} disabled={starting} sublabel="Works offline, no AI" />
          </>
        ) : (
          <Button kind="primary" label={starting ? 'Starting…' : 'Start'} icon="play" onPress={start} disabled={starting} />
        )}
        {!live && liveAudioAvailable() && !prefs.ai_allowed ? (
          <Button kind="ghost" label="Try the live AI tutor" icon="sparkles-outline" onPress={() => router.push('/ai-consent')} hint="Turns on AI features first" />
        ) : null}
      </Screen>
    );
  }

  if (snap.phase === 'done') {
    const right = snap.results.filter((r) => r.outcome === 'right').length;
    const missed = snap.results.filter((r) => r.outcome !== 'right');
    return (
      <Screen title="Session done">
        <Txt variant="h2" accessibilityLiveRegion="polite">{`${right} of ${snap.results.length} right`}</Txt>
        {missed.length ? (
          <View style={{ gap: 12 }}>
            <Txt variant="h3">Worth another look</Txt>
            {missed.map((r) => (
              <View key={r.card.id} style={{ gap: 2 }}>
                <Txt variant="body">{r.card.front}</Txt>
                <Txt variant="small">{r.answer ? `You said “${r.answer}”. Answer: ${r.card.back}` : `Answer: ${r.card.back}`}</Txt>
              </View>
            ))}
          </View>
        ) : null}
        <Button kind="primary" label="Done" icon="checkmark" onPress={() => router.back()} />
      </Screen>
    );
  }

  const typed = draft.index === snap.index ? draft.text : '';
  const setTyped = (text: string) => setDraft({ index: snap.index, text });
  const listening = snap.phase === 'listening';
  const paused = snap.phase === 'paused';
  const status =
    snap.phase === 'asking' ? (snap.message || 'Reading the question…')
    : listening ? 'Listening… say your answer'
    : snap.phase === 'ready' ? (snap.message || 'Your turn. Answer aloud or type it.')
    : snap.phase === 'typing' ? (snap.message || 'Type your answer.')
    : paused ? 'Paused'
    : snap.message;
  const tone = snap.phase === 'feedback' || snap.phase === 'waiting' ? (snap.last?.outcome === 'right' ? c.good : snap.last?.outcome === 'close' ? c.review : c.again) : null;

  return (
    <Screen>
      <Txt variant="label">{`Card ${Math.min(snap.index + 1, snap.total)} of ${snap.total}`}</Txt>
      <ProgressBar value={snap.index / Math.max(1, snap.total)} label={`${snap.index} of ${snap.total} done`} />

      <Txt variant="h2" accessibilityRole="header">{snap.card?.front ?? ''}</Txt>

      {notice ? (
        <View style={{ backgroundColor: c.warm, borderRadius: theme.radius, padding: 14 }}>
          <Txt variant="body" color={c.warmText}>{notice}</Txt>
        </View>
      ) : null}

      <View style={{ alignItems: 'center', gap: 12, paddingVertical: 12 }}>
        <ListeningBadge active={listening} />
        <Txt variant="h3" center accessibilityLiveRegion="polite" color={tone ? tone[1] : c.ink}>{status}</Txt>
        {snap.heard && (snap.phase === 'feedback' || snap.phase === 'waiting') ? <Txt variant="muted" center>{`You said “${snap.heard}”`}</Txt> : null}
      </View>

      {snap.phase === 'typing' ? (
        <>
          <Field label="Your answer" value={typed} onChangeText={setTyped} autoFocus returnKeyType="done" onSubmitEditing={() => typed.trim() && session.submitTyped(typed)} />
          <Button kind="primary" label="Check" icon="checkmark" onPress={() => session.submitTyped(typed)} disabled={!typed.trim()} />
          {session.canListen ? <Button label="Answer aloud" icon="mic-outline" onPress={() => session.listen()} /> : null}
        </>
      ) : null}

      {snap.phase === 'ready' && session.canListen ? <Button kind="primary" label="Answer aloud" icon="mic-outline" onPress={() => session.listen()} /> : null}
      {snap.phase === 'waiting' ? <Button kind="primary" label="Next" icon="arrow-forward" onPress={() => session.next()} /> : null}

      <Row style={{ alignItems: 'stretch' }}>
        <Button compact label={paused ? 'Resume' : 'Pause'} icon={paused ? 'play' : 'pause'} onPress={() => (paused ? session.resume() : session.pause())} style={{ flex: 1 }} />
        <Button compact label="Repeat" icon="refresh" onPress={() => session.repeat()} style={{ flex: 1 }} hint="Reads the question again" />
      </Row>
      <Row style={{ alignItems: 'stretch' }}>
        <Button compact label="Skip" icon="play-skip-forward-outline" onPress={() => session.skip()} style={{ flex: 1 }} hint="Moves on without rating this card" />
        {snap.phase !== 'typing' ? <Button compact label="Type instead" icon="create-outline" onPress={() => session.typeInstead()} style={{ flex: 1 }} /> : null}
      </Row>
    </Screen>
  );
}
