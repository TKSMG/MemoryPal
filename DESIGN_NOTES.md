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

Page changes show a skeleton of the next page until it is ready. Fast feedback still matters, but the transition should not flash, slide, or pull attention away from the study task.

Custom Canvas shapes should use antialiased image drawing when Pillow is available. The app should still run without Pillow, but polished builds should install the image-preview extra so rounded titlebar and navigation controls look softer.

The app can reuse the feeling of the startup fade after layout changes without fading the whole app window. Build the new state first, then fade away a temporary same-color overlay so the background shell stays solid.

The logo is a lowercase "m" drawn as one unbroken white line of two arches (one idea leading to the next), with a single amber dot at the top right for the idea you just recalled. It sits on a flat blue tile with only a gentle top-to-bottom shade. The earlier blue-to-violet gradient, sparkle and bead-like nodes were dropped in v70: sparkles and glossy purple gradients are what generic AI-made apps look like, and the beads blurred at small sizes. Keep it flat: no shadows, glows, sparkles or extra colours. The mark is simple enough to need no special small-size version; it stays crisp at 16px.

The navigation mark should use the generated MemoryPal logo as the standard product mark. A plain letter should only appear as an emergency fallback if the logo renderer fails.

The titlebar and navigation should use the same mark so the app feels like one product instead of a mix of sketches.

Checked-in icon exports should stay in `assets/` so the project has a reusable `.ico`, PNG preview, and scalable SVG even before a packaged release exists.

Wide builder pages need horizontal scrolling when they use side-by-side panels. Keeping the page reachable is more important than forcing every panel to squeeze into a narrow viewport.

Custom resize grips should apply the final size on release. This avoids constant redraw jitter and gives the fade a single settled state to reveal.

Feedback capture should stay local, short, and easy to export. Sending is always the tester's choice: one button sends directly, with email and a saved file as fallbacks, and the report says plainly what it includes. It never includes profile names or study cards. Testers should not need an account just to say that something was confusing, too small, broken, or useful.

Legacy data migration should copy old files forward without overwriting newer app-data changes. Long testing periods make data trust part of the user experience.

Data trust also covers damaged files and two open windows:

- Every save keeps the previous file as `memorypal-data.json.bak`.
- A damaged data file is copied aside and the last good save is loaded. Before v70, a damaged file loaded as an empty profile, and the next save wrote over it.
- A card deleted in one window stays deleted, even when another window saved in the meantime.
- Two profile names that would share a data folder ("My Profile" and "my-profile") are refused, because deleting one would have deleted the other's cards.

## Design System (v70)

These rules came out of a full review against Khan Academy, Duolingo and NeuroNation. All three feel professional for the same reasons: one clear next action, a consistent set of controls, real type hierarchy, and colour used only to mean something.

Colour and contrast:

- Every text/background pair meets WCAG AA (4.5:1). That includes white text on primary, green, danger and violet in light mode, and those colours used as text on cards.
- Filled controls never hard-code white text. `on_color(fill)` picks white or dark ink, whichever reads better. Bright dark-mode accents such as `#65afff` get dark text, because white on them is only 2.3:1.
- Colours are tokens in `constants.py` (`primary`, `rail_active`, `rail_text`, `rail_muted`, `focus`, `on_light`, ...). Don't use hex literals in views.
- A secondary button that would vanish into a tinted card is lifted to the card colour automatically.

Type: the scale is Title 28, H2 18, body 12, muted 11 (before the text-size multiplier). Do not set a global `*Font` option. It gives every ttk widget its own font, which overrides the style font, and until v70 it flattened every title and heading to body size. Fonts go on styles, or on classic Tk widget classes only.

Controls: buttons, dropdowns, choice pills and text fields are rounded 9-slice image elements (`install_rounded_controls`).

- Their corners take the colour of the surface they sit on, applied when the control is mapped.
- Text fields always show an edge. A white field on a white card with no border gives no hint of where to type.
- Use `row_button`, `solid_button` or a ttk style. Avoid new classic `tk.Button`s, which can't share the look.

Focus: keyboard focus is always visible as a solid amber rounded ring (WCAG 2.4.7). It is not an opt-in setting. The setting and high contrast only make the ring thicker.

Navigation rail:

- The rail holds five destinations, the same as the phone's tabs: Today, Study, Create, Practice and Progress. Feedback and Settings are pinned at the bottom. It still falls back to paging on very short windows or very large text.
- The active destination is a calm filled pill, not a bright block. Pages inside a destination (Review inside Study, Puzzles inside Practice) light up their destination.
- The line above each page title names the destination it belongs to.

Destructive actions: never put them next to everyday actions. Reset all data lives in Settings. Delete card lives inside the card editor, behind a confirmation. Import shows how many cards a backup has and keeps a copy of the current data before replacing it.

### Five destinations (v72)

The rail used to hold 17 pages. Duolingo has 5 tabs and Khan Academy about 4, and scanning 17 labels was slow, especially for older users. The pages are now grouped into five destinations (`HUBS` and `HUB_PAGES` in `MemoryPalDesktop.py`):

- **Today**: Dashboard, which also leads to the Study Plan.
- **Study**: a hub page with Review, Focus, Quiz, Repetition and Test Lab.
- **Create**: a hub page with Capture, Decks, Library and Cue Lab.
- **Practice**: a hub page with Memory Gym, Everyday Memory, Associations and Puzzles.
- **Progress**: Stats.

Hub pages show one tile per page, with a live count where it helps ("4 cards due now"). The tiles follow the profile's page order, so Everyday Memory comes first for the everyday and caregiver personas. Settings → Page Order now sets that order inside each destination. Every page stays reachable through Ctrl+K and Back. Feedback moves into Settings or the help menu once testing ends.

## Platform Conventions

Each build should feel native where it runs, checked against Apple's Human Interface Guidelines (audit of 2026-10-11):

- **Mac:** a real menu bar (About, Settings… ⌘,, Edit, View, Go, Window, Help). Shortcuts use Command, and on-screen hints are written the Mac way (⌘K, ⌘Z, ⌘[ for Back). Text uses the system font instead of Segoe UI. Dialogs keep the native frame, so close is top-left. Tk only displays menu shortcuts, so every shortcut shown in a menu must also be bound.
- **Windows:** the custom title bar and borderless dialogs stay. Shortcuts are written Ctrl+K.
- **iPhone and iPad:** screens stop growing at a 720pt reading width and centre, so iPad lines stay readable. Sheets have Cancel or Done in the bar. Text follows Apple's styles (Large Title 34, Title 2 22, Headline 17 semibold, Body 17, Footnote 13), with sentence-case labels rather than spaced capitals. Buttons and cards shrink slightly the moment they're pressed.
- **Reduce motion** means a cross-fade, not no transition: people still see that the screen changed.

## Navigation And Motion

People should never feel lost: every page is reachable from the rail, from Ctrl+K, and by going Back. Big changes (theme, text size, rebuilding the shell) happen out of sight and appear in one frame; popups appear already finished instead of fading.

Resizing shows an outline of the new size while dragging and applies it once on release, the same way Windows does, so the page never reflows repeatedly. Small in-page updates use the same snapshot swap as page changes.

### Rendering Rules (v70)

Tk on Windows paints each widget separately and later than it is moved or created, which shows up as tearing and as elements flashing in. These rules keep every change appearing as one finished frame:

- **Every page switch shows a skeleton** (`show_view`). `show_page_skeleton` paints a placeholder of the page's layout ("list", "grid" or "study", from `SKELETON_PAGES`) and switches the title and rail straight away, so every click answers at once and every page change looks the same. The page is built underneath it, out of sight, and the skeleton comes off with painting paused (`set_redraw_frozen`), so the finished page is drawn in one pass. No screen snapshot is used for page changes; re-showing the current page is an in-place update and still uses one.
- **Skeletons are drawn from the theme**: surface-coloured cards with soft bars for text, never a spinner or a blank page.
- **Control artwork is made ahead of time.** The rounded tiles for buttons, menus and fields on each card colour are worked out while the app is idle after starting (`warm_corner_styles`), one style per timer tick, instead of on the first visit to a page.
- **Scrolling runs under one snapshot of the scrolling area** (`ScrollFrame._present`). Without it, cards moved before their text was redrawn. The snapshot goes up on the first step and each later step only swaps its picture (`refresh_screen_cover`), so a step waits for one screen refresh instead of two; it comes down 90ms after scrolling stops.
- **Snapshots copy the app's own window, not the screen.** In-page updates and scroll steps pass `source=` to `show_screen_cover`, which copies from the window's device context (about 1ms, from memory) instead of reading back the whole composed screen (10-50ms). Because that copy can't include other windows, the snapshot is slotted into the z-order directly above the app, under any dialog, tooltip or other program already above it. Resizing still copies the screen, since the window grows past its old area.
- **The wheel glides at the screen's refresh rate.** Each notch moves a target, and every 16.7ms of time covers half the remaining distance, so a notch eases in over about 100ms and a fast spin becomes one continuous glide. Steps are scheduled one screen refresh apart (30, 60, 144Hz..., read from Windows with `display_refresh_hz` when each glide starts, 60 elsewhere), counted from the start of the previous step. While gliding, Windows is asked for 1ms timers (`set_fine_timers`): its default ~15.6ms timer tick made an 8ms wait last 16 or 31ms, so the glide stepped unevenly. A scrollbar drag, Page Up/Down, Home or End takes over from it. With Reduce motion on, each notch jumps straight there.
- **Keep pages short.** Tk's layout time grows with the number of widgets on a page, and every scroll step pays for it. Long lists show a preview or a page at a time: Library builds 20 cards per "Show more", and Focus lists 12 due cards with a count of the rest.
- **Snapshots are click-through** (`WS_EX_TRANSPARENT`), so a click or drag during the swap still reaches the app.
- **Images drawn in widgets must be opaque.** Tk on Windows draws a transparent image by reading the screen back on every redraw; with rounded buttons that took startup from about 1s to 14s and made pages paint piece by piece. Rounded tiles are baked onto the colour of the surface they sit on, with a separate set per surface.
- **Large 9-slice tiles.** ttk repeats an image element's middle rather than stretching it, so tiles are built large (in C, with Tk's photo copy) and the element is given a small minimum size.

How to check: run `python tools\render_check\render_probe.py <outdir>` on Windows. It records the window at screen rate while it switches pages, scrolls, goes fullscreen, resizes, and changes theme and text size. For each scenario it reports how many distinct pictures appeared, any white flash, and any "mixed" frame that is neither the before nor the after state; mixed frames are saved as PNGs. A clean result is `changes=1 mixed_frames=0` for every scenario except scrolling. For scrolling, every saved frame should be a whole, fully drawn page.

Speed budget (150 cards): startup about 1.5s, most page switches under 0.25s, Library and Stats under 0.4s. A wheel step on the Dashboard about 20ms, on Library about 35ms.

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

## Accounts And Sync

Accounts are optional and never block studying: the apps work fully offline, and sync runs quietly in the background (20 s after a change on the desktop, 15 s on the phone, on launch, and every 10 minutes).

- **Merging, not overwriting.** Each card, capture, settings group and day of activity is its own sync record. Both apps keep the last synced copy and merge field by field; the review schedule moves as one group and the side with more progress wins. An edit beats a delete, so nothing studied is lost.
- **Plain-language account screens.** Codes rather than links (links break across devices and confuse older users), one question per step, a live strength line under new passwords, and friendly messages for every server error.
- **Security lives on the server.** Row Level Security protects every row, and a restrictive policy makes two-step accounts finish the second step before any data is readable. The apps make no access decisions of their own: there are no client-side admin checks, because anything decided on a device can be changed by whoever holds it.
- **Tokens in protected storage.** Windows DPAPI, the iOS Keychain or Android Keystore, and `sessionStorage` on the web build. Never `localStorage`, where any script on the page could read a long-lived token.
- **Device checks are for friendliness.** Password rules (at least 10 characters, not common, not the email name, no runs like 1234), a breached-password lookup that sends only a 5-character hash prefix, and a wait that grows after five wrong tries give quick feedback. The server's rate limits and password policy are the real protection (`CLOUD_SYNC_SETUP.md`).

## Mobile Feel

The mobile version (`mobile/`, React Native + Expo) doesn't copy the desktop layout. It has five bottom tabs (Today, Study, Create, Practice, Progress), one main action per screen, large targets, and native share sheets and file pickers. The desktop rail now uses the same five destinations.

Why React Native + Expo rather than Kivy or Flutter: the controls are real native ones, so TalkBack and VoiceOver work. For this audience that is non-negotiable, and Kivy has no screen-reader support. It runs on an actual phone straight away through Expo Go, needing no Mac or Android SDK, and one TypeScript codebase also gives a web build and a straightforward path to cloud sync.

Rules carried over from the desktop:

- **Colour and type:** the same WCAG AA palette, text on fills chosen by contrast, and the Comfort / Large / Extra Large text sizes. The phone's own font-size setting applies on top.
- **Touch and screen readers:** targets are at least 44–52pt. Every control has an accessibility role and label. Groups of choices are radio groups, and toggles are switches.
- **Calm results:** Smart Check results and puzzle feedback are announced politely (live regions), and the simple-language wording matches the desktop's.
- **Never rushed:** puzzles show a countdown and an "I'm ready" button. More time doubles every timer and slows the voice.
- **Ending a session:** every review ends with a summary of how many cards were reviewed and remembered, and which were missed. Duolingo's end-of-lesson screen is the model.

Behaviour lives in `mobile/src/core/`, a line-by-line port of `latest_app/memorypal/`. Parity tests (`tools/parity/make_fixtures.py`) check that both versions give identical results. Change the logic on both sides together, regenerate the fixtures, and run the tests.
