# Setting up MemoryPal accounts (Supabase)

MemoryPal's accounts and sync run on [Supabase](https://supabase.com): email + password sign-in,
6-digit email codes, optional two-step sign-in with an authenticator app, and one table of
sync records protected by Row Level Security. Until a project is configured, both apps work
exactly as before, fully offline, and the account screens say sync isn't set up.

**From 0.51.0, cards sync through each person's own Google Drive** and Supabase keeps accounts
only (sign-in, two-step, consent, the AI allowance). See [GOOGLE_DRIVE_SYNC.md](GOOGLE_DRIVE_SYNC.md).
The `sync_records` table below is still created because builds without the Google clients, and
apps older than 0.51.0, sync through it; a later release will lock and remove it.

You don't need a domain to build or test this. You will want one before a public launch (see
"Before launch").

## 1. Create the project

1. Create a free project at supabase.com. Pick the region closest to your users.
2. Open **SQL Editor**, paste all of [`supabase/schema.sql`](../supabase/schema.sql) and run it.
   It creates the `sync_records` table, its Row Level Security policies (people can read and
   write only their own rows, and two-step accounts need the second step), a storage
   allowance per person (20,000 records or 25 MB, far above real use), and the
   `delete_my_account()` function used by "Delete account". The script is safe to run again
   after it changes; rerun it whenever `schema.sql` is updated. An existing project can
   instead run just the newer changes in [`supabase/migrations/`](../supabase/migrations).
3. Open **Project Settings → API keys** and copy the **Project URL** and the **publishable
   key** (`sb_publishable_...`). Never put the secret / service-role key in either app.

## 2. Point the apps at it

- **Desktop:** fill in `latest_app/memorypal/cloud_config.py`:
  ```python
  SUPABASE_URL = "https://<project>.supabase.co"
  SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
  ```
  For a quick test without editing the file, set `MEMORYPAL_SUPABASE_URL` and
  `MEMORYPAL_SUPABASE_KEY` in the environment instead.
- **Phone:** fill in `mobile/app.json` → `expo.extra.supabaseUrl` and
  `expo.extra.supabasePublishableKey`, then restart `npx expo start`.

The publishable key is meant to ship inside apps. Row Level Security is what keeps each
person's data private, so the key alone gives nobody access to anyone's cards.

## 3. Authentication settings

**Email templates** (Authentication → Emails → Templates). Both apps ask people to type a
6-digit code rather than click a link, so the emails must show the code:

- **Confirm signup:** include `{{ .Token }}`, for example
  `Your MemoryPal code is {{ .Token }}. It expires in one hour.`
- **Reset password:** include `{{ .Token }}` the same way.

**Password policy** (Authentication → Sign In / Providers → Email, or Attack Protection):

- Minimum length **10** (the apps check 10 too).
- Required characters: letters and digits (the apps ask for both too).
- **Leaked password protection** (Pro plan) checks new passwords against Have I Been Pwned on the
  server. The apps already run the same check on the device, but only the server-side check
  can't be bypassed.

**Rate limits** (Authentication → Rate Limits). The defaults are sensible. Keep sign-in and
token verification limited per IP. The built-in email sender allows only about 2 emails an
hour, which is enough for testing and not for real users (see "Before launch").

**Two-step sign-in (TOTP)** is enabled by default on Supabase projects. Check that
Authentication → Multi-Factor shows TOTP enabled. Nothing else is needed: the restrictive
policy in `schema.sql` makes the database refuse a two-step account until the authenticator
code has been entered.

**Email confirmation** should stay on (Authentication → Sign In / Providers → Email →
"Confirm email"), so nobody can create an account with someone else's address.

## 4. Check it works

1. On the desktop: Settings → Account & sync → Create account. Enter the emailed code.
2. Sign in on the phone with the same account. A card added on one device should appear on
   the other within a minute (or straight away with "Sync now").
3. Optional: Settings → Two-step sign-in on either app, scan or type the setup key into an
   authenticator app, then sign out and back in. The authenticator code is now required.

Without a real project you can still run the automated checks:

```powershell
python -m unittest discover -s latest_app\tests -p test_cloud_sync.py
$env:PYTHONIOENCODING="utf-8"; python tools\parity\sync_interop.py   # desktop <-> phone through a local fake server
```

## AI notes and questions

Make with AI (study notes and practice questions from notes, a PDF or a photo) uses the
same project. The apps call a Supabase Edge Function named `ai`, which calls Google Gemini,
so the Gemini key stays on the server and never goes in the apps. Until the function is
deployed, the AI buttons say AI isn't ready yet and everything else keeps working.

The full steps are in [`supabase/functions/ai/README.md`](../supabase/functions/ai/README.md).
In short:

1. Run [`supabase/migrations/2026-10-18-ai-usage.sql`](../supabase/migrations/2026-10-18-ai-usage.sql)
   in the SQL Editor. It adds the per-person daily counter. New projects get it from
   `schema.sql`.
2. Get a free Gemini API key from <https://aistudio.google.com> and add it as the secret
   `GEMINI_API_KEY`.
3. Optional secrets: `GEMINI_MODEL` (default `gemini-3.5-flash-lite`) and `AI_DAILY_LIMIT`
   (default `10` requests per person per day). The free tier's daily allowance is shared
   by everyone using the key, so keep the per-person limit well below it.
4. Deploy with `supabase functions deploy ai`, or paste `index.ts` and `logic.ts` into the
   dashboard's editor.

On Gemini's free tier Google may keep, use and review what people send. The apps' consent
screen and `PRIVACY_POLICY.md` say so; if you move the key's Google Cloud project to the paid
tier, update both.

## Before launch

- **Custom SMTP** (Authentication → Emails → SMTP Settings), so codes arrive reliably and aren't
  capped at 2 an hour. MemoryPal uses Gmail SMTP for now, with the plan to move to Brevo with its
  own domain: see `launch/supabase/auth-email-provider.md` in the project files.
- **A privacy policy and terms** page on that domain. App stores require one for any app with
  accounts. They are [`PRIVACY_POLICY.md`](../PRIVACY_POLICY.md) and
  [`TERMS_OF_USE.md`](../TERMS_OF_USE.md) (linked from the apps on GitHub). If they move to a
  domain, put their addresses in `cloud_config.py` (`TERMS_URL`, `PRIVACY_URL`) and
  `mobile/app.json` (`expo.extra.termsUrl`, `privacyUrl`). The sign-up screens link to them.
- **CAPTCHA** stops bots from mass-creating accounts. The apps open a Cloudflare Turnstile
  check (`site/verify/`, published to https://tksmg.github.io/MemoryPal/verify/ by
  `.github/workflows/pages.yml`) before signing in, creating an account, resetting a password
  or resending a code, and send its token along. The page address is `CAPTCHA_URL` in
  `cloud_config.py` and `expo.extra.captchaUrl` in `mobile/app.json`. To turn it on, in order:
  1. Cloudflare dashboard → Turnstile → Add widget: hostname `tksmg.github.io`, mode Managed.
  2. GitHub → Settings → Pages → Source: **GitHub Actions**; Settings → Secrets and variables →
     Actions → Variables: `TURNSTILE_SITE_KEY` = the widget's site key. Run **Publish website**.
  3. Release the apps (older versions can't pass the check).
  4. Supabase → Authentication → Attack Protection → Enable CAPTCHA protection: provider
     Turnstile, the widget's **secret** key.
- **Google and Apple sign-in for MemoryPal accounts** are not built. Connecting Google Drive is
  storage access, not the app's account sign-in, so Apple's Sign in with Apple rule (4.8) should
  not apply. Say so in the App Review notes in case a reviewer asks.
- Consider the Pro plan for leaked-password protection, daily backups and no project pausing.

## Age and consent

- **Accounts are for people 13 and older** (`MIN_ACCOUNT_AGE` in `security.py` / `security.ts`),
  the age where US children's privacy law (COPPA) stops requiring a parent's verified consent.
  Everything else in MemoryPal works without an account for any age.
- Sign-up asks for the month and year of birth first, with no hint of the required age. The
  check runs on the device, and **the birth date is never stored or sent**. A refusal blocks
  sign-up on that device for a day, so the answer can't simply be changed.
- Sign-up requires agreeing to the Terms of Use and Privacy Policy. The account keeps only
  `age_confirmed: "13+"`, the `terms_version` and `terms_accepted_at` (Supabase user metadata),
  as a record of consent. Bump `TERMS_VERSION` when the documents change.
- In the EU, some countries set the age for consent-based processing at up to 16. Sync is
  provided as a service the person asked for rather than on consent, but get advice before
  launching there; raising `MIN_ACCOUNT_AGE` is a one-line change on each side.

## Security design notes

- **Where the session lives.** Sign-in tokens are kept in the operating system's protected
  storage: Windows DPAPI on the desktop (`account.bin`), the iOS Keychain or Android Keystore
  on phones (expo-secure-store), and `sessionStorage` on the web build, cleared when the tab
  closes. They are deliberately **not** kept in `localStorage`, where any script running on
  the page can read them and they never expire.
- **No client-side admin checks.** Anything an app decides on the device can be changed by
  whoever holds the device, so the apps make no access decisions. Every rule is enforced by
  the server: Row Level Security on every row, the aal2 policy for two-step accounts, and
  `delete_my_account()` acting only on the caller's own user. If admin tools are ever needed,
  build them as a separate server-side function that checks a role stored in the database,
  never as a flag the app reads.
- **Device-side limits are for friendliness.** The password checks, the leaked-password
  lookup (only the first 5 characters of the password's SHA-1 hash leave the device) and the
  growing wait after repeated wrong passwords or codes give quick feedback. The server's rate
  limits and password policy above are the real protection.
- A sign-in that still needs its authenticator code is never saved, so closing the app at
  that step leaves you signed out.
- **Off Windows** (the macOS desktop build) there is no DPAPI, so `account.bin` is created
  readable only by its owner (permissions 600), the way command-line tools keep their tokens.
  Moving it into the macOS Keychain would be stronger.
- **Attachments are local and fenced in.** Attachment paths travel inside backups and synced
  cards, so the desktop only ever opens, previews or plays files inside the profile's own
  attachments folder (`media.attachment_file`), and never programs or scripts. A path
  pointing anywhere else is treated as missing. Without this, a backup someone sent you could
  run a program when you pressed Open, or leak your Windows sign-in to a network share just
  by showing a card.
