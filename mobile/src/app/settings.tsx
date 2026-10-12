/** Settings: comfort and accessibility, appearance, daily goal, and backups. */
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { Linking } from 'react-native';

import { legalLinks } from '../cloud/client';
import { persona } from '../core/personas';
import { TextSize } from '../core/store';
import { exportBackup, pickBackup } from '../state/backup';
import { ThemeChoice, usePrefs, useStore, useSync } from '../state/AppState';
import { Button, Card, Pills, Row, Screen, SectionTitle, ToggleRow, Txt } from '../ui/components';
import { confirm, notify, speak } from '../ui/feedback';
import { useTheme } from '../ui/theme';

export default function Settings() {
  const store = useStore();
  const theme = useTheme();
  const [prefs, setPrefs] = usePrefs();
  const sync = useSync();
  const legal = legalLinks();
  const a = store.accessibility;

  const doExport = async () => {
    try {
      await exportBackup(store.exportBackup());
    } catch (error) {
      notify('Backup not saved', String((error as Error)?.message ?? error));
    }
  };

  const doImport = async () => {
    let text: string | null;
    try {
      text = await pickBackup();
    } catch (error) {
      return notify("Couldn't open the file", String((error as Error)?.message ?? error));
    }
    if (text === null) return;
    let raw: unknown;
    try {
      raw = JSON.parse(text);
    } catch {
      raw = null;
    }
    if (!raw || typeof raw !== 'object' || Array.isArray(raw) || !Array.isArray((raw as { cards?: unknown }).cards)) {
      return notify("That isn't a MemoryPal backup", 'Choose a .json file saved from MemoryPal on a phone or computer.');
    }
    const count = ((raw as { cards: unknown[] }).cards).length;
    const ok = await confirm(
      'Replace your cards with this backup?',
      `The backup has ${count} card${count === 1 ? '' : 's'}. Everything on this phone is replaced. Tip: save a backup of this phone first if you might want it back.`,
      'Replace',
      true,
    );
    if (ok) {
      sync.account.startOver();
      store.importBackup(raw as Record<string, unknown>);
      notify('Backup loaded', `${store.cards.length} cards are ready.`);
    }
  };

  const doReset = async () => {
    if (await confirm('Start over?', 'This deletes all cards and progress on this phone and brings back the welcome screen. It cannot be undone.', 'Delete everything', true)) {
      sync.account.startOver();
      store.reset();
      router.replace('/welcome');
    }
  };

  return (
    <Screen>
      <SectionTitle>Account & sync</SectionTitle>
      <Card onPress={() => router.push('/account')} accessibilityLabel="Account and sync" accessibilityHint="Sign in to keep your cards on all your devices">
        <Txt variant="h3">{sync.account.signedIn ? sync.account.email : 'Use MemoryPal on all your devices'}</Txt>
        <Txt variant="muted">
          {!sync.configured
            ? "Sync isn't set up in this copy yet."
            : sync.account.signedIn
              ? sync.syncing ? 'Syncing…' : sync.error || (sync.account.state.last_synced ? `Last synced ${sync.account.state.last_synced}` : 'Not synced yet')
              : 'Sign in or create an account to keep your cards, reviews and settings in step with your computer.'}
        </Txt>
      </Card>

      <SectionTitle>Comfort</SectionTitle>
      <Card>
        <Txt variant="h3">Text size</Txt>
        <Pills<TextSize> label="Text size" value={a.text_size} onChange={(value) => store.setAccessibility({ text_size: value })} options={[{ value: 'Comfort', label: 'Standard' }, { value: 'Large', label: 'Large' }, { value: 'Extra Large', label: 'Extra large' }]} />
        <Txt variant="small">Your phone’s own text-size setting is respected too.</Txt>
        <ToggleRow label="Read questions aloud" description="Uses the phone's voice, offline." value={a.read_aloud} onChange={(value) => { store.setAccessibility({ read_aloud: value }); if (value) speak('Reading aloud is on.', a.more_time); }} />
        <ToggleRow label="More time" description="Slower voice and longer puzzle timers." value={a.more_time} onChange={(value) => store.setAccessibility({ more_time: value })} />
        <ToggleRow label="Simpler wording" description="Shorter, plainer instructions and results." value={a.simple_language} onChange={(value) => store.setAccessibility({ simple_language: value })} />
        <ToggleRow label="Higher contrast" description="Stronger text and borders." value={a.high_contrast} onChange={(value) => store.setAccessibility({ high_contrast: value })} />
        <ToggleRow label="Reduce motion" description="No sliding screen transitions." value={a.reduce_motion} onChange={(value) => store.setAccessibility({ reduce_motion: value })} />
        <ToggleRow label="Gentle vibrations" description="A light tap when you answer." value={prefs.haptics} onChange={(value) => setPrefs({ haptics: value })} />
      </Card>

      <SectionTitle>Appearance</SectionTitle>
      <Card>
        <Pills<ThemeChoice> label="Appearance" value={prefs.theme} onChange={(value) => setPrefs({ theme: value })} options={[{ value: 'system', label: 'Match phone' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }]} />
      </Card>

      <SectionTitle>Daily goal</SectionTitle>
      <Card>
        <Txt variant="muted">How many reviews make a completed day.</Txt>
        <Row style={{ justifyContent: 'space-between' }}>
          <Button label="−" onPress={() => store.setDailyGoal(store.dailyGoal - 5)} hint="Five fewer" style={{ width: 64 }} />
          <Txt variant="big" accessibilityRole="text">{String(store.dailyGoal)}</Txt>
          <Button label="+" onPress={() => store.setDailyGoal(store.dailyGoal + 5)} hint="Five more" style={{ width: 64 }} />
        </Row>
      </Card>

      <SectionTitle>Who’s using MemoryPal</SectionTitle>
      <Card>
        <Txt variant="body">{persona(store.onboarding.persona).title}</Txt>
        <Button label="Choose again" icon="people-outline" onPress={() => router.push('/welcome')} hint="Changes the study modes and comfort defaults." />
      </Card>

      <SectionTitle>Your data</SectionTitle>
      <Card>
        <Txt variant="muted">{theme.plain('Cards stay on this phone. Backups use the same file as the MemoryPal desktop app, so you can move cards between them.', 'Your cards stay on this phone. A backup file keeps a copy safe.')}</Txt>
        <Button kind="primary" label="Save a backup" icon="share-outline" onPress={doExport} />
        <Button label="Load a backup" icon="folder-open-outline" onPress={doImport} />
      </Card>

      {/* Kept apart from everyday actions so it is never pressed by mistake. */}
      {!a.caregiver_mode ? (
        <>
          <SectionTitle>Start over</SectionTitle>
          <Card>
            <Txt variant="muted">Deletes every card and all progress on this phone. Save a backup first if you might want them back.</Txt>
            <Button kind="danger" label="Delete everything and start over" icon="trash-outline" onPress={doReset} />
          </Card>
        </>
      ) : null}

      {legal.privacy || legal.terms ? (
        <Row style={{ justifyContent: 'center', flexWrap: 'wrap' }}>
          {legal.privacy ? <Button kind="ghost" compact label="Privacy Policy" onPress={() => Linking.openURL(legal.privacy).catch(() => undefined)} /> : null}
          {legal.terms ? <Button kind="ghost" compact label="Terms of Use" onPress={() => Linking.openURL(legal.terms).catch(() => undefined)} /> : null}
        </Row>
      ) : null}
      <Txt variant="small" center>{`MemoryPal ${Constants.expoConfig?.version ?? ''} · ${store.cards.length} cards`}</Txt>
    </Screen>
  );
}
