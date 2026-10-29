/**
 * The one-time AI screen (App Store guideline 5.1.2(i)): what is sent, to
 * whom, and what Google may do with it, before anything is sent. Matches the
 * "AI features" section of PRIVACY_POLICY.md.
 */
import { Linking, View } from 'react-native';

import { legalLinks } from '../cloud/client';
import { AI_DAILY_LIMIT } from '../features/aiHelpers';
import { Button, Icon, ListGroup, ListRow, Txt } from './components';
import { useTheme } from './theme';

export const GEMINI_TERMS_URL = 'https://ai.google.dev/gemini-api/terms';

export function AiConsent({ onAllow, onNotNow }: { onAllow: () => void; onNotNow: () => void }) {
  const theme = useTheme();
  const privacy = legalLinks().privacy;
  return (
    <View style={{ gap: 16 }}>
      <View style={{ alignItems: 'center', gap: 8, paddingTop: 8 }}>
        <Icon name="sparkles-outline" size={40} color={theme.colors.primary} />
        <Txt variant="h2" center accessibilityRole="header">Before you use AI</Txt>
        <Txt variant="muted" center>AI can make study notes and practice questions from your notes, a PDF or a photo, and talk through your cards with you as a live tutor. It’s optional.</Txt>
      </View>

      <ListGroup>
        <ListRow icon="document-text-outline" title="What is sent" detail="Only what you choose for each request: the text, or the one PDF or photo, plus your existing card questions so the AI doesn’t repeat them. For the live tutor: that session’s cards and your voice while you talk. Nothing is sent until you press an AI button." />
        <ListRow icon="cloud-outline" title="Who gets it" detail="It goes through MemoryPal’s server to Google’s Gemini API, which writes the notes or questions. Live tutor voice goes straight from your phone to Google. Our server doesn’t keep any of it; it only counts your requests for the daily limit." />
        <ListRow icon="eye-outline" title="What Google may do" detail="We use Gemini’s free tier. Google may keep what is sent, including your voice, use it to improve its products, and people at Google may read or listen to it." tint={theme.colors.warmText} />
        <ListRow icon="hand-left-outline" title="Don’t send private things" detail="No health details, ID numbers, passwords or other people’s personal information." tint={theme.colors.again[1]} />
        <ListRow icon="checkmark-done-outline" title="Check what it makes" detail={`AI can be wrong. AI cards are labelled “Made with AI, check it”, and you can report a bad result. You need a MemoryPal account, and each account gets up to ${AI_DAILY_LIMIT} AI requests a day.`} />
      </ListGroup>

      <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center' }}>
        {privacy ? <Button kind="ghost" compact label="Privacy Policy" onPress={() => Linking.openURL(privacy).catch(() => undefined)} /> : null}
        <Button kind="ghost" compact label="Google’s Gemini API terms" onPress={() => Linking.openURL(GEMINI_TERMS_URL).catch(() => undefined)} />
      </View>

      <Button kind="primary" label="Allow" icon="checkmark" onPress={onAllow} hint="Turns on AI features. You can turn them off in Settings." />
      <Button label="Not now" onPress={onNotNow} hint="Nothing is sent. AI stays off." />
      <Txt variant="small" center>You can turn AI off again at any time in Settings.</Txt>
    </View>
  );
}
