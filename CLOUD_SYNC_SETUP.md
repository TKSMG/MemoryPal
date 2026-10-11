# Setting up accounts and cloud sync

MemoryPal's accounts and sync run on [Supabase](https://supabase.com): email + password sign-in,
6-digit email codes, optional two-step sign-in with an authenticator app, and one table of
sync records protected by Row Level Security. Until a project is configured, both apps work
exactly as before, fully offline, and the account screens say sync isn't set up.

You don't need a domain to build or test this. You will want one before a public launch (see
"Before launch").

## 1. Create the project

1. Create a free project at supabase.com. Pick the region closest to your users.
2. Open **SQL Editor**, paste all of [`supabase/schema.sql`](supabase/schema.sql) and run it.
   It creates the `sync_records` table, its Row Level Security policies (people can read and
   write only their own rows, and two-step accounts need the second step), and the
   `delete_my_account()` function used by "Delete account".
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
- Required characters: letters and digits.
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

## Before launch

- **A domain and custom SMTP** (Authentication → Emails → SMTP Settings), for example Resend,
  Postmark or Amazon SES with your domain, so codes arrive reliably and aren't capped at 2
  an hour.
- **A privacy policy and terms** page on that domain. App stores require one for any app with
  accounts. It should say what is stored (cards, review history, settings; photos and
  recordings stay on the device), where (the Supabase region), and how to delete it (Delete
  account in the app removes the account and its cloud copy).
- **CAPTCHA** (Authentication → Attack Protection) helps stop bot sign-ups, but the apps
  don't send a CAPTCHA token yet. Turning it on before that is built will block every sign-up
  and sign-in.
- **Google and Apple sign-in** are planned. Apple requires Sign in with Apple on iOS if any
  other social sign-in is offered.
- Consider the Pro plan for leaked-password protection, daily backups and no project pausing.

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
