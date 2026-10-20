# MemoryPal

## Project Note

I built MemoryPal as a desktop memory trainer for learners, older adults, and anyone who benefits from calm, structured recall practice. The main idea was to put several useful memory techniques in one place without making the program feel heavy or complicated.

This version is a Python/Tkinter desktop app. It is meant to show the working concept clearly while the mobile version is still in prototype form.

## Project Files

- Latest app: `latest_app/MemoryPalDesktop.py`
- Desktop support package: `latest_app/memorypal/`
- Unit tests: `latest_app/tests/`
- App icon exports: `assets/memorypal.ico`, `assets/memorypal-logo-preview.png` (1024px), `assets/memorypal-logo.svg`
- Logo source: `latest_app/memorypal/icon.py` (run `python latest_app\memorypal\icon.py` to re-export the `.ico` and PNG)
- Testing checklist: `TESTING_CHECKLIST.md`
- Tester quick-start guide: `TESTER_START_HERE.md`
- Build notes: `BUILDING_APP.md`
- Design notes: `DESIGN_NOTES.md`
- Memory techniques notes: `notes/MemoryPal_Memory_Techniques.md`
- Python project config: `pyproject.toml`
- Mobile app (React Native + Expo): `mobile/` (see `mobile/README.md`)
- Accounts and cloud sync: `latest_app/memorypal/cloud.py`, `sync.py`, `security.py`, the database schema in `supabase/schema.sql`, and set-up steps in `CLOUD_SYNC_SETUP.md`
- Desktop/mobile parity fixtures: `tools/parity/make_fixtures.py`
- Rendering check (tearing and flashes): `tools/render_check/render_probe.py`
- Old Kivy mobile prototype (superseded): `mobile_app/MemoryPalMobile.py`
- Development versions: `development_versions/`
- Version journal: `development_versions/VERSION_JOURNAL.md`
- Program outline: `development_versions/MemoryPal_Project_Outline.py`
- Desktop dependencies: `requirements-desktop.txt`
- Windows build dependencies: `requirements-build.txt`
- One-shot Windows release command (tests, app, installer, tester zip): `build_release_windows.cmd`
- Windows build command: `build_windows.cmd`
- Windows installer command: `build_installer_windows.cmd`
- macOS build command: `build_macos.sh`
- Clean build artifacts command: `clean_build_artifacts.cmd`
- Tester package command: `package_for_testers.cmd`
- Installer script: `installer/inno/MemoryPal.iss`
- Alternate Nuitka build command: `build_nuitka_windows.cmd`
- GitHub Actions Windows build: `.github/workflows/build-windows.yml`
- GitHub Actions macOS build: `.github/workflows/build-macos.yml`
- Mobile prototype dependencies: `requirements-mobile.txt`

## Running The App

Open a terminal in this folder and run:

```powershell
python latest_app\MemoryPalDesktop.py
```

For a full optional desktop setup:

```powershell
python -m pip install -e ".[documents,image-previews,media,speech]"
```

Local app data uses the normal app-data folder for the operating system. On Windows, this is usually:

```text
%LOCALAPPDATA%\MemoryPal
```

Older `%USERPROFILE%\MemoryPalData` data is copied forward automatically the first time the new storage layer runs.

## Running The Tests

The support package has a standard-library `unittest` suite (no extra packages needed). From this folder:

```powershell
python -m unittest discover -s latest_app\tests
```

The tests point MemoryPal at a throwaway data folder, so they never touch real profile data. They cover text parsing and Smart Check, card models, scheduling and saving, study planning, memory-technique generators, and onboarding personas.

## Building An EXE

The Windows build path is documented in `BUILDING_APP.md`.

To make a complete tester release in one go (unit tests, clean, app folder, installer, and tester zip), run:

```powershell
.\build_release_windows.cmd
```

To build only the app folder, run:

```powershell
.\build_windows.cmd
```

The default build uses PyInstaller in normal app-folder mode. It creates `release\MemoryPal\MemoryPal.exe`, which opens faster than a self-extracting one-file EXE and proved steadier for the current tester package than the latest local Nuitka build. The build also bundles the checked-in icon assets so installed copies do not regenerate the app icon during startup. The release folder is ignored by Git so the repository stays focused on source code and documentation.
The tester build needs no media packages: audio recording, playback, image previews, and spoken cue files use what Windows already includes (MCI, Windows Imaging, and the System.Speech voice), and video is recorded with the Windows Camera app. Heavy optional libraries such as OpenCV and `pyttsx3` stay out of the package.

Before making a fresh package, generated build leftovers can be cleared with:

```powershell
.\clean_build_artifacts.cmd
```

This removes MemoryPal build folders, cache folders, and MemoryPal-named temp build files. It does not remove saved profile data.

GitHub Actions can also build the Windows app and installer from `.github/workflows/build-windows.yml` and upload them as artifacts.

To make a Windows installer after the app folder exists, install Inno Setup 7 or 6 and run:

```powershell
.\build_installer_windows.cmd
```

The installer output should appear at `release\MemoryPalSetup.exe`.

`build_installer_windows.cmd` only builds the app when `release\MemoryPal\MemoryPal.exe` is missing, so after code changes either run `build_release_windows.cmd` or rebuild the app first. Otherwise the installer can ship an older app.

For testers, package `release\MemoryPalSetup.exe` plus `TESTER_START_HERE.md` and `TESTING_CHECKLIST.md`. The whole `release\MemoryPal\` app folder can go in too as a portable fallback. Build and design notes stay in the repository.
After a build exists, this command gathers the installer, portable app folder, and tester notes into `release\MemoryPalTesterPackage.zip`:

```powershell
.\package_for_testers.cmd
```

If multiple Python installs exist, point MemoryPal's build scripts at the one with working Tkinter:

```powershell
$env:MEMORYPAL_PYTHON = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
.\build_windows.cmd
```

## Building macOS Packages

macOS app bundles must be built on macOS because `.app` and `.dmg` packaging are platform-specific. The repo now includes `build_macos.sh` for macOS machines and `.github/workflows/build-macos.yml` for GitHub Actions builds.

On a Mac, run:

```bash
./build_macos.sh
```

The script creates a `MemoryPal.app` bundle, a compressed `.dmg`, and a zipped app bundle under `release/`. The GitHub workflow builds separate Intel and Apple Silicon artifacts so testers can download the right package from the Actions run. These beta Mac builds are ad-hoc signed at most, so formal Apple Developer ID signing and notarization should be added before public distribution outside a small testing group.

## Current Features

- AI notes, mixed quizzes, talk-back and simpler set building (desktop and phone):
  - Make with AI turns typed notes, a PDF or a photo of a page into study notes or practice questions. It runs through MemoryPal's Supabase Edge Function `ai` to Google Gemini (free tier, Gemini 3.5 Flash-Lite by default), so no AI key ships in the apps. It needs a signed-in account and internet, allows 10 requests per person per day, asks for consent once, and can be turned off in Settings. Questions arrive as cards to check, edit or remove before saving. Everything AI makes is labelled "Made with AI, check it" with a Report link. On the free tier Google may keep and review what is sent (see `PRIVACY_POLICY.md`). Set-up steps are in `supabase/functions/ai/README.md`.
  - Quizzes mix seven question types: pick the answer, reverse (which question goes with this answer), fill in the blank, true or false, match the pairs, what comes next in a list, and type the answer. The next round avoids the questions you just had. Both apps build questions with the same seeded logic (`latest_app/memorypal/questions.py`, `mobile/src/core/questions.ts`), checked by the parity fixtures.
  - Talk-back study is hands-free: each question is read aloud, you answer out loud, and you hear whether you were right. The phone listens with its own speech recognition. On Windows, the desktop uses the recogniser built into Windows, offline, with no extra packages. On Mac and Linux, and wherever the microphone isn't available, questions are still read aloud and you type the answers.
  - A read-aloud button on every card, question, answer and note, on both apps.
  - Building a set is two steps: name the set, then add cards by typing them, pasting notes, or using Make with AI. On the desktop, Decks has New set and Rename set; on the phone, a set's page can rename or delete it.
  - Desktop: dropdowns fit their longest label and stay on screen, dialogs grow to fit their text, the mouse wheel glides smoothly (touchpads follow your fingers), the system title bar matches the light or dark theme, and dialogs, dropdowns and fields are calmer and bordered.
  - Phone: new permission requests for the microphone and speech recognition (Talk-back) and the camera (Take a photo in Make with AI). Each is asked only when you use that feature. Choosing a photo uses the system picker.
- Accounts and cloud sync (desktop and phone), once a Supabase project is set up (`CLOUD_SYNC_SETUP.md`):
  - Email + password accounts, confirmed with a 6-digit email code; forgotten passwords are reset the same way.
  - Cards, reviews, streaks and settings sync automatically between computers and phones, merging changes made on both rather than overwriting.
  - Optional two-step sign-in with an authenticator app.
  - Password strength meter, refusal of common and breached passwords, and a growing wait after repeated wrong passwords or codes.
  - Sign-in tokens kept in Windows DPAPI, the iOS Keychain or the Android Keystore. Delete account removes the account and its cloud copy.
  - Without a project, both apps keep working fully offline as before.
- New phone app (`mobile/`, React Native + Expo) for iPhone and Android:
  - Five simple tabs: Today, Study, Create, Practice, Progress.
  - Review with Smart Check, plain-language results, undo, skip-for-today, and an end-of-session summary.
  - Multiple-choice quiz, adaptive memory puzzles, and memory-technique generators.
  - Study plans, charts and badges, everyday-memory cards, and read aloud.
  - Large-text and high-contrast modes, and full screen-reader labels.
  - Backups use the desktop's file format, so cards move between the two.
- The phone app's study logic is checked against the desktop's by parity tests on hundreds of cases.
- The navigation rail spreads the pages evenly over its height instead of bunching them at the top, and Settings is pinned at the bottom under a divider.
- Smart Check hints show real words ("increasing") instead of word stems ("increas").

- Page switches, scrolling, fullscreen, focus mode, resizing, theme and text-size changes, and startup each appear as one finished frame, with no tearing, white flashes, or elements painting in one by one. Scrolling shows only fully drawn frames. `tools/render_check/render_probe.py` measures this by recording the window at screen rate.
- Rounded controls use opaque, pre-blended tiles, keeping startup at about 1.5s and page switches fast.

- New logo: a lowercase "m" drawn as one line of two arches, with an amber recall dot, on a flat blue tile. It replaces the gradient, sparkle, and bead design.
- Page titles, headings, and stat numbers now show at their designed sizes. A global font setting had been drawing them all as body text.
- Rounded buttons, dropdowns, choice pills, and text fields across the app. Text fields always show an edge, so it's clear where to type.
- All text and button colours meet WCAG AA contrast in light and dark mode. Bright dark-mode buttons use dark text instead of white.
- Keyboard focus is always visible as a solid amber ring.
- The navigation rail shows every page on a normal laptop screen instead of six at a time. The active page is a calm filled pill, and each page title names its area (Today, Study, Create, Practice, Progress).
- Cards can be edited, reset to new ("Learn again"), or deleted from Library. Library shows 60 cards at a time with Show more, so large collections stay fast.
- Import asks before replacing a profile, shows how many cards the backup holds, and saves a copy of the current data first. Reset all data lives only in Settings.
- Every save keeps a `.bak` of the previous file. A damaged data file is set aside and the last good save is loaded, instead of opening as an empty profile.
- A card deleted in one window is no longer brought back by a second open window.
- Profile names that would share a data folder (for example "My Profile" and "my-profile") are refused.
- Smart Check no longer accepts a wrong number ("1954" for "1945") or a flipped meaning ("reversible" for "not reversible") as close enough.
- Pasted notes keep leading years and decimals ("1945 …", "3.14"). Tab-separated Quizlet or spreadsheet lines import as cards.
- Multi-day plans no longer count today's backlog again on every later day.
- Successful reviews always grow the interval; load-spreading can no longer shrink it.
- Peg lists read naturally ("a bundle of sticks").
- Document import refuses decompression bombs and oversized files instead of freezing.
- PowerShell is always run from its full system path.

- Feedback can be sent to the MemoryPal team straight from the Feedback Log: Send Feedback Now posts the waiting notes through FormSubmit (no mail account needed), Email Feedback opens the tester's own mail app or Gmail with the report filled in, and Save Feedback File writes a text report to attach. Notes are marked as sent so they are not sent twice. Reports include the notes plus Windows version, text size, and theme, never the profile name or study cards, and nothing is sent unless the person presses a button.
- Dragging the custom resize edges shows a Windows-style outline of the new size; the window resizes once when the mouse is released.
- In-page updates (adding rows, showing a new section) swap in finished in one frame, using the same snapshot method as page switches, so sections no longer flash or jump.
- Popups become the active window so typing goes to them straight away, stay above the main window, and hand focus back when closed.
- Flat buttons no longer nudge their text when pressed.
- Text in labels can be highlighted and copied (drag, double-click for a word, triple-click for a line, Ctrl+C).
- New MemoryPal logo: a cleaner connected "memory path" M on a blue-to-violet tile, with mint and amber recall nodes and a small spark. The same design is used for the app/taskbar icon, title strip, navigation rail, installer, macOS icon, and the `assets/` exports; tiny sizes use a simplified mark so it stays crisp at 16-32px.
- Ctrl+K page finder opens a searchable list of every page and common action; a Back button in the header (or Alt+Left) returns to the previous page.
- App-styled dropdown lists replace the stock Tk menus.
- Theme, text-size, and accessibility changes rebuild the whole interface under a screen snapshot and swap it in one frame, so there is no white or half-drawn flash. Popups are laid out invisibly and appear already finished instead of fading in.
- Dashboard is built around today: the saved study plan's steps for today (tick them off as you go), a greeting and best next action, a progress strip with streak, level and XP, persona-picked study modes (Quick 10, Deep study, Exam cram, Gentle review, and more), and the next badge to earn.
- Study Plan can be saved with Make this my plan; minute plans repeat daily and day/week plans follow the right day of the multi-day schedule. Plans can include Pomodoro-style rest breaks with a break timer, a capped Learn new cards step, an Explain it back step, and a short Wrap up.
- Stats page now shows charts: the last 30 days, cards coming up over two weeks, card maturity, how recent answers went, weekday rhythm, the activity calendar, deck mastery, and achievement badges with progress.
- Audio can be recorded with a live level meter and played back without extra packages; videos are recorded through the Windows Camera app and pulled in automatically; image previews support JPEG, PNG, GIF, BMP, TIFF, WebP, and HEIC through Windows; spoken cues can be saved as audio files.
- Document import reads `.rtf`, handles Notepad encodings (UTF-8, UTF-16, ANSI), keeps tabs and line breaks from `.docx`, and reads ordinary PDFs with a built-in reader when `pypdf` is not installed. Scanned PDFs get a clear message instead of an error.
- Saving only merges with the data file when another window has actually written to it, which makes normal saves faster; undo now correctly lowers review counts after a merge.
- The logo is drawn once at 256px and cached on disk, so startup does not redraw it at every size.
- First-run Welcome screen asks who is using MemoryPal (studying, everyday memory, helping someone else, or just exploring), then sets the navigation order, text size, calmer accessibility defaults, and read-aloud choice to match.
- Guided tour for each persona walks through the pages that person will use most, and can be replayed or redone from Settings > Welcome & tour. Existing profiles skip the Welcome screen automatically.
- Finishing or skipping the Welcome screen, and moving between tour steps, build the new layout under a screen snapshot and swap it in one frame (the same calculation-gap method used for window resizing), so no white or half-styled frames flash on Windows.
- Offline Read aloud uses the voice built into the operating system (Windows System.Speech, macOS `say`, or Linux `espeak`), with no extra packages. Questions and answers can be read automatically, and card text is passed on standard input so it cannot break the command.
- More time accessibility setting doubles timed displays in puzzles and messages and slows the read-aloud voice.
- Multi-day Study Plan projects which cards will be due on each day, schedules new material on expanding review days (2, 4, 7, 14, 21, 30), grows heavy review days instead of using a fixed block, and makes the day before a test a light confidence pass.
- Review scheduling now separates Review, Good, and Easy steps, gives partial credit when an overdue card is still remembered, spreads cards learned together across nearby days, and caps intervals at one year.
- Smart Check scores typed answers against the saved answer only, so a correct answer is no longer marked down for not repeating the question.
- Association generators give every idea its own peg, memory-palace spot, or story scene; long lists continue with distinct twists (golden, frozen, garden, garage) instead of reusing the same hook.
- Acronym builder also suggests an acrostic sentence.
- Unit test suite in `latest_app/tests/` for the support package.
- Modern Tkinter desktop interface with a soft app header, local-save status, styled cue menus, hover feedback, and steadier page reveals.
- Header controls are split into status and action zones, with the active profile shown as a compact numbered profile chip on the top-right edge.
- Dashboard action cards reflow across wide, normal, and scaled windows so the bottom rows stay reachable instead of feeling clipped.
- Low-end readiness pass reduces repeated custom-chrome redraw work and caches optional graphics lookups so slower Windows PCs and future Mac builds do less work at launch.
- macOS packaging support adds a native-chrome guard for Mac, a Mac build script, and a GitHub Actions workflow for Intel and Apple Silicon tester artifacts.
- Page switches use a same-window reveal over the page panel, so the header and content fade in together without dimming the whole app shell or fighting the Windows compositor.
- Fullscreen and focus mode use a same-window cover while the operating system resizes the app, avoiding root-window opacity changes that can freeze Tkinter on Windows.
- The left navigation rail stays expanded for a steadier desktop layout.
- App-styled modal dialogs for profile names, recording lengths, alerts, confirmations, and errors.
- Refreshed generated MemoryPal app icon for the Windows title/taskbar icon, custom title strip, packaged executable, and exported project assets.
- The mobile prototype also uses in-app validation and confirmation modals instead of silent or system-style feedback.
- Expanded left navigation rail with clear labels, hover hints, and its own scroll area for smaller screens.
- Settings page can reorder the main navigation pages per profile.
- Settings page for theme, navigation, profiles, daily goal, storage, backups, reset, focus mode, and true fullscreen.
- Accessibility settings for larger text, higher contrast, reduced motion, simpler wording, caregiver mode, and a senior-friendly layout preset.
- Everyday Memory page for older adults and caregivers, with a Today board, gentle review, starter cards, and person/routine/place/reminder card creation.
- Settings stays pinned at the bottom of the navigation rail so the header has more room for status and profile controls.
- Window controls separate true fullscreen from borderless focus mode: F11 and the Settings fullscreen control use true fullscreen, while the titlebar square and Settings focus control use borderless focus mode.
- Windowed page changes, theme changes, and interface rebuilds use matching same-theme covers to hide redraw flashes without the older strip-opening effect.
- Fullscreen and focus changes preserve the active page instead of rebuilding the interface.
- Custom window resizing applies after the user releases the resize grip, then reveals the settled layout without fading the whole app window.
- Custom titlebar, navigation, and button shapes use Pillow-backed antialiasing when available, with a built-in smoothed fallback for source runs without Pillow.
- The titlebar and left navigation use the same generated MemoryPal logo artwork.
- The generated logo renders directly through Tk, so the rail mark and titlebar mark stay consistent even without Pillow.
- The desktop launcher now relies on the split `latest_app/memorypal/` package instead of carrying a second stale copy of models, storage, parsing, and planning code.
- Profile config reads, generated logo pixels, and antialiased UI shapes are cached so normal shell rebuilds do less repeat work.
- The custom borderless titlebar restore path is debounced so fullscreen/focus changes and startup do not repeatedly force expensive idle redraws.
- File dialogs, CSV export, browser opening, desktop recording, webcam recording, and text-to-speech load only when those features are used.
- The header and navigation logo load from the checked-in PNG asset during startup, with generated pixels kept as a fallback.
- The main desktop window is resizable from the right edge, bottom edge, and corner while keeping the custom app chrome and DPI-scaled title bar controls.
- More forgiving responsive button rows and Study Plan controls for larger DPI/text scaling.
- Separate local profiles, so different learners or study areas can keep independent data.
- Local saves merge newly added cards, captures, feedback, review counters, and newer saved card progress so two open windows are less likely to overwrite each other's work.
- App data uses a platform-correct local data folder with non-destructive migration from the older home-folder location.
- Dark and light appearance modes.
- In-progress page drafts for Capture, Repetition, Test Lab, Quiz, Associations, and Puzzles while switching sections.
- Study Plan page that builds a short session plan from time, goal, deck choice, and preferred study habits.
- Stats page with daily goal editing, streaks, activity heatmap, and upcoming review preview.
- Stats page includes weekly pace, active-day count, best-day signal, weak-card count, daily goal, streaks, and heatmap.
- Feedback Log page for tester ratings, bug notes, confusing moments, accessibility comments, and spreadsheet (CSV) export.
- Focus queue for due, weak, and fresh cards.
- Dashboard next-step recommendations, mastery progress, due/learning/mastered chips, and a small daily-action prompt.
- Memory Gym page with separate student-study and everyday-memory practice paths.
- Everyday Memory keeps routines, people, places, familiar cues, and caregiver-created cards in the normal review system.
- Chunk-based capture, with each study bit stored separately.
- Capture has horizontal scrolling for the two-column set builder, so the right-side captured/cue panel remains reachable on smaller or scaled windows.
- Note/document imports for `.txt`, `.md`, `.csv`, `.rtf`, `.docx`, and text-based PDFs.
- Imported note/document text can be extracted into the study bit box and turned into decks/cards.
- Separate question/title and answer boxes for prompt-answer cards.
- Optional self-check cards without a saved answer.
- Text, image, audio, and video cues attached to study material where useful.
- Text previews, image previews when supported, and clear play/open buttons for audio or video cues.
- Compact resource strips on major study pages so attached notes, audio, images, and videos stay reachable while planning or practicing.
- Compact cue menus for text, image, audio, and video imports or recordings.
- Test Lab for focused answering, revealing, Smart Check, bucket highlighting, and review scheduling.
- Review quality shortcuts, skip-for-today, undo last rating, and leech warnings for repeatedly missed cards.
- Smart Check for close-enough typed responses, with cleaner key-cue feedback for proper nouns and common terms.
- Repetition Path with separate prompt and answer fields, staged items, a focused round player, and the clarified pattern: `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Quick Quiz with self-check and multiple-choice modes.
- Association tools for acronyms, mini-stories, peg lists, memory palace routes, chunk maps, link chains, and practical technique plans.
- Technique planning for retrieval practice, spaced practice, interleaving, elaboration, concrete examples, dual coding, and spaced retrieval.
- Puzzles for Sequence Recall, Word Recall, Pair Recall, Missing Item, Visual Search, N-Back Lite, Category Sort, and Routine Recall practice.
- Library search with All, Due, Weak, and Captures filters.
- Pointer-aware page scrolling plus keyboard scrolling with Page Up, Page Down, Home, and End, with extra bottom room so final controls stay reachable after scaling.
- Saves are written atomically and merge with existing local data so two open MemoryPal windows keep newly added cards, captures, feedback, and newer review progress.
- Build scripts check for a Tkinter-capable Python before packaging, with PyInstaller as the current stable Windows app-folder path and Nuitka kept as an alternate script to revisit.
- Build scripts generate the MemoryPal `.ico` during packaging, pass it to Nuitka or PyInstaller, and bundle the reusable icon assets into the app folder.
- Inno Setup installer script and command file for making a user-friendly Windows setup file.
- The latest desktop build separates core paths, models, storage, planning, and study helpers into `latest_app/memorypal/`.

## Development History

The `development_versions/` folder contains standalone milestone prototypes that show the feature path of the project. They are not exact saved snapshots from every tiny edit, but each file represents a real stage in how the app grew.

The latest milestone file is:

```text
development_versions/MemoryPal_v29_beta_page_draft_preservation.py
development_versions/MemoryPal_v30_beta_profiles_planning_stats.py
development_versions/MemoryPal_v31_beta_repetition_player_polish.py
development_versions/MemoryPal_v32_beta_collapsible_nav_document_notes.py
development_versions/MemoryPal_v33_release_candidate.py
development_versions/MemoryPal_v34_beta_modern_dialogs.py
development_versions/MemoryPal_v35_test_speech_to_text.py
development_versions/MemoryPal_v44_beta_memory_gym_fades.py
development_versions/MemoryPal_v45_beta_memory_games.py
development_versions/MemoryPal_v46_beta_fullscreen_icon_polish.py
development_versions/MemoryPal_v47_beta_custom_navigation_stats.py
development_versions/MemoryPal_v48_beta_stable_transitions_soft_themes.py
development_versions/MemoryPal_v49_beta_no_reload_focus_nav.py
development_versions/MemoryPal_v50_beta_nav_alignment_antialias.py
development_versions/MemoryPal_v51_beta_soft_fade_logo_polish.py
development_versions/MemoryPal_v52_beta_capture_scroll_resize_fade.py
development_versions/MemoryPal_v53_beta_element_fade_logo_fix.py
development_versions/MemoryPal_v54_beta_logo_assets.py
development_versions/MemoryPal_v55_beta_testing_feedback_installer.py
development_versions/MemoryPal_v56_beta_safe_saves_fast_build.py
development_versions/MemoryPal_v57_beta_motion_startup_icon_polish.py
development_versions/MemoryPal_v58_beta_clean_startup_release_prep.py
development_versions/MemoryPal_v59_beta_transition_launch_polish.py
development_versions/MemoryPal_v60_beta_stable_motion_followup.py
development_versions/MemoryPal_v61_beta_fixed_rail_fullscreen_stability.py
development_versions/MemoryPal_v62_beta_concurrent_save_stability.py
development_versions/MemoryPal_v63_beta_header_release_polish.py
development_versions/MemoryPal_v64_beta_low_end_readiness.py
development_versions/MemoryPal_v65_beta_macos_packaging.py
development_versions/MemoryPal_v66_beta_accessibility_elder_support.py
v67 beta - onboarding, read aloud, and planning (live app only; see VERSION_JOURNAL.md)
v68 beta - dashboard, charts, navigation, media, and new logo (live app only; see VERSION_JOURNAL.md)
v69 beta - in-app feedback sending, resize outline, and smoothness fixes (live app only; see VERSION_JOURNAL.md)
assets/memorypal.ico
assets/memorypal-logo-preview.png
assets/memorypal-logo.svg
latest_app/memorypal/
latest_app/MemoryPalDesktop.py
```

## Mobile Version

The phone app lives in `mobile/` and is built with React Native and Expo. To try it, install Expo Go on a phone, then run:

```powershell
cd mobile
npm install
npx expo start
```

Scan the QR code to open it. `mobile/README.md` covers tests, structure, and the parity checks that keep it in step with the desktop logic.

The older `mobile_app/` folder contains the first Kivy prototype, kept as history. It keeps the core card, review, repetition, and resources flow touch-friendly, with simple app-styled feedback for empty prompts and saved cards. A finished mobile app still needs native phone APIs for microphone recording, camera/video recording, file picking, permissions, storage, and large touch controls. The desktop Tkinter interface should guide the feature set, but the mobile UI should be redesigned for touch.
