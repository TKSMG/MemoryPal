/**
 * Account & sync: sign in, create an account (confirmed with a code from the
 * email), reset a forgotten password with a code, two-step sign-in with an
 * authenticator app, and sync status. Mirrors the desktop's account dialogs.
 */
import * as Clipboard from 'expo-clipboard';
import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, Linking, TextInput, View } from 'react-native';

import { checkPassword, CloudError, consentRecord, legalLinks, looksLikeEmail, needsSecondStep, Session } from '../cloud/client';
import { useCaptcha } from '../cloud/captcha';
import { leakedMessage, pwnedCount } from '../cloud/pwned';
import { readSecret, writeSecret } from '../cloud/secrets';
import { accountAgeCheck, AGE_RETRY_SECONDS, AttemptLimiter, MIN_PASSWORD, passwordProblems, passwordStrength, STRENGTH_LABELS, UNDER_AGE_MESSAGE, waitMessage } from '../core/security';
import { useStore, useSync } from '../state/AppState';
import { Button, Card, Field, Pills, ProgressBar, Row, Screen, ToggleRow, Txt } from '../ui/components';
import { confirm, notify } from '../ui/feedback';
import { useTheme } from '../ui/theme';

// Remembers a refused age check on this device for a day (see security.ts).
const AGE_GATE_KEY = 'memorypal.ageRefusedUntil';

type Mode = 'signin' | 'create' | 'code' | 'reset' | 'reset-code' | 'second-step';

interface Pending {
  session: Session;
  newPassword?: string;
}

interface Setup {
  factorId: string;
  secret: string;
  uri: string;
}

// One limiter for the whole app run, so leaving and reopening the screen doesn't reset it.
const limiter = new AttemptLimiter();

function guarded<T>(key: string, work: () => Promise<T>, counts: (error: CloudError) => boolean = () => true): Promise<T> {
  const wait = limiter.waitSeconds(key);
  if (wait) throw new CloudError(waitMessage(wait), 'local_rate_limit');
  return work().then(
    (result) => {
      limiter.succeeded(key);
      return result;
    },
    (error) => {
      if (error instanceof CloudError && counts(error)) limiter.failed(key);
      throw error;
    },
  );
}

async function checkNotLeaked(password: string) {
  const seen = await pwnedCount(password);
  if (seen) throw new CloudError(leakedMessage(seen), 'pwned_password');
}

/** One line on where sync stands. */
function syncStatus(syncing: boolean, error: string, auto: boolean, last: string): string {
  if (syncing) return 'Syncing…';
  if (error) return error;
  const when = last ? ` Last synced ${last}.` : ' Not synced yet.';
  return auto ? `Syncs automatically.${when}` : `Automatic sync is off.${when}`;
}

export default function Account() {
  return <AccountScreen />;
}

/**
 * The account screen. With `intro` it is the first page a new install shows:
 * sign in or create an account, or go on without one, then the setup questions.
 */
export function AccountScreen({ intro = false }: { intro?: boolean }) {
  const sync = useSync();
  const store = useStore();
  const theme = useTheme();
  const c = theme.colors;
  const account = sync.account;
  const client = account.client;
  // Signing in, creating an account and emailing a code pass a CAPTCHA first.
  const captcha = useCaptcha();
  useEffect(() => {
    client.setCaptcha(captcha.request);
    return () => client.setCaptcha(undefined);
  }, [client, captcha.request]);
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState(account.email);
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [pending, setPending] = useState<Pending | null>(null);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [birthMonth, setBirthMonth] = useState('');
  const [birthYear, setBirthYear] = useState('');
  const [agreed, setAgreed] = useState(false);
  // The keyboard's return key walks through the form, and the last field submits it.
  const yearRef = useRef<TextInput>(null);
  const emailRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);
  const againRef = useRef<TextInput>(null);
  const links = legalLinks();
  const onboarded = store.onboarding.done;

  // On the first-launch page, signing in moves straight on to the setup
  // questions (or to Today when the account already brought them along).
  useEffect(() => {
    if (intro && account.signedIn && !sync.syncing) router.replace(onboarded ? '/' : '/welcome');
  }, [intro, account.signedIn, sync.syncing, onboarded]);

  const continueWithout = () => {
    sync.markPrompted();
    router.replace(onboarded ? '/' : '/welcome');
  };

  const run = async (work: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await work();
    } catch (failure) {
      setError(failure instanceof CloudError ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  const go = (next: Mode, message = '') => {
    setMode(next);
    setError('');
    setInfo(message);
    setPassword('');
    setAgain('');
    setCode('');
  };

  const requireEmail = () => {
    if (!looksLikeEmail(email)) throw new CloudError("That doesn't look like an email address.");
  };

  /** Finish signing in, or ask for the authenticator code first. */
  const proceed = async (session: Session, newPassword?: string) => {
    if (needsSecondStep(session)) {
      setPending({ session, newPassword });
      go('second-step');
      return;
    }
    if (newPassword) await client.setPassword(session, newPassword);
    await sync.signedIn(session);
  };

  const signIn = () => run(async () => {
    requireEmail();
    try {
      const session = await guarded(email, () => client.signIn(email, password), (failure) => ['invalid_credentials', 'invalid_grant'].includes(failure.code));
      await proceed(session);
    } catch (failure) {
      if (failure instanceof CloudError && failure.code === 'email_not_confirmed') {
        await client.resendConfirmation(email);
        go('code', `We sent a new code to ${email.trim()}.`);
        return;
      }
      throw failure;
    }
  });

  const create = () => run(async () => {
    // The age check runs on the device before anything is sent, and the birth
    // month and year are never stored or uploaded.
    if (Date.now() < Number((await readSecret(AGE_GATE_KEY)) ?? 0)) throw new CloudError(UNDER_AGE_MESSAGE, 'under_age');
    const today = new Date();
    const [problem, underAge] = accountAgeCheck(birthMonth, birthYear, today.getFullYear(), today.getMonth() + 1);
    if (underAge) await writeSecret(AGE_GATE_KEY, String(Date.now() + AGE_RETRY_SECONDS * 1000));
    if (problem) throw new CloudError(problem, underAge ? 'under_age' : 'age_format');
    requireEmail();
    if (password !== again) throw new CloudError("The two passwords don't match.");
    if (!agreed) throw new CloudError('To create an account, turn on the switch to agree to the Terms of Use and Privacy Policy.');
    checkPassword(password, email);
    await checkNotLeaked(password);
    const session = await client.signUp(email, password, consentRecord());
    if (session) await sync.signedIn(session);
    else go('code', `We sent a code to ${email.trim()}. It can take a minute; check the spam folder too.`);
  });

  const confirmCode = () => run(async () => {
    await sync.signedIn(await guarded(`${email}#confirm`, () => client.verifyCode(email, code, 'signup')));
  });

  const sendReset = () => run(async () => {
    requireEmail();
    await client.requestPasswordReset(email);
    go('reset-code', `If ${email.trim()} has a MemoryPal account, a code is on its way there.`);
  });

  const finishReset = () => run(async () => {
    if (password !== again) throw new CloudError("The two passwords don't match.");
    checkPassword(password, email);
    await checkNotLeaked(password);
    const session = await guarded(`${email}#reset`, () => client.verifyCode(email, code, 'recovery'));
    // Two-step accounts confirm the authenticator before the password changes.
    await proceed(session, password);
  });

  const secondStep = () => run(async () => {
    if (!pending) return;
    const { session, newPassword } = pending;
    const full = await guarded(`${session.email}#authenticator`, () => client.verifyAuthenticator(session, session.factors[0].id, code));
    if (newPassword) await client.setPassword(full, newPassword);
    setPending(null);
    await sync.signedIn(full);
  });

  const manageTwoStep = () => run(async () => {
    const session = await account.activeSession();
    const factors = await client.factors(session);
    if (!factors.length) {
      setSetup(await client.enrollAuthenticator(session));
      setCode('');
      return;
    }
    if (await confirm('Turn off two-step sign-in?', 'Signing in will need only your password again. Your account is safer with two-step sign-in on.', 'Turn off', true)) {
      await client.removeAuthenticator(session, factors[0].id);
      notify('Two-step sign-in is off', 'Signing in now needs only your password.');
    }
  });

  const turnOnTwoStep = () => run(async () => {
    if (!setup) return;
    const full = await client.verifyAuthenticator(await account.activeSession(), setup.factorId, code);
    setSetup(null);
    setCode('');
    await sync.signedIn(full);
    notify('Two-step sign-in is on', "You'll need your authenticator code when you sign in on a new device.");
  });

  const signOut = async () => {
    if (await confirm('Sign out?', 'Your cards stay on this phone; they just stop syncing until you sign in again.', 'Sign out')) {
      await sync.signOut();
    }
  };

  const deleteAccount = async () => {
    if (!(await confirm('Delete your account?', 'This permanently deletes your MemoryPal account and the cloud copy of your cards on every device. The cards on this phone stay here. This cannot be undone.', 'Delete account', true))) return;
    run(async () => {
      await sync.deleteAccount();
      notify('Account deleted', 'Your account and its cloud copy were deleted.');
    });
  };

  const errorBox = error ? (
    <View accessibilityLiveRegion="assertive" style={{ backgroundColor: c.again[0], borderRadius: 12, padding: 12 }}>
      <Txt variant="body" color={c.again[1]}>{error}</Txt>
    </View>
  ) : null;

  if (!sync.configured) {
    return (
      <Screen narrow>
        <Card>
          <Txt variant="h3">Sync isn’t set up in this copy of MemoryPal yet</Txt>
          <Txt variant="muted">Your cards are safe on this phone. Use Settings → Save a backup to move them to another device for now.</Txt>
        </Card>
      </Screen>
    );
  }

  if (account.signedIn && setup) {
    const grouped = setup.secret.match(/.{1,4}/g)?.join(' ') ?? setup.secret;
    return (
      <Screen narrow>
        <Card>
          <Txt variant="h2">Set up two-step sign-in</Txt>
          <Txt variant="body">1. Open an authenticator app (Microsoft Authenticator, Google Authenticator, 1Password…).</Txt>
          <Txt variant="body">2. Tap “Open in authenticator app”, or add an account there and choose “enter a setup key” (time-based).</Txt>
          <Txt variant="body">3. Type the 6-digit code the app shows.</Txt>
          <View style={{ backgroundColor: c.alt, borderRadius: 12, padding: 14, gap: 6 }}>
            <Txt variant="label">Setup key</Txt>
            <Txt variant="h3">{grouped}</Txt>
          </View>
          <Row wrap>
            {/* Only ever an authenticator link: the server's answer must not open a web page or another app. */}
            {/^otpauth:\/\//i.test(setup.uri) ? <Button compact icon="open-outline" label="Open in authenticator app" onPress={() => Linking.openURL(setup.uri).catch(() => setError('No authenticator app opened. Type the setup key into it instead.'))} /> : null}
            <Button compact icon="copy-outline" label="Copy key" onPress={async () => { await Clipboard.setStringAsync(setup.secret); setInfo('Key copied.'); }} />
          </Row>
          {info ? <Txt variant="body" color={c.link}>{info}</Txt> : null}
          <Field label="Code from the app" value={code} onChangeText={setCode} keyboardType="number-pad" autoComplete="one-time-code" textContentType="oneTimeCode" maxLength={8} returnKeyType="go" onSubmitEditing={turnOnTwoStep} />
          {errorBox}
          <Button kind="primary" label={busy ? 'Checking…' : 'Turn on'} disabled={busy} onPress={turnOnTwoStep} />
        </Card>
        <Button kind="ghost" label="Cancel" onPress={() => { setSetup(null); setError(''); setInfo(''); }} />
      </Screen>
    );
  }

  if (account.signedIn) {
    const last = account.state.last_synced;
    const twoStepOn = Boolean(account.session?.factors.length);
    return (
      <Screen narrow>
        <Card tone="alt">
          <Txt variant="label">Signed in</Txt>
          <Txt variant="h2">{account.email}</Txt>
          <View accessibilityLiveRegion="polite">
            <Txt variant="muted">{syncStatus(sync.syncing, sync.error, sync.auto, last)}</Txt>
          </View>
          <Button label={sync.syncing ? 'Syncing…' : 'Sync now'} icon="sync" disabled={sync.syncing} onPress={async () => {
            const problem = await sync.syncNow();
            if (problem) notify("Couldn't sync", problem);
          }} />
        </Card>
        <Card>
          <ToggleRow
            label="Sync automatically"
            description="A few seconds after each change, when you open MemoryPal, and every few minutes. Turn off to sync only when you tap Sync now."
            value={sync.auto}
            onChange={(value) => sync.setAuto(value)}
          />
        </Card>
        <Card>
          <Txt variant="body">Sign in with this account on your computer and other devices: cards, reviews, streaks and settings stay in step automatically.</Txt>
          <Txt variant="small">Photos, recordings and attached files stay on the device that has them.</Txt>
        </Card>
        <Card>
          <Txt variant="h3">Two-step sign-in</Txt>
          <Txt variant="muted">{twoStepOn ? 'On: signing in on a new device needs your password and a code from your authenticator app.' : 'Add a code from an authenticator app to your password, so a stolen password alone is not enough.'}</Txt>
          <Button label={busy ? 'Checking…' : twoStepOn ? 'Turn off two-step sign-in' : 'Set up two-step sign-in'} icon="shield-checkmark-outline" disabled={busy} onPress={manageTwoStep} />
        </Card>
        <Button label="Sign out" icon="log-out-outline" onPress={signOut} />
        <Button kind="ghost" label="Delete account" onPress={deleteAccount} hint="Deletes the account and its cloud copy. Cards on this phone stay." />
        {errorBox}
      </Screen>
    );
  }

  const title = { signin: 'Sign in', create: 'Create your account', code: 'Check your email', reset: 'Reset your password', 'reset-code': 'Choose a new password', 'second-step': 'Two-step sign-in' }[mode];
  const choosing = mode === 'create' || mode === 'reset-code';
  const score = passwordStrength(password, email);
  const problems = passwordProblems(password, email);
  const meterColor = [c.again[1], c.again[1], c.review[1], c.good[1], c.good[1]][score];

  const submit = { signin: signIn, create, code: confirmCode, reset: sendReset, 'reset-code': finishReset, 'second-step': secondStep }[mode];
  // Return key: `next` moves on to the following field; `last` submits the form.
  const next = { returnKeyType: 'next' as const, submitBehavior: 'submit' as const };
  const focusYear = () => yearRef.current?.focus();
  const focusEmail = () => emailRef.current?.focus();
  const focusPassword = () => passwordRef.current?.focus();
  const focusAgain = () => againRef.current?.focus();
  const last = { returnKeyType: 'go' as const, onSubmitEditing: submit };

  return (
    <Screen narrow>
      {captcha.sheet}
      {intro ? (
        <View style={{ alignItems: 'center', gap: 8, marginTop: 24, marginBottom: 8 }}>
          <Image source={require('../../assets/icon.png')} style={{ width: 72, height: 72, borderRadius: 18 }} accessibilityIgnoresInvertColors accessible={false} />
          <Txt variant="title" center>MemoryPal</Txt>
          <Txt variant="muted" center>Sign in to keep your cards, progress and settings on all your devices.</Txt>
        </View>
      ) : null}
      {mode === 'signin' || mode === 'create' ? (
        <Pills<Mode> label="Account" value={mode} onChange={(value) => go(value)} options={[{ value: 'signin', label: 'Sign in' }, { value: 'create', label: 'Create account' }]} />
      ) : null}
      <Card>
        {/* With the Sign in / Create account pills just above, a heading repeating the same words adds nothing. */}
        {mode === 'signin' || mode === 'create' ? null : <Txt variant="h2">{title}</Txt>}
        {mode === 'signin' ? <Txt variant="muted">Use the same account on every device to keep your cards in step.</Txt> : null}
        {mode === 'create' ? <Txt variant="muted">Use an email you can check: we’ll email you a code to confirm it. You don’t need an account to use MemoryPal; it only keeps your cards in step across devices.</Txt> : null}
        {mode === 'second-step' ? <Txt variant="muted">Open your authenticator app and type the 6-digit code it shows for MemoryPal.</Txt> : null}
        {info ? <Txt variant="body" color={c.link}>{info}</Txt> : null}

        {mode === 'create' ? (
          <>
            <Field label="Month you were born (1-12)" value={birthMonth} onChangeText={setBirthMonth} keyboardType="number-pad" maxLength={2} {...next} onSubmitEditing={focusYear} />
            <Field ref={yearRef} label="Year you were born" value={birthYear} onChangeText={setBirthYear} keyboardType="number-pad" maxLength={4} {...next} onSubmitEditing={focusEmail} />
          </>
        ) : null}

        {mode === 'signin' || mode === 'create' || mode === 'reset' ? (
          <Field ref={emailRef} label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" autoComplete="email" keyboardType="email-address" textContentType="emailAddress" {...(mode === 'reset' ? last : { ...next, onSubmitEditing: focusPassword })} />
        ) : null}
        {mode === 'code' || mode === 'reset-code' || mode === 'second-step' ? (
          <Field label={mode === 'second-step' ? 'Authenticator code' : 'Code from the email'} value={code} onChangeText={setCode} keyboardType="number-pad" autoComplete="one-time-code" textContentType="oneTimeCode" maxLength={10} {...(mode === 'reset-code' ? { ...next, onSubmitEditing: focusPassword } : last)} />
        ) : null}
        {mode === 'signin' || choosing ? (
          <Field ref={passwordRef} {...(mode === 'signin' ? last : { ...next, onSubmitEditing: focusAgain })} label={mode === 'reset-code' ? 'New password' : 'Password'} value={password} onChangeText={setPassword} secureTextEntry autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} textContentType={mode === 'signin' ? 'password' : 'newPassword'} />
        ) : null}
        {choosing ? (
          <View accessibilityLiveRegion="polite" style={{ gap: 6 }}>
            {password ? (
              <>
                <ProgressBar value={score / 4} color={meterColor} height={8} label={`Password strength: ${STRENGTH_LABELS[score]}`} />
                <Txt variant="small" color={meterColor}>{`Strength: ${STRENGTH_LABELS[score]}.${problems.length ? ` ${problems[0]}` : ''}`}</Txt>
              </>
            ) : (
              <Txt variant="small">{`At least ${MIN_PASSWORD} characters, with letters and at least one number. Three or four unrelated words and a number make a strong, memorable password.`}</Txt>
            )}
          </View>
        ) : null}
        {choosing ? (
          <Field
            ref={againRef}
            label="Password again"
            value={again}
            onChangeText={setAgain}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            // Creating an account still needs the terms ticked below, so the
            // return key just closes the keyboard there.
            {...(mode === 'create' ? { returnKeyType: 'done' as const } : last)}
          />
        ) : null}
        {mode === 'create' ? (
          <>
            <ToggleRow label="I agree to the Terms of Use and Privacy Policy" value={agreed} onChange={setAgreed} />
            <Row wrap>
              {links.terms ? <Button kind="ghost" compact label="Read the Terms of Use" onPress={() => Linking.openURL(links.terms).catch(() => undefined)} /> : null}
              {links.privacy ? <Button kind="ghost" compact label="Read the Privacy Policy" onPress={() => Linking.openURL(links.privacy).catch(() => undefined)} /> : null}
            </Row>
          </>
        ) : null}

        {errorBox}

        {mode === 'signin' ? <Button kind="primary" label={busy ? 'Signing in…' : 'Sign in'} disabled={busy} onPress={signIn} /> : null}
        {mode === 'create' ? <Button kind="primary" label={busy ? 'Creating…' : 'Create account'} disabled={busy} onPress={create} /> : null}
        {mode === 'code' ? <Button kind="primary" label={busy ? 'Checking…' : 'Confirm'} disabled={busy} onPress={confirmCode} /> : null}
        {mode === 'reset' ? <Button kind="primary" label={busy ? 'Sending…' : 'Send code'} disabled={busy} onPress={sendReset} /> : null}
        {mode === 'reset-code' ? <Button kind="primary" label={busy ? 'Saving…' : 'Save new password'} disabled={busy} onPress={finishReset} /> : null}
        {mode === 'second-step' ? <Button kind="primary" label={busy ? 'Checking…' : 'Continue'} disabled={busy} onPress={secondStep} /> : null}
      </Card>
      <Row wrap style={{ justifyContent: 'center' }}>
        {mode === 'signin' ? <Button kind="ghost" compact label="Forgot your password?" onPress={() => go('reset')} /> : null}
        {mode === 'code' ? <Button kind="ghost" compact label="Send a new code" onPress={() => run(async () => { await client.resendConfirmation(email); setInfo('A new code is on its way.'); })} /> : null}
        {mode !== 'signin' && mode !== 'create' ? <Button kind="ghost" compact label="Back to sign in" onPress={() => { setPending(null); go('signin'); }} /> : null}
      </Row>
      {intro ? (
        <Button kind="ghost" label="Continue without an account" hint="Your cards stay on this phone. You can sign in later from Settings." onPress={continueWithout} />
      ) : (
        <Button kind="ghost" label="Not now" onPress={() => router.back()} />
      )}
    </Screen>
  );
}
