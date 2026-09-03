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
The latest desktop UI uses a steady same-theme page cover for page switches, while fullscreen/focus and sidebar collapse preserve the active page instead of rebuilding it.
The newest polish pass changes transition fades from whole-window opacity to content/root overlay reveals, keeping the app shell solid while elements appear.
The current project structure moves paths, models, storage, planning, and study helpers into `../latest_app/memorypal/` so the desktop entry point is no longer responsible for every layer of the app.

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

### v36 Beta - Modular project structure

- Moved paths, models, storage, planning, and study helpers into the `memorypal` package.
- Added platform-correct app data storage, `pyproject.toml`, Taskfile notes, and GitHub Actions build support.
- Kept the desktop launcher as the simple file to run while making the codebase easier to maintain.

### v37 Beta - Custom window chrome and flash polish

- Replaced old native-looking title bars with MemoryPal-styled chrome for the main window and app-owned popups.
- Added startup and popup fade-ins, fuller window controls, and custom resize grips.
- Preserved normal desktop usability while improving the app's visual identity.

### v38 Beta - Settings and window controls

- Added Settings for theme, navigation, profiles, daily goal, storage, backup, reset, focus mode, and fullscreen.
- Separated true fullscreen from borderless focus mode.
- Added taskbar-presence handling so MemoryPal behaves more like its own Windows app when launched normally.

### v39 Beta - Settings access and fade polish

- Added easier Settings access and improved the navigation collapse control.
- Restored same-color covers around page, focus, fullscreen, resize, and rebuild moments.
- Improved scaling around the title bar and compact controls.

### v40 Beta - Stable fullscreen polish

- Simplified fullscreen and focus transitions to avoid freezing while Windows changes display state.
- Removed risky overlay behavior from fullscreen enter and exit.
- Kept the app responsive while hiding resize flashes with a same-color blocker.

### v41 Beta - Softer transition pass

- Removed the floating Settings cog after it created a square artifact in Tkinter.
- Kept Settings in the header and the pinned bottom navigation item.
- Softened the transition system without fading the entire app window.

### v42 Beta - Fade cover balance

- Brought back real fading covers for normal windowed page switches and interface rebuilds.
- Kept fullscreen and focus mode steadier during the actual resize operation.
- Improved the balance between visual polish and app stability.

### v43 Beta - Page flash fix

- Replaced a flashing page overlay with an in-app same-color veil.
- Prevented the whole app from blinking during quick navigation.
- Marked the final strip-reveal attempt before the current fade pass.

### v44 Beta - Memory Gym and softer fades

- Added the standalone `MemoryPal_v44_beta_memory_gym_fades.py` milestone.
- Added Memory Gym as a clearer hub for student study and everyday memory practice.
- Added technique planning plus Visual Search and N-Back Lite to the latest desktop app.

### v45 Beta - Everyday memory games

- Added the standalone `MemoryPal_v45_beta_memory_games.py` milestone.
- Added Category Sort and Routine Recall for gentle everyday-memory practice.
- Restored fading page covers while already in fullscreen or focus mode, while keeping fullscreen enter and exit stable.

### v46 Beta - Fullscreen and icon polish

- Added the standalone `MemoryPal_v46_beta_fullscreen_icon_polish.py` milestone.
- Debounced fullscreen and focus transitions so repeated clicks or F11 presses do not stack window-manager calls.
- Removed double-cover transitions during shell rebuilds such as theme, navigation, and profile changes.
- Added a generated MemoryPal icon for the app window, custom title strip, Windows build scripts, and GitHub Actions packaging.

### v47 Beta - Custom navigation and stats rhythm

- Added the standalone `MemoryPal_v47_beta_custom_navigation_stats.py` milestone.
- Forced transition covers to render before page rebuilds and removed the color-flash fallback that made some page switches feel odd.
- Added per-profile page ordering in Settings with Move Up, Move Down, Apply Order, and Reset Order controls.
- Changed the header into a title row plus a control row so page titles do not crowd streak, daily goal, profile, settings, or backup controls.
- Added Stats rhythm cards for this week, active days, best day, and weak-card attention.

### v48 Beta - Stable transitions and soft themes

- Added the standalone `MemoryPal_v48_beta_stable_transitions_soft_themes.py` milestone.
- Replaced page-level top-window fade covers with in-window same-theme covers so page switches do not flash, blink, or briefly show half-built content.
- Removed the duplicate header Settings button and kept Settings pinned in the left navigation rail.
- Softened both dark and light palettes so cards, inputs, borders, and status chips feel calmer.

### v49 Beta - No-reload focus and navigation

- Added the standalone `MemoryPal_v49_beta_no_reload_focus_nav.py` milestone.
- Changed navigation collapse/reopen so only the left rail is redrawn.
- Changed fullscreen and focus toggles so they preserve the active page instead of adding a full-window cover.
- Kept the no-flash page-switch behavior from v48.

### v50 Beta - Navigation alignment and antialiasing

- Added the standalone `MemoryPal_v50_beta_nav_alignment_antialias.py` milestone.
- Centered the expanded navigation collapse capsule.
- Added optional Pillow-backed antialiasing for custom titlebar buttons, the app mark, and the navigation toggle.
- Kept a normal Tk drawing fallback so the app remains runnable without optional image dependencies.

### v51 Beta - Soft fade and logo polish

- Added the standalone `MemoryPal_v51_beta_soft_fade_logo_polish.py` milestone.
- Reintroduced a gentle startup-style opacity reveal for page switches, resize release, navigation collapse, focus mode, and fullscreen.
- Kept the no-reload behavior for focus and navigation changes.
- Replaced the large rail letter mark with the generated MemoryPal logo artwork when Pillow is available.

### v52 Beta - Capture scroll, resize release, and fade tuning

- Added the standalone `MemoryPal_v52_beta_capture_scroll_resize_fade.py` milestone.
- Added horizontal scrolling to the Capture page so the right-side captured/cue panel remains accessible.
- Changed custom resizing so the window resizes after the user releases the grip.
- Made page/layout fades more visible by fading after the same-theme cover comes off.
- Removed the navigation collapse toast while keeping notifications for real user actions.
- Matched the titlebar and navigation logo artwork when image support is available.

### v53 Beta - Element fade and logo fix

- Added the standalone `MemoryPal_v53_beta_element_fade_logo_fix.py` milestone.
- Replaced whole-window opacity changes during page/layout transitions with temporary overlay reveals.
- Kept startup and popup fade behavior, since those are separate windows and do not dim an already-visible shell.
- Rendered the generated MemoryPal logo directly through Tk for the titlebar and navigation mark.

### v54 Beta - Logo assets

- Added the standalone `MemoryPal_v54_beta_logo_assets.py` milestone.
- Added reusable logo exports in `../assets/`: `.ico`, PNG preview, and SVG.
- Updated the desktop app to prefer the checked-in `.ico` while keeping generated-icon fallback behavior.
- Added a small export entry point in `latest_app/memorypal/icon.py` for refreshing the icon assets later.

## Mobile Version Note

A separate production mobile version is still needed later. The Kivy prototype in `mobile_app/` is a starting point, but the finished app should use native phone APIs for the microphone, camera, file picker, storage permissions, and large touch controls instead of copying the desktop Tkinter interface directly.
