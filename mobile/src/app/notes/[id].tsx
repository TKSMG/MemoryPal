/** One saved note: read it, hear it, edit it (with bold, italics and highlighting), make questions from it, or delete it. A card's "Where it came from" opens it at its bit. */
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import * as Sharing from 'expo-sharing';
import { useState } from 'react';
import { Image, Platform, View } from 'react-native';

import { AI_NOTE } from '../../core/questions';
import { plain } from '../../core/richtext';
import { captureDeck } from '../../core/store';
import { sendNotesToAi } from '../../features/aiHandoff';
import { useStore } from '../../state/AppState';
import { AiTag, Button, Card, EmptyState, Field, RichField, RichText, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../../ui/components';
import { confirm, notify } from '../../ui/feedback';
import { useTheme } from '../../ui/theme';

export default function Notes() {
  const store = useStore();
  const theme = useTheme();
  const params = useLocalSearchParams<{ id: string; bit?: string }>();
  const capture = store.findCapture(String(params.id));
  useStopSpeechOnLeave();
  // While editing: the title and the notes, one study bit per line.
  const [draft, setDraft] = useState<{ title: string; text: string } | null>(null);

  if (!capture) {
    return (
      <Screen narrow>
        <Stack.Screen options={{ title: 'Notes' }} />
        <EmptyState icon="alert-circle-outline" title="These notes are gone" body="They may have been deleted." action={<Button label="Go back" onPress={() => router.back()} />} />
      </Screen>
    );
  }

  const deck = captureDeck(capture, store.decks());
  const ai = capture.notes.startsWith(AI_NOTE);
  const bits = capture.chunks;
  const bit = params.bit !== undefined ? Number(params.bit) : -1;
  const body = ai ? capture.notes.slice(AI_NOTE.length).trim() : capture.notes;
  const localFile = (uri: string) => uri.startsWith('file:');

  const makeQuestions = () => {
    sendNotesToAi(body);
    router.push(`/ai?deck=${encodeURIComponent(deck)}&notes=${encodeURIComponent(capture.title)}` as Href);
  };
  const openPdf = () => {
    Sharing.shareAsync(capture.text_file, { mimeType: 'application/pdf', dialogTitle: 'Open the PDF', UTI: 'com.adobe.pdf' }).catch(() => notify('Couldn’t open the PDF', 'The file may have been removed from this phone.'));
  };
  const remove = async () => {
    if (await confirm('Delete these notes?', `“${capture.title}” will be removed. Cards made from them stay. This can’t be undone.`, 'Delete', true)) {
      store.deleteCapture(capture.id);
      router.back();
    }
  };

  const startEditing = () => setDraft({ title: capture.title, text: bits.join('\n') });
  const saveEdit = () => {
    if (!draft) return;
    if (!draft.text.trim()) return notify('Notes need some text', 'To remove these notes, use Delete notes instead.');
    store.updateCapture(capture.id, draft.title, draft.text);
    setDraft(null);
  };

  if (draft) {
    return (
      <Screen narrow>
        <Stack.Screen options={{ title: 'Edit notes' }} />
        <Field label="Title" value={draft.title} onChangeText={(title) => setDraft({ ...draft, title })} />
        <RichField
          label="Notes"
          hint="Each line is one study bit. Select words, then tap B, I or Highlight. Bold or highlighted words become the blank in questions made from these notes."
          value={draft.text}
          onChangeText={(text) => setDraft({ ...draft, text })}
          style={{ minHeight: 220 }}
          autoFocus
        />
        <Button kind="primary" icon="checkmark" label="Save notes" onPress={saveEdit} />
        <Button label="Cancel" onPress={() => setDraft(null)} />
      </Screen>
    );
  }

  return (
    <Screen narrow>
      <Stack.Screen options={{ title: capture.title }} />
      <Txt variant="muted">{[deck ? `In ${deck}` : 'Not in a set', capture.created_at].filter(Boolean).join(' · ')}</Txt>
      {ai ? <AiTag /> : null}
      {capture.image && localFile(capture.image) ? (
        <Image source={{ uri: capture.image }} resizeMode="contain" style={{ width: '100%', height: 220, borderRadius: 12 }} accessibilityLabel="The photo these notes were made from" />
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        <SpeakButton text={plain([capture.title, ...bits].join('. '))} label="Read these notes aloud" />
      </View>
      {bits.map((text, index) => (
        <Card key={index} tone={index === bit ? 'warm' : 'default'}>
          {index === bit ? <Txt variant="label" color={theme.colors.primary}>Your card came from here</Txt> : null}
          <RichText text={text} />
        </Card>
      ))}
      <Button kind="primary" icon="help-circle-outline" label="Make questions from these notes" onPress={makeQuestions} hint="Opens Make with AI with these notes filled in" />
      <Button icon="create-outline" label="Edit notes" onPress={startEditing} hint="Change these notes, and make words bold, italic or highlighted" />
      {capture.text_file && localFile(capture.text_file) && Platform.OS !== 'web' ? <Button icon="document-outline" label="Open the PDF" onPress={openPdf} hint="The PDF these notes were made from" /> : null}
      <Button kind="dangerGhost" icon="trash-outline" label="Delete notes" onPress={remove} />
    </Screen>
  );
}
