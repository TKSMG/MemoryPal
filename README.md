# MemoryPal

## Project Note

I built MemoryPal as a desktop memory trainer for learners, older adults, and anyone who benefits from calm, structured recall practice. The main idea was to put several useful memory techniques in one place without making the program feel heavy or complicated.

This version is a Python/Tkinter desktop app. It is meant to show the working concept clearly while the mobile version is still in prototype form.

## Project Files

- Latest app: `latest_app/MemoryPalDesktop.py`
- Desktop support package: `latest_app/memorypal/`
- App icon exports: `assets/memorypal.ico`, `assets/memorypal-logo-preview.png`, `assets/memorypal-logo.svg`
- Testing checklist: `TESTING_CHECKLIST.md`
- Build notes: `BUILDING_APP.md`
- Design notes: `DESIGN_NOTES.md`
- Memory techniques notes: `notes/MemoryPal_Memory_Techniques.md`
- Python project config: `pyproject.toml`
- Mobile prototype: `mobile_app/MemoryPalMobile.py`
- Development versions: `development_versions/`
- Version journal: `development_versions/VERSION_JOURNAL.md`
- Program outline: `development_versions/MemoryPal_Project_Outline.py`
- Desktop dependencies: `requirements-desktop.txt`
- Windows build dependencies: `requirements-build.txt`
- Windows build command: `build_windows.cmd`
- Windows installer command: `build_installer_windows.cmd`
- Clean build artifacts command: `clean_build_artifacts.cmd`
- Installer script: `installer/inno/MemoryPal.iss`
- Fallback PyInstaller build command: `build_pyinstaller_windows.cmd`
- GitHub Actions Windows build: `.github/workflows/build-windows.yml`
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

## Building An EXE

The Windows build path is documented in `BUILDING_APP.md`.

From this folder, run:

```powershell
.\build_windows.cmd
```

The default build uses Nuitka with Tkinter support enabled. It now creates a normal app folder at `release\MemoryPal\MemoryPal.exe`, which opens faster than a self-extracting one-file EXE. The build also bundles the checked-in icon assets so installed copies do not regenerate the app icon during startup. The release folder is ignored by Git so the repository stays focused on source code and documentation.
The fast tester build keeps desktop recording and text-to-speech packages optional, so normal launches do not carry large media libraries unless a special media-enabled build is made later.

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

For testers, package either `release\MemoryPalSetup.exe` plus the testing notes, or the whole `release\MemoryPal\` app folder plus the same notes.

If multiple Python installs exist, point MemoryPal's build scripts at the one with working Tkinter:

```powershell
$env:MEMORYPAL_PYTHON = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
.\build_windows.cmd
```

## Building macOS Packages

macOS app bundles must be built on macOS because `.app` packaging is platform-specific. The current repository keeps the desktop source portable, but the supported installer flow in this folder is Windows.

## Current Features

- Modern Tkinter desktop interface with a soft app header, local-save status, styled cue menus, hover feedback, and steadier page reveals.
- Page switches use a real alpha fade over only the content area, so redraws do not flash through and the app shell does not dim.
- Fullscreen, focus mode, and manual resize changes keep the active page alive and use a short content-only settling fade after the new size lands.
- Sidebar collapse and reopen animate the rail width while preserving the active page and avoiding clipped long labels mid-motion.
- App-styled modal dialogs for profile names, recording lengths, alerts, confirmations, and errors.
- Refreshed generated MemoryPal app icon for the Windows title/taskbar icon, custom title strip, packaged executable, and exported project assets.
- The mobile prototype also uses in-app validation and confirmation modals instead of silent or system-style feedback.
- Collapsible left navigation rail for focus mode, with compact labels, a cleaner capsule toggle, hover hints, and its own scroll area for smaller screens.
- Settings page can reorder the main navigation pages per profile.
- Settings page for theme, navigation, profiles, daily goal, storage, backups, reset, focus mode, and true fullscreen.
- Settings stays pinned at the bottom of the navigation rail so the header has more room for status and profile controls.
- Window controls separate true fullscreen from borderless focus mode: F11 uses true fullscreen, while the app buttons use focus mode.
- Windowed page changes, theme changes, and interface rebuilds use matching same-theme covers to hide redraw flashes without the older strip-opening effect.
- Collapsing or reopening the navigation rail now redraws only the rail, so the active study page and unsaved work stay in place.
- Fullscreen and focus changes preserve the active page instead of rebuilding the interface.
- Custom window resizing applies after the user releases the resize grip, then gives the content area a short same-color reveal.
- Custom titlebar, navigation, and button shapes use optional Pillow-backed antialiasing when Pillow is installed, with a normal Tk fallback.
- The titlebar and left navigation use the same generated MemoryPal logo artwork.
- The generated logo renders directly through Tk, so the rail mark and titlebar mark stay consistent even without Pillow.
- The desktop launcher now relies on the split `latest_app/memorypal/` package instead of carrying a second stale copy of models, storage, parsing, and planning code.
- Profile config reads, generated logo pixels, and antialiased UI shapes are cached so normal shell rebuilds do less repeat work.
- File dialogs, CSV export, browser opening, desktop recording, webcam recording, and text-to-speech load only when those features are used.
- The main desktop window is resizable from the right edge, bottom edge, and corner while keeping the custom app chrome and DPI-scaled title bar controls.
- More forgiving responsive button rows and Study Plan controls for larger DPI/text scaling.
- Separate local profiles, so different learners or study areas can keep independent data.
- Local saves merge newly added cards, captures, feedback, and review counters so two open windows are less likely to overwrite each other's work.
- App data uses a platform-correct local data folder with non-destructive migration from the older home-folder location.
- Dark and light appearance modes.
- In-progress page drafts for Capture, Repetition, Test Lab, Quiz, Associations, and Puzzles while switching sections.
- Study Plan page that builds a short session plan from time, goal, deck choice, and preferred study habits.
- Stats page with daily goal editing, streaks, activity heatmap, and upcoming review preview.
- Stats page includes weekly pace, active-day count, best-day signal, weak-card count, daily goal, streaks, and heatmap.
- Feedback Log page for tester ratings, bug notes, confusing moments, accessibility comments, and CSV export.
- Focus queue for due, weak, and fresh cards.
- Dashboard next-step recommendations, mastery progress, due/learning/mastered chips, and a small daily-action prompt.
- Memory Gym page with separate student-study and everyday-memory practice paths.
- Chunk-based capture, with each study bit stored separately.
- Capture has horizontal scrolling for the two-column set builder, so the right-side captured/cue panel remains reachable on smaller or scaled windows.
- Note/document imports for `.txt`, `.md`, `.csv`, `.docx`, and PDFs when a PDF reader library is available.
- Imported note/document text can be extracted into the study bit box and turned into decks/cards.
- Separate question/title and answer boxes for prompt-answer cards.
- Optional self-check cards without a saved answer.
- Text, image, audio, and video cues attached to study material where useful.
- Text previews, image previews when supported, and clear play/open buttons for audio or video cues.
- Compact resource strips on major study pages so attached notes, audio, images, and videos stay reachable while planning or practicing.
- Compact cue menus for text, image, audio, and video imports or recordings.
- Test Lab for focused answering, revealing, Smart Check, bucket highlighting, and review scheduling.
- Review quality shortcuts, skip-for-today, undo last rating, and leech warnings for repeatedly missed cards.
- Smart Check for close-enough typed responses.
- Repetition Path with separate prompt and answer fields, staged items, a focused round player, and the clarified pattern: `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Quick Quiz with self-check and multiple-choice modes.
- Association tools for acronyms, mini-stories, peg lists, memory palace routes, chunk maps, link chains, and practical technique plans.
- Technique planning for retrieval practice, spaced practice, interleaving, elaboration, concrete examples, dual coding, and spaced retrieval.
- Puzzles for Sequence Recall, Word Recall, Pair Recall, Missing Item, Visual Search, N-Back Lite, Category Sort, and Routine Recall practice.
- Library search with All, Due, Weak, and Captures filters.
- Pointer-aware page scrolling plus keyboard scrolling with Page Up, Page Down, Home, and End.
- Saves are written atomically and merge with existing local data so two open MemoryPal windows are less likely to overwrite each other's newly added cards, captures, or feedback.
- Build scripts check for a Tkinter-capable Python before packaging, with Nuitka as the recommended Windows app-folder path and PyInstaller kept as a fallback.
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
assets/memorypal.ico
assets/memorypal-logo-preview.png
assets/memorypal-logo.svg
latest_app/memorypal/
latest_app/MemoryPalDesktop.py
```

## Mobile Version Note

The `mobile_app/` folder now contains a Kivy prototype for Android and iOS planning. It keeps the core card, review, repetition, and resources flow touch-friendly, with simple app-styled feedback for empty prompts and saved cards. A finished mobile app still needs native phone APIs for microphone recording, camera/video recording, file picking, permissions, storage, and large touch controls. The desktop Tkinter interface should guide the feature set, but the mobile UI should be redesigned for touch.
