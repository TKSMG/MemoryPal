# MemoryPal Design Notes

I want MemoryPal to feel like a calm study app, not a giant school form.

The current direction is based on a few patterns that good learning apps tend to share:

- Start with a clear daily action.
- Keep sessions short enough to begin without overthinking.
- Show progress, streaks, and due work without making the app stressful.
- Use a focused testing screen when the learner is answering.
- Keep audio, notes, images, and other cues close to the task.
- Keep navigation steady; use focus mode or fullscreen when the user needs more room.
- Ask who the app is for on first launch, then show only the pages that person needs first.
- Make mistakes easy to recover from with undo, skip, and repeat options.
- Keep dialogs visually consistent with the app so profile names, recording prompts, warnings, and confirmations do not feel like a separate older program.

## Main UX Goals

The app should always answer three questions quickly:

- What should I study now?
- What am I trying to remember?
- What happens after I answer?

For testing builds, the app should also answer one project question quickly:

- What felt helpful, confusing, broken, or hard to use?

## Desktop Feel

The desktop app should stay fast and lightweight, but it should not feel unfinished. The visual style uses soft dark and light themes, clear cards, hover hints, a fixed navigation rail, and quiet page reveals. The rail stopped collapsing in v61 because the moving page felt unstable during study.

The goal is not to add decoration everywhere. The goal is to make the app feel intentional and easy to trust.

Dialogs should feel like part of the app. Stock system prompts are still useful for file picking, but app decisions such as profile names, reset confirmation, recording length, and error messages should use MemoryPal's own modal style.

Page changes should be covered until the next page is ready. Fast feedback still matters, but the transition should not flash, slide, or pull attention away from the study task.

Custom Canvas shapes should use antialiased image drawing when Pillow is available. The app should still run without Pillow, but polished builds should install the image-preview extra so rounded titlebar and navigation controls look softer.

The app can reuse the feeling of the startup fade after layout changes without fading the whole app window. Build the new state first, then fade away a temporary same-color overlay so the background shell stays solid.

The logo is a connected "memory path" M: one unbroken white stroke with three recall nodes where the path turns (mint for the first and recalled idea, amber for the link that makes it stick) and a small spark for the moment something is remembered. It sits on a blue-to-violet tile that reads on both the dark rail and light backgrounds. Keep it flat and clean: one soft shadow, no extra glows or ghost lines. At 32px and below, drop the node cores and spark so the M stays sharp.

The navigation mark should use the generated MemoryPal logo as the standard product mark. A plain letter should only appear as an emergency fallback if the logo renderer fails.

The titlebar and navigation should use the same mark so the app feels like one product instead of a mix of sketches.

Checked-in icon exports should stay in `assets/` so the project has a reusable `.ico`, PNG preview, and scalable SVG even before a packaged release exists.

Wide builder pages need horizontal scrolling when they use side-by-side panels. Keeping the page reachable is more important than forcing every panel to squeeze into a narrow viewport.

Custom resize grips should apply the final size on release. This avoids constant redraw jitter and gives the fade a single settled state to reveal.

Feedback capture should stay local, short, and easy to export. Sending is always the tester's choice: one button sends directly, with email and a saved file as fallbacks, and the report says plainly what it includes. It never includes profile names or study cards. Testers should not need an account just to say that something was confusing, too small, broken, or useful.

Legacy data migration should copy old files forward without overwriting newer app-data changes. Long testing periods make data trust part of the user experience.

## Navigation And Motion

People should never feel lost: every page is reachable from the rail, from Ctrl+K, and by going Back. Big changes (theme, text size, rebuilding the shell) happen out of sight and appear in one frame; popups appear already finished instead of fading.

Resizing shows an outline of the new size while dragging and applies it once on release, the same way Windows does, so the page never reflows repeatedly. Small in-page updates use the same snapshot swap as page changes.

## Dashboard And Progress

The Dashboard should answer "what do I do now?" with today's plan steps first, then quick study modes chosen for the person's persona. Progress (streaks, levels, badges, charts) should encourage without pressure: badges show how close the next one is, and charts explain what they mean in plain words.

## First Run And Onboarding

A new profile should not open on a page full of tools. The Welcome screen asks one plain question (who is using MemoryPal?) and uses the answer to set page order, text size, and calmer defaults. Every choice stays editable in Settings, and choosing again resets only the settings the persona controls.

Existing profiles skip the Welcome screen. People already using the app should never be interrupted by setup they did not ask for.

The tour should be short (five or six steps), describe what the person will do on each page rather than listing every button, and always offer an End Tour exit.

## Read Aloud And Pace

Read aloud should work without extra downloads or internet access, so it uses the voice already built into the operating system. Card text goes through standard input, never the command line, so unusual text cannot break the command.

More time is a pace setting, not a separate mode: it stretches timed displays and slows the voice while leaving every other page the same.

## Memory Technique Output

Each idea needs its own hook. When a peg list, memory palace, or story runs past its built-in list, it continues with a clearly different twist (golden, frozen, garden, garage) instead of reusing a peg or place, because two ideas sharing one hook interfere with each other.

## Mobile Feel

The mobile version should not copy the desktop layout. It should use fewer controls per screen, larger buttons, simple bottom navigation, and native phone features for recording and file picking.

The Kivy prototype is only a starting point. Its validation and save feedback should use the same calm in-app language as the desktop app, while a real mobile release should still be tested on actual phones before it is treated as finished.
