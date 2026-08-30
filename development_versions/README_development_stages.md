# MemoryPal Development Versions

This folder contains standalone milestone versions of MemoryPal. Each `MemoryPal_vXX_*.py` file is an independent Python/Tkinter program and can be run by itself.

The versions are reconstructed from the project history. They are not exact saved snapshots from every edit, because the earliest states were not preserved as separate files, but each one represents a meaningful development stage.

## Current Full App

The current full recovered app is:

`../latest_app/MemoryPalDesktop.py`

It includes DPI-aware scaling, chunk-based capture, prompt-answer modes, smart checking, repetition paths, text/image/audio/video file imports, and on-demand text/audio/video capture controls.
It also includes profiles, study planning, stats, dark/light themes, review repair controls, and a focused Repetition round player.
The newest build adds a collapsible navigation rail, document-note importing, resource strips on study pages, and improved scaling on Study Plan and shared button rows.
The release-prep build adds testing notes, Windows build instructions, and a mobile prototype path.
The latest desktop UI uses a calm fade-in page transition instead of the older skeleton/slide reveal.

## How to Run a Version

Open a terminal in this folder and run:

```powershell
python MemoryPal_v14_test_walkback_repetition.py
```

If `python` is not on PATH, use the Python interpreter installed on the PC and pass it the file path.

## Version History

### v01 Alpha - Initial runnable PC app

- Created the first runnable desktop app.
- Established the memory trainer idea with capture, review, quiz, associations, puzzles, and library areas.

### v02 Alpha - Scaled UI resolution

- Increased the window and control sizes.
- Added DPI-aware setup so the UI looks sharper on scaled Windows displays.

### v03 Alpha - Multiple study bits and newline parsing

- Added parsing for `/n`, real newlines, numbering, and separators.
- Made revision work with several small bits of information instead of one long text field.

### v04 Alpha - Media support beyond flashcards

- Added image and audio import controls to the capture flow.
- Media cues became part of the study material rather than flashcard-only extras.

### v05 Beta - First modern UI pass

- Replaced the plain form feeling with modern dashboard cards.
- Improved color, spacing, and large action buttons.

### v06 Beta - Removed decorative animation

- Removed the distracting decorative animation.
- Kept the interface calm and predictable for learners and elderly users.

### v07 Beta - Structured non-random revision path

- Changed shuffle from random order into an intentional revision path.
- The prototype previews the order before the user starts.

### v08 Beta - Notesheet and design artifacts

- Added memory technique project notes.
- Added design/development documentation alongside the code.

### v09 Test - Home button scaling fixes

- Fixed dashboard button scaling and clipping.
- The prototype uses equal-width action cards to behave better in smaller windows.

### v10 Test - Start/range repetition and smart checking

- Added start/range repetition controls.
- Added close-enough Smart Check scoring with suggested repetitions.

### v11 Test - Text, image, audio, and video support

- Added text, image, audio, and video import concepts.
- Media cues are shared by the study item rather than locked to one mode.

### v12 Test - Chunk-based capture and card creation

- Changed capture into a study-set builder.
- Each chunk can become its own card.

### v13 Test - Scrollable practice and capture screens

- Added scrollable long forms.
- Buttons remain reachable when the window is smaller.

### v14 Test - Final walk-back repetition rule

- Implemented the clarified pattern: start `5`, range `3` gives `5`, `5-4`, `5-4-3`, then `3-2-1`.
- The version focuses on the exact repetition behavior requested.

### v15 Beta - Modernized dashboard and shell

- Polished the app shell and dashboard cards.
- Improved hierarchy so the interface feels more like a deliberate app.

### v16 Test - Prompt-answer practice modes

- Added question/title prompt-first practice.
- Users can reveal or Smart Check without a fixed number of repetition rounds.

### v17 Test - Imported and on-demand text/audio/video inputs

- Added file-import and on-demand capture controls for text, audio, and video.
- The desktop prototype supports text-note recording directly and prepares audio/video recording for optional desktop dependencies and a future mobile build.

### v18 Beta - Study-app polish pass

- Added a Focus queue for due, weak, and fresh cards.
- Improved the dashboard, direct Q/A card creation, and library search/filtering to better match what users expect from a study app.

### v19 Beta - Interaction and capture polish

- Added separate question and answer boxes for exact prompt-answer card creation.
- Improved answer input panels and added a subtle section transition animation.

### v20 Beta - Review testing and Q/A polish

- Added optional saved answers for question cards and a separate Test Lab page.
- Smart Check now visually highlights the selected bucket, and mini-story generation creates ordered memory scenes.

### v21 Test - Pointer-aware page scrolling

- Improved scrolling so the mouse wheel works over the active page section instead of requiring the scrollbar area.
- Nested scroll areas now scroll the section under the pointer.

### v22 Beta - Test Lab review flow

- Review now launches cards into Test Lab instead of doing answer/reveal inline.
- Test Lab can complete review scheduling, and self-check quiz cards can open there too.

### v23 Beta - Learning app polish

- Remade the dashboard around a clear next action, mastery progress, and a compact daily study prompt.
- Added hover hints, cleaner learner queue cues, and a warmer Test Lab guide while preserving the existing capture, media, review, repetition, quiz, and library features.

### v24 Beta - Accessible repetition and media polish

- Changed Repetition Path to use separate question/title and answer boxes, matching the Set Builder style instead of relying on one prompt-answer field.
- Decluttered Set Builder media controls so audio and video each use one button, with import or record chosen after clicking.
- Added clearer quiz/practice guide panels, extra hover hints, and a smoother page reveal animation.

### v25 Test - Final scroll and UX polish

- Fixed the Repetition scaling issue by making the builder, staged items, controls, and generated rounds one continuous scrollable page.
- Stacked the Repetition prompt and answer fields to reduce cramped text on smaller windows.
- Added keyboard-friendly scrolling with Page Up, Page Down, Home, and End on scrollable pages.

### v26 Beta - Puzzles and cue menus

- Expanded Puzzles into Sequence Recall, Word Recall, Pair Recall, and Missing Item.
- Replaced Set Builder's larger media rows with compact cue menu buttons for text, image, audio, and video.
- Audio and video import/record choices now open from the cue button instead of a separate dialog.

### v27 Beta - Cue previews, associations, and skeleton loading

- Study cues now render inside review/testing surfaces with text previews, image previews when supported, and play buttons for audio/video.
- Expanded Associations with peg lists, memory palace routes, chunk maps, and link chains.
- Replaced the older page wipe with a skeleton-style loading screen and small spinner.

### v28 Beta - App feel visual polish

- Warmed up the visual system with a softer palette, app-like header, and local-save status chip.
- Restyled buttons, menu buttons, entries, and scrollbars to reduce the stock desktop feel while keeping the app fast.
- Added hover-highlight behavior to key dashboard cards and softened filled button feedback.

### v29 Beta - Page draft preservation

- Added in-memory draft saving before page switches.
- Capture, Repetition, Test Lab, Quiz, Associations, and Puzzles restore in-progress work when the user returns.
- Drafts are cleared where appropriate after a capture is saved or a review is scheduled.

### v30 Beta - Profiles, planning, and stats

- Added separate local profiles so different learners or study areas can keep independent data.
- Added a Study Plan page that turns available time, deck choice, goal, and study habits into a short session plan.
- Added stats features such as daily goal editing, streaks, activity history, upcoming reviews, and stronger dashboard progress signals.

### v31 Beta - Repetition player polish

- Changed Repetition Path output from a long generated stack into a focused round-by-round player.
- Added round progress, previous/next controls, current-prompt grouping, Smart Check, reveal, and bucket feedback inside the player.
- Kept the requested start/range behavior while making the exercise easier to use on smaller screens.

### v32 Beta - Collapsible navigation and document notes

- Added a focus-friendly collapsible left navigation rail with compact labels, hover hints, and different open/closed toggle colors.
- Reworked Study Plan controls and shared button rows so larger scaling does not cut off important actions.
- Added note/document importing for text, Markdown, CSV, Word `.docx`, and PDFs when a PDF reader is available.
- Added compact resource strips so saved notes, audio, images, and video cues remain reachable from major study pages.

### v33 Release candidate - Testing, build, and mobile start

- Added a release testing checklist for first run, capture, review, repetition, planning, library, resources, and accessibility checks.
- Added Windows build instructions, dependency files, and a `build_windows.cmd` helper for making `MemoryPal.exe`.
- Added a Kivy mobile prototype that carries the core MemoryPal flow toward iOS and Android.
- Added light comments to the main desktop code where future maintenance needs orientation.

### v34 Beta - Modern dialogs

- Replaced old stock Tk prompts and message boxes with app-styled MemoryPal modal dialogs.
- Updated profile naming, daily goal editing, recording length prompts, reset confirmation, media errors, import errors, and optional-feature warnings.
- Aligned the mobile prototype and applicable later milestone files so app-owned feedback does not fall back to old system message boxes.
- Kept native file pickers for file selection while making app-owned decisions feel visually consistent.

### v35 Test - Speech-to-text capture

- Added a standalone desktop prototype for microphone dictation and audio-file transcription.
- Transcripts can be inserted into separate question and answer boxes, edited, and saved as normal study cards.
- Speech recognition stays optional, with a clear in-app message when the needed packages are not installed. The default recognizer may need an internet connection.

## Mobile Version Note

A separate production mobile version is still needed later. The Kivy prototype in `mobile_app/` is a starting point, but the finished app should use native phone APIs for the microphone, camera, file picker, storage permissions, and large touch controls instead of copying the desktop Tkinter interface directly.
