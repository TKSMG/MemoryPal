/**
 * Memory puzzles. Calm by design, with older players in mind: a short intro
 * with a tip, a visible countdown and an "I'm ready" button, More time
 * doubles every timer, every answer is a big tap (typing is optional), a
 * "Help me" clue, and a few short rounds that follow the player's level.
 *
 * /puzzle?kind=<kind>      one puzzle, ROUNDS rounds, starting at the saved level
 * /puzzle?daily=1          today's mix (core/puzzles todaysPuzzles), story questions asked again at the end
 * /puzzle?deck=<set>       pair, word and list puzzles with that set's own cards
 *
 * The rules (rounds, scoring, levels, results) are core/puzzles.ts, the same as the desktop.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import { ReactNode, useEffect, useState } from 'react';
import { AccessibilityInfo, Pressable, View } from 'react-native';

import { todayIso } from '../core/dates';
import {
  ChoiceQuestion, clue, DAILY_ROUNDS, digitGroups, enoughFor, feedback, makeRound, Material, materialFrom, nextLevel, PlayedRound, puzzle,
  PuzzleKind, PuzzleRound, recordGame, ROUNDS, RoundScore, score, showMs, startLevel, streakText, todaysPuzzles,
} from '../core/puzzles';
import { deckCards } from '../features/decks';
import { usePrefs, useStore } from '../state/AppState';
import { Button, Card, Field, Pills, ProgressBar, Row, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../ui/components';
import { useTheme } from '../ui/theme';

type Phase = 'intro' | 'show' | 'answer' | 'result' | 'later' | 'done';

interface GameLine {
  kind: PuzzleKind;
  right: number;
  rounds: number;
  best: boolean;
}

const MATERIAL_KINDS: PuzzleKind[] = ['pairs', 'words', 'missing', 'search', 'nback'];
/** A fresh seed for a round, clue or praise line. */
const nextSeed = () => Math.floor(Math.random() * 2_000_000_000);
const AVATAR_TONES = ['#c8553d', '#2a7f62', '#3d5a80', '#9a6fb0', '#b5838d', '#6b8f71'];

export default function Puzzle() {
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const [prefs, setPrefs] = usePrefs();
  const params = useLocalSearchParams<{ kind?: string; deck?: string; daily?: string }>();
  const deck = params.deck ?? '';
  const daily = params.daily === '1' && !deck;
  const everyday = ['everyday', 'caregiver'].includes(store.onboarding.persona) || store.accessibility.caregiver_mode;
  const moreTime = store.accessibility.more_time;
  const simple = store.accessibility.simple_language;
  useStopSpeechOnLeave();

  // Worked out once, so a round's words never change under the player.
  const [material] = useState<Material | null>(() => (deck ? materialFrom(deckCards(store, deck).map((card) => [card.front, card.back] as [string, string])) : null));
  const [queue] = useState<PuzzleKind[]>(() => {
    if (daily) return todaysPuzzles(prefs.puzzles, todayIso(), everyday);
    const asked = puzzle(params.kind ?? (deck ? 'pairs' : 'sequence')).kind;
    return [asked];
  });

  const [slot, setSlot] = useState(0);
  const kind = queue[slot];
  const info = puzzle(kind);
  const roundsFor = (which: PuzzleKind) => (daily ? (which === 'story' ? 1 : DAILY_ROUNDS) : ROUNDS);
  const [phase, setPhase] = useState<Phase>('intro');
  const [roundNumber, setRoundNumber] = useState(1);
  const [level, setLevel] = useState(() => startLevel(prefs.puzzles, kind));
  const [round, setRound] = useState<PuzzleRound>(() => makeRound(kind, level, 1, material));
  const [played, setPlayed] = useState<PlayedRound[]>([]);
  const [log, setLog] = useState<GameLine[]>([]);
  const [helped, setHelped] = useState(false);
  const [last, setLast] = useState<RoundScore | null>(null);
  const [lastLine, setLastLine] = useState('');
  // Story recall in today's mix: half the questions come back at the very end.
  const [later, setLater] = useState<{ round: PuzzleRound; played: PlayedRound[] } | null>(null);
  const [ending, setEnding] = useState(false);

  // Answers in progress.
  const [qIndex, setQIndex] = useState(0);
  const [picks, setPicks] = useState<string[]>([]);
  const [trimmed, setTrimmed] = useState<string[] | null>(null);
  const [reveal, setReveal] = useState<string | null>(null);
  const [digits, setDigits] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState('');
  const [order, setOrder] = useState<number[]>([]);
  const [found, setFound] = useState<number[]>([]);
  const [wrongTaps, setWrongTaps] = useState(0);
  const [nbackStarted, setNbackStarted] = useState(false);

  // The countdown while things are on show.
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [tick, setTick] = useState(startedAt);
  const showFor = showMs(round, moreTime);
  const left = Math.max(0, showFor - (tick - startedAt));
  // A screen reader takes far longer to read things out than the timer
  // allows, so with one on, they stay until "I'm ready" is pressed.
  const [screenReader, setScreenReader] = useState(false);
  useEffect(() => {
    let live = true;
    AccessibilityInfo.isScreenReaderEnabled().then((value) => live && setScreenReader(value)).catch(() => undefined);
    const subscription = AccessibilityInfo.addEventListener('screenReaderChanged', setScreenReader);
    return () => {
      live = false;
      subscription.remove();
    };
  }, []);
  useEffect(() => {
    if (phase !== 'show' || screenReader) return undefined;
    const timer = setInterval(() => {
      const now = Date.now();
      setTick(now);
      if (now - startedAt >= showFor) {
        clearInterval(timer);
        setPhase('answer');
      }
    }, 200);
    return () => clearInterval(timer);
  }, [phase, startedAt, showFor, screenReader]);

  const resetAnswers = () => {
    setQIndex(0);
    setPicks([]);
    setTrimmed(null);
    setReveal(null);
    setDigits('');
    setChosen([]);
    setTyping(false);
    setTyped('');
    setOrder([]);
    setFound([]);
    setWrongTaps(0);
    setNbackStarted(false);
    setHelped(false);
  };

  const startRound = (which: PuzzleKind, atLevel: number) => {
    let made = makeRound(which, atLevel, nextSeed(), material);
    if (daily && which === 'story') {
      const half = Math.ceil(made.questions.length / 2);
      setLater({ round: { ...made, questions: made.questions.slice(half) }, played: [] });
      made = { ...made, questions: made.questions.slice(0, half) };
    }
    const now = Date.now();
    setRound(made);
    setStartedAt(now);
    setTick(now);
    resetAnswers();
    setPhase(showMs(made) > 0 ? 'show' : 'answer');
  };

  const finish = (response: Parameters<typeof score>[1]) => {
    const result = score(round, response);
    setLast(result);
    setLastLine(feedback(result.right, nextSeed(), simple));
    setPlayed((value) => [...value, { level: round.level, right: result.right, helped }]);
    setPhase('result');
  };

  const saveGame = (which: PuzzleKind, rounds: PlayedRound[]) => {
    const before = prefs.puzzles.kinds[which]?.best ?? 0;
    const results = recordGame(prefs.puzzles, which, rounds, todayIso());
    setPrefs({ puzzles: results });
    const best = (results.kinds[which]?.best ?? 0) > before && before > 0;
    setLog((value) => [...value, { kind: which, right: rounds.filter((item) => item.right).length, rounds: rounds.length, best }]);
  };

  const goOn = () => {
    if (ending) {
      setPhase('done');
      return;
    }
    if (roundNumber < roundsFor(kind)) {
      const next = nextLevel(kind, round.level, !!last?.right, helped);
      setLevel(next);
      setRoundNumber((value) => value + 1);
      startRound(kind, next);
      return;
    }
    // This puzzle is finished.
    if (daily && kind === 'story' && later) setLater({ ...later, played });
    else saveGame(kind, played);
    store.recordPractice();
    if (slot + 1 < queue.length) {
      const nextKind = queue[slot + 1];
      setSlot(slot + 1);
      setRoundNumber(1);
      setPlayed([]);
      setLevel(startLevel(prefs.puzzles, nextKind));
      setPhase('intro');
      return;
    }
    if (later) {
      setRound(later.round);
      resetAnswers();
      setPhase('later');
      return;
    }
    setPhase('done');
  };

  const finishLater = (laterPicks: string[]) => {
    if (!later) return;
    const result = score(later.round, laterPicks);
    setLast(result);
    setLastLine(feedback(result.right, nextSeed(), simple));
    saveGame('story', [...later.played, { level: later.round.level, right: result.right }]);
    setLater(null);
    setEnding(true);
    setPhase('result');
  };

  // ------------------------------------------------------------ choice questions
  const questions = round.questions;
  const question: ChoiceQuestion | undefined = questions[qIndex];
  const pace = moreTime ? 1600 : 900;
  const choose = (option: string) => {
    if (!question || reveal) return;
    setReveal(option);
    setTimeout(() => {
      const all = [...picks, option];
      setReveal(null);
      setTrimmed(null);
      if (qIndex + 1 < questions.length) {
        setPicks(all);
        setQIndex(qIndex + 1);
      } else if (phase === 'later') {
        finishLater(all);
      } else {
        finish(all);
      }
    }, pace);
  };
  const helpChoice = () => {
    if (!question) return;
    setHelped(true);
    setTrimmed(clue(question, nextSeed()));
  };

  const restart = () => {
    setSlot(0);
    setRoundNumber(1);
    setPlayed([]);
    setLog([]);
    setLater(null);
    setEnding(false);
    setLevel(startLevel(prefs.puzzles, queue[0]));
    setPhase('intro');
  };

  const title = daily ? 'Today’s puzzles' : info.title;

  // -------------------------------------------------------------------- views
  if (phase === 'done') {
    return (
      <Screen title="All done" subtitle={title}>
        <Stack.Screen options={{ title }} />
        <Card tone="alt">
          {log.map((line) => (
            <Row key={line.kind} style={{ justifyContent: 'space-between' }}>
              <Txt variant="h3" style={{ flex: 1 }}>{puzzle(line.kind).title}</Txt>
              <Txt variant="body">{`${line.right} of ${line.rounds}`}</Txt>
            </Row>
          ))}
          {log.filter((line) => line.best).map((line) => (
            <Txt key={`best-${line.kind}`} variant="body" color={c.good[1]}>{`New best in ${puzzle(line.kind).title}!`}</Txt>
          ))}
          <Txt variant="body">{streakText(prefs.puzzles, todayIso())}</Txt>
          <Txt variant="muted">{theme.plain('The puzzles follow your level, so they stay just challenging enough.', 'Come back tomorrow for more.')}</Txt>
        </Card>
        <Button kind="primary" label="Play again" icon="refresh" onPress={restart} />
        <Button label="Back to Practice" icon="arrow-back" onPress={() => router.back()} />
      </Screen>
    );
  }

  const header = (
    <>
      <Stack.Screen options={{ title }} />
      {deck && phase === 'intro' ? (
        <>
          <Pills
            label={`Cards from ${deck}`}
            value={kind}
            onChange={(value) => router.replace(`/puzzle?deck=${encodeURIComponent(deck)}&kind=${value}` as Href)}
            options={MATERIAL_KINDS.map((value) => ({ value, label: puzzle(value).title }))}
          />
          {!enoughFor(kind, material) ? <Txt variant="muted">{`${deck} doesn’t have enough short answers for this yet, so it uses everyday words.`}</Txt> : null}
        </>
      ) : null}
      {phase !== 'intro' && phase !== 'later' ? (
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="label">{daily ? `${info.title} · round ${roundNumber} of ${roundsFor(kind)}` : `Round ${roundNumber} of ${roundsFor(kind)}`}</Txt>
          <Txt variant="label">{`Level ${round.level}`}</Txt>
        </Row>
      ) : null}
    </>
  );

  if (phase === 'intro') {
    return (
      <Screen>
        {header}
        {daily ? <Txt variant="label">{`Puzzle ${slot + 1} of ${queue.length}`}</Txt> : null}
        <Card>
          <Txt variant="h2">{info.title}</Txt>
          <Txt variant="body">{info.body}</Txt>
          <View style={{ backgroundColor: c.alt, borderRadius: 14, padding: 14, flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
            <Ionicons name="bulb-outline" size={22} color={c.ink} />
            <Txt variant="body" style={{ flex: 1 }}>{`Tip: ${info.tip}`}</Txt>
          </View>
          <Txt variant="muted">{`Level ${level}${(prefs.puzzles.kinds[kind]?.best ?? 0) > 0 ? ` · your best is ${prefs.puzzles.kinds[kind]?.best}` : ''}`}</Txt>
        </Card>
        <Button kind="primary" label="Start" icon="play" onPress={() => startRound(kind, level)} />
      </Screen>
    );
  }

  if (phase === 'show') {
    const spoken = round.kind === 'sequence' ? String(round.answer).split('').join(' ') : round.show.join('. ');
    return (
      <Screen>
        {header}
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="h2" style={{ flex: 1 }}>{SHOW_TITLES[round.kind] ?? 'Remember these'}</Txt>
          <SpeakButton text={spoken} label="Read it aloud" />
        </Row>
        <Card style={{ alignItems: round.kind === 'story' || round.kind === 'routine' || round.kind === 'names' || round.kind === 'places' ? 'stretch' : 'center', paddingVertical: 24, gap: 12 }}>
          {round.kind === 'sequence' ? (
            <Txt variant="big" style={{ letterSpacing: 6 }}>{round.show[0]}</Txt>
          ) : round.kind === 'story' ? (
            <Txt variant="h3" style={{ lineHeight: 30, fontWeight: '500' }}>{round.show[0]}</Txt>
          ) : round.kind === 'names' ? (
            (round.people ?? []).map(([name, detail], index) => (
              <Row key={name} gap={14}>
                <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: AVATAR_TONES[index % AVATAR_TONES.length], alignItems: 'center', justifyContent: 'center' }}>
                  <Txt variant="h2" color="#ffffff">{name[0]}</Txt>
                </View>
                <View style={{ flex: 1 }}>
                  <Txt variant="h2">{name}</Txt>
                  <Txt variant="body">{detail}</Txt>
                </View>
              </Row>
            ))
          ) : (
            round.show.map((item) => <Txt key={item} variant="h2">{item}</Txt>)
          )}
        </Card>
        {screenReader ? (
          <Txt variant="muted">Take your time. Press “I’m ready” when you have them.</Txt>
        ) : (
          <ProgressBar value={left / (showFor || 1)} label={`${Math.ceil(left / 1000)} seconds left`} />
        )}
        <Button kind="primary" label="I'm ready" icon="arrow-forward" onPress={() => setPhase('answer')} />
      </Screen>
    );
  }

  if (phase === 'result' && last) {
    const isLast = ending || (roundNumber >= roundsFor(kind) && slot + 1 >= queue.length && !later);
    return (
      <Screen>
        {header}
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: last.right ? c.good[0] : c.review[0], borderRadius: 14, padding: 16, gap: 6 }}>
          <Txt variant="h3" color={last.right ? c.good[1] : c.review[1]}>{lastLine}</Txt>
          <Txt variant="body" color={last.right ? c.good[1] : c.review[1]}>{resultDetail(round, last)}</Txt>
        </View>
        <Button kind="primary" label={isLast ? 'Finish' : roundNumber >= roundsFor(kind) ? 'Next puzzle' : 'Next round'} icon="arrow-forward" onPress={goOn} />
      </Screen>
    );
  }

  // ------------------------------------------------------------------ answers
  const optionButton = (option: string, onPress: () => void, state: 'plain' | 'picked' | 'right' | 'wrong' | 'dim' = 'plain', key?: string, label?: string) => {
    const tone = state === 'right' ? c.good : state === 'wrong' ? c.review : null;
    return (
      <Pressable
        key={key ?? option}
        onPress={onPress}
        accessibilityRole="button"
        accessibilityState={{ selected: state === 'picked' }}
        accessibilityLabel={label ?? option}
        style={({ pressed }) => ({
          minHeight: 60, borderRadius: 14, padding: 14, borderWidth: 2, justifyContent: 'center', flexGrow: 1,
          borderColor: state === 'picked' ? c.primary : tone ? tone[1] : c.line,
          backgroundColor: tone ? tone[0] : state === 'picked' ? c.alt : pressed ? c.alt : c.surface,
          opacity: state === 'dim' ? 0.45 : 1,
        })}
      >
        <Txt variant="h3" center>{label ?? option}</Txt>
      </Pressable>
    );
  };

  const helpButton = (onPress: () => void, disabled = false) => (
    <Button label="Help me" icon="help-buoy-outline" onPress={onPress} disabled={disabled} hint="Gives a clue. The level stays the same." />
  );

  let body: ReactNode = null;
  const choiceKinds = ['pairs', 'missing', 'names', 'places', 'story', 'sort', 'nback'];
  if (phase === 'later' || choiceKinds.includes(round.kind)) {
    if (round.kind === 'nback' && !nbackStarted) {
      body = (
        <>
          <Txt variant="h2">Remember this word</Txt>
          <Card style={{ alignItems: 'center', paddingVertical: 32 }}>
            <Txt variant="big">{round.items?.[0] ?? ''}</Txt>
          </Card>
          <Txt variant="muted">Next, say whether each new word is the same as the one just before it.</Txt>
          <Button kind="primary" label="Next word" icon="arrow-forward" onPress={() => setNbackStarted(true)} />
        </>
      );
    } else if (question) {
      const options = trimmed ?? question.options;
      const prompt = round.kind === 'nback' ? 'Same as the word before?' : round.kind === 'sort' ? 'Where does it belong?' : question.prompt;
      body = (
        <>
          {phase === 'later' ? <Txt variant="muted">Earlier you read a story. Do you still remember it?</Txt> : null}
          {round.kind === 'missing' && round.remaining ? (
            <Card style={{ gap: 6 }}>
              <Txt variant="label">Still here</Txt>
              <Txt variant="h3">{round.remaining.join(', ')}</Txt>
            </Card>
          ) : null}
          {round.kind === 'nback' || round.kind === 'sort' ? (
            <Card style={{ alignItems: 'center', paddingVertical: 28 }}>
              <Txt variant="big">{question.prompt}</Txt>
            </Card>
          ) : null}
          <Row style={{ justifyContent: 'space-between' }}>
            <Txt variant="h2" style={{ flex: 1 }}>{prompt}</Txt>
            <SpeakButton text={`${round.kind === 'nback' || round.kind === 'sort' ? `${question.prompt}. ` : ''}${prompt} The choices are ${options.join(', ')}.`} label="Read the question and choices aloud" />
          </Row>
          {questions.length > 1 && round.kind !== 'nback' ? <Txt variant="label">{`Question ${qIndex + 1} of ${questions.length}`}</Txt> : null}
          <View style={{ gap: 10, flexDirection: options.length === 2 ? 'row' : 'column' }}>
            {options.map((option) => optionButton(option, () => choose(option), reveal ? (option === question.answer ? 'right' : option === reveal ? 'wrong' : 'dim') : 'plain'))}
          </View>
          {options.length > 2 ? helpButton(helpChoice, !!trimmed || !!reveal) : null}
        </>
      );
    }
  } else if (round.kind === 'sequence') {
    const answer = String(round.answer);
    body = (
      <>
        <Txt variant="h2">Tap the numbers in order</Txt>
        <Card style={{ alignItems: 'center', paddingVertical: 18, minHeight: 80 }}>
          <Txt variant="big" style={{ letterSpacing: 6 }} accessibilityLiveRegion="polite">{digits ? digitGroups(digits).join(' ') : '–'}</Txt>
        </Card>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {['1', '2', '3', '4', '5', '6', '7', '8', '9', 'back', '0', 'ok'].map((key) => (
            <View key={key} style={{ width: '31%', flexGrow: 1 }}>
              {key === 'back'
                ? optionButton('back', () => setDigits(digits.slice(0, -1)), 'plain', key, '⌫ Undo')
                : key === 'ok'
                  ? optionButton('ok', () => finish(digits), digits.length ? 'picked' : 'dim', key, 'Check')
                  : optionButton(key, () => digits.length < answer.length + 2 && setDigits(digits + key))}
            </View>
          ))}
        </View>
        {helpButton(() => {
          setHelped(true);
          setDigits(answer.slice(0, Math.max(1, Math.floor(answer.length / 3))));
        }, helped)}
      </>
    );
  } else if (round.kind === 'words') {
    const options = round.options ?? [];
    const shown = round.answer as string[];
    body = typing ? (
      <>
        <Field label="Type the words you remember" value={typed} onChangeText={setTyped} autoCapitalize="none" autoFocus multiline />
        <Button kind="primary" label="Check" icon="checkmark" onPress={() => finish(typed)} />
        <Button label="Tap them instead" icon="grid-outline" onPress={() => setTyping(false)} />
      </>
    ) : (
      <>
        <Txt variant="h2">Tap the words you saw</Txt>
        <Txt variant="muted">{`${shown.length} of these were on the screen.`}</Txt>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {options.map((option) => (
            <View key={option} style={{ width: '47%', flexGrow: 1 }}>
              {optionButton(option, () => setChosen(chosen.includes(option) ? chosen.filter((item) => item !== option) : [...chosen, option]), chosen.includes(option) ? 'picked' : 'plain')}
            </View>
          ))}
        </View>
        <Button kind="primary" label="Done" icon="checkmark" onPress={() => finish(chosen)} disabled={!chosen.length} />
        {helpButton(() => {
          const missing = shown.find((word) => !chosen.includes(word));
          setHelped(true);
          if (missing) setChosen([...chosen, missing]);
        }, helped)}
        <Button label="Type them instead" icon="create-outline" onPress={() => setTyping(true)} />
      </>
    );
  } else if (round.kind === 'routine') {
    const options = round.options ?? [];
    const answer = round.answer as string[];
    const tapStep = (index: number) => {
      if (order.includes(index)) return;
      const next = [...order, index];
      setOrder(next);
      if (next.length === options.length) setTimeout(() => finish(next.map((i) => options[i])), 400);
    };
    body = (
      <>
        <Txt variant="h2">Tap the steps in order</Txt>
        <Txt variant="muted">{`Which comes first? ${order.length} of ${options.length} placed.`}</Txt>
        <View style={{ gap: 10 }}>
          {options.map((option, index) => {
            const at = order.indexOf(index);
            return optionButton(option, () => tapStep(index), at >= 0 ? 'picked' : 'plain', `${index}`, at >= 0 ? `${at + 1}. ${option}` : option);
          })}
        </View>
        <Row>
          <Button label="Undo" icon="arrow-undo-outline" onPress={() => setOrder(order.slice(0, -1))} disabled={!order.length} />
          {helpButton(() => {
            const nextStep = answer[order.length];
            const index = options.findIndex((option, i) => option === nextStep && !order.includes(i));
            setHelped(true);
            if (index >= 0) tapStep(index);
          }, helped)}
        </Row>
      </>
    );
  } else if (round.kind === 'search') {
    const tiles = round.tiles ?? [];
    const total = round.answer as number;
    const tapTile = (index: number) => {
      if (found.includes(index)) return;
      if (tiles[index] !== round.target) {
        setWrongTaps(wrongTaps + 1);
        return;
      }
      const next = [...found, index];
      setFound(next);
      if (next.length >= total) setTimeout(() => finish({ found: next.length, wrong: wrongTaps }), 400);
    };
    body = (
      <>
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="h2" style={{ flex: 1 }}>{`Find every “${round.target}”`}</Txt>
          <SpeakButton text={`Find every ${round.target}`} label="Read it aloud" />
        </Row>
        <Txt variant="muted" accessibilityLiveRegion="polite">{`Found ${found.length} of ${total}${wrongTaps ? ` · ${wrongTaps} other word${wrongTaps === 1 ? '' : 's'} tapped` : ''}`}</Txt>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
          {tiles.map((tile, index) => (
            <View key={`${index}`} style={{ width: '31%', flexGrow: 1 }}>
              {optionButton(tile, () => tapTile(index), found.includes(index) ? 'right' : 'plain', `${index}`)}
            </View>
          ))}
        </View>
        <Row>
          <Button label="I’m done" icon="checkmark" onPress={() => finish({ found: found.length, wrong: wrongTaps })} />
          {helpButton(() => {
            const index = tiles.findIndex((tile, i) => tile === round.target && !found.includes(i));
            setHelped(true);
            if (index >= 0) tapTile(index);
          }, helped)}
        </Row>
      </>
    );
  }

  return (
    <Screen>
      {header}
      {body}
    </Screen>
  );
}

const SHOW_TITLES: Partial<Record<PuzzleKind, string>> = {
  sequence: 'Remember these numbers',
  words: 'Remember these words',
  pairs: 'Remember which go together',
  missing: 'Remember this list',
  names: 'Meet these people',
  places: 'Remember where you put them',
  story: 'Read this short story',
  routine: 'Remember the steps in order',
};

function resultDetail(round: PuzzleRound, result: RoundScore): string {
  if (round.kind === 'sequence') return `It was ${digitGroups(String(round.answer)).join(' ')}.`;
  if (round.kind === 'words') return `You remembered ${result.correct} of ${result.total}: ${(round.answer as string[]).join(', ')}.`;
  if (round.kind === 'routine') return `${result.correct} of ${result.total} steps in the right place. The order was: ${(round.answer as string[]).join(', then ')}.`;
  if (round.kind === 'search') return `You found ${result.correct} of ${result.total}.`;
  return `${result.correct} of ${result.total} right.`;
}

