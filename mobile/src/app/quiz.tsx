/**
 * Quick quiz: a round of mixed questions made from the cards (pick the
 * answer, which one goes with it, true or false, fill in the blank, match the
 * pairs, what comes next, or type it). Due and weak cards come first, and the
 * last round's questions are avoided.
 */
import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';

import type { Question } from '../core/questions';
import { checkAnswer, isAiCard } from '../core/questions';
import { answerAssessment, Assessment } from '../core/smartCheck';
import { makeRound, matchBoard, MatchBoard, matchDone, nextRecent, optionsSpeech, promptParts, promptSpeech, quizCards, tapMatch, typedOutcome } from '../features/quizPlay';
import { useStore, usePrefs } from '../state/AppState';
import { AiTag, Button, Card, EmptyState, Field, ProgressBar, Row, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../ui/components';
import { speak, stopSpeaking, tap } from '../ui/feedback';
import { useTheme } from '../ui/theme';

const TYPE_LABEL: Record<Question['type'], string> = {
  choice: 'Pick the answer',
  reverse: 'Which one goes with it?',
  cloze: 'Fill in the blank',
  truefalse: 'True or false',
  match: 'Match the pairs',
  order: 'What comes next?',
  recall: 'Type the answer',
};

type Outcome = 'right' | 'close' | 'wrong';

export default function Quiz() {
  const store = useStore();
  const theme = useTheme();
  const [prefs, setPrefs] = usePrefs();
  const c = theme.colors;
  const params = useLocalSearchParams<{ deck?: string }>();
  const deck = params.deck || null;
  const slow = store.accessibility.more_time;

  const [questions, setQuestions] = useState<Question[]>(() => makeRound(store.cards, deck, prefs.quiz_recent));
  const [index, setIndex] = useState(0);
  const [score, setScore] = useState(0);
  // The answer to the current question: an option picked, a typed check, or a finished match.
  const [picked, setPicked] = useState<number | null>(null);
  const [typed, setTyped] = useState('');
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [gaveUp, setGaveUp] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [boardState, setBoard] = useState<MatchBoard | null>(null);
  const question = questions[index];
  const board = boardState ?? (question?.type === 'match' ? matchBoard(question) : null);

  // Each question starts with a clean slate.
  const goTo = (next: number) => {
    setPicked(null);
    setTyped('');
    setAssessment(null);
    setGaveUp(false);
    setShowHint(false);
    setBoard(null);
    setIndex(next);
  };

  // The round's questions are remembered on this phone, so the next round asks others.
  useEffect(() => {
    if (questions.length) setPrefs({ quiz_recent: nextRecent(prefs.quiz_recent, questions) });
  }, [questions]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (question && store.accessibility.read_aloud) speak(promptSpeech(question), slow);
    return stopSpeaking;
  }, [question]); // eslint-disable-line react-hooks/exhaustive-deps
  useStopSpeechOnLeave();

  if (quizCards(store.cards, deck).length < 2 || !questions.length) {
    return (
      <Screen>
        <EmptyState icon="help-circle-outline" title="Add a few more cards" body="A quiz needs at least two cards with answers, and works best with four or more." action={<Button kind="primary" label="Add cards" onPress={() => router.replace(deck ? `/add?deck=${encodeURIComponent(deck)}` : '/add')} />} />
      </Screen>
    );
  }

  const again = () => {
    setQuestions(makeRound(store.cards, deck, prefs.quiz_recent));
    goTo(0);
    setScore(0);
  };

  if (index >= questions.length) {
    return (
      <Screen title="Quiz done">
        <Card tone="alt">
          <Txt variant="big">{score} / {questions.length}</Txt>
          <Txt variant="body">{score === questions.length ? 'Every one right!' : 'Cards you missed are worth a proper review. Typing the answer from memory works better than picking it.'}</Txt>
        </Card>
        <Button kind="primary" label="Done" onPress={() => router.back()} />
        <Button label="Another round" icon="refresh" onPress={again} hint="New questions; the ones you just had come last." />
        <Button label="Review weaker cards" onPress={() => router.replace('/review?mode=weak')} />
      </Screen>
    );
  }

  const card = store.findCard(question.card_id);
  const matchFinished = !!board && matchDone(board);
  const outcome: Outcome | null =
    question.type === 'match'
      ? matchFinished ? (board!.mistakes === 0 ? 'right' : 'wrong') : null
      : question.typed
        ? gaveUp ? 'wrong' : assessment ? typedOutcome(assessment) : null
        : picked !== null ? (checkAnswer(question, picked) ? 'right' : 'wrong') : null;

  const finish = (result: Outcome) => {
    if (result === 'right') setScore((value) => value + 1);
    store.recordPractice();
    if (store.accessibility.read_aloud) speak(result === 'right' ? 'Correct.' : `The answer is ${question.answer}`, slow);
  };

  const choose = (i: number) => {
    if (picked !== null) return;
    tap(prefs.haptics);
    setPicked(i);
    finish(checkAnswer(question, i) ? 'right' : 'wrong');
  };

  const checkTyped = () => {
    if (!typed.trim() || assessment) return;
    const result = answerAssessment(typed, question.answer, question.context || question.prompt);
    setAssessment(result);
    finish(typedOutcome(result));
  };

  const giveUp = () => {
    setGaveUp(true);
    finish('wrong');
  };

  const tapPair = (side: 'left' | 'right', i: number) => {
    if (!board || matchFinished) return;
    tap(prefs.haptics);
    const next = tapMatch(board, question, side, i);
    setBoard(next);
    if (matchDone(next)) finish(next.mistakes === 0 ? 'right' : 'wrong');
  };

  const parts = promptParts(question.prompt);
  const outcomeColors = outcome === 'right' ? c.good : outcome === 'close' ? c.review : outcome ? c.again : null;
  const outcomeText =
    outcome === 'right'
      ? question.type === 'match' ? 'All matched first time!' : 'Correct!'
      : outcome === 'close' ? `Nearly. The answer is “${question.answer}”.`
        : question.type === 'match' ? `All matched, with ${board?.mistakes ?? 0} wrong ${board?.mistakes === 1 ? 'try' : 'tries'}.`
          : `The answer is “${question.answer}”.`;

  return (
    <Screen>
      <Row style={{ justifyContent: 'space-between' }}>
        <Txt variant="label" style={{ flex: 1 }}>{`Question ${index + 1} of ${questions.length} · ${TYPE_LABEL[question.type]}`}</Txt>
        <SpeakButton text={promptSpeech(question)} label="Read the question aloud" />
        {question.options.length && question.type !== 'match' ? <SpeakButton text={optionsSpeech(question.options)} label="Read the choices aloud" /> : null}
      </Row>
      <ProgressBar value={index / questions.length} />

      <Card style={{ minHeight: 110, justifyContent: 'center' }}>
        {question.type === 'cloze' && question.context ? <Txt variant="label">{question.context}</Txt> : null}
        <Txt variant="h2" accessibilityRole="header" accessibilityLabel={promptSpeech(question)}>
          {parts.before}
          {parts.blank ? <Txt variant="h2" color={c.primary} style={{ textDecorationLine: 'underline' }}>{'      '}</Txt> : null}
          {parts.after}
        </Txt>
        {card && isAiCard(card) ? <AiTag /> : null}
      </Card>

      {question.type === 'match' && board ? (
        <MatchView board={board} onTap={tapPair} />
      ) : question.typed ? (
        <View style={{ gap: 10 }}>
          <Field
            label="Your answer"
            value={typed}
            onChangeText={setTyped}
            editable={!outcome}
            placeholder="Type the answer…"
            returnKeyType="done"
            onSubmitEditing={checkTyped}
            autoCapitalize="none"
          />
          {showHint && question.hint ? <Txt variant="muted" accessibilityLiveRegion="polite">{`Hint: ${question.hint}`}</Txt> : null}
          {!outcome ? (
            <>
              <Button kind="primary" label="Check" icon="checkmark-done" onPress={checkTyped} disabled={!typed.trim()} />
              <Row style={{ alignItems: 'stretch' }}>
                {question.hint && !showHint ? <Button compact label="Show a hint" icon="bulb-outline" onPress={() => setShowHint(true)} style={{ flex: 1 }} /> : null}
                <Button compact label="I don’t know" icon="help-outline" onPress={giveUp} style={{ flex: 1 }} />
              </Row>
            </>
          ) : null}
        </View>
      ) : (
        <View accessibilityRole="radiogroup" style={{ gap: 10 }}>
          {question.options.map((option, i) => {
            const isAnswer = i === question.answer_index;
            const state = picked === null ? 'idle' : isAnswer ? 'right' : i === picked ? 'wrong' : 'idle';
            const colors = state === 'right' ? c.good : state === 'wrong' ? c.again : null;
            return (
              <Pressable
                key={`${option}-${i}`}
                onPress={() => choose(i)}
                accessibilityRole="radio"
                accessibilityState={{ selected: i === picked, disabled: picked !== null }}
                accessibilityHint={state === 'right' ? 'Correct answer' : state === 'wrong' ? 'Not the answer' : undefined}
                style={({ pressed }) => ({
                  minHeight: 56,
                  borderRadius: 14,
                  padding: 14,
                  borderWidth: 1.5,
                  borderColor: colors ? colors[1] : c.line,
                  backgroundColor: colors ? colors[0] : pressed ? c.alt : c.surface,
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: 10,
                })}
              >
                <Txt variant="body" style={{ flex: 1 }} color={colors ? colors[1] : c.ink}>{option}</Txt>
                {state === 'right' ? <Ionicons name="checkmark-circle" size={theme.icon(24)} color={c.good[1]} /> : null}
                {state === 'wrong' ? <Ionicons name="close-circle" size={theme.icon(24)} color={c.again[1]} /> : null}
              </Pressable>
            );
          })}
        </View>
      )}

      {outcome && outcomeColors ? (
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: outcomeColors[0], borderRadius: 14, padding: 14, gap: 4 }}>
          <Txt variant="h3" color={outcomeColors[1]}>{outcomeText}</Txt>
          {question.type === 'truefalse' && card?.back ? <Txt variant="small" color={outcomeColors[1]}>{`${card.front} → ${card.back}`}</Txt> : null}
          {assessment && outcome !== 'right' ? <Txt variant="small" color={outcomeColors[1]}>{`You typed “${typed.trim()}”.`}</Txt> : null}
        </View>
      ) : null}

      {outcome ? (
        <Row>
          <Button kind="primary" label={index + 1 === questions.length ? 'See results' : 'Next question'} icon="arrow-forward" onPress={() => goTo(index + 1)} style={{ flex: 1 }} />
        </Row>
      ) : null}
    </Screen>
  );
}

/** Tap one on the left, then its partner on the right (or the other way round). */
function MatchView({ board, onTap }: { board: MatchBoard; onTap: (side: 'left' | 'right', index: number) => void }) {
  const theme = useTheme();
  const c = theme.colors;
  const pairNumber = (side: 'left' | 'right', i: number): number | null => {
    const entries = Object.entries(board.matched).map(([left, right]) => [Number(left), right] as const);
    const at = entries.findIndex(([left, right]) => (side === 'left' ? left === i : right === i));
    return at < 0 ? null : at + 1;
  };
  const item = (side: 'left' | 'right', text: string, i: number) => {
    const done = pairNumber(side, i);
    const selected = board.selected?.side === side && board.selected.index === i;
    const wrong = board.wrong && (side === 'left' ? board.wrong.left === i : board.wrong.right === i);
    const colors = done ? c.good : wrong ? c.again : null;
    return (
      <Pressable
        key={`${side}-${i}`}
        onPress={() => onTap(side, i)}
        disabled={!!done}
        accessibilityRole="button"
        accessibilityState={{ selected, disabled: !!done }}
        accessibilityLabel={`${text}${done ? `, matched, pair ${done}` : selected ? ', selected' : ''}`}
        accessibilityHint={done ? undefined : side === 'left' ? 'Then tap what goes with it on the right' : 'Then tap what goes with it on the left'}
        style={({ pressed }) => ({
          minHeight: 56,
          borderRadius: 14,
          padding: 12,
          borderWidth: selected ? 2.5 : 1.5,
          borderColor: selected ? c.primary : colors ? colors[1] : c.line,
          backgroundColor: colors ? colors[0] : pressed ? c.alt : c.surface,
          flexDirection: 'row',
          alignItems: 'center',
          gap: 6,
        })}
      >
        <Txt variant="body" style={{ flex: 1 }} color={colors ? colors[1] : c.ink}>{text}</Txt>
        {done ? <Txt variant="label" color={c.good[1]}>{String(done)}</Txt> : null}
      </Pressable>
    );
  };
  return (
    <View style={{ gap: 8 }}>
      <Txt variant="muted">Tap one on the left, then the one that goes with it on the right.</Txt>
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <View style={{ flex: 1, gap: 10 }}>{board.lefts.map((text, i) => item('left', text, i))}</View>
        <View style={{ flex: 1, gap: 10 }}>{board.rights.map((text, i) => item('right', text, i))}</View>
      </View>
      {board.wrong ? <Txt variant="small" color={c.again[1]} accessibilityLiveRegion="polite">Not a pair. Try again.</Txt> : null}
    </View>
  );
}
