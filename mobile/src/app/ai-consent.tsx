/** The one-time AI screen, opened from Settings when AI is turned on. */
import { router } from 'expo-router';

import { usePrefs } from '../state/AppState';
import { AiConsent } from '../ui/AiConsent';
import { Screen } from '../ui/components';

export default function AiConsentScreen() {
  const [, setPrefs] = usePrefs();
  return (
    <Screen narrow>
      <AiConsent
        onAllow={() => {
          setPrefs({ ai_allowed: true, ai_allowed_at: new Date().toISOString() });
          router.back();
        }}
        onNotNow={() => {
          setPrefs({ ai_allowed: false, ai_allowed_at: '' });
          router.back();
        }}
      />
    </Screen>
  );
}
