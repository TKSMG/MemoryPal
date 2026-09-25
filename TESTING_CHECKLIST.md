# MemoryPal Testing Checklist

This checklist is for getting MemoryPal ready to show and eventually turn into a real packaged app.

## Automated Tests

- Run `python -m unittest discover -s latest_app\tests` and confirm every test passes.
- Confirm the test run does not create or change anything in `%LOCALAPPDATA%\MemoryPal`.

## Welcome And Tour

- Create a brand-new profile and confirm MemoryPal opens on the Welcome screen instead of the dashboard.
- Confirm an existing profile with saved cards goes straight to the dashboard and is not interrupted by the Welcome screen.
- Choose each persona (I'm studying, Help with everyday memory, I'm helping someone else, Just exploring) in turn and confirm the navigation order changes to match.
- Choose Help with everyday memory or I'm helping someone else and confirm text size defaults to Large and simple language, more time, and reduced motion are turned on as expected.
- Change the text size on the Welcome screen after picking a persona and confirm your choice is kept.
- Tick "read questions and answers aloud" and confirm the setting is on in Settings afterwards.
- Pick Start the Tour and step through every tour page; confirm each step opens the page it describes and the tour can be finished or closed.
- Pick Skip the Tour and confirm the dashboard opens.
- On Windows, press Skip the Tour and Start the Tour (try Large text too) and confirm there is no white flash, blank frame, or unstyled page before the new layout appears.
- Step through the tour with Next and Back and confirm each page and its tour card appear together with no white flash.
- Use Back, Next, Finish, and End Tour, then press the ? button at the top and confirm the tour starts again.
- In Settings > Welcome & tour, confirm the chosen persona is shown, Replay Tour works, and Redo Welcome Questions reopens the Welcome screen.
- Redo the Welcome questions with a different persona and confirm settings from the old persona do not stay stuck on.

## Read Aloud And More Time

- On a review card, press Read aloud and confirm the question is spoken using the built-in Windows voice.
- Reveal the answer and press Read answer aloud.
- Press Read aloud twice quickly and confirm the first reading stops instead of two voices overlapping.
- Turn on automatic read aloud in Settings and confirm new questions and revealed answers are read without pressing a button.
- Try a card with quotes, ampersands, or non-English letters and confirm it reads correctly without an error.
- On a PC with no voice installed, confirm a calm "Read aloud isn't available on this computer" message appears instead of a crash.
- Turn on More time and confirm timed puzzle displays and messages stay on screen about twice as long, and read aloud is slower.
- Confirm no console window flashes when read aloud starts in the packaged app.

## First Run

- Open `latest_app/MemoryPalDesktop.py`.
- Confirm the dashboard loads without errors.
- Confirm the app opens quickly enough for a short practice session instead of sitting on a long blank startup.
- Confirm a packaged Windows app opens to its first visible window in roughly a couple of seconds on a normal tester machine.
- Confirm repeated page changes, focus mode, fullscreen, and resize release do not leave stuck transition covers.
- Confirm page transitions affect only the page panel while the app shell/background stays steady.
- Confirm the title/taskbar icon uses the MemoryPal mark instead of the default Python/Tk icon.
- Confirm the main app uses the MemoryPal title strip instead of an old native-looking title bar.
- Confirm the app appears as its own taskbar item when launched normally.
- Confirm the right edge, bottom edge, and corner resize grips let the app resize when it is not in true fullscreen.
- Confirm data is created in the normal app-data folder, not directly in the home folder.
- If old `%USERPROFILE%\MemoryPalData` data exists, confirm it is copied into the new app-data profile folder without overwriting newer profile edits.
- Open two MemoryPal windows, add different cards in both, save both, reopen the app, and confirm both cards remain.
- In two MemoryPal windows, review a shared card in one window, add a new card in the other window, save both, and confirm the reviewed card keeps its newer score/repetition state.
- Switch between dark and light mode and confirm the app does not freeze, flash white, or keep old-theme colors stuck on screen.
- Confirm the left navigation rail stays expanded and no collapse control is shown.
- Type something into a page field, switch pages, return, and confirm the typed work is still there.
- Confirm the header status chips stay on the left and Theme, Backup, Settings, and profile controls stay aligned on the right.
- Confirm the top-right profile chip opens profile management and shows the active profile number.
- Confirm the top-right Theme, Backup, Settings, and profile controls are centered inside their square buttons in dark and light mode.
- Confirm the Dashboard action cards reflow from three columns on wide/fullscreen layouts down to two or one columns on smaller/scaled windows without hiding the bottom rows.
- Open Everyday Memory and confirm the Today board, gentle review button, caregiver card builder, starter cards, and care note are readable.
- Add a Person card, Routine card, Place card, and Reminder card from Everyday Memory, then confirm they appear in the Library under the Everyday Memory deck.
- Use Start Gentle Review from Everyday Memory and confirm it opens Test Lab with an everyday-memory card when one exists.
- On a shorter window, scroll inside the left navigation area and confirm every section stays reachable.
- Open each main page in a shorter window and confirm mouse wheel, Page Down, and End can reach the last control with a little bottom breathing room.
- Open Settings, move a page up/down in Page Order, apply the change, and confirm the left navigation updates.
- In Settings, change Accessibility text size to Large and Extra Large, then confirm the app rebuilds without clipping major controls.
- Turn on Higher Contrast and confirm muted labels, borders, inputs, and navigation remain clear in dark and light mode.
- Turn on Reduce Motion and confirm page switches and popups avoid unnecessary fades.
- Use Senior Layout and confirm Everyday Memory moves near the top of the navigation and accessibility options stay enabled.
- Reset Page Order and confirm the default navigation order returns.
- Open Settings from the pinned bottom navigation item.
- Resize the window smaller than fullscreen and check that no main button disappears.
- On Capture, resize the app narrower and confirm the horizontal scrollbar can reach the right-side captured/cue panel.
- Open profile, recording, reset, import-error, and media-error dialogs and confirm they match the MemoryPal visual style.
- Open the profile manager, create a profile, rename a profile, and confirm popups fade in without a white flash.
- Switch between several pages and confirm the same-theme cover hides redraw flashes without a strip-opening effect.
- Confirm page switches fade in cleanly instead of flashing after the new page is drawn.
- Confirm page/layout fades do not dim the entire app window; the background shell should stay solid while content appears.
- Press F11 and confirm it enters true fullscreen, then press Escape to exit.
- Use the Settings true fullscreen button and confirm it matches F11 behavior.
- Repeatedly press F11 a few times and confirm the app ignores overlapping fullscreen requests instead of freezing.
- Use the titlebar square button and confirm it uses borderless focus mode instead of true fullscreen.
- While editing a field, toggle true fullscreen and focus mode and confirm the current page is not rebuilt.
- Confirm fullscreen, focus mode, and resize release do not rebuild the active page or lose current field contents.
- Drag a custom resize grip and confirm a thin outline shows the new size while dragging, the window only changes after releasing the mouse, and the outline disappears afterwards.
- Toggle true fullscreen and focus mode from Settings and confirm the active page returns cleanly without a white flash, whole-window dim, freeze, or stuck cover.
- While already in true fullscreen, switch pages and confirm the page content changes without white flashes.
- Confirm fullscreen/focus changes do not freeze the app or leave a cover stuck on screen.
- Open Settings and confirm theme, navigation, profile manager, daily goal, storage folder, backup, import, and reset controls are reachable.
- Confirm the title bar controls and resize handles remain correctly sized at higher Windows display scaling.
- Confirm the custom titlebar buttons, header controls, profile chip, and app mark have smooth curved edges even when Pillow is not installed.
- If Pillow is installed, confirm the optional image-backed smoothing still looks clean around curved edges.
- Confirm the default packaged app includes Pillow for smoother custom UI edges but does not bundle heavy optional audio/video/TTS libraries.
- Confirm the left navigation mark uses the generated MemoryPal logo artwork instead of a plain letter.
- Confirm the titlebar mark and navigation mark look like the same MemoryPal logo.
- Confirm the new logo (white connected M with mint and amber nodes and a small spark on a blue-to-violet tile) appears in the titlebar, taskbar, navigation rail, Start Menu shortcut, installer, and desktop shortcut.
- At 16-32px (titlebar, taskbar) confirm the logo shows a clean white M without coloured speckles.
- If Windows still shows the old icon after installing, restart Explorer or sign out and in; Windows caches shortcut icons.
- Confirm `assets/memorypal.ico`, `assets/memorypal-logo-preview.png`, and `assets/memorypal-logo.svg` open as reusable project icon exports.
- After a Windows package is built, confirm `release\MemoryPal\assets\memorypal.ico` exists so installed copies do not regenerate icons during startup.
- Confirm the header and navigation logo appear immediately from packaged assets instead of causing a long startup delay.
- Confirm the header title stays on its own row and does not crowd the streak, daily goal, profile chip, settings, or backup controls.
- In the mobile prototype, try saving an empty card and a complete card; confirm both use in-app feedback instead of silent behavior.

## Windows Build

- Run `.\clean_build_artifacts.cmd` before the first fresh package attempt.
- Run `.\build_release_windows.cmd` and confirm it runs the tests, cleans, builds the app, builds the installer, and writes the tester zip without stopping.
- Or run `.\build_windows.cmd` from a normal Command Prompt or PowerShell window.
- Confirm the build output mentions PyInstaller and collects Tkinter support.
- Confirm the build output does not reject the generated `memorypal.ico` icon.
- Confirm the build output excludes unused optional media stacks unless a media-enabled build is being made.
- Confirm the script says it is using a Python install that can import Tkinter.
- Open `release\MemoryPal\MemoryPal.exe` and confirm the app loads without a `No module named 'tkinter'` error.
- Treat `.\build_nuitka_windows.cmd` as an alternate build path until the local Nuitka runtime crash is understood.
- After the app folder exists, run `.\build_installer_windows.cmd`; if prompted, allow the script to install Inno Setup with `winget`.
- Confirm `release\MemoryPalSetup.exe` is created and opens the normal MemoryPal installer flow with install-location, Start Menu, optional desktop shortcut, and launch-after-install.
- Run `.\package_for_testers.cmd` after the build and confirm `release\MemoryPalTesterPackage.zip` contains `MemoryPalSetup.exe`, the `MemoryPal\` app folder, `TESTER_START_HERE.md`, `TESTING_CHECKLIST.md`, `README.md`, and `notes\MemoryPal_Memory_Techniques.md`.
- Right-click `MemoryPalSetup.exe`, open Properties > Details, and confirm the version matches the current release.
- Install over an older MemoryPal and confirm existing cards and settings are kept.
- Zip either `release\MemoryPalSetup.exe` with the tester notes or the full `release\MemoryPal\` folder with the tester notes.
- In GitHub, run the `Build Windows App` workflow and confirm the `MemoryPal-Windows` artifact includes the app folder and installer when the workflow succeeds.

## macOS Build

- Run the `Build macOS App` workflow in GitHub Actions.
- Confirm the workflow creates separate `MemoryPal-macOS-Intel` and `MemoryPal-macOS-AppleSilicon` artifacts.
- On a Mac, download the matching artifact, open the `.dmg`, drag or copy `MemoryPal.app`, and launch it.
- If macOS blocks the unsigned beta build, right-click `MemoryPal.app`, choose Open, and confirm the app launches.
- Confirm the Mac app uses the normal macOS title bar instead of the custom Windows title strip.
- Press Control-Command-F and confirm true fullscreen behaves normally.
- Confirm page switching, resizing, dialogs, profile saves, and app-data storage behave like the Windows source run.
- Confirm the app icon appears in Finder, the Dock, and the app title area.
- Treat Developer ID signing, hardened runtime, notarization, and a polished signed DMG as required before wide public Mac distribution.

## Capture And Cards

- Add a study bit manually.
- Split pasted notes with new lines, numbered lists, `/n`, and semicolons.
- Add a question/title card with a saved answer.
- Add a question/title card without a saved answer.
- Import a `.txt`, `.md`, or `.csv` note and confirm the text appears in the study bit box.
- Import a `.docx` note and confirm readable text is extracted.
- Import a text-based PDF with no extra packages installed and confirm the built-in reader extracts the text.
- Import a scanned (image-only) PDF and confirm a clear no-text-layer message appears and the file is still attached.
- Import an `.rtf` file and a Notepad `.txt` saved as UTF-16 and ANSI, and confirm the text is readable.
- Import a `.docx` with tabs and line breaks and confirm they are kept.
- Attach image, audio, and video cues.
- Record an audio cue, watch the level meter move, stop, and play it back.
- Record a video with Record video: press Open Camera, record in the Camera app, then Use my recording, and confirm the video is attached.
- Attach JPEG, PNG, and WebP images (and HEIC if the Windows HEIF extension is installed) and confirm previews appear.
- Save a spoken cue as an audio file and play it.
- Run `development_versions/MemoryPal_v35_test_speech_to_text.py`; confirm it opens without speech packages installed and shows a clear unavailable message when dictation is requested.

## Study Modes

- Open Memory Gym and confirm the student-study and everyday-memory tracks are visible.
- Use Memory Gym buttons to open Test Lab, Review, Quiz, Associations, Capture, Cue Lab, Repetition, and Puzzles.
- Start a due card from Review and confirm it opens in Test Lab.
- Type a close answer and use Smart Check.
- Type the correct answer without repeating the question wording and confirm Smart Check still scores it as correct.
- Type an incorrect answer for a proper noun such as Paris and confirm the missing-cue text stays readable.
- Reveal and hide the saved answer.
- Use each rating button: Again, Review, Good, Easy.
- Test keyboard ratings `1`, `2`, `3`, `4`.
- Use Undo last rating after a review.
- Use Skip for today and confirm the card leaves the due queue.

## Repetition

- Add at least five repetition items.
- Set start to `5` and range to `3`.
- Confirm the pattern is `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Use Previous and Next Round.
- Smart Check a round and reveal the answer.

## Techniques And Puzzles

- In Associations, paste 12 or more ideas and generate a Peg list; confirm every idea gets a different peg and items past ten use a twist such as "giant golden".
- Generate a Memory palace for 25 or more ideas and confirm no two ideas share the same spot.
- Generate a Mini-story and confirm scenes are not reused for different ideas.
- Generate an Acronym and confirm it also shows an acrostic sentence.
- Separate ideas with commas, new lines, semicolons, pipes, and `/n`, and confirm each is split correctly.
- In Associations, build a technique plan for retrieval practice, spaced practice, interleaving, elaboration, concrete examples, dual coding, and spaced retrieval.
- In Puzzles, play Sequence Recall, Word Recall, Pair Recall, Missing Item, Visual Search, N-Back Lite, Category Sort, and Routine Recall.
- Confirm Visual Search marks only correct target tiles.
- Confirm N-Back Lite advances item by item and keeps score.
- Confirm Category Sort creates suggested groups from pasted or sample items.
- Confirm Routine Recall hides the shown steps and scores the typed recall attempt.

## Smoothness And Text

- On pages that add or remove rows (Capture, Study Plan, Feedback Log), confirm the section updates in one step without a flash or jump.
- Open a dialog, type straight away without clicking it, and confirm the text goes into the dialog. Close it and confirm typing goes back to the main window.
- Press and hold a flat button and confirm its text does not shift.
- Drag across text in a label, double-click a word, triple-click a line, press Ctrl+C, and paste elsewhere to confirm the copy worked.

## Navigation

- Press Ctrl+K, type part of a page name, use the arrow keys and Enter, and confirm the page opens. Press Escape to close the finder.
- Visit three pages, then press the header Back button and Alt+Left and confirm you step back through them. On the first page, confirm a friendly "nothing to go back to" message appears.
- Open several dropdowns (deck, goal, time unit) and confirm they open in the app's style, scroll with the mouse wheel, and close with Escape or a click outside.
- Change theme, text size, and Higher Contrast and confirm the interface swaps in one step with no white flash.
- Open dialogs and popups and confirm they appear already drawn, without fading or a blank first frame.

## Dashboard

- Confirm the Dashboard shows a greeting, the best next action, today's plan steps, the progress strip (streak, level, XP), study modes for your persona, and the next badge.
- Tick off a plan step, switch pages, return, and confirm it stays ticked for today.
- Try Quick 10 and one other study mode and confirm each opens the right page or plan.

## Planning And Progress

- Build a 60-minute plan with the rest-breaks habit and confirm a Rest break appears after about every 25 minutes (never at the very end) and the minutes still add up.
- Start a break from a plan and confirm a message appears when the break ends.
- With new cards waiting, confirm the plan includes a Learn new cards step capped at a sensible number.
- Tick the explain-in-my-own-words habit and confirm an Explain it back step appears.
- Press Make this my plan and confirm the Dashboard shows today's part of the plan; for a multi-day plan, confirm the day number is right and a finished plan says it is complete.
- Open Stats and confirm the 30-day chart, Coming up chart, card maturity bar, answer results, weekly rhythm, activity calendar, deck mastery, and achievements all show sensible values. Hover over chart bars to see their values.

- Build a minutes-based Study Plan.
- Build a days- or weeks-based Study Plan.
- In a multi-day plan, confirm each day shows a date, a day type, and the number of cards due on that day.
- Build a multi-day plan for New material and confirm day 1 is a learn day, days 2, 4, 7, 14, 21, and 30 are review days, and other days are short maintenance days.
- Build an exam-prep or cram plan of three or more days and confirm the last day is a light pass that suggests stopping for the day.
- With many due cards, confirm a heavy review day gets more minutes (up to 90) instead of a fixed block.
- Review a card as Review, Good, and Easy on different cards and confirm Easy cards are scheduled furthest out.
- Confirm the Study Plan page scrolls correctly and no button is cut off.
- Check the Stats page after completing reviews.
- Confirm Stats shows this week, active days, best day, weak-card count, streak, daily goal, heatmap, and deck breakdown.
- Add a note in Feedback Log and confirm it stays after switching pages.
- Close and reopen the app, then confirm Feedback Log still shows the saved note.
- Export Feedback Log with Export as Spreadsheet and confirm the CSV opens with rating, category, page, note, and created date.
- Press Send Feedback Now while online and confirm a "Sent!" message appears and the notes are marked as sent (they are not offered again).
- On the very first send, confirm the "Almost ready" message explains the one-time activation, then activate the form from the confirmation email in memorypal09@gmail.com and send again.
- Turn Wi-Fi off, press Send Feedback Now, and confirm a calm offline message appears and the notes stay saved.
- Press Email Feedback and confirm the mail app (or Gmail link) opens with the report filled in; with a long report, confirm the file to attach is saved and shown in File Explorer.
- Press Save Feedback File and confirm the text report contains the notes, Windows version, text size, and theme, but not the profile name or any cards.
- Confirm the app stays responsive (no freeze) while a send is in progress.
- Switch profiles and confirm each profile has separate data.
- Confirm each profile can keep a different navigation order.

## Library And Resources

- Search the library.
- Filter All, Due, Weak, and Captures.
- Confirm notes, images, audio, and video appear as resources on the main study pages.
- Export a JSON backup.
- Import that backup into a fresh profile.

## Accessibility Pass

- Increase Windows display scaling and test the app again.
- Check that long button text wraps into new rows instead of clipping.
- Use the app through a full review flow with the expanded navigation rail.
- Confirm hover hints appear on compact navigation and important controls.

## Code Structure

- Confirm the desktop entry point imports core logic from `latest_app/memorypal/`.
- Confirm profile config, logo rendering, and antialiased shape rendering use caching instead of repeated disk/pixel work.
- Confirm borderless chrome restoration is debounced and does not repeatedly run expensive idle redraws during startup, fullscreen exit, or focus exit.
- Confirm optional modules for file dialogs, CSV export, browser opening, audio recording, video recording, and text-to-speech are loaded only when needed.
- Confirm `latest_app/memorypal/` includes `onboarding.py`, `speech.py`, and `techniques.py`, and that the desktop app imports them instead of keeping duplicate copies.
- Confirm `pyproject.toml` lists core dependencies and optional extras.
- Confirm `requirements-*.txt` files still work for simple setup.
