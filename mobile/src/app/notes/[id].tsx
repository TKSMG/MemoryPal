/** One saved note: read it, hear it, make questions from it, or delete it. A card's "Where it came from" opens it at its bit. */
import { Href, router, Stack, useLocalSearchParams } from 'expo-router';
import * as Sharing from 'expo-sharing';
import { Image, Platform, View } from 'react-native';

import { AI_NOTE } from '../../core/questions';
import { captureDeck } from '../../core/store';
import { sendNotesToAi } from '../../features/aiHandoff';
import { useStore } from '../../state/AppState';
import { AiTag, Button, Card, EmptyState, Screen, SpeakButton, Txt, useStopSpeechOnLeave } from '../../ui/components';
import { confirm, notify } from '../../ui/feedback';
import { useTheme } from '../../ui/theme';

export default function Notes() {
  const store = useStore();
  const theme = useTheme();
  const params = useLocalSearchParams<{ id: string; bit?: string }>();
  const capture = store.findCapture(String(params.id));
  useStopSpeechOnLeave();

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

  return (
    <Screen narrow>
      <Stack.Screen options={{ title: capture.title }} />
      <Txt variant="muted">{[deck ? `In ${deck}` : 'Not in a set', capture.created_at].filter(Boolean).join(' · ')}</Txt>
      {ai ? <AiTag /> : null}
      {capture.image && localFile(capture.image) ? (
        <Image source={{ uri: capture.image }} resizeMode="contain" style={{ width: '100%', height: 220, borderRadius: 12 }} accessibilityLabel="The photo these notes were made from" />
      ) : null}
      <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        <SpeakButton text={[capture.title, ...bits].join('. ')} label="Read these notes aloud" />
      </View>
      {bits.map((text, index) => (
        <Card key={index} tone={index === bit ? 'warm' : 'default'}>
          {index === bit ? <Txt variant="label" color={theme.colors.primary}>Your card came from here</Txt> : null}
          <Txt variant="body">{text}</Txt>
        </Card>
      ))}
      <Button kind="primary" icon="help-circle-outline" label="Make questions from these notes" onPress={makeQuestions} hint="Opens Make with AI with these notes filled in" />
      {capture.text_file && localFile(capture.text_file) && Platform.OS !== 'web' ? <Button icon="document-outline" label="Open the PDF" onPress={openPdf} hint="The PDF these notes were made from" /> : null}
      <Button kind="dangerGhost" icon="trash-outline" label="Delete notes" onPress={remove} />
    </Screen>
  );
}
