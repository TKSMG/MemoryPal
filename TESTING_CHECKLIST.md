# MemoryPal Testing Checklist

This checklist is for getting MemoryPal ready to show and eventually turn into a real packaged app.

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
- Confirm the header status chips stay on the left and Theme, Fullscreen, and Backup stay aligned on the right.
- Confirm the top-right profile avatar opens profile management and shows the active profile number.
- On a shorter window, scroll inside the left navigation area and confirm every section stays reachable.
- Open Settings, move a page up/down in Page Order, apply the change, and confirm the left navigation updates.
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
- Click the header Fullscreen button and confirm it uses true fullscreen.
- Repeatedly press F11 a few times and confirm the app ignores overlapping fullscreen requests instead of freezing.
- Use the titlebar square button and confirm it uses borderless focus mode instead of true fullscreen.
- While editing a field, toggle true fullscreen and focus mode and confirm the current page is not rebuilt.
- Confirm fullscreen, focus mode, and resize release do not rebuild the active page or lose current field contents.
- Drag a custom resize grip and confirm the window size only changes after releasing the mouse.
- Toggle true fullscreen and focus mode from Settings and confirm the active page returns cleanly without a white flash, whole-window dim, freeze, or stuck cover.
- While already in true fullscreen, switch pages and confirm the page content changes without white flashes.
- Confirm fullscreen/focus changes do not freeze the app or leave a cover stuck on screen.
- Open Settings and confirm theme, navigation, profile manager, daily goal, storage folder, backup, import, and reset controls are reachable.
- Confirm the title bar controls and resize handles remain correctly sized at higher Windows display scaling.
- If Pillow is installed, confirm the custom titlebar buttons and app mark look smoother around the curved edges.
- Confirm the default packaged app includes Pillow for smoother custom UI edges but does not bundle heavy optional audio/video/TTS libraries.
- Confirm the left navigation mark uses the generated MemoryPal logo artwork instead of a plain letter.
- Confirm the titlebar mark and navigation mark look like the same MemoryPal logo.
- Confirm the refreshed icon still has the connected-dot M and does not look jagged in the titlebar, taskbar, or navigation rail.
- Confirm `assets/memorypal.ico`, `assets/memorypal-logo-preview.png`, and `assets/memorypal-logo.svg` open as reusable project icon exports.
- After a Windows package is built, confirm `release\MemoryPal\assets\memorypal.ico` exists so installed copies do not regenerate icons during startup.
- Confirm the header and navigation logo appear immediately from packaged assets instead of causing a long startup delay.
- Confirm the header title stays on its own row and does not crowd the streak, daily goal, profile avatar, fullscreen, or backup controls.
- In the mobile prototype, try saving an empty card and a complete card; confirm both use in-app feedback instead of silent behavior.

## Windows Build

- Run `.\clean_build_artifacts.cmd` before the first fresh package attempt.
- Run `.\build_windows.cmd` from a normal Command Prompt or PowerShell window.
- Confirm the build output mentions PyInstaller and collects Tkinter support.
- Confirm the build output does not reject the generated `memorypal.ico` icon.
- Confirm the build output excludes unused optional media stacks unless a media-enabled build is being made.
- Confirm the script says it is using a Python install that can import Tkinter.
- Open `release\MemoryPal\MemoryPal.exe` and confirm the app loads without a `No module named 'tkinter'` error.
- Treat `.\build_nuitka_windows.cmd` as an alternate build path until the local Nuitka runtime crash is understood.
- After the app folder exists, run `.\build_installer_windows.cmd`; if prompted, allow the script to install Inno Setup with `winget`.
- Confirm `release\MemoryPalSetup.exe` is created and opens the normal MemoryPal installer flow with install-location, Start Menu, optional desktop shortcut, and launch-after-install.
- Run `.\package_for_testers.cmd` after the build and confirm `release\MemoryPalTesterPackage.zip` contains the installer or portable app folder plus the tester notes.
- Zip either `release\MemoryPalSetup.exe` with the tester notes or the full `release\MemoryPal\` folder with the tester notes.
- In GitHub, run the `Build Windows App` workflow and confirm the `MemoryPal-Windows` artifact includes the app folder and installer when the workflow succeeds.

## Capture And Cards

- Add a study bit manually.
- Split pasted notes with new lines, numbered lists, `/n`, and semicolons.
- Add a question/title card with a saved answer.
- Add a question/title card without a saved answer.
- Import a `.txt`, `.md`, or `.csv` note and confirm the text appears in the study bit box.
- Import a `.docx` note and confirm readable text is extracted.
- Import a PDF and confirm extraction works when `pypdf` or `PyPDF2` is installed.
- Attach image, audio, and video cues.
- Try audio/video recording without the optional packages installed and confirm the modern unavailable dialog appears.
- Run `development_versions/MemoryPal_v35_test_speech_to_text.py`; confirm it opens without speech packages installed and shows a clear unavailable message when dictation is requested.

## Study Modes

- Open Memory Gym and confirm the student-study and everyday-memory tracks are visible.
- Use Memory Gym buttons to open Test Lab, Review, Quiz, Associations, Capture, Cue Lab, Repetition, and Puzzles.
- Start a due card from Review and confirm it opens in Test Lab.
- Type a close answer and use Smart Check.
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

- In Associations, build a technique plan for retrieval practice, spaced practice, interleaving, elaboration, concrete examples, dual coding, and spaced retrieval.
- In Puzzles, play Sequence Recall, Word Recall, Pair Recall, Missing Item, Visual Search, N-Back Lite, Category Sort, and Routine Recall.
- Confirm Visual Search marks only correct target tiles.
- Confirm N-Back Lite advances item by item and keeps score.
- Confirm Category Sort creates suggested groups from pasted or sample items.
- Confirm Routine Recall hides the shown steps and scores the typed recall attempt.

## Planning And Progress

- Build a minutes-based Study Plan.
- Build a days- or weeks-based Study Plan.
- Confirm the Study Plan page scrolls correctly and no button is cut off.
- Check the Stats page after completing reviews.
- Confirm Stats shows this week, active days, best day, weak-card count, streak, daily goal, heatmap, and deck breakdown.
- Add a note in Feedback Log and confirm it stays after switching pages.
- Close and reopen the app, then confirm Feedback Log still shows the saved note.
- Export Feedback Log and confirm the CSV opens with rating, category, page, note, and created date.
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
- Confirm `pyproject.toml` lists core dependencies and optional extras.
- Confirm `requirements-*.txt` files still work for simple setup.
