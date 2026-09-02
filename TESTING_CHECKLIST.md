# MemoryPal Testing Checklist

This checklist is for getting MemoryPal ready to show and eventually turn into a real packaged app.

## First Run

- Open `latest_app/MemoryPalDesktop.py`.
- Confirm the dashboard loads without errors.
- Confirm data is created in the normal app-data folder, not directly in the home folder.
- If old `%USERPROFILE%\MemoryPalData` data exists, confirm it is copied into the new app-data profile folder.
- Switch between dark and light mode.
- Collapse and reopen the left navigation rail.
- Resize the window smaller than fullscreen and check that no main button disappears.
- Open profile, recording, reset, import-error, and media-error dialogs and confirm they match the MemoryPal visual style.
- Switch between several pages and confirm the content fades in instead of flashing or sliding.
- In the mobile prototype, try saving an empty card and a complete card; confirm both use in-app feedback instead of silent behavior.

## Windows Build

- Run `build_windows.cmd` from a normal Command Prompt or PowerShell window.
- Confirm the build output mentions Nuitka and the `tk-inter` plugin.
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

## Planning And Progress

- Build a minutes-based Study Plan.
- Build a days- or weeks-based Study Plan.
- Confirm the Study Plan page scrolls correctly and no button is cut off.
- Check the Stats page after completing reviews.
- Switch profiles and confirm each profile has separate data.

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
