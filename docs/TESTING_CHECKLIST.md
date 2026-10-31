# MemoryPal Testing Checklist

This checklist is for getting MemoryPal ready to show and eventually turn into a real packaged app.

## Automated Tests

- Run `python -m unittest discover -s latest_app\tests` and confirm every test passes.
- Confirm the test run does not create or change anything in `%LOCALAPPDATA%\MemoryPal`.
- In `mobile/`, run `npm test` and confirm the parity tests (including the quiz questions) pass. After changing `questions.py`, run `python tools\parity\make_fixtures.py` first.
- If Deno is installed, run `deno test supabase/functions/ai/logic_test.ts` and confirm the AI function's checks pass.

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

## AI Notes And Questions

These need a Supabase project with the `ai` function deployed (see `supabase/functions/ai/README.md`) and a signed-in account. Not yet tried against the live server.

- Signed out, open the set builder, choose Make with AI, and press Make notes. Confirm a "Sign in to use AI" message offers Sign in, Create an account and Not now, and nothing is sent. On the phone, confirm Make with AI shows "Sign in to use AI" with a button to sign in or create an account.
- In a build with no cloud project set up, confirm Make with AI says "AI isn't ready yet" (desktop) or "AI isn't available yet" (phone) instead of an error.
- On a new profile, confirm the welcome has three questions and no AI question, and that AI is on in Settings. Confirm the Create account and Sign in screens say that agreeing turns AI on, what is sent to Google's Gemini (free tier), and that AI can be turned off in Settings; the account switch reads "including AI features".
- With AI turned off in Settings, use Make with AI and confirm the one-time AI screen appears, explaining what is sent, who gets it (Google's Gemini API through MemoryPal's server), that Google may keep and read it on the free tier, and the 10-a-day limit. Confirm the Privacy policy and Gemini API terms links open.
- Press Not now on the AI screen and confirm nothing is sent and AI stays off in Settings. Use Make with AI again and confirm the AI screen asks again.
- Press Allow and confirm a short message says AI is on. Confirm Settings > AI features shows "Use AI notes and questions" (desktop) or "AI notes and questions" (phone) switched on.
- Type or paste a short paragraph, press Make notes, and confirm a "this can take up to a minute" style wait, then study notes with a title, sections, bullets and key terms. On the desktop, press Cancel during the wait and confirm "Cancelled. Nothing was added."
- On the notes, confirm the "Made with AI, check it" label, Read aloud, Save notes, and Make questions from these notes all work. Confirm saved notes appear in the Library (desktop) or stay on the phone.
- Type a pattern under "How should it look?" (for example "one line per date: the year, then what happened") with some history notes, press Make notes, and confirm the bullets follow it. Try "only the causes" and confirm the notes stay on that.
- Paste three or four past exam questions under "Questions your teacher has asked" (for example clinical cases), press Make questions, and confirm the new ones are in the same style without copying them. Open Make with AI for the same set again and confirm both boxes are filled in from last time.
- In a set that already has some questions, leave both boxes empty, press Make questions, and confirm the new ones match the set's existing style and length.
- Open a set, fill in About and an exam date a few weeks away, and save. Confirm the set shows "Exam in N days" (phone set page and Create list; desktop Decks tile), and that "Plan for the exam" opens a day-by-day Exam prep plan for that set. After syncing, confirm the same details appear on your other device.
- Save AI notes in a set, then confirm they show on the set's page (phone) and in the Library filtered to that set (desktop). Open them, use Read aloud and "Make questions from these notes". Rename the set and confirm the notes and details move with it; delete it and confirm the notes stay (Saved notes / Library).
- On an AI card made from saved notes, confirm "Where it came from" (phone card page) or "Open ..., where this card came from" (desktop Edit card) opens the notes with the right part marked.
- In Practice (phone) or Techniques (desktop), pick a set, choose a technique, and save the hooks. Confirm each card in the set gained its own line in its memory hook, and that saving again adds nothing.
- From a set's page (phone) open "Puzzles with these cards" and play pair and word recall with that set's answers; on the desktop choose the set under "Use cards from" on the Puzzles page.
- Confirm AI questions make sense on their own (they name the topic instead of "the text"), and that each AI card's hook ends with Source: and the sentence the answer came from.
- Press Make questions and confirm the questions arrive as cards in the set builder to check, edit or remove before saving. Save the set and confirm each card keeps the "Made with AI, check it" label in the Library and in quizzes.
- Desktop: choose A PDF or picture, then Choose a file, and try a text PDF, a scanned PDF and a PNG or JPEG photo of a page. Confirm cards made from a picture show that picture, and cards from a PDF say which page they came from (with the page's picture when the page has one).
- Phone: try Choose a PDF, Take a photo and Choose a photo, then Make notes and Make questions with each. Confirm the camera permission is asked only the first time you take a photo, and that refusing it shows a calm message suggesting Choose a photo instead. Not yet tried on a real phone.
- Choose a file over 8 MB and confirm "That file is larger than 8 MB" instead of a send. On the desktop, choose a file that isn't a PDF or picture and confirm "That file can't be used".
- Press Report on an AI card or AI notes. On the desktop, confirm the Send feedback dialog opens with an "AI content report" note filled in and nothing is sent until you press Send, Email it or Save as file. On the phone, confirm an email to MemoryPal opens with the notes filled in (or a "No email app" message).
- Watch the "AI uses left today" count go down after each request. Use all 10 and confirm the next request shows "You've used today's AI requests. They reset tomorrow" and the rest of the app keeps working.
- Turn Wi-Fi off and press Make notes. Confirm a calm offline message ("Couldn't reach the MemoryPal cloud" on the desktop, "Needs internet" on the phone) and that nothing is lost.
- Turn AI off in Settings and confirm Make with AI asks for consent again before anything is sent. Turn it back on and confirm the AI screen appears again.
- With a two-step account that hasn't entered its authenticator code, confirm AI asks you to finish signing in first.
- Send material Gemini refuses or wait for a busy period, and confirm "This material can't be used" or "The AI is busy right now" instead of a crash, and that a busy failure doesn't use up one of the 10 requests.

## Google Drive Sync

Needs a 0.51.0 or newer build and a Google account listed as a test user on the Google consent screen (while it says Testing).

- First launch: the welcome page offers Connect Google Drive and Continue without syncing. Connect opens Google's page (desktop: your browser; phone: Google's sheet). It should ask only for MemoryPal's own app data, not all of Drive.
- After connecting, Settings > Account & sync shows "Sync with Google Drive" with your Google email, Sync now and Disconnect.
- Add a card on the desktop, press Sync now, then Sync now on the phone (same Google account). The card appears. Edit it on the phone, sync both, and confirm the edit reaches the desktop.
- Delete a card on one device and sync both. It is gone on both.
- Review a card offline on both devices, then sync both. The review counts add up and nothing is lost.
- Connect a different Google account on one device. The "other account" prompt offers to merge or replace.
- Disconnect, then reconnect. Cards are still there.
- Signed in to an old MemoryPal account with cards in the cloud: after the first Drive sync the cards are in Drive, and an older app version signed in to that account no longer gets them.
- Android APK from GitHub Releases: if connecting fails with DEVELOPER_ERROR, see GOOGLE_DRIVE_SYNC.md (second Android client).

## Quiz Question Types

- Make a set with at least six cards: some short answers, a few sentence answers ("The heart pumps blood around the body"), one answer that is a numbered or comma list, and one with a year.
- Start a Quick Quiz (desktop) or Quiz (phone) and confirm the round mixes question types: pick the answer, which question goes with this answer, fill in the blank, true or false, match the pairs, what comes next, and type the answer.
- For fill in the blank, confirm a key word (often a year or name) is blanked from a sentence and the blank can be picked or typed.
- For true or false, confirm both true and false statements appear across a few rounds and the false ones use an answer from the same set.
- For match the pairs, confirm three or four short pairs can be matched, and a round with a wrong pairing counts as missed.
- For what comes next, confirm the question never offers the item already named in the question.
- For type the answer, confirm Smart Check accepts close answers, and Show a hint and I don't know work (phone).
- Finish a round, start another, and confirm the questions you just had come last or are avoided. Confirm the answers were saved to each card's review schedule.
- On the desktop, switch the set chooser between one set and All sets and confirm the quiz uses only that set.
- With too few cards that have answers, confirm "Nothing to quiz yet" (desktop) or "Add a few more cards" (phone) instead of an empty quiz.
- Confirm AI-made cards in a quiz still show "Made with AI, check it".

## Talk-Back And Read Aloud

- Confirm every card, question, answer and note has one read-aloud button: Review, Quick Quiz, Library, the set builder and AI notes on the desktop; review, quiz and AI notes on the phone. Pressing it again while speaking stops the voice.
- Desktop (Windows): open Study > Talk-back study. Confirm each question is read aloud ("Question 1 ..."), the status then says "Listening. Say your answer.", and saying the answer gives "Correct." or "Not quite. The answer is ...". Not yet tried on a real Windows PC with a microphone.
- Desktop (Windows): say "I don't know" and confirm the answer is given and the card counts as missed. Stay silent and confirm "Didn't catch that", then a pause with a Resume button after repeated silence.
- Desktop (Windows): with no microphone or no speech recogniser installed, confirm Talk-back switches to typed answers with a short message instead of failing.
- Desktop (Mac and Linux): confirm Talk-back reads each question aloud and asks you to type the answer, then press Enter. Not yet tried on a real Mac.
- Desktop: with no due cards, confirm Talk-back uses cards that need more practice and says so. With no cards that have answers, confirm "Nothing to practise yet".
- Desktop: finish a round and confirm "Round finished" with your score read aloud, plus Study again and Back to Study.
- Phone: start Talk-back and confirm the microphone and speech-recognition permissions are asked the first time. Answer out loud and confirm the result is spoken and the card is rated. Not yet tried on a real phone.
- Phone: refuse the microphone permission and confirm the message says questions will be read and you can type the answer.
- Phone: with a screen reader (VoiceOver or TalkBack) on, confirm the screen reader announces the questions and the app's own voice stays quiet.
- Leave the Talk-back page in the middle of a question and confirm the voice and microphone stop.

## Set Builder

- Desktop: on Decks press New set, name it, and confirm the set builder opens with that name. Phone: start a new set from Create.
- Confirm the set builder asks for a set name first; "Existing sets" (desktop) or "Your sets" (phone) fills in a set you already have.
- Try to add cards without a name and confirm "Name your set first".
- Type questions: type a question and answer and press Enter (desktop) or Add a card (phone). Leave the answer empty and confirm a self-check card is made.
- Paste notes: paste "Capital of France :: Paris", "Question => Answer", a tab-separated line and a plain sentence, then split them. Confirm each question line becomes that card and each other line becomes a recall card.
- Make with AI: confirm the third choice opens the AI options described above.
- Remove or edit a card before saving and confirm only the saved set reaches the Library.
- With unsaved cards, start a new set and confirm "Discard unsaved cards?" (desktop) or "Discard these cards?" (phone) asks first.
- Desktop: on Decks, use Rename set and confirm every card moves to the new name. Phone: open a set and rename it, then delete a test set and confirm its cards are removed after the warning.

## Dialogs, Dropdowns And Title Bar

- Open dropdowns with long labels (deck chooser, note menus, set chooser) near the right and bottom edges of the screen and confirm each list fits its longest label, stays fully on screen, and opens above its button when there is no room below.
- Open dialogs with long messages (consent, sign in, discard, rename) at Large and Extra Large text and confirm no text is cut off; the dialog grows to fit.
- Confirm dialogs and dropdowns have a thin border and the same look in light and dark mode, and select fields look like text fields.
- With a mouse wheel, scroll a long page, a text box, the Library list and a dropdown and confirm each notch glides smoothly instead of jumping, and a fast spin keeps gliding without stutter.
- With a Windows precision touchpad, scroll the same places and confirm the page follows your fingers directly without lagging behind.
- Mac: try a mouse wheel and a trackpad and confirm the wheel glides and the trackpad follows your fingers. Not yet tried on a real Mac.
- Windows 10/11: switch between light and dark theme and confirm the main window's and dialogs' title bars match it (exact colours on Windows 11). Drag the window to a screen edge and confirm it snaps like other apps.
- Mac: confirm the title bar follows the app's light or dark theme.

## First Run

- Open `latest_app/MemoryPalDesktop.py`.
- Confirm the dashboard loads without errors.
- Confirm the app opens quickly enough for a short practice session instead of sitting on a long blank startup.
- Confirm a packaged Windows app opens to its first visible window in roughly a couple of seconds on a normal tester machine.
- Confirm repeated page changes, full screen and resizing never leave the window half drawn.
- Confirm page transitions affect only the page panel while the app shell/background stays steady.
- Confirm the title/taskbar icon uses the MemoryPal mark instead of the default Python/Tk icon.
- Confirm the main window has the normal system title bar, in the theme's colours.
- Confirm the app appears as its own taskbar item when launched normally.
- Resize the window from any edge or corner and confirm the page reflows without white flashes.
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
- Use Start Gentle Review from Everyday Memory and confirm Review opens on an everyday-memory card when one exists, with the rating buttons and "Gentle review · N left".
- On a shorter window, scroll inside the left navigation area and confirm every section stays reachable.
- Open each main page in a shorter window and confirm mouse wheel, Page Down, and End can reach the last control with a little bottom breathing room.
- In Settings, change Accessibility text size to Large and Extra Large, then confirm the app rebuilds without clipping major controls.
- Turn on Higher Contrast and confirm muted labels, borders, inputs, and navigation remain clear in dark and light mode.
- Turn on Reduce Motion and confirm page switches and popups avoid unnecessary fades.
- Use Senior Layout and confirm accessibility options stay enabled.
- Open Settings from the pinned bottom navigation item.
- Resize the window smaller than fullscreen and check that no main button disappears.
- On Capture, resize the app narrower and confirm the horizontal scrollbar can reach the right-side captured/cue panel.
- Open profile, recording, reset, import-error, and media-error dialogs and confirm they match the MemoryPal visual style.
- Open the profile manager, create a profile, rename a profile, and confirm popups fade in without a white flash.
- Switch between several pages and confirm each new page appears in one step, without white flashes.
- Confirm page switches fade in cleanly instead of flashing after the new page is drawn.
- Confirm page/layout fades do not dim the entire app window; the background shell should stay solid while content appears.
- Press F11 and confirm it enters true fullscreen, then press Escape to exit.
- Use the Settings true fullscreen button and confirm it matches F11 behavior.
- Repeatedly press F11 a few times and confirm the app doesn't freeze.
- While editing a field, toggle full screen and confirm the typed text is kept.
- Leave full screen and confirm there is no white flash.
- While already in true fullscreen, switch pages and confirm the page content changes without white flashes.
- Open Settings and confirm theme, navigation, profile manager, daily goal, storage folder, backup, import, and reset controls are reachable.
- Confirm the header controls, profile chip, panels, fields and tick boxes have smooth curved edges.
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

- Open Study and confirm it shows the number due, Start review, and the list: Quick 10, Weak cards, New cards, Talk-back study, Quick quiz, Study plan.
- Start review and confirm the line above the card reads "Due cards · N left" and goes down by one after each rating; after the last card you are back on Study.
- Start Weak cards and New cards and confirm each shows its own name and count, and ends after its cards (at most 20).
- Start Quick 10 with nothing due and no weak cards and confirm a fast quiz opens instead.
- Open Review from the page finder (Ctrl+K) with nothing due and confirm "You're all caught up" with Practise weak cards and Quick quiz.
- Open a study plan step that drills weak cards (or one saved before v97 that named Focus, Test Lab or Repetition) and confirm weak-card review starts.
- Type a close answer and use Smart Check.
- Type the correct answer without repeating the question wording and confirm Smart Check still scores it as correct.
- Type an incorrect answer for a proper noun such as Paris and confirm the missing-cue text stays readable.
- Reveal and hide the saved answer.
- Use each rating button: Again, Review, Good, Easy.
- Test keyboard ratings `1`, `2`, `3`, `4`.
- Use Undo last rating after a review.
- Use Skip for today and confirm the card leaves the due queue.

## Cues in Edit card

- Open a card in Library with Edit, press First letters, Key words and Memory sentence, and confirm each adds a line to the memory hook (Cancel leaves the card unchanged).
- Use Picture > Choose a picture, Sound > Make a spoken cue, and Video > Choose a video file, and confirm the line under them lists what is attached; then remove each one.
- On Windows, use Sound > Record your voice and Video > Record with the camera.

## Techniques And Puzzles

- In Memory techniques, paste 12 or more ideas and generate a Peg list; confirm every idea gets a different peg and items past ten use a twist such as "giant golden".
- Generate a Memory palace for 25 or more ideas and confirm no two ideas share the same spot.
- Generate a Mini-story and confirm scenes are not reused for different ideas.
- Generate an Acronym and confirm it also shows an acrostic sentence.
- Separate ideas with commas, new lines, semicolons, pipes, and `/n`, and confirm each is split correctly.
- In Memory techniques, build a technique plan for retrieval practice, spaced practice, interleaving, elaboration, concrete examples, dual coding, and spaced retrieval.
- In Puzzles, play Sequence Recall, Word Recall, Pair Recall, Missing Item, Visual Search, N-Back Lite, Category Sort, and Routine Recall.
- Confirm Visual Search marks only correct target tiles.
- Confirm N-Back Lite advances item by item and keeps score.
- Confirm Category Sort creates suggested groups from pasted or sample items.
- Confirm Routine Recall hides the shown steps and scores the typed recall attempt.

## Smoothness And Text

- On pages that add or remove rows (Capture, Study Plan), confirm the section updates in one step without a flash or jump.
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
- Press Feedback (top right) on any page and confirm the dialog names that page ("about: Review").
- Press Send while online and confirm a "Sent!" message appears, the dialog closes, and the notes are marked as sent (they are not offered again).
- In Settings, use Export feedback notes and confirm the CSV opens with rating, category, page, note, and created date.
- Confirm the dialog never shows the team's email address (not in the dialog, in messages, or in a saved feedback file).
- Turn Wi-Fi off, press Send, and confirm a calm offline message appears above the dialog and the note stays saved.
- Press Email it and confirm the mail app (or Gmail link) opens with the report filled in; with a long report, confirm the file to attach is saved and shown in File Explorer.
- Press Save as file and confirm the text report contains the notes, Windows version, text size, and theme, but not the profile name or any cards.
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
