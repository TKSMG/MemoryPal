# Syncing cards through Google Drive

From this version, MemoryPal can sync cards, reviews, streaks and settings through the person's own
Google Drive instead of the MemoryPal cloud (Supabase). Supabase then only keeps accounts (sign-in,
two-step, consent, the AI allowance). Design notes: the "drive" sections of
`latest_app/memorypal/sync.py` and `latest_app/memorypal/drive.py`.

**Status:** on from release 0.51.0 (October 21, 2026). The Google Cloud project, the clients
below, the GitHub variables and the Supabase function are all set up. A build made without the
Google clients still syncs through Supabase as before, and the two don't see each other's cards.

## How it works

- MemoryPal asks only for `drive.appdata`: a hidden folder in the person's Drive that only MemoryPal
  can see. Google rates it **non-sensitive**, so there is no paid security assessment (CASA), only
  Google's free branding check.
- Each device writes one file there, `memorypal-<device id>.json`, holding all its records with a
  stamp each. No two devices ever write the same file. A sync reads the files that changed since
  last time, takes each record's newest copy, merges with the same rules as before (an edit beats a
  delete, more reviews win a schedule conflict, review counts add up), and rewrites its own file only
  when something changed.
- Desktop: the person's browser opens Google's page; MemoryPal waits on `127.0.0.1` for the answer
  (PKCE). The refresh token is kept like the MemoryPal sign-in (DPAPI on Windows, Keychain on a Mac).
- Phone: Google's own sign-in sheet (`@react-native-google-signin/google-signin`). Google keeps the
  connection; MemoryPal stores only the account's id and email.
- **Moving existing data:** the first Drive sync of a profile that is signed in to a MemoryPal
  account syncs with Supabase one last time, merges everything into the Drive, then deletes that
  account's rows with `delete_my_sync_records()`. If that delete fails it is retried after later
  syncs.
- A MemoryPal account is still used for AI notes and questions.

## Turning it on

### 1. Google Cloud project

1. Open https://console.cloud.google.com and create a project called **MemoryPal** (or use an
   existing one).
2. **APIs & Services → Library**: enable **Google Drive API**.
3. **Google Auth Platform → Branding**: app name *MemoryPal*, support email *memorypal09@gmail.com*,
   the app icon, the home page, the Privacy Policy and Terms links, and an authorised domain.
   The authorised domain has to be one you can prove you own in Google Search Console
   (for example `tksmg.github.io`, by adding the HTML file Search Console gives you to `site/`).
4. **Audience**: *External*. While it says **Testing**, add up to 100 test users (their Gmail
   addresses). In Testing, Google ends each connection after 7 days, so testers must reconnect
   weekly. Press **Publish app** before the public release.
5. **Data Access → Add or remove scopes**: `.../auth/drive.appdata`, `openid` and
   `.../auth/userinfo.email`. Nothing else.

### 2. OAuth clients (Google Auth Platform → Clients → Create client)

| Client type | Settings | Where it goes |
|---|---|---|
| Desktop app | name *MemoryPal desktop* | Client ID → repository **variable** `GOOGLE_DESKTOP_CLIENT_ID`; client secret → repository **secret** `GOOGLE_DESKTOP_CLIENT_SECRET` |
| iOS | bundle ID `app.memorypal.mobile` | Client ID → repository **variable** `GOOGLE_IOS_CLIENT_ID` |
| Android | package `app.memorypal.mobile`, SHA-1 of the **app signing key** (Play Console → Test and release → App integrity → App signing) | nothing to copy |

Google checks the SHA-1 of the key that signed the installed app. MemoryPal's Play Console shows
only an app signing key (no separate upload key), so one Android client covers it. If the APK
from GitHub Releases ever fails to connect with `DEVELOPER_ERROR`, it was signed with a different
key: add a second Android client with that key's SHA-1 (`keytool -list -v -keystore <file>.jks`).

GitHub: Settings → Secrets and variables → Actions. The build workflows write the desktop values
into `latest_app/memorypal/google_client.py` (ignored by git) and pass `GOOGLE_IOS_CLIENT_ID` to
`mobile/app.config.js`. For EAS builds, add `GOOGLE_IOS_CLIENT_ID` to the EAS environment too.

Running the desktop app from the Python files (`python latest_app/MemoryPalDesktop.py`) doesn't
get these values, so it shows the old account sync and no Google Drive option. To use Drive
there, create `latest_app/memorypal/google_client.py` (git ignores it) with the same values as
`GOOGLE_DESKTOP_CLIENT_ID` and `GOOGLE_DESKTOP_CLIENT_SECRET`:

```python
CLIENT_ID = "1234-abc.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-..."
```

Set all three at once and release desktop and phone together: a build with them syncs through
Drive, a build without them through Supabase, and the two don't see each other's cards.

### 3. Supabase

Run `supabase/migrations/2026-10-20-move-to-drive.sql` once in the SQL editor (it only adds the
`delete_my_sync_records()` function). Done on the live project on October 21, 2026.

### 4. Before the public release

- **Privacy Policy and Terms**: updated on October 21, 2026 ("Syncing with Google Drive").
- **Google consent screen**: press **Publish app** under Audience, then submit the free branding
  check. Until then only the listed test users can connect, and Google ends each connection
  after 7 days.
- **Play Data safety / App Store privacy / Microsoft Store**: the answers are in the project's
  launch notes (`launch/store-forms-and-rules.md`); synced cards go to the person's own Google
  account, so they are not "collected" by MemoryPal.
- **Store screenshots**: the Account & sync screens now show "Connect Google Drive". Retake them
  only if a store shows that screen.

### Later

- A release after everyone is on 0.51.0 or newer removes the Supabase sync code, revokes writes
  to `sync_records` and drops the table.
- OneDrive and iCloud, and syncing attachments (pictures, recordings), are not built yet.

## Testing without Google

- Desktop: `python -m unittest latest_app/tests/test_drive_sync.py` (two devices sharing a folder
  "drive", the move off Supabase, and the Drive API against a fake Google).
- Phone: `npx jest __tests__/drive.test.ts`.
- Both apps together: `python tools/parity/drive_interop.py` (the laptop in Python and the phone in
  TypeScript sync through one folder).
- Setting `MEMORYPAL_GOOGLE_CLIENT_ID` to anything shows the Drive screens on the desktop.
