# MemoryPal Privacy Policy

Last updated: October 21, 2026

MemoryPal is made by Kirthik Sai Mouli Parthiban ("we"). This policy explains what MemoryPal
collects, why, and the choices you have. Contact us at memorypal09@gmail.com with any question or
request.

## The short version

- **Unless you connect Google Drive or use an AI feature, nothing leaves your device.** Your
  cards, notes, study plans, settings, photos and recordings are saved on your computer or phone.
- **Sync goes through your own Google Drive, not our servers.** If you connect Google Drive, your
  cards are kept in a hidden MemoryPal folder in your own Google account (see "Syncing with
  Google Drive").
- **AI features are optional and off until you allow them.** They need an account. Only the
  notes or file you choose are sent, and only when you press an AI button (see "AI features").
- **A MemoryPal account is optional.** It is only needed for AI features.
- **We don't sell your data, show ads, or use tracking or analytics tools.**
- **Accounts are for people 13 and older.**
- **You can disconnect Google Drive or delete your account at any time** in the app.

## What is stored on your device

Everything you make in MemoryPal: cards, notes, study plans, review history, settings and any
pictures, recordings or documents you attach. On Windows this is in
`%LOCALAPPDATA%\MemoryPal`, and on a Mac in `~/Library/Application Support/MemoryPal`. It
stays there until you delete it, and uninstalling the desktop app does not remove it. On a
phone or tablet it is kept in the app's own private storage and is removed when you uninstall
the app.

## Syncing with Google Drive

You can connect a Google account under **Settings > Account & sync** to keep your cards in step
across your computer and phone. When you do:

- You sign in on Google's own page or sheet. MemoryPal asks only for permission to use **its own
  hidden app folder** in your Google Drive (Google calls this `drive.appdata`) and to see your
  Google email address, so the app can show which account is connected. MemoryPal **cannot see
  or change any of your other Drive files.**
- MemoryPal saves there: your cards and notes (the text you typed or imported), your review
  history and study progress, your MemoryPal settings, and a random identifier for each of your
  devices. Each device writes one file.
- **Not uploaded:** the pictures, recordings, videos and documents you attach stay only on the
  device where you added them.
- The files go **directly between your device and Google**. They never pass through our servers
  and we cannot read them. Google stores them under its own
  [Privacy Policy](https://policies.google.com/privacy), and they count toward your Google storage.
- On the desktop, the Google sign-in is kept in the system's protected storage (Windows DPAPI or
  the Mac Keychain). On a phone, Google's own sign-in keeps it; MemoryPal keeps only the
  account's id and email address.
- **Disconnect Google Drive** in the app stops syncing and signs MemoryPal out of Google. It
  leaves the files in your Drive. To remove them, open Google Drive on the web, then
  **Settings > Manage apps > MemoryPal > Delete hidden app data**.

**Moving from the MemoryPal cloud.** Earlier versions kept a copy of your cards on our servers
(Supabase) while you were signed in. The first time a signed-in device syncs with Google Drive,
it copies those cards into your Drive and then **deletes them from our servers**. Older app
versions that have not been updated still sync through our servers until you update them.

## If you create a MemoryPal account

A MemoryPal account is only needed for AI features. To create one we ask for:

- **Your email address**, to sign you in and to send one-time codes that confirm the account or
  reset the password.
- **A password.** It is stored only as a secure hash by our hosting provider. We never see it.
- **The month and year you were born**, only to check that you are 13 or older. This check
  happens on your device. **Your birth date is never stored or sent.** We keep only a record
  that the check passed, plus the version and time you accepted these terms.

Your account no longer holds your cards: they sync through Google Drive (above). Our servers
keep only the account itself, your AI consent and a daily count of AI requests.

If you turn on two-step sign-in, a code for your authenticator app is stored with your
account.

Your sign-in on each device is kept in the system's protected storage (Windows DPAPI, the
iOS Keychain or the Android Keystore), never your password.

## AI features

MemoryPal can make study notes and practice questions from your notes, a PDF or a photo. This
is optional:

- It only works when you are signed in and have allowed it on the one-time AI screen. You can
  turn it off again in Settings.
- Only what you choose is sent: the text, or the one file, you picked for that request, anything
  you typed under "How should it look?" or "Questions your teacher has asked", and a list of your
  existing card questions in that set, so the AI doesn't repeat them and can follow their style.
- It goes through our server (Supabase) to **Google's Gemini API**, which writes the notes or
  questions and sends them back. Our server does not keep the text or file; it only counts how
  many AI requests your account made each day, to apply a daily limit.
- **We use Gemini's free tier.** Under Google's terms for unpaid use, Google may keep what is
  sent and use it to improve its products, and people at Google may read it. Depending on where
  you live, Google's stricter paid-service terms may apply instead. **Don't send anything
  private or sensitive** (for example health details, ID numbers or other people's personal
  information). See [Google's Gemini API terms](https://ai.google.dev/gemini-api/terms).
- AI-made cards are labelled "Made with AI, check it." AI can be wrong; check cards before you
  rely on them. You can report a bad result from the card.

## Services we use

| Service | What it does | What it receives |
|---|---|---|
| Supabase (United States, AWS us-east-1) | Hosts MemoryPal accounts and the AI request counter (and, for older app versions only, the old cloud copy of cards) | Your account details, as listed above |
| Google (Drive API and Google sign-in) | Stores your synced cards in your own Drive, if you connect it | Your synced cards, settings and review history, and your Google account's id and email. We don't receive any of it |
| Google (Gmail) | Sends sign-in and reset codes | Your email address |
| Google (Gemini API) | Makes notes and questions when you use an AI feature | The text or file you chose for that request, and your existing card questions. Not your email or password |
| Cloudflare Turnstile | Checks that a person, not a bot, is signing in, creating an account or asking for an emailed code | Technical signals from the check page, such as your IP address and browser details. Not your email, password or cards |
| GitHub Pages | Hosts that check page | Your IP address and browser details, like any website |
| Have I Been Pwned | Checks whether a new password has appeared in a data breach | Only the first 5 characters of a scrambled (SHA-1) form of the password, never the password itself |
| FormSubmit | Delivers feedback you choose to send from the desktop app | Your feedback notes, your system version, text size and theme, and a reply address if you give one |

Feedback is only sent when you press **Send Feedback Now**. It never includes your profile name
or your cards.

Read aloud uses your device's own voice and works offline; the text is not sent to us.

The image-search button on the desktop opens Google in your web browser. That search
happens in your browser, under Google's own privacy policy.

## Why we use your information (legal bases)

- To provide the account and Google Drive sync you asked for (performance of a contract).
- To keep accounts secure: email confirmation, password checks and attempt limits (legitimate
  interests).
- To answer feedback you send us (legitimate interests, or your consent).
- To run AI features you turned on (your consent, which you can withdraw in Settings).

## How long we keep it

Your account is kept until you delete it. **Delete account** in the app removes it (and any old
cloud copy of cards on our servers) straight away. Cards in your Google Drive stay there until you
remove them as described in "Syncing with Google Drive". Feedback emails are kept for as long as they are useful for fixing
problems, then deleted.

## Deleting your account

You can delete your MemoryPal account yourself at any time:

- **Phone or tablet:** Settings, then **Account & sync**, then **Delete account**.
- **Desktop:** Settings, then **Account & sync**, then **Delete account**.

If you can no longer open the app, email memorypal09@gmail.com from the address you signed up with
and ask us to delete your account. We will delete the account within 30 days and tell you when
it is done. Cards on your devices and in your Google Drive are not affected; remove them by
uninstalling the app or deleting its data folder, and in Google Drive under **Settings > Manage
apps > MemoryPal > Delete hidden app data**.

## Your rights

You can:

- **See and export your data.** Export a backup from the app at any time.
- **Correct it.** Edit your cards in the app.
- **Delete it.** Use Delete account in the app, or ask us. Remove the Google Drive copy in Google
  Drive's settings (above).
- **Object or complain.** Contact us. In the EU or UK you can also complain to your data
  protection authority. In California and other US states with privacy laws, you have the
  rights those laws give, and we don't sell or share personal information for advertising.

We will answer requests within 30 days.

## Children

MemoryPal can be used without an account by anyone. Accounts are only for people 13 and
older, and the app checks this before an account is created. If you believe a child under 13
has created an account, contact us at memorypal09@gmail.com and we will delete it.

## Security

Connections to our servers are encrypted (HTTPS). The database only lets each account
read and change its own data, and two-step accounts need the second step. No system is
perfectly secure. If a breach affects your data, we will tell you and the relevant
authorities as the law requires.

## Where your data is processed

Our hosting provider stores MemoryPal accounts in the United States. If that is outside your country, it is
protected by our hosting provider's data processing agreement, which includes the EU standard contractual clauses.

## Changes

If we change this policy, we will update the date above. If the change matters, the app will
ask you to agree again.

## Contact

Kirthik Sai Mouli Parthiban
memorypal09@gmail.com
