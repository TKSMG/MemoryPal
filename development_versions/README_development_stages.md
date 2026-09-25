# MemoryPal Development Versions

This folder contains standalone milestone versions of MemoryPal. Each `MemoryPal_vXX_*.py` file is an independent Python/Tkinter program and can be run by itself.

The versions are reconstructed from the project history. They are not exact saved snapshots from every edit, because the earliest states were not preserved as separate files, but each one represents a meaningful development stage.

## Current Full App

The current full recovered app is:

`../latest_app/MemoryPalDesktop.py`

It includes DPI-aware scaling, chunk-based capture, prompt-answer modes, smart checking, repetition paths, text/image/audio/video file imports, and on-demand text/audio/video capture controls.
It also includes profiles, study planning, stats, dark/light themes, review repair controls, and a focused Repetition round player.
The newest build keeps the navigation rail expanded, adds document-note importing, resource strips on study pages, and improved scaling on Study Plan and shared button rows.
The release-prep build adds testing notes, Windows build instructions, and a mobile prototype path.
The latest desktop UI uses steady same-theme covers for page switches, fullscreen, focus, and resize release, while the fixed navigation rail avoids collapse-related redraw glitches.
The newest polish pass changes transition fades from whole-window opacity to content/root overlay reveals, keeping the app shell solid while elements appear.
The current project structure moves paths, models, storage, planning, and study helpers into `../latest_app/memorypal/` so the desktop entry point is no longer responsible for every layer of the app.
The newest stability pass keeps newer saved review progress when two open windows save at different times.
The latest header pass separates status chips from actions and turns the active profile into a numbered avatar control.
The newest packaging pass keeps Mac window behavior native, adds a macOS build script, and adds a GitHub workflow for Mac tester artifacts.
The newest accessibility pass adds an Everyday Memory section and profile-level accessibility preferences for older adults and caregiver-supported use.

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

### v55 Beta - Testing feedback and installer

- Added the standalone `MemoryPal_v55_beta_testing_feedback_installer.py` milestone.
- Added a Feedback Log page for tester ratings, bug notes, accessibility comments, and feature ideas.
- Saved feedback in the active profile data and added CSV export for longer testing periods.
- Made legacy data migration non-destructive so old home-folder data does not overwrite newer app-data edits.
- Added an Inno Setup installer script and `build_installer_windows.cmd`.

### v56 Beta - Safe saves and fast build

- Added the standalone `MemoryPal_v56_beta_safe_saves_fast_build.py` milestone.
- Added merge-before-save behavior so separate open windows can add cards, captures, and feedback without wiping each other out.
- Wrote profile data atomically through a temporary file to reduce the chance of corrupted JSON after interrupted saves.
- Changed the Windows build target from a slow one-file executable to a normal `release\MemoryPal\MemoryPal.exe` app folder.
- Updated the installer script to package the whole app folder instead of a single self-extracting executable.
- Removed blank/fade covers from fullscreen, focus mode, sidebar collapse, and custom resize so layout changes scale directly.
- Kept fade behavior for page switches and pop-up windows where it still feels intentional.

### v57 Beta - Motion, startup, and icon polish

- Added the standalone `MemoryPal_v57_beta_motion_startup_icon_polish.py` milestone.
- Removed the old duplicate models, helpers, and storage layer from the desktop launcher now that those pieces live in `latest_app/memorypal/`.
- Changed page transitions so the shell stays solid while only a same-color content cover fades away.
- Animated the navigation rail width instead of rebuilding the active page when the rail opens or closes.
- Kept optional audio, video, and text-to-speech packages out of the default tester build unless those features are installed separately.
- Refreshed the generated MemoryPal `.ico`, PNG preview, and SVG logo with a sharper connected-dot M and smoother exported edges.

### v58 Beta - Clean startup and release prep

- Added the standalone `MemoryPal_v58_beta_clean_startup_release_prep.py` milestone.
- Added `clean_build_artifacts.cmd` for clearing local release folders, build folders, Python caches, and MemoryPal-named temp build leftovers.
- Added profile-config caching so profile reads do less repeated disk work.
- Cached generated logo pixels and antialiased UI shapes so repeated titlebar, rail, and hover redraws are lighter.
- Moved file dialog, CSV export, browser opening, recording, webcam, and text-to-speech imports out of the startup path.
- Kept build scripts guarded by a real Tkinter window preflight so a broken Tcl/Tk Python does not create another broken EXE.

### v59 Beta - Transition and launch polish

- Added the standalone `MemoryPal_v59_beta_transition_launch_polish.py` milestone.
- Bundled the checked-in icon assets with the Windows app folder so installed builds do not regenerate icons during startup.
- Changed page switches back to a true alpha overlay over the content area instead of the coarse stipple cover.
- Changed fullscreen, focus, and custom resize to keep the active page alive and use a short content-only settling fade after the new size lands.
- Changed rail collapse so compact labels appear before the rail shrinks, preventing long labels from clipping through the animation.
- Increased antialiasing resolution for small custom titlebar, nav, and button shapes when Pillow is installed.

### v60 Beta - Stable motion follow-up

- Added the standalone `MemoryPal_v60_beta_stable_motion_followup.py` milestone.
- Changed page switches so a same-window reveal covers the full page panel, including the title/header, before the new page is built.
- Delayed the page-cover fade until after the new page has painted, avoiding the pop-in, pop-out, fade-back-in effect.
- Replaced fullscreen and focus post-resize fades with same-window reveal covers that hide native redraw flashes.
- Changed sidebar collapse and reopen to snap between final widths, then reveal the rail without repeated active-page reflow.

### v61 Beta - Fixed rail and fullscreen stability

- Added the standalone `MemoryPal_v61_beta_fixed_rail_fullscreen_stability.py` milestone.
- Removed the collapsible navigation control from the live desktop app.
- Kept the navigation rail expanded so page width does not shift during study.
- Removed root-window opacity fades from fullscreen and focus changes to avoid Windows/Tkinter freezing.
- Kept same-window covers around fullscreen, focus, resize release, and page switches so redraw flashes stay hidden.

### v62 Beta - Concurrent save stability

- Added the standalone `MemoryPal_v62_beta_concurrent_save_stability.py` milestone.
- Tracked the saved state of loaded cards, captures, and feedback before merging new saves.
- Kept newer on-disk card progress when another open window saves an unchanged stale copy later.
- Preserved the existing merge behavior for newly added cards, captures, feedback, daily activity, and navigation settings.
- Cleaned up Smart Check keyword stemming so missing-cue feedback does not make proper nouns look broken.
- Added a tester-package command for gathering the installer/app folder and notes into one zip after a build exists.

### v63 Beta - Header release polish

- Added the standalone `MemoryPal_v63_beta_header_release_polish.py` milestone.
- Split the header toolbar into left-side status chips and right-side app actions.
- Replaced the long active-profile button with a numbered profile chip on the top-right edge.
- Moved true fullscreen to F11 and Settings while keeping borderless focus on the titlebar square and Settings.
- Added Control-Command-F as a guarded macOS-style true fullscreen shortcut where Tk supports it.
- Changed startup logo rendering to load the packaged PNG first, with generated pixels kept only as a fallback.

### v64 Beta - Low-end readiness

- Added the standalone `MemoryPal_v64_beta_low_end_readiness.py` milestone.
- Debounced custom borderless-chrome restoration so startup, focus exit, and fullscreen exit do less repeated Tk idle work.
- Cached the optional Pillow drawing backend decision so source runs without image-preview extras do not keep retrying unavailable imports.
- Cached the startup logo asset lookup and kept generated icon pixels as a fallback for source-only runs.
- Fixed the PyInstaller fallback asset paths and made the default Windows tester build use the stable PyInstaller app-folder path after the fresh local Nuitka package failed its launch check.
- Rechecked page rendering, two-window save merging, source import timing, and temporary installer launch behavior for tester readiness.

### v65 Beta - macOS packaging

- Added the standalone `MemoryPal_v65_beta_macos_packaging.py` milestone.
- Added `build_macos.sh` for building a Mac `.app`, `.dmg`, and zipped app bundle on macOS.
- Added a GitHub Actions workflow that creates separate Intel and Apple Silicon Mac tester artifacts.
- Updated the live desktop app so macOS uses native window chrome instead of the custom borderless Windows chrome.
- Documented the beta Mac packaging limits, including the need for Developer ID signing and notarization before broad public distribution.

### v66 Beta - accessibility and elder support

- Added the standalone `MemoryPal_v66_beta_accessibility_elder_support.py` milestone.
- Added an Everyday Memory page for older adults, people with memory changes, and caregivers.
- Added profile-level accessibility preferences for larger text, higher contrast, reduced motion, simple language, and caregiver mode.
- Added a senior-friendly layout preset that moves Everyday Memory near the top and turns on calmer accessibility defaults.
- Added caregiver-friendly person, routine, place, and reminder card creation that feeds into the normal Test Lab review flow.

### v67 Beta - onboarding, read aloud, and smarter planning

- Recorded in the live app only; no separate standalone milestone file.
- Added a first-run Welcome screen with four personas (`memorypal/onboarding.py`) that set page order, text size, and accessibility defaults, plus a replayable guided tour.
- Added offline read aloud through the operating system voice (`memorypal/speech.py`) and a More time accessibility setting.
- Moved the Associations generators into `memorypal/techniques.py` and made pegs, palace spots, and story scenes unique on long lists; the acronym tool now suggests an acrostic sentence.
- Improved review scheduling with hard/good/easy steps, credit for late-but-remembered cards, load spreading, and a one-year cap.
- Added multi-day Study Plans that project due cards per day, expanding review days for new material, and a light final day before a test.
- Changed Smart Check to score against the saved answer only.
- Added the first `unittest` suite in `latest_app/tests/`.
- Removed white flashes after finishing or skipping the Welcome screen and between tour steps by reusing the resize snapshot method (`run_hidden_change`).
- Added `build_release_windows.cmd` and `TESTER_START_HERE.md`, and trimmed the tester zip to tester-facing files. Release version bumped to 0.43.0.

### v68 Beta - dashboard, charts, navigation, media, and new logo

- Recorded in the live app only; no separate standalone milestone file.
- Rebuilt the Dashboard around today's saved study plan (tick-off steps), a greeting and best next action, a streak/level/XP progress strip, persona study modes, and the next badge (`memorypal/progress.py`).
- Added Stats charts (30-day activity, two-week forecast, card maturity, answer mix, weekday rhythm, deck mastery) and achievement badges.
- Added a Ctrl+K page finder, a header Back button with Alt+Left, and app-styled dropdowns.
- Made theme, text-size, and accessibility rebuilds use the screen-snapshot swap, and changed popups to appear fully drawn instead of fading.
- Added saved study plans (Make this my plan) with daily steps, Pomodoro rest breaks and a break timer, capped new-card steps, Explain it back, and Wrap up.
- Added package-free media on Windows (`memorypal/media.py`): audio recording with a level meter, playback, Camera app video capture, Windows Imaging previews, and spoken cue files.
- Added RTF and encoding-aware text import, better `.docx` reading, and a built-in PDF text reader (`memorypal/pdftext.py`).
- Made saves skip the merge when no other window has written, fixed undo counts after merges, and cached the logo master on disk.
- Redesigned the logo as a flatter connected "memory path" M with mint/amber nodes and a spark; updated `icon.py`, the `.ico`, a 1024px PNG, and the SVG, with a simplified mark at 32px and below.
- Added tests for documents, media, progress, planning, store, and the icon. Release version bumped to 0.44.0.

## Mobile Version Note

A separate production mobile version is still needed later. The Kivy prototype in `mobile_app/` is a starting point, but the finished app should use native phone APIs for the microphone, camera, file picker, storage permissions, and large touch controls instead of copying the desktop Tkinter interface directly.
