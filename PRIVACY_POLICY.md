# MemoryPal Privacy Policy

> **Draft for review.** Written from what the app actually does as of version 0.46.0. Fill in the
> bracketed parts, have it checked by someone qualified in privacy law for the places you
> publish in, then host it at the address in `cloud_config.PRIVACY_URL` and `mobile/app.json`
> (`expo.extra.privacyUrl`). Bump `TERMS_VERSION` in `security.py` / `security.ts` whenever
> this changes in a way people should agree to again.

Last updated: [date]

MemoryPal is made by [your name or company] ("we"). This policy explains what MemoryPal
collects, why, and the choices you have. Contact us at [contact email] with any question or
request.

## The short version

- **Without an account, nothing leaves your device.** Your cards, notes, study plans,
  settings, photos and recordings are saved only on your computer or phone.
- **An account is optional.** It only keeps your cards in step across your devices.
- **We don't sell your data, show ads, or use tracking or analytics tools.**
- **Accounts are for people 13 and older.**
- **You can delete your account at any time** in the app, which removes your cloud copy.

## What is stored on your device

Everything you make in MemoryPal: cards, notes, study plans, review history, settings and any
pictures, recordings or documents you attach. On Windows this is in
`%LOCALAPPDATA%\MemoryPal`, and on a Mac in `~/Library/Application Support/MemoryPal`. It
stays there until you delete it, and uninstalling the desktop app does not remove it. On a
phone or tablet it is kept in the app's own private storage and is removed when you uninstall
the app.

## If you create an account

To create an account we ask for:

- **Your email address**, to sign you in and to send one-time codes that confirm the account or
  reset the password.
- **A password.** It is stored only as a secure hash by our hosting provider. We never see it.
- **The month and year you were born**, only to check that you are 13 or older. This check
  happens on your device. **Your birth date is never stored or sent.** We keep only a record
  that the check passed, plus the version and time you accepted these terms.

While you are signed in, MemoryPal keeps a copy in the cloud of:

- your cards and notes (the text you typed or imported),
- your review history and study progress,
- your MemoryPal settings,
- a random identifier for each of your devices, used to combine review counts.

**Not uploaded:** the pictures, recordings, videos and documents you attach stay only on the
device where you added them.

If you turn on two-step sign-in, a code for your authenticator app is stored with your
account.

Your sign-in on each device is kept in the system's protected storage (Windows DPAPI, the
iOS Keychain or the Android Keystore), never your password.

## Services we use

| Service | What it does | What it receives |
|---|---|---|
| Supabase (United States, AWS us-east-1) | Hosts accounts and the cloud copy | Your account and cloud copy, as listed above |
| Google (Gmail) | Sends sign-in and reset codes | Your email address |
| Have I Been Pwned | Checks whether a new password has appeared in a data breach | Only the first 5 characters of a scrambled (SHA-1) form of the password, never the password itself |
| FormSubmit | Delivers feedback you choose to send from the desktop app | Your feedback notes, your system version, text size and theme, and a reply address if you give one |

Feedback is only sent when you press **Send Feedback Now**. It never includes your profile name
or your cards.

Read aloud uses your device's own voice and works offline; the text is not sent to us.

The image-search button on the desktop opens Google in your web browser. That search
happens in your browser, under Google's own privacy policy.

## Why we use your information (legal bases)

- To provide the account and sync you asked for (performance of a contract).
- To keep accounts secure: email confirmation, password checks and attempt limits (legitimate
  interests).
- To answer feedback you send us (legitimate interests, or your consent).

## How long we keep it

Your cloud copy is kept while you have an account. **Delete account** in the app removes the
account and its cloud copy straight away. [Our hosting provider's backups, if enabled, are
deleted within [7] days.] Feedback emails are kept for as long as they are useful for fixing
problems, then deleted.

## Deleting your account

You can delete your account and its cloud copy yourself at any time:

- **Phone or tablet:** Settings, then **Account & sync**, then **Delete account**.
- **Desktop:** Settings, then **Account & sync**, then **Delete account**.

If you can no longer open the app, email [contact email] from the address you signed up with
and ask us to delete your account. We will delete the account and its cloud copy within 30
days and tell you when it is done. Cards saved only on your devices are not affected; remove
them by uninstalling the app or deleting its data folder.

## Your rights

You can:

- **See and export your data.** Export a backup from the app at any time.
- **Correct it.** Edit your cards in the app.
- **Delete it.** Use Delete account in the app, or ask us.
- **Object or complain.** Contact us. In the EU or UK you can also complain to your data
  protection authority. In California and other US states with privacy laws, you have the
  rights those laws give, and we don't sell or share personal information for advertising.

We will answer requests within 30 days.

## Children

MemoryPal can be used without an account by anyone. Accounts are only for people 13 and
older, and the app checks this before an account is created. If you believe a child under 13
has created an account, contact us at [contact email] and we will delete it.

## Security

Connections to our servers are encrypted (HTTPS). The database only lets each account
read and change its own data, and two-step accounts need the second step. No system is
perfectly secure. If a breach affects your data, we will tell you and the relevant
authorities as the law requires.

## Where your data is processed

Our hosting provider stores the cloud copy in the United States. If that is outside your country, it is
protected by [the provider's standard contractual clauses / data processing agreement].

## Changes

If we change this policy, we will update the date above. If the change matters, the app will
ask you to agree again.

## Contact

[Your name or company]
[Postal address, if required where you publish]
[contact email]
