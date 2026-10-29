/**
 * Live Talk-back: talk through a set with the AI tutor like a voice call.
 * Talk over it at any time, ask for a hint or why, and it saves a result for
 * each card as it goes. Needs AI turned on, an account and the internet;
 * classic Talk-back (talkback.tsx) works offline.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useNetworkState } from 'expo-network';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ActivityIndicator, Animated, View } from 'react-native';

import { startLive } from '../cloud/ai';
import { aiErrorText, aiGate, isOnline } from '../features/aiHelpers';
import { makeLiveAudio, prepareLiveMic } from '../features/liveAudio';
import { liveAssessment, LiveSnapshot, LiveTutor } from '../features/liveTutor';
import { buildQueue, Mode } from '../features/queue';
import { talkCards } from '../features/talkback';
import type { TalkCard } from '../features/talkback';
import { usePrefs, useStore, useSync } from '../state/AppState';
import { Button, Row, Screen, Txt } from '../ui/components';
import { stopSpeaking } from '../ui/feedback';
import { useTheme } from '../ui/theme';

const IDLE: LiveSnapshot = { phase: 'connecting', speaking: null, tutorLine: '', youLine: '', muted: false, results: [], total: 0, secondsLeft: 0, error: '' };
const noop = () => () => undefined;

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

/** A soft circle that swells with whoever is speaking: the tutor in blue, you in green. */
function VoiceOrb({ level, who, muted }: { level: Animated.Value; who: LiveSnapshot['speaking']; muted: boolean }) {
  const theme = useTheme();
  const c = theme.colors;
  const size = theme.icon(148);
  const color = muted ? c.surfaceSoft : who === 'you' ? c.good[1] : c.primary;
  const scale = theme.reduceMotion ? 1 : level.interpolate({ inputRange: [0, 1], outputRange: [1, 1.22], extrapolate: 'clamp' });
  const halo = theme.reduceMotion ? 0.18 : level.interpolate({ inputRange: [0, 1], outputRange: [0.12, 0.34], extrapolate: 'clamp' });
  return (
    <View accessible={false} style={{ width: size * 1.4, height: size * 1.4, alignItems: 'center', justifyContent: 'center' }}>
      <Animated.View style={{ position: 'absolute', width: size * 1.3, height: size * 1.3, borderRadius: size, backgroundColor: color, opacity: halo, transform: [{ scale }] }} />
      <Animated.View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: color, alignItems: 'center', justifyContent: 'center', transform: [{ scale }] }}>
        <Ionicons name={muted ? 'mic-off' : who === 'you' ? 'mic' : 'chatbubble-ellipses'} size={theme.icon(46)} color={muted ? c.muted : c.onPrimary} />
      </Animated.View>
    </View>
  );
}

export default function TalkLive() {
  const store = useStore();
  const sync = useSync();
  const theme = useTheme();
  const c = theme.colors;
  const [prefs] = usePrefs();
  const network = useNetworkState();
  const params = useLocalSearchParams<{ mode?: string; deck?: string }>();
  const [tutor, setTutor] = useState<LiveTutor | null>(null);
  const [startError, setStartError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [level] = useState(() => new Animated.Value(0));
  const levelNow = useRef(0);

  const queue = useMemo(() => talkCards(buildQueue(store, (params.mode as Mode) || 'due', params.deck || null).filter((card) => card.back.trim())), []); // eslint-disable-line react-hooks/exhaustive-deps
  const snap = useSyncExternalStore(tutor?.subscribe ?? noop, tutor?.getSnapshot ?? (() => IDLE), tutor?.getSnapshot ?? (() => IDLE));
  const gate = aiGate({ allowed: prefs.ai_allowed, signedIn: sync.account.signedIn, online: isOnline(network), configured: sync.configured });

  // Leaving the screen ends the call; ratings already saved stay saved.
  useFocusEffect(useCallback(() => () => tutor?.stop(), [tutor]));
  useEffect(() => () => tutor?.stop(), [tutor]);

  useEffect(() => {
    if (gate !== 'ready' || !queue.length) return undefined;
    let live = true;
    let made: LiveTutor | null = null;
    (async () => {
      stopSpeaking();
      const mic = await prepareLiveMic();
      if (!live) return;
      if (mic !== 'granted') {
        setStartError(mic === 'denied' ? 'Microphone access is off. Allow it in the phone’s Settings, or use classic Talk-back and type your answers.' : 'Live conversations need the full MemoryPal app on Android 10 or later, or an iPhone. Classic Talk-back works here.');
        return;
      }
      const audio = makeLiveAudio((who, value) => {
        // Smooth the loudness a little so the circle breathes rather than flickers.
        levelNow.current = levelNow.current * 0.6 + Math.min(1, value * 1.6) * 0.4;
        level.setValue(levelNow.current);
      });
      if (!audio) return setStartError('Live conversations aren’t available in this copy of the app.');
      try {
        const cards = queue.slice(0, 40);
        const started = await startLive(sync.account, cards, params.deck ?? '');
        if (!live) return;
        const byKey: Record<string, TalkCard> = {};
        cards.forEach((card, i) => (byKey[`c${i + 1}`] = card));
        made = new LiveTutor({
          token: started.token,
          setup: started.setup,
          cards: byKey,
          minutes: started.minutes,
          audio,
          openSocket: (url) => new WebSocket(url) as unknown as import('../features/liveTutor').LiveSocket,
          onRate: (talkCard, outcome) => {
            const card = store.findCard(talkCard.id);
            const assessment = liveAssessment(outcome);
            if (card && assessment) store.schedule(card, assessment.quality, assessment);
          },
        });
        setTutor(made);
        made.start();
      } catch (error) {
        if (live) setStartError(aiErrorText(error));
      }
    })();
    return () => {
      live = false;
      made?.stop();
    };
  }, [gate, attempt]); // eslint-disable-line react-hooks/exhaustive-deps

  const classic = () => router.replace(`/talkback?mode=${encodeURIComponent(params.mode || 'due')}${params.deck ? `&deck=${encodeURIComponent(params.deck)}` : ''}`);

  if (!queue.length) {
    return (
      <Screen narrow>
        <Txt variant="h2">No cards to talk through</Txt>
        <Txt variant="body">The tutor needs cards with answers. Try all your cards, or add some first.</Txt>
        <Button kind="primary" label="Go back" onPress={() => router.back()} />
      </Screen>
    );
  }

  if (gate !== 'ready' || startError || snap.phase === 'error') {
    const message =
      startError || snap.error ||
      (gate === 'consent' ? 'Turn on AI features in Settings to talk with the tutor.'
      : gate === 'sign_in' ? 'The AI tutor needs a free MemoryPal account, so each person gets a fair daily share.'
      : gate === 'offline' ? 'The AI tutor needs the internet. Classic Talk-back works offline.'
      : 'This copy of MemoryPal isn’t connected to the MemoryPal cloud.');
    return (
      <Screen narrow>
        <Txt variant="h2">Live tutor</Txt>
        <Txt variant="body">{message}</Txt>
        {snap.results.length ? <Txt variant="muted">{`${snap.results.length} card${snap.results.length === 1 ? '' : 's'} saved before it stopped.`}</Txt> : null}
        {gate === 'consent' ? <Button kind="primary" label="Turn on AI" icon="sparkles-outline" onPress={() => router.push('/ai-consent')} /> : null}
        {gate === 'sign_in' ? <Button kind="primary" label="Sign in or create an account" icon="person-outline" onPress={() => router.push('/account')} /> : null}
        {gate === 'ready' && !startError.includes('Settings') ? (
          <Button kind="primary" label="Try again" icon="refresh" onPress={() => { setTutor(null); setStartError(''); setAttempt((n) => n + 1); }} />
        ) : null}
        <Button label="Use classic Talk-back" icon="chatbubbles-outline" onPress={classic} />
      </Screen>
    );
  }

  if (snap.phase === 'done') {
    const right = snap.results.filter((r) => r.outcome === 'right').length;
    const rated = snap.results.filter((r) => r.outcome !== 'skipped');
    const missed = snap.results.filter((r) => r.outcome !== 'right');
    return (
      <Screen title="Nice work">
        <Txt variant="h2" accessibilityLiveRegion="polite">{rated.length ? `${right} of ${rated.length} right` : 'No cards answered this time'}</Txt>
        {missed.length ? (
          <View style={{ gap: 12 }}>
            <Txt variant="h3">Worth another look</Txt>
            {missed.map((r) => (
              <View key={r.card.id} style={{ gap: 2 }}>
                <Txt variant="body">{r.card.front}</Txt>
                <Txt variant="small">{r.said ? `You said “${r.said}”. Answer: ${r.card.back}` : `Answer: ${r.card.back}`}</Txt>
              </View>
            ))}
          </View>
        ) : null}
        <Button kind="primary" label="Done" icon="checkmark" onPress={() => router.back()} />
      </Screen>
    );
  }

  const connecting = !tutor || snap.phase === 'connecting';
  const status = connecting ? 'Connecting to your tutor…' : snap.muted ? 'Muted. Tap Unmute to answer.' : snap.speaking === 'tutor' ? 'Tutor is talking. Jump in any time.' : 'Listening…';
  const doneCount = snap.results.length;

  return (
    <Screen scroll={false}>
      <View style={{ flex: 1, gap: 16 }}>
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="label">{`${doneCount} of ${Math.min(queue.length, 40)} cards`}</Txt>
          {!connecting ? <Txt variant="label" accessibilityLabel={`${Math.ceil(snap.secondsLeft / 60)} minutes left`}>{`${clock(snap.secondsLeft)} left`}</Txt> : null}
        </Row>

        <View style={{ alignItems: 'center', justifyContent: 'center', flex: 1, gap: 18 }}>
          {connecting ? <ActivityIndicator size="large" color={c.primary} /> : <VoiceOrb level={level} who={snap.speaking} muted={snap.muted} />}
          <Txt variant="h3" center color={c.muted}>{status}</Txt>
        </View>

        <View style={{ gap: 8, minHeight: theme.icon(120) }}>
          {snap.tutorLine ? <Txt variant="body" numberOfLines={4}>{snap.tutorLine}</Txt> : null}
          {snap.youLine ? <Txt variant="muted" numberOfLines={2}>{`You: ${snap.youLine}`}</Txt> : null}
        </View>

        <Row style={{ alignItems: 'stretch' }}>
          <Button
            label={snap.muted ? 'Unmute' : 'Mute'}
            icon={snap.muted ? 'mic-outline' : 'mic-off-outline'}
            onPress={() => tutor?.setMuted(!snap.muted)}
            disabled={connecting}
            style={{ flex: 1 }}
          />
          <Button kind="danger" label="End" icon="stop" onPress={() => tutor?.stop()} style={{ flex: 1 }} hint="Ends the conversation. Answers so far are saved." />
        </Row>
        <Txt variant="small" center>{'Say “skip”, “give me a hint” or “why?” at any time. AI can be wrong.'}</Txt>
      </View>
    </Screen>
  );
}
