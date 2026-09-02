# MemoryPal

## Project Note

I built MemoryPal as a desktop memory trainer for learners, older adults, and anyone who benefits from calm, structured recall practice. The main idea was to put several useful memory techniques in one place without making the program feel heavy or complicated.

This version is a Python/Tkinter desktop app. It is meant to show the working concept clearly while the mobile version is still in prototype form.

## Project Files

- Latest app: `latest_app/MemoryPalDesktop.py`
- Desktop support package: `latest_app/memorypal/`
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
build_windows.cmd
```

The default build uses Nuitka with Tkinter support enabled. The built app should appear in `release\MemoryPal.exe`. The release folder is ignored by Git so the repository stays focused on source code and documentation.

GitHub Actions can also build the Windows app from `.github/workflows/build-windows.yml` and upload it as an artifact.

## Current Features

- Modern Tkinter desktop interface with a warm app header, local-save status, styled cue menus, hover feedback, and calm fade-in page transitions.
- Page transitions use a matching color cover so content fades in without a white flash.
- App-styled modal dialogs for profile names, recording lengths, alerts, confirmations, and errors.
- The mobile prototype also uses in-app validation and confirmation modals instead of silent or system-style feedback.
- Collapsible left navigation rail for focus mode, with compact labels and hover hints.
- More forgiving responsive button rows and Study Plan controls for larger DPI/text scaling.
- Separate local profiles, so different learners or study areas can keep independent data.
- App data uses a platform-correct local data folder with automatic migration from the older home-folder location.
- Dark and light appearance modes.
- In-progress page drafts for Capture, Repetition, Test Lab, Quiz, Associations, and Puzzles while switching sections.
- Study Plan page that builds a short session plan from time, goal, deck choice, and preferred study habits.
- Stats page with daily goal editing, streaks, activity heatmap, and upcoming review preview.
- Focus queue for due, weak, and fresh cards.
- Dashboard next-step recommendations, mastery progress, due/learning/mastered chips, and a small daily-action prompt.
- Chunk-based capture, with each study bit stored separately.
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
- Association tools for acronyms, mini-stories, peg lists, memory palace routes, chunk maps, and link chains.
- Puzzles for Sequence Recall, Word Recall, Pair Recall, and Missing Item practice.
- Library search with All, Due, Weak, and Captures filters.
- Pointer-aware page scrolling plus keyboard scrolling with Page Up, Page Down, Home, and End.
- Build scripts check for a Tkinter-capable Python before packaging, with Nuitka as the recommended Windows EXE path and PyInstaller kept as a fallback.
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
latest_app/memorypal/
```

## Mobile Version Note

The `mobile_app/` folder now contains a Kivy prototype for Android and iOS planning. It keeps the core card, review, repetition, and resources flow touch-friendly, with simple app-styled feedback for empty prompts and saved cards. A finished mobile app still needs native phone APIs for microphone recording, camera/video recording, file picking, permissions, storage, and large touch controls. The desktop Tkinter interface should guide the feature set, but the mobile UI should be redesigned for touch.
