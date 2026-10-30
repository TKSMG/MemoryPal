# MemoryPal Version Journal

Each version gets two short sentences. This is meant to read like a simple development journal, not a formal changelog.

## v01 Alpha - Initial Runnable PC App

This version made MemoryPal real as a runnable desktop program. It set up the first memory trainer structure with capture, review, quiz, associations, puzzles, and library ideas.

## v02 Alpha - Scaled UI Resolution

This version made the app larger and easier to read. It also added early DPI handling so the UI would look better on Windows display scaling.

## v03 Alpha - Multiple Study Bits

This version stopped treating pasted notes as one big block. It split `/n`, newlines, numbered lists, and separators into separate study bits.

## v04 Alpha - Multimedia Capture

This version moved media cues into the wider capture flow. Image and audio imports became part of study material instead of only flashcard attachments.

## v05 Beta - Modern UI Pass

This version moved the app away from a plain form layout. The dashboard cards, color, and spacing made it feel more like a modern study tool.

## v06 Beta - Removed Animation

This version removed the distracting top-right animation. The app became calmer and more suitable for learners and elderly users.

## v07 Beta - Structured Revision

This version changed shuffle into an intentional practice order. The user could revise recent items while pulling older items back into memory.

## v08 Beta - Notes And Design

This version added project notes for the memory techniques. It also started recording the design direction alongside the code.

## v09 Test - Button Scaling

This version fixed the awkward dashboard button clipping. The buttons now behave more predictably when the window is not fullscreen.

## v10 Test - Repetition And Smart Check

This version introduced start/range repetition and close-enough answer checking. The app could begin suggesting how much repetition a user might need.

## v11 Test - Native Multimedia

This version made text, image, audio, and video part of the study system. Media cues could travel with the material through different modes.

## v12 Test - Chunk Cards

This version changed capture into a study-set builder. Each study bit could become its own separate practice card.

## v13 Test - Scrollable Forms

This version made long screens scrollable. It fixed the problem where buttons could get pushed under the window.

## v14 Test - Walk-Back Repetition

This version matched the requested repetition example exactly. Start 5 and range 3 gives 5, 5-4, 5-4-3, then 3-2-1.

## v15 Beta - Polished Dashboard

This version made the dashboard and shell feel more intentional. The app became easier to scan and less like a generated interface.

## v16 Test - Prompt Answer Modes

This version changed practice around prompts, answers, reveal, and Smart Check. Repetition became open-ended instead of tied to fixed rounds.

## v17 Test - Import And Record Inputs

This version added import and recording paths for text, audio, and video. It also marks the point where a future mobile version became important for native microphone and camera recording.

## v18 Beta - Study App Polish

This version compared MemoryPal against the everyday workflow of a typical study app. It added a Focus queue, next-step dashboard guidance, direct Q/A card creation, and library filters so the app feels more useful in daily practice.

## v19 Beta - Interaction And Capture Polish

This version made the prompt-answer workflow feel more like a real app by separating question and answer entry. It also cleaned up answer panels and added a small transition when moving between sections.

## v20 Beta - Review Testing And Q/A Polish

This version made question cards more flexible by allowing optional saved answers. It also added a separate Test Lab page, visual Smart Check bucket highlights, and automatic mini-story generation.

## v21 Test - Pointer-Aware Page Scrolling

This version made scrolling feel more natural. The mouse wheel now follows the section under the pointer instead of expecting the user to hover over the scrollbar.

## v22 Beta - Test Lab Review Flow

This version made Test Lab the main place for focused review. Review and self-check quiz cards now use the separate test page instead of placing all answer controls below the prompt.

## v23 Beta - Learning App Polish

This version made MemoryPal feel closer to a complete study product. The dashboard now shows the next best action, mastery progress, daily practice guidance, hover hints, and a gentler Test Lab guide while keeping the requested feature set intact.

## v24 Beta - Accessible Repetition And Media Polish

This version made Repetition Path match the clearer Set Builder pattern by separating question/title and answer entry. It also cleaned up audio/video capture, added more practice hints, and made page changes feel smoother.

## v25 Test - Final Scroll And UX Polish

This version fixed the Repetition screen scaling problem by making it one continuous scrollable page. It also stacked the prompt and answer fields and added keyboard scrolling so the interface feels more forgiving on smaller windows.

## v26 Beta - Puzzles And Cue Menus

This version made Puzzles feel more like a real practice area by adding pair recall and missing-item recall. It also made Set Builder calmer by turning media cues into compact menu buttons instead of separate audio/video chooser dialogs.

## v27 Beta - Cue Previews, Associations, And Skeleton Loading

This version made media cues visible during testing instead of leaving them as plain file links. It also expanded Associations into a fuller memory-toolbox and replaced the page wipe with a calmer skeleton loader.

## v28 Beta - App Feel Visual Polish

This version focused on making MemoryPal feel more like a real desktop app without slowing it down. It softened the palette, improved the header, restyled controls, and added subtle hover feedback to important cards.

## v29 Beta - Page Draft Preservation

This version fixed the problem where switching pages could wipe unsaved work. It keeps page drafts in memory for capture, repetition, testing, quiz, associations, and puzzles.

## v30 Beta - Profiles, Planning, And Stats

This version made MemoryPal feel more complete as a study app instead of one local deck. It added separate profiles, study planning, progress stats, streaks, and stronger daily guidance.

## v31 Beta - Repetition Player Polish

This version made Repetition Path calmer by replacing the long generated stack with a round-by-round player. It keeps the requested 5, 5-4, 5-4-3, 3-2-1 pattern while adding progress, navigation, reveal, and Smart Check in one focused exercise.

## v32 Beta - Collapsible Navigation And Document Notes

This version made the interface easier to focus on by adding a collapsible left navigation rail and stronger scaling behavior. It also added document-note imports so PDFs, Word files, and text notes can become study bits and stay accessible as resources across study pages.

## v33 Release Candidate - Testing, Build, And Mobile Start

This version moved MemoryPal closer to something that can be tested like a real app. It added release notes, a testing checklist, Windows build files, a mobile prototype, and a few useful comments in the main desktop code.

## v34 Beta - Modern Dialogs

This version removed the remaining old-looking prompt and warning boxes from the desktop app. Profile names, recording lengths, confirmations, errors, mobile capture feedback, and applicable milestone notices now use a MemoryPal-styled modal surface.

## v35 Test - Speech-To-Text Capture

This version added a desktop speech-to-text prototype for spoken study capture. It lets dictated or transcribed text become editable question and answer cards while keeping the speech packages optional.

## v36 Beta - Modular Project Structure

This version responded to code review feedback by moving core paths, models, storage, planning, and study helpers into a small `memorypal` package. It also added platform-correct app data storage, `pyproject.toml`, Taskfile build notes, and a GitHub Actions Windows build workflow.

## v37 Beta - Custom Window Chrome And Flash Polish

This version replaced the old native-looking title bars with MemoryPal-styled window chrome on the main app and in-app popups. It also added fade-in startup, popup fade-ins, fullscreen/rebuild covers, and a custom resize grip so the app keeps a modern feel without losing normal desktop usability.

## v38 Beta - Settings And Window Controls

This version added a real Settings page for theme, navigation, profile, daily-goal, storage, backup, and reset controls. It also separated true fullscreen from borderless focus mode, restored normal resizable-window behavior, and nudged Windows to show MemoryPal as its own app in the taskbar.

## v39 Beta - Settings Access And Fade Polish

This version made Settings easier to find with a floating bottom-right cog and replaced the plain navigation collapse button with a cleaner capsule control. It also restored same-color fade covers around focus, fullscreen, resize, popup, and page transitions, with extra scaling attention for the title bar and floating controls.

## v40 Beta - Stable Fullscreen Polish

This version simplified fullscreen and focus transitions so they use an in-window blocker instead of a separate cover window. It also cleaned up the settings cog into a simpler scaled circle and kept fade protection around resize, fullscreen, focus, page, and popup changes.

## v41 Beta - Softer Transition Pass

This version removed the floating Settings cog after it created an unavoidable square artifact in Tkinter. Settings now appears in the header and as a pinned bottom navigation item, while page, fullscreen, focus, resize, and rebuild transitions use in-window covers instead of fading the entire app window.

## v42 Beta - Fade Cover Balance

This version brought back real fading covers for normal windowed page switches and interface rebuilds. Fullscreen and borderless focus still use simpler in-window blockers, which keeps those modes steadier while hiding the white flash.

## v43 Beta - Page Flash Fix

This version removed the separate page-transition overlay window that could still flash during navigation. Page switches now use an in-app same-color veil with a quick strip reveal, so fast navigation stays hidden and the whole app window does not blink.

## v44 Beta - Memory Gym And Softer Fades

This version removed the strip-opening page transition and brought back a calmer fade cover for normal page switches. It also added Memory Gym, technique planning, Visual Search, and N-Back Lite so the app better supports both students and older adults practicing memory skills.

## v45 Beta - Everyday Memory Games

This version kept the Memory Gym direction going by adding Category Sort and Routine Recall. It also let page transitions use fading covers while already in fullscreen or focus mode, while fullscreen enter and exit still use the steadier resize blocker.

## v46 Beta - Fullscreen And Icon Polish

This version made fullscreen and focus changes less buggy by debouncing window transitions and removing stacked covers during shell rebuilds. It also added a generated MemoryPal icon for the running app, custom title strip, Windows build scripts, and GitHub Actions packaging.

## v47 Beta - Custom Navigation And Stats Rhythm

This version made page transitions more consistent by forcing the cover to render before rebuilding each page and removing the color-flash fallback. It also added per-profile page ordering in Settings, a less cramped two-row header, and stronger Stats rhythm cards for weekly practice, active days, best day, and weak-card attention.

## v48 Beta - Stable Transitions And Soft Themes

This version replaced the fragile page fade overlay with a steadier in-window cover that stays above the old and new page until the rebuild is ready. It also removed the duplicate Settings button from the header and softened both themes so light mode and dark mode feel more like the same finished app.

## v49 Beta - No-Reload Focus And Navigation

This version made the app feel less jumpy by keeping the current page alive while the sidebar collapses or the window enters focus/fullscreen. It keeps the clean no-flash page switches, but avoids rebuilding the interface when the user only wants more screen space.

## v50 Beta - Navigation Alignment And Softer Edges

This version centered the expanded navigation collapse control and made the hand-drawn titlebar/nav shapes smoother when Pillow is installed. The app still falls back to normal Tk drawing, but polished installs can use the optional image preview dependency for softer rounded edges.

## v51 Beta - Soft Fade And Logo Polish

This version brought back the pleasant startup-style fade for page switches and layout changes without returning to the buggy overlay-window transition. It also changed the large rail mark to use the generated MemoryPal logo art when Pillow is available, with the hand-drawn logo as a fallback.

## v52 Beta - Capture Scroll, Resize Release, And Fade Tuning

This version fixed the Capture page when the two-column builder is wider than the window by adding horizontal scrolling. It also changed custom resizing to happen on mouse release, made the fade visible after the transition cover drops away, removed the unnecessary navigation-collapse notification, and matched the titlebar and rail logo artwork.

## v53 Beta - Element Fade And Logo Fix

This version corrected the fade approach so page and layout changes no longer dim the entire app window. The app now keeps the shell background solid and fades away a same-color overlay over the changed area, while the generated MemoryPal logo renders consistently in both the titlebar and navigation rail.

## v54 Beta - Logo Assets

This version settled the current MemoryPal logo into reusable project assets. It kept the sharper connected-dot M, exported `.ico`, PNG, and SVG versions, and made the desktop app prefer the checked-in icon before falling back to generated files.

## v55 Beta - Testing Feedback And Installer

This version prepared MemoryPal for longer testing by adding a local Feedback Log with ratings, categories, affected pages, notes, and CSV export. It also made legacy data migration non-destructive and added an Inno Setup installer path so the Windows build can become a tester-friendly setup file once the EXE is built.

## v56 Beta - Safe Saves And Fast Build

This version made local data safer when two MemoryPal windows are open at the same time. It also changed the Windows build toward a normal app folder so installed copies launch faster, and it removed blank/fade covers from fullscreen, focus mode, sidebar collapse, and manual resize.

## v57 Beta - Motion, Startup, And Icon Polish

This version made the split project cleaner by removing old duplicated support code from the desktop launcher. It also kept fades inside the changed content area, animated the navigation rail width, excluded optional media stacks from the fast tester build, and refreshed the connected-dot MemoryPal icon.

## v58 Beta - Clean Startup And Release Prep

This version added a clean-build script and removed old project/temp build leftovers so new packages can start fresh. It also made startup lighter by caching profile config and generated UI images, and by delaying file dialog, CSV, browser, audio, video, and speech imports until those features are used.

## v59 Beta - Transition And Launch Polish

This version made the installed app launch path lighter by bundling the checked-in icon assets instead of regenerating them on startup. It also smoothed page changes with a real content-only fade, made fullscreen/resize settling less blank, and cleaned up sidebar collapse so labels do not crush during the motion.

## v60 Beta - Stable Motion Follow-Up

This version tightened the remaining transition bugs by covering the full page panel before a new page is built, then fading the same-window cover away after the page has painted. It also moved fullscreen and focus protection to same-window reveal covers, and changed sidebar collapse to a clean width snap with a small rail reveal so the current page no longer reflows repeatedly.

## v61 Beta - Fixed Rail And Fullscreen Stability

This version removed the collapsible navigation rail from the live desktop app so the study page no longer shifts sideways during use. It also removed root-window opacity fades from fullscreen and focus changes, keeping same-window covers for redraw protection without the freeze-prone whole-app alpha transition.

## v62 Beta - Concurrent Save Stability

This version made two-window saving safer by keeping newer saved review progress when a stale window saves later. It also cleaned up Smart Check cue wording and added a tester-package helper so the built installer/app folder and notes can be zipped together cleanly.

## v63 Beta - Header Release Polish

This version spread out the top header by separating status chips from action buttons and replacing the long profile control with a numbered profile chip. It kept true fullscreen available through F11 and Settings, kept borderless focus on the titlebar square and Settings, and sped up startup by loading the packaged logo asset first.

## v64 Beta - Low-End Readiness

This version focused on keeping MemoryPal comfortable on slower Windows PCs and future Mac builds. It reduced repeated custom-titlebar redraw work, cached optional graphics checks, kept the packaged-logo startup path light, and moved the default Windows tester build to the stable PyInstaller path after a fresh Nuitka package failed launch testing.

## v65 Beta - macOS Packaging

This version made Mac testing more realistic without disturbing the current Windows release path. It added a macOS build script, Intel and Apple Silicon GitHub Actions artifacts, native Mac window chrome handling, and clearer notes about signing before wider release.

## v66 Beta - Accessibility And Elder Support

This version made MemoryPal more directly useful for older adults, people with memory changes, and caregiver-supported setup. It added Everyday Memory, persistent accessibility preferences, a senior-friendly layout preset, and simple person/routine/place/reminder cards that flow into normal review.

## v67 Beta - Onboarding, Read Aloud, And Smarter Planning

This version made the first launch friendlier and the study engine more accurate. New profiles open on a Welcome screen that sets the page order and comfort settings for a student, an everyday-memory user, a caregiver, or someone just exploring, followed by a short guided tour. Read aloud now works offline through the computer's built-in voice, and a More time setting slows timed displays and speech. Behind the scenes, review scheduling gained separate hard/good/easy steps, overdue credit, and load spreading; the Study Plan can look ahead over several days; Smart Check stopped penalizing answers that do not repeat the question; and the memory-technique generators no longer reuse pegs or palace spots on long lists. The support package also gained its first unit test suite. A follow-up fix hides the white flashes after the Welcome screen and between tour steps by building the new layout under a screen snapshot and swapping it in a single frame. This build is packaged as tester release 0.43.0.

## v68 Beta - Dashboard, Charts, Navigation, Media, And New Logo

This version made MemoryPal quicker to move around and more rewarding to come back to. The Dashboard now centres on today's saved study plan with tick-off steps, a progress strip with streak, level and XP, study modes picked for each persona, and the next badge to earn. Stats gained real charts and achievements. Navigation got a Ctrl+K page finder, a Back button, and app-styled dropdowns, and theme or text-size changes now rebuild out of sight and swap in one frame while popups appear already finished. Study Plans can be saved and followed day by day, with rest breaks, explain-it-back practice, and paced new cards. Media works without extra packages: audio recording and playback, Windows Camera video, image previews through Windows, and saved spoken cues, and document import now covers RTF, text encodings, and ordinary PDFs with a built-in reader. Saves skip merging when no other window has written, and the logo is cached on disk for a lighter startup. Finally, the logo was redesigned as a cleaner connected "memory path" M with mint and amber recall nodes and a small spark, updated everywhere it appears. This build is packaged as tester release 0.44.0.

## v69 Beta - In-App Feedback, Resize Outline, And Smoothness

This version made it easy for testers to get feedback back to the team and polished how the app feels. The Feedback Log can now send notes straight from the app, open them in the tester's email app or Gmail, or save them as a file, and it remembers which notes were already sent. Reports include only the notes and basic system details, never profile names or cards. Resizing now shows a Windows-style outline while dragging, in-page updates swap in finished in one frame, popups take keyboard focus properly and give it back when closed, flat buttons stop shifting their text when pressed, and text in labels can be selected and copied. Several small bugs were fixed along the way. This build is packaged as tester release 0.45.0.

## v70 Beta - Design System, Data Safety, And A New Logo

This version came from a full review against Khan Academy, Duolingo, and NeuroNation, aimed at making MemoryPal look professional rather than improvised.

Design:

- A global font setting had been drawing every title and heading at body size; removing it brought back the real type hierarchy.
- Buttons, choice pills, dropdowns, and text fields became one rounded set with a solid keyboard focus ring.
- Every colour pair was brought up to WCAG AA contrast.
- The navigation rail now shows all pages instead of six.
- The logo was redrawn as a flat lowercase "m" of two arches with an amber recall dot.

Features and data safety:

- Cards can finally be edited, reset, or deleted.
- Import confirms before replacing anything and keeps a copy of the old data.
- Saves keep a backup, so a damaged file no longer opens as an empty profile.
- A card deleted in one window can't be revived by another window.
- Profile names that would share a folder are refused.

Smarter study engine:

- Smart Check stopped accepting wrong numbers or flipped meanings.
- Multi-day plans stopped counting the backlog every day.
- Successful reviews always grow the interval.
- Pasted notes keep their years and decimals.

Security: document import got limits against decompression bombs, and PowerShell runs by its full path.

Rendering, measured with a new frame-recording check:

- Page switches, every scroll step, fullscreen, resizing, and theme changes now appear as single finished frames, with no tearing or white flashes.
- Rounded controls use opaque tiles, keeping the app as fast as before they were added.
- The navigation rail spaces its pages evenly and pins Settings at the bottom.

This version also starts the phone app: a React Native + Expo port in `mobile/` with five tabs, full review, quizzes, puzzles, plans, progress, and backups in the desktop's file format. Parity tests check its study logic against the desktop's.

Accounts and cloud sync arrive on both apps through Supabase: email codes, automatic field-by-field merging between devices, optional two-step sign-in, password strength and breach checks, and a growing wait after repeated wrong tries. Sign-in tokens stay in DPAPI or the phone's Keychain/Keystore, all access rules are enforced by the database, and `CLOUD_SYNC_SETUP.md` explains the project set-up.

This build is packaged as tester release 0.46.0. The installer, the Windows and macOS build scripts, and the tester guide were brought up to date for it, and the phone app's Android themed icon is now a proper one-colour mark.

## v71-v76 Beta - Five Hubs, Apple Design Pass, Sync, And Installers For Every Platform

v71 to v75 brought the Apple design pass (Mac menu bar, Command shortcuts, system font, native dialogs; iPad reading width and iOS sheets on the phone), the five-hub desktop rail with line icons, skeleton page loads, a display-paced wheel glide, and a fix for sync being refused on every account.

v76 is the pre-release review:

- Sync can't be stopped by one damaged cloud record, a huge number or a wrong type; such records are skipped.
- Loading a backup, starting over, or recovering a damaged data file no longer deletes cards on every synced device. The next sync merges with the cloud as if new.
- A miss on one device now wins a review conflict, so a forgotten card comes back soon.
- Starter cards deleted on one device stay deleted when a new device signs in.
- Undo after a sync no longer lowers the review count.
- Changes made while a sync is running go up right after it.
- On the phone, ratings made after a background sync are no longer lost, and Undo after Skip returns to the rated card.
- Deleting an account with two-step sign-in now needs the second step. The database also refuses non-object records and no longer grants delete rights it never used.
- Attachments keep only plain file extensions, and the Windows preview quotes every kind of apostrophe.
- Mac: wheel and trackpad scrolling at normal speed, a text box scrolls without moving the page, recording actions that only work on Windows are hidden, and the app shows its real version.
- Phone: no extra gap under the navigation bar, forms stay above the keyboard, the phone's own Reduce Motion is followed, dark mode covers the whole window on Android, unused Android permissions are removed, and the card list stays smooth while searching.
- Privacy Policy and Terms links are in Settings on both apps.

This build is packaged as release 0.47.0, the first with installers for Windows, macOS, Android and iOS built together by the Release Installers workflow.

## v77 Beta - Sign-In First, Automatic Sync, And A Top Tab Bar On The Desktop

From testing the 0.47.0 Android build:

- Both apps now open on sign-in for a new install (sign in, create an account, or continue without one), then the setup questions, then Today. The page shows once per device.
- Sync is automatic once signed in: a few seconds after a change, when the app is opened or brought back, and every five minutes. A "Sync automatically" switch in Account & sync turns it off, and "Sync now" is always there. The phone's Today header and the desktop's page header show whether everything is synced.
- Email codes are called "the code from the email" instead of "6-digit code", since the length is a Supabase setting.
- Phone: the tab bar keeps its labels at the system tab size (so "Progress" no longer cuts off with larger text), sits clear of Android's gesture bar and buttons, and shows labels beside icons on tablets. Side margins follow the screen width, and big titles grow less with the in-app text size so they fit on small phones.
- Desktop: the side rail is replaced by a tab bar across the top with the same five sections as the phone. Feedback sits on the right; on narrow windows the tabs drop to icons.

This build is packaged as release 0.48.0.

## v78 - Icons to Scale

The desktop header buttons now use the same drawn line icons as the tab bar, about half the button's size on every system, and the tab and hub-tile icons are a little larger. On the phone, icons grow with the in-app text size so they stay in step with their labels.

This build is packaged as release 0.48.1.

## v79 - Sign-in, Sync and Scrolling Check

- Sign-in and sync: a refresh token the server says was already used now signs out cleanly instead of failing every few minutes, and turning on two-step sign-in on one device asks the other devices to sign in again with the code. Signing out while a refresh is on its way stays signed out. On the desktop, signing in before confirming the email goes to the code box. Signing in on a new device during first launch waits for the account's data, so the setup questions aren't asked again.
- Scrolling (desktop): a sync that brings changes keeps the page where it was instead of jumping to the top; the wheel glide eases more evenly during a steady spin; precision touchpads move smoothly instead of in notch-sized jumps; background style work waits until scrolling stops. On the phone, cards don't flash pressed when a finger starts a scroll on them.
- Icons: the streak and sync chips in the desktop header use drawn line icons (flame, cloud, sync, warning) instead of tiny text symbols, and the Associations link icon is larger.

This build is packaged as release 0.48.2.

## v80 - Store Readiness

- Mac: opening an attachment and emailing feedback no longer fail on a Mac (they used a Windows-only call); saved feedback reports open in Finder.
- iPhone and iPad: the app icon has no transparency layer (App Store Connect rejects one), and the build now carries Apple's privacy manifest.
- Privacy Policy: corrected facts (one-time codes, where data is kept on Mac and phones, the hosting region and code sender) and a new "Deleting your account" section.

This build is packaged as release 0.48.3.

## v82-v84 - Developer Name, Smoother Edges and Final UI Review

- The Privacy Policy and Terms name the developer, Kirthik Sai Mouli Parthiban.
- Desktop: the title bar's close, minimise and maximise symbols, the tick in check boxes and the rounded corners of the loading skeleton are now antialiased like the rest of the icons, instead of jagged on Windows.
- Desktop: links, plan ticks and the time unit work from the keyboard; error text is easier to read in dark mode; the light focus ring is darker; the Feedback page speaks to everyone, not testers; study modes and the streak use drawn line icons; Library tools sit on a card; right-click copy works on a Mac.
- Phone: "Choose again" in Settings opens the persona chooser (with a way back); text boxes stay above the Android keyboard; Android tap targets are 48dp; switch "off" states are visible; Edit card asks before discarding changes; puzzles wait for "I'm ready" when a screen reader is on; the Study tab is titled "Review and quiz".

This build is packaged as release 0.48.4.

## v85 - Finished Policies and Store Packages

- The Privacy Policy and Terms are complete: contact memorypal09@gmail.com, last updated October 12, 2026, governed by California law; the draft banners are gone.
- The release now includes the signed Google Play bundle (`MemoryPal-Android-PlayStore.aab`) and the Microsoft Store package (`MemoryPal-Windows-Store.msix`) built with the Partner Center identity.

This build is packaged as release 0.48.5.

## v86 - Smooth Scrolling, Security Pass and Safer Account Switching

- Desktop: scrolling runs at the screen's full refresh rate (64 instead of 31 steps a second on a 60Hz Windows screen); touchpads follow your fingers 1:1; Macs use their real refresh rate (120Hz on ProMotion screens).
- Accounts: signing a profile or phone in to a different account now asks first (use that account's cards, add these cards to it, or sign out) instead of copying everything across; a copy is kept before switching. Signing two profiles in to one account warns first. Settings changed on two devices merge setting by setting.
- Security: a CAPTCHA check (Cloudflare Turnstile) runs before signing in, creating an account and emailing a code; the Mac keeps its sign-in in the Keychain; crafted study plans, PDFs and sync records can no longer freeze or crash the app; signing out ends the session on the server; Android no longer backs app data up to Google.
- Phone: 19 design fixes, including visible text-field borders, pressed states, large-text layouts, return-key flow on the sign-in form and a faster card list.
- The Privacy Policy lists Cloudflare Turnstile and GitHub Pages (October 15, 2026).

This build is packaged as release 0.49.0.

## v87 - AI Notes, Varied Quizzes and Talk-Back

- Make with AI: turn typed notes, a PDF or a photo of a page into study notes or practice questions, through MemoryPal's own server (a Supabase Edge Function) to Google's Gemini API. It needs an account, asks permission first, can be turned off in Settings, labels everything it makes "Made with AI, check it", and has a Report link. The Gemini key stays on the server.
- Quizzes mix question types (multiple choice, the other way round, fill the gap, true or false, match, put in order, recall), built by the same seeded logic on desktop and phone and checked by parity tests.
- Talk-back: hear each question and answer out loud, hands-free (phone speech recognition; Windows speech on the desktop, typed answers elsewhere). Read aloud on every card.
- A simpler set builder, and New and Rename set.
- Desktop: dropdowns and dialogs no longer clip their text, the scroll wheel glides like the touchpad, the title bar follows the theme, and dialogs, pop-ups and fields share the new look.
- The Privacy Policy and Terms have an AI section (October 18, 2026).

## v88 - AI Defaults and Docs

- AI uses Gemini 3.5 Flash-Lite by default (about 500 free requests a day for the whole key, against about 20 for the Flash models) and allows 10 requests per person a day; both apps say 10.
- The README, testing checklist, tester guide, sync setup and build notes cover the new features.

This build is packaged as release 0.50.0.

## v89 - Cards Sync Through Google Drive

- Cards, sets, reviews and settings sync through a hidden folder in the person's own Google Drive, on desktop and phone. MemoryPal's server keeps only the account.
- The first Drive sync of a signed-in profile moves its cards off the MemoryPal cloud and then deletes them there.

## v90 - Limits

- AI has a per-minute limit and a shared daily limit, and emailed codes say how many seconds to wait before asking again.
- The phone syncs on return to the app at most once a minute.

This build is packaged as release 0.51.0.

## v91 - AI That Follows Your Pattern

- Make with AI has an optional "How should it look?" box: describe the layout or focus in your own words, such as one line per date, and the notes and questions follow it.
- A second box, "Questions your teacher has asked", takes past exam questions; new questions copy their style, level and the parts of the material they pull from. Leave both empty and new questions follow the set's own questions. Both boxes are saved with the set.
- Sets have their own details that sync: a line about the set, an exam date with a countdown and a "Plan for the exam" button, and the two AI boxes.
- Saved notes belong to a set. The phone finally shows them (on the set's page and in Create > Saved notes) with a reader; the desktop Library filters them by set. AI cards made from saved notes open them at the part they came from.
- Memory techniques can use a set's answers and save each card's line as its memory hook. Puzzles can use a set's cards.
- AI questions name their topic so they make sense on their own, and each AI card quotes the sentence its answer came from. The phone's Talk-back screen no longer crashes in Expo Go.

This build is packaged as release 0.52.0.

## v92 - A Desktop App That Behaves Like One

- The Windows app uses the system title bar and frame (in the theme's colours), so it moves, snaps, resizes, minimises and goes full screen the way other apps do. The screenshot covers that hid redrawing during scrolling, resizing and full screen are gone: page changes pause painting while they are built (WM_SETREDRAW), and Windows fills new space with the app's background instead of white.
- Panels, text boxes, lists and tick boxes have rounded corners, and multi-line boxes look like the one-line fields with an accent ring while typing. Buttons keep the width of their label instead of stretching across the card, the small label above each page title is gone, and Library rows are more compact.
- Settings > Window has a single Full screen button (F11, Esc to leave).
- Run from the Python files, Settings explains that Google Drive sync needs latest_app/memorypal/google_client.py, which installed versions already have.
- Full screen on Windows changes the window's style instead of using Tk's full screen, which built a brand-new window each time and flashed white when leaving it. This is how Chrome and Windows Terminal do it.
- On 120-165Hz screens, pages that take longer than one refresh to draw scroll on every second refresh, evenly, instead of landing two steps in one refresh and none in the next.
- Tooltips are smaller and sit under the pointer, with system rounded corners on Windows 11. Notices ("Card saved") rise in at the bottom centre on a raised panel instead of a black box in the corner. Dialog buttons line up on the right at their natural width, and the title bar names the app instead of repeating the question. Unchosen options in choice rows no longer look like empty text boxes. The round profile button is no longer clipped.
- Windows: when the window grows (dragging an edge, maximising, full screen) the new space is filled with the app's background straight away instead of showing white until Tk repaints, as Chrome and Electron do. On 144Hz screens heavy pages may also step on every third refresh (48 a second, evenly).
- The welcome has a fourth question, whether to use AI, answered "Yes" unless changed, with what is sent and to whom spelled out beside it. The header's profile circle is smaller and its letter sits exactly in the middle.

This build is packaged as release 0.52.0.

## v93 - Says Things The Way People Do

- Page titles match the tabs and read in sentence case on both apps: the desktop's "Dashboard" is Today, "Stats & Streaks" is Progress, "Decks" is Sets, and "deck" is "set" everywhere people read it.
- Library rows say "Due tomorrow" and "Last: Got it" instead of a raw date and "New 0%"; set tiles separate new cards from ones that need focus, and their More menu holds Make with AI so the buttons fit.
- Wording that explained how the app was built is gone from Spaced review and Study plan, and an empty review page offers a next step.
- Quiz fixes: a true-or-false answer that ends in a full stop no longer gets a second one, everyday words like "over" aren't blanked out or offered as wrong answers, and the phone reads the question and choices from one button.
- The phone's two-week chart labels its dates instead of an ambiguous run of single letters, compares with the week before, and Today shows "Start a streak today" instead of "0 days in a row".

## v94 - Dialogs That Sit Right

- Profiles is one tidy list: each profile has its initials, its name, and the same columns of buttons, so names no longer crowd the Switch button. Rename and Delete are in each row's More menu, the profile in use says "In use now", and the bottom has New profile on the left and Done on the right instead of two full-width bars. It no longer leaves an empty band under the list.
- Dialog buttons always stay on screen: on a short or zoomed screen the text runs out of room first, so Create account and the AI question can always be answered. Create account puts birth month and year, and the two password boxes, side by side.
- Error lines in dialogs take no room until there is something to say (the window grows to show it), so there is no blank gap under the fields. Sign in's two links share one line.
- Longer dialogs can be resized: the AI question, Edit card (both kinds), set details and saved notes. Their text boxes grow with the window, and they no longer open almost as wide as the main window. Short questions (OK, Cancel, Rename) keep their size, like system message boxes.
- Notices ("AI notes and questions are on") always show their thin edge. Clearing the shape-picture cache sometimes threw away the edge layer, so it came and went.
- The main window can be resized again. Its minimum was the full design size, so at 150% on a 1080p screen it equalled the starting height and the window couldn't be made shorter. It can now shrink to about half a laptop screen. It opens at most of the screen's free area (taskbar excluded), centred a little above the middle, and the streak and sync line under the page title no longer gets cut short in a narrow window. Its flame and cloud symbols have a fixed gap before their words instead of a narrow space.
- Main and plain buttons are the same height everywhere (the main one used a larger font). An error message's OK button is the usual accent colour; red is kept for buttons that delete things. Set details' hints wrap to the width of the window.

## v98 - Bold, Italics and Highlighting

Notes can now be bold, italic or highlighted on the desktop and the phone, and saved notes can be edited. Words made bold or highlighted become the blank when notes are turned into questions.

- B, I and Highlight buttons sit over the Paste notes box and in the new Edit notes (Library > Read > Edit on the desktop, Edit notes on the phone's notes page). Desktop shortcuts: Ctrl/Cmd+B, Ctrl/Cmd+I, Ctrl/Cmd+Shift+H.
- The formatting is stored as Markdown-style marks in the text (`**bold**`, `_italic_`, `==highlight==`), so nothing about saving or syncing changed. Marks only count next to words, so "2 * 3", "a == b" and snake_case stay as typed.
- The desktop box shows the formatting as you type with the marks faint; the phone shows "How it looks" under the box. Read aloud, Library previews and cards skip the marks.
