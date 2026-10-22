/**
 * Make with AI: study notes or practice questions from typed notes, a PDF or
 * a photo. The one-time AI screen comes first, then sign-in; nothing is sent
 * until a Make button is pressed. Questions go to the set builder as rows to
 * check and edit before saving; notes are shown here and can be saved.
 */
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import { useNetworkState } from 'expo-network';
import { useState } from 'react';
import { ActivityIndicator, Linking, Platform, View } from 'react-native';

import { aiStyleFor, fileFromBase64, makeNotes, makeQuestions, notesText, rememberAiStyle } from '../cloud/ai';
import type { AiAuth, AiInput, AiNotes } from '../cloud/ai';
import { nowLabel } from '../core/dates';
import { uid } from '../core/models';
import { AI_NOTE } from '../core/questions';
import { normalizeSpace, splitStudyBits } from '../core/text';
import { deckCards } from '../features/decks';
import { sendRowsToBuilder, takeNotesForAi } from '../features/aiHandoff';
import { aiErrorText, aiGate, isOnline, needsAccount, remainingText, reportMailto, rowsFromAiQuestions, sectionSpeech } from '../features/aiHelpers';
import { AiSource, keepSource, pickPdf, pickPhoto, PickResult } from '../features/aiSource';
import { usePrefs, useStore, useSync } from '../state/AppState';
import { AiConsent } from '../ui/AiConsent';
import { AiTag, Button, Card, EmptyState, Field, IconButton, ListGroup, ListRow, Row, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../ui/components';
import { notify } from '../ui/feedback';
import { useTheme } from '../ui/theme';

/**
 * Browser previews only: a stand-in for the AI server (set on window by a
 * screenshot script), so the screens can be shown without an account.
 */
function previewFetcher(): typeof fetch | undefined {
  if (Platform.OS !== 'web') return undefined;
  return (globalThis as { __memorypalAiFetch?: typeof fetch }).__memorypalAiFetch;
}

type Busy = 'notes' | 'questions' | null;

export default function MakeWithAi() {
  const store = useStore();
  const sync = useSync();
  const theme = useTheme();
  const c = theme.colors;
  const [prefs, setPrefs] = usePrefs();
  const network = useNetworkState();
  const params = useLocalSearchParams<{ deck?: string; from?: string }>();
  const deck = normalizeSpace(String(params.deck ?? ''));
  const [text, setText] = useState(() => takeNotesForAi());
  const [source, setSource] = useState<AiSource | null>(null);
  // A set's style and teacher's questions are remembered on this phone and filled in next time.
  const [style, setStyle] = useState(() => aiStyleFor(prefs.ai_styles, deck).style);
  const [examples, setExamples] = useState(() => aiStyleFor(prefs.ai_styles, deck).examples);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState('');
  const [accountNeeded, setAccountNeeded] = useState(false);
  const [left, setLeft] = useState('');
  const [notes, setNotes] = useState<AiNotes | null>(null);
  const [notesSaved, setNotesSaved] = useState('');
  useStopSpeechOnLeave();

  const preview = previewFetcher();
  const gate = aiGate({ allowed: prefs.ai_allowed, signedIn: sync.account.signedIn || !!preview, online: isOnline(network), configured: sync.configured || !!preview });
  const auth: AiAuth = preview ? 'preview' : sync.account;

  if (gate === 'consent') {
    return (
      <Screen narrow>
        <Stack.Screen options={{ title: 'Make with AI' }} />
        <AiConsent onAllow={() => setPrefs({ ai_allowed: true, ai_allowed_at: new Date().toISOString() })} onNotNow={() => router.back()} />
      </Screen>
    );
  }
  if (gate === 'sign_in' || gate === 'not_configured') {
    return (
      <Screen narrow>
        <Stack.Screen options={{ title: 'Make with AI' }} />
        <EmptyState
          icon="person-circle-outline"
          title={gate === 'sign_in' ? 'Sign in to use AI' : 'AI isn’t available yet'}
          body={gate === 'sign_in' ? 'AI notes and questions need a free MemoryPal account, so each person gets a fair daily share. Everything else works without one.' : 'This copy of MemoryPal isn’t connected to the MemoryPal cloud.'}
          action={gate === 'sign_in' ? <Button kind="primary" label="Sign in or create an account" icon="person-outline" onPress={() => router.push('/account')} /> : <Button label="Go back" onPress={() => router.back()} />}
        />
      </Screen>
    );
  }
  const offline = gate === 'offline';

  const choose = async (picker: () => Promise<PickResult>) => {
    setError('');
    try {
      const result = await picker();
      if ('denied' in result) return notify('Can’t open the camera', result.denied);
      if ('source' in result) {
        fileFromBase64(result.source.base64, result.source.mime); // size and type check now, not after waiting
        setSource(result.source);
      }
    } catch (problem) {
      setError(aiErrorText(problem));
    }
  };

  const input = (): AiInput => ({ text: text.trim(), file: source ? fileFromBase64(source.base64, source.mime) : null, title: deck || undefined, style: style.trim() || undefined });

  const run = async (kind: Exclude<Busy, null>, from?: AiInput) => {
    if (busy) return;
    setError('');
    setAccountNeeded(false);
    setBusy(kind);
    try {
      const request = from ?? input();
      if (deck) setPrefs({ ai_styles: rememberAiStyle(prefs.ai_styles, deck, style, examples) });
      if (kind === 'notes') {
        const made = await makeNotes(auth, request, { fetcher: preview });
        setLeft(remainingText(made.remaining));
        setNotes({ title: made.title, sections: made.sections, key_terms: made.key_terms });
        setNotesSaved('');
      } else {
        const avoid = deck ? deckCards(store, deck).map((card) => card.front) : [];
        const made = await makeQuestions(auth, { ...request, style: style.trim() || undefined, examples, count: 10, avoid }, { fetcher: preview });
        const usesLeft = remainingText(made.remaining);
        setLeft(usesLeft);
        if (!made.questions.length) {
          setError('The AI didn’t find questions to ask in that. Try longer notes or a clearer page.');
          return;
        }
        // Cards made from a file keep a copy of it (only when this request used the file).
        const kept = source && !from ? await keepSource(source) : '';
        const title = deck || notes?.title || 'Notes';
        const rows = rowsFromAiQuestions(made.questions, deck, title, source && !from ? { kind: source.kind, uri: kept } : null);
        const count = rows.length;
        sendRowsToBuilder(rows, [`${count} card${count === 1 ? '' : 's'} made with AI. Check each one, edit or remove any that are wrong, then save.`, usesLeft].filter(Boolean).join(' '));
        if (params.from === 'add') router.back();
        else router.replace(`/add?deck=${encodeURIComponent(deck)}` as Href);
      }
    } catch (problem) {
      setError(aiErrorText(problem));
      setAccountNeeded(needsAccount(problem));
    } finally {
      setBusy(null);
    }
  };

  const saveNotes = async () => {
    if (!notes) return;
    const kept = source ? await keepSource(source) : '';
    const body = `${AI_NOTE}\n\n${notesText(notes)}`;
    const title = deck ? `${deck}: ${notes.title}` : notes.title;
    store.addCapture({ id: uid(), title, notes: body, chunks: splitStudyBits(notesText(notes)), text_file: source?.kind === 'pdf' ? kept : '', image: source?.kind === 'image' ? kept : '', audio: '', video: '', created_at: nowLabel() });
    setNotesSaved(`Notes saved${deck ? ` with ${deck}` : ''}.`);
  };

  const report = () => {
    if (!notes) return;
    Linking.openURL(reportMailto('notes', notesText(notes))).catch(() => notify('No email app', 'Email memorypal09@gmail.com to report this result.'));
  };

  const hasInput = !!text.trim() || !!source;
  const makeLabel = (label: string) => (offline ? 'Needs internet' : label);

  return (
    <Screen narrow>
      <Stack.Screen options={{ title: 'Make with AI' }} />
      <Txt variant="muted">{deck ? `Notes or questions for ${deck}.` : 'Notes or questions for a new set.'} Choose what the AI should read.</Txt>

      <Field label="Your notes" hint="Type or paste notes, or leave this empty and choose a file." value={text} onChangeText={setText} multiline placeholder="The heart pumps blood around the body…" style={{ minHeight: 120 }} />

      <ListGroup footer="Don’t send anything private or sensitive: Google may keep what is sent, and people may read it.">
        {source ? (
          <ListRow
            icon={source.kind === 'pdf' ? 'document-outline' : 'image-outline'}
            title={source.name}
            detail={source.kind === 'pdf' ? 'PDF chosen' : 'Photo chosen'}
            right={<IconButton icon="close" label="Remove the chosen file" onPress={() => setSource(null)} />}
          />
        ) : null}
        <ListRow icon="document-outline" title="Choose a PDF" detail="Up to 8 MB" onPress={() => choose(pickPdf)} />
        {Platform.OS !== 'web' ? <ListRow icon="camera-outline" title="Take a photo" detail="Of a page, a slide or a whiteboard" onPress={() => choose(() => pickPhoto('camera'))} /> : null}
        <ListRow icon="image-outline" title="Choose a photo" onPress={() => choose(() => pickPhoto('library'))} />
      </ListGroup>

      <Field
        label="How should it look? (optional)"
        hint="For example “one line per date: the year, then what happened”, “word, meaning, then an example”, or “only the causes of the war”."
        value={style}
        onChangeText={setStyle}
        placeholder="One line per date…"
        maxLength={500}
      />

      <Field
        label="Questions your teacher has asked (optional)"
        hint={`One per line. New questions follow their style, level and the parts of the material they come from. Leave both boxes empty and questions follow the ones already in ${deck ? 'this set' : 'the set'}.${deck ? ' Saved with this set on this phone.' : ''}`}
        value={examples}
        onChangeText={setExamples}
        multiline
        placeholder="A 60-year-old has crushing chest pain. What is the first test?"
        maxLength={8000}
        style={{ minHeight: 90 }}
      />

      <Row>
        <Button kind="primary" icon={offline ? 'cloud-offline-outline' : 'reader-outline'} label={makeLabel('Make notes')} onPress={() => run('notes')} disabled={offline || !hasInput || !!busy} style={{ flex: 1 }} />
        <Button icon={offline ? 'cloud-offline-outline' : 'help-circle-outline'} label={makeLabel('Make questions')} onPress={() => run('questions')} disabled={offline || !hasInput || !!busy} style={{ flex: 1 }} />
      </Row>

      {busy ? (
        <View accessibilityLiveRegion="polite" style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <ActivityIndicator color={c.primary} />
          <Txt variant="muted" style={{ flex: 1 }}>{busy === 'notes' ? 'Making notes… this can take up to a minute.' : 'Making questions… this can take up to a minute.'}</Txt>
        </View>
      ) : null}
      {error ? (
        <View accessibilityLiveRegion="polite" style={{ backgroundColor: c.again[0], borderRadius: theme.radius, padding: 14, gap: 10 }}>
          <Txt variant="body" color={c.again[1]}>{error}</Txt>
          {accountNeeded ? <Button label="Open Account & sync" icon="person-outline" onPress={() => router.push('/account')} /> : null}
        </View>
      ) : null}
      {left ? <Txt variant="small" accessibilityLiveRegion="polite">{left}</Txt> : null}

      {notes ? <NotesView notes={notes} /> : null}
      {notes ? (
        <View style={{ gap: 10 }}>
          {notesSaved ? <Txt variant="body" color={c.good[1]} accessibilityLiveRegion="polite">{notesSaved}</Txt> : null}
          <Button kind="primary" icon="bookmark-outline" label="Save notes" onPress={saveNotes} disabled={!!notesSaved} hint={deck ? `Keeps these notes with ${deck}` : 'Keeps these notes on this phone'} />
          <Button icon="help-circle-outline" label={makeLabel('Make questions from these notes')} onPress={() => run('questions', { text: notesText(notes), title: deck || notes.title })} disabled={offline || !!busy} />
          <Button kind="ghost" icon="flag-outline" label="Report these notes" onPress={report} hint="Opens an email to MemoryPal with the notes, so you can say what is wrong" />
        </View>
      ) : null}
    </Screen>
  );
}

/** AI notes laid out for reading: title, sections with their points, key terms. */
export function NotesView({ notes }: { notes: AiNotes }) {
  return (
    <View style={{ gap: 12 }}>
      <Card>
        <AiTag />
        <Row style={{ justifyContent: 'space-between' }}>
          <Txt variant="h2" accessibilityRole="header" style={{ flex: 1 }}>{notes.title}</Txt>
          <SpeakButton text={notesText(notes).replace(/ :: /g, ': ')} label="Read all the notes aloud" />
        </Row>
      </Card>
      {notes.sections.map((section, i) => (
        <Card key={`${section.heading}-${i}`}>
          <Row style={{ justifyContent: 'space-between' }}>
            <Txt variant="h3" accessibilityRole="header" style={{ flex: 1 }}>{section.heading || `Part ${i + 1}`}</Txt>
            <SpeakButton text={sectionSpeech(section)} label={`Read “${section.heading || `Part ${i + 1}`}” aloud`} />
          </Row>
          {section.bullets.map((bullet, j) => (
            <Row key={j} style={{ alignItems: 'flex-start' }} gap={8}>
              <Txt variant="body">•</Txt>
              <Txt variant="body" style={{ flex: 1 }}>{bullet}</Txt>
            </Row>
          ))}
        </Card>
      ))}
      {notes.key_terms.length ? (
        <ListGroup header="Key terms">
          {notes.key_terms.map((item) => (
            <ListRow key={item.term} title={item.term} detail={item.definition} right={<SpeakButton text={`${item.term}. ${item.definition}`} label={`Read ${item.term} aloud`} />} />
          ))}
        </ListGroup>
      ) : null}
    </View>
  );
}
