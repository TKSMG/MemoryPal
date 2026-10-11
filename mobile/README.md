# MemoryPal Mobile

The iPhone and Android version of MemoryPal, built with React Native and Expo (SDK 57) in TypeScript. It replaces the earlier Kivy prototype in `../mobile_app/`.

## Try it on your phone

1. Install **Expo Go** from the App Store or Google Play.
2. From this folder:

   ```powershell
   npm install
   npx expo start
   ```

3. Scan the QR code with the phone's camera (iPhone) or with Expo Go (Android). The phone and the computer need to be on the same Wi-Fi network.

`npx expo start --web` runs it in a browser instead.

## Checks

```powershell
npm test              # unit tests, including the parity tests against the desktop logic
npm run typecheck     # TypeScript
npx expo lint         # ESLint (Expo config)
npx expo-doctor       # dependency and config health
```

## How it is organised

- `src/core/`: the study engine, ported from `latest_app/memorypal/`:
  - review scheduler and store (`store.ts`)
  - Smart Check (`smartCheck.ts`)
  - text splitting (`text.ts`)
  - planner (`planning.ts`)
  - memory techniques (`techniques.ts`)
  - levels and badges (`progress.ts`)
  - personas (`personas.ts`)
  - sync records and merging (`sync.ts`)
  - password checks and the attempt limiter (`security.ts`)

  There is no UI code in this folder.
- `src/app/`: the screens (Expo Router). The five tabs are Today, Study, Create, Practice, and Progress. The other screens are review, quiz, add, edit card, plan, puzzle, settings, and welcome.
- `src/cloud/`: the Supabase client (`client.ts`, including two-step sign-in), the account and sync loop (`account.ts`), secure token storage (`secrets.ts`) and the breached-password check (`pwned.ts`).
- `src/ui/`: theme tokens (the same WCAG AA palette as the desktop), shared components, read-aloud, and haptics.
- `src/state/`: the app's single store and storage. Phones use Expo's SQLite key-value store and the web build uses `localStorage`. Backups are saved and opened with the system share sheet and file picker.

## Keeping desktop and mobile in step

The desktop (Python) and mobile (TypeScript) apps implement the same scheduler, Smart Check, planner, and generators. `../tools/parity/make_fixtures.py` runs the real Python code on hundreds of cases (202 answers, 240 schedules, 452 session plans, 135 multi-day plans, and more) and writes `__tests__/fixtures/parity.json`. `__tests__/parity.test.ts` must reproduce every result exactly.

After changing logic on either side:

```powershell
python ..\tools\parity\make_fixtures.py
npm test
```

## Data

Cards and progress use the desktop's JSON format (same snake_case fields), so a backup moves freely between the two apps. Settings → Save a backup / Load a backup. Phone-only preferences (appearance, vibrations) are stored separately and are never part of a backup. Signed-in phones also sync with the cloud (Settings → Account & sync): see `src/cloud/` and `../CLOUD_SYNC_SETUP.md`. The sign-in token lives in expo-secure-store (Keychain / Keystore), or `sessionStorage` on the web.

## Icons

`python ..\tools\mobile_icons.py` regenerates `assets/` from the desktop logo geometry (`latest_app/memorypal/icon.py`).
