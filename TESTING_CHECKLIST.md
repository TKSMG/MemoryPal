# MemoryPal Testing Checklist

This checklist is for getting MemoryPal ready to show and eventually turn into a real packaged app.

## First Run

- Open `latest_app/MemoryPalDesktop.py`.
- Confirm the dashboard loads without errors.
- Confirm the title/taskbar icon uses the MemoryPal mark instead of the default Python/Tk icon.
- Confirm the main app uses the MemoryPal title strip instead of an old native-looking title bar.
- Confirm the app appears as its own taskbar item when launched normally.
- Confirm the right edge, bottom edge, and corner resize grips let the app resize when it is not in true fullscreen.
- Confirm data is created in the normal app-data folder, not directly in the home folder.
- If old `%USERPROFILE%\MemoryPalData` data exists, confirm it is copied into the new app-data profile folder.
- Switch between dark and light mode and confirm the app does not freeze, flash white, or keep old-theme colors stuck on screen.
- Collapse and reopen the left navigation rail using the capsule toggle.
- Type something into a page field, collapse/reopen the navigation rail, and confirm the typed work is still there.
- In expanded navigation, confirm the collapse capsule sits centered in the rail instead of drifting right.
- On a shorter window, scroll inside the left navigation area and confirm every section stays reachable.
- Open Settings, move a page up/down in Page Order, apply the change, and confirm the left navigation updates.
- Reset Page Order and confirm the default navigation order returns.
- Open Settings from the pinned bottom navigation item.
- Resize the window smaller than fullscreen and check that no main button disappears.
- On Capture, resize the app narrower and confirm the horizontal scrollbar can reach the right-side captured/cue panel.
- Open profile, recording, reset, import-error, and media-error dialogs and confirm they match the MemoryPal visual style.
- Open the profile manager, create a profile, rename a profile, and confirm popups fade in without a white flash.
- Switch between several pages and confirm the same-theme cover hides redraw flashes without a strip-opening effect.
- Confirm page switches gently reveal instead of snapping or flashing after the new page is drawn.
- Confirm page/layout fades do not dim the entire app window; the background shell should stay solid while content appears.
- Press F11 and confirm it enters true fullscreen, then press Escape to exit.
- Repeatedly press F11 a few times and confirm the app ignores overlapping fullscreen requests instead of freezing.
- Use the header Focus button and titlebar square button, then confirm both use borderless focus mode instead of true fullscreen.
- While editing a field, toggle true fullscreen and focus mode and confirm the current page is not rebuilt.
- Confirm fullscreen, focus mode, navigation collapse, and resize release use a soft reveal without losing the current field contents.
- Drag a custom resize grip and confirm the window size only changes after releasing the mouse.
- Toggle true fullscreen and focus mode from Settings and confirm the app uses the same-color cover while the window changes size.
- While already in true fullscreen, switch pages and confirm the page content changes without white flashes.
- Confirm fullscreen/focus changes do not freeze the app or leave a cover stuck on screen.
- Open Settings and confirm theme, navigation, profile manager, daily goal, storage folder, backup, import, and reset controls are reachable.
- Confirm the title bar controls, resize handles, and nav toggle remain correctly sized at higher Windows display scaling.
- If Pillow is installed, confirm the custom titlebar buttons, app mark, and navigation toggle look smoother around the curved edges.
- Confirm the left navigation mark uses the generated MemoryPal logo artwork instead of a plain letter.
- Confirm the titlebar mark and navigation mark look like the same MemoryPal logo.
- Confirm `assets/memorypal.ico`, `assets/memorypal-logo-preview.png`, and `assets/memorypal-logo.svg` open as reusable project icon exports.
- Confirm collapsing the navigation rail does not show a toast notification.
- Confirm the header title stays on its own row and does not crowd the streak, daily goal, profile, or backup controls.
- In the mobile prototype, try saving an empty card and a complete card; confirm both use in-app feedback instead of silent behavior.

## Windows Build

- Run `build_windows.cmd` from a normal Command Prompt or PowerShell window.
- Confirm the build output mentions Nuitka and the `tk-inter` plugin.
- Confirm the build output does not reject the generated `memorypal.ico` icon.
- Confirm the script says it is using a Python install that can import Tkinter.
- Open `release\MemoryPal.exe` and confirm the app loads without a `No module named 'tkinter'` error.
- If the Nuitka build fails for a local setup reason, try `build_pyinstaller_windows.cmd` as a fallback.
- In GitHub, run the `Build Windows App` workflow and confirm the `MemoryPal-Windows` artifact is created.

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
- Use the app with the nav rail collapsed for a full review flow.
- Confirm hover hints appear on compact navigation and important controls.

## Code Structure

- Confirm the desktop entry point imports core logic from `latest_app/memorypal/`.
- Confirm `pyproject.toml` lists core dependencies and optional extras.
- Confirm `requirements-*.txt` files still work for simple setup.
