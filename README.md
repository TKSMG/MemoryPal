# MemoryPal

## Project Note

I built MemoryPal as a desktop memory trainer for learners, older adults, and anyone who benefits from calm, structured recall practice. The main idea was to put several useful memory techniques in one place without making the program feel heavy or complicated.

MemoryPal now comes as a Python/Tkinter desktop app for Windows and macOS and a React Native phone app for iPhone and Android. An optional account keeps them in sync.

## Download

Installers for every platform are on the [latest release](https://github.com/TKSMG/MemoryPal/releases/latest). [installers/README.md](installers/README.md) explains how to install each one.

## What it does

- **Flashcards that come back at the right time**: spaced review with Smart Check, which tells you how close a typed answer was.
- **Make with AI** (optional, needs an account): turn notes, a PDF or a photo of a page into study notes or practice questions.
- **Quizzes that mix it up**: multiple choice, the other way round, fill the gap, true or false, match, put in order and recall.
- **Talk-back and read aloud**: hear each question and answer out loud, hands-free.
- **Memory techniques**: acronyms, stories, peg lists, memory palaces, chunk maps and link chains, plus memory puzzles.
- **Study plans and progress**: daily goals, streaks, charts and badges.
- **Made for everyone**: larger text, a simpler-language mode, extra time, high contrast and screen-reader support.
- **Private by default**: everything except AI and sync works offline, and nothing leaves the device without an account.

Every feature is listed in [docs/FEATURES.md](docs/FEATURES.md), and each release's changes are in [development_versions/VERSION_JOURNAL.md](development_versions/VERSION_JOURNAL.md).

## Repository layout

| Folder | What's in it |
| --- | --- |
| `latest_app/` | The desktop app: `MemoryPalDesktop.py` (the views), the `memorypal/` logic package and the `tests/` |
| `mobile/` | The phone app (Expo / React Native). See [mobile/README.md](mobile/README.md) |
| `supabase/` | Database schema, migrations and the `ai` Edge Function |
| `docs/` | Build, sync, design and testing guides (below) |
| `tools/` | Parity fixtures, the render and scroll probes, store screenshots and the MSIX packager |
| `installer/`, `installers/` | Inno Setup script for the Windows installer, and the download and release guide |
| `site/verify/` | The CAPTCHA page published to GitHub Pages |
| `assets/` | App icon exports |
| `development_versions/` | Milestone versions, the version journal and the old Kivy phone prototype |
| `.github/workflows/` | Builds for every platform, the release, GitHub Pages and the probes |
| Root `*.cmd`, `build_macos.sh` | Windows and macOS build scripts |

## Documentation

- [docs/BUILDING_APP.md](docs/BUILDING_APP.md): building the desktop app, installer and tester package
- [docs/CLOUD_SYNC_SETUP.md](docs/CLOUD_SYNC_SETUP.md): setting up Supabase for accounts, sync and AI
- [supabase/functions/ai/README.md](supabase/functions/ai/README.md): deploying the AI function
- [docs/DESIGN_NOTES.md](docs/DESIGN_NOTES.md): the design system shared by both apps
- [docs/TESTING_CHECKLIST.md](docs/TESTING_CHECKLIST.md): the full manual test pass
- [docs/TESTER_START_HERE.md](docs/TESTER_START_HERE.md): the short guide for testers
- [docs/MemoryPal_Memory_Techniques.md](docs/MemoryPal_Memory_Techniques.md): background on the memory techniques
- [installers/README.md](installers/README.md): installing, releasing and signing
- [PRIVACY_POLICY.md](PRIVACY_POLICY.md) and [TERMS_OF_USE.md](TERMS_OF_USE.md)

## Running the desktop app

Open a terminal in this folder and run:

```powershell
python latest_app\MemoryPalDesktop.py
```

For the full optional desktop setup:

```powershell
python -m pip install -e ".[documents,image-previews,media,speech]"
```

App data lives in the normal app-data folder for the operating system (on Windows, `%LOCALAPPDATA%\MemoryPal`). Older `%USERPROFILE%\MemoryPalData` data is copied forward automatically.

## Running the tests

```powershell
python -m unittest discover -s latest_app\tests
```

The tests use a throwaway data folder, so they never touch real profiles. For the phone app, run `npm ci` and `npx jest` in `mobile/`. Any logic change goes in both `latest_app/memorypal/` and `mobile/src/core/`; then run `python tools/parity/make_fixtures.py` so the parity tests compare the two.

## Building

[docs/BUILDING_APP.md](docs/BUILDING_APP.md) covers Windows (`build_release_windows.cmd` does tests, app, installer and tester zip in one go) and macOS (`build_macos.sh`). A release is built by GitHub Actions: run the `release.yml` workflow with a tag such as `v0.50.0`, and it builds Windows, macOS, Android and iOS and publishes them as a GitHub Release.

## Phone app

```powershell
cd mobile
npm install
npx expo start
```

Talk-back needs a development build (`npx expo run:android` or `run:ios`) because Expo Go doesn't include speech recognition. [mobile/README.md](mobile/README.md) covers tests, structure and the parity checks.
