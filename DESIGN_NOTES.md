# MemoryPal Design Notes

I want MemoryPal to feel like a calm study app, not a giant school form.

The current direction is based on a few patterns that good learning apps tend to share:

- Start with a clear daily action.
- Keep sessions short enough to begin without overthinking.
- Show progress, streaks, and due work without making the app stressful.
- Use a focused testing screen when the learner is answering.
- Keep audio, notes, images, and other cues close to the task.
- Let the user hide navigation when they need more focus.
- Make mistakes easy to recover from with undo, skip, and repeat options.
- Keep dialogs visually consistent with the app so profile names, recording prompts, warnings, and confirmations do not feel like a separate older program.

## Main UX Goals

The app should always answer three questions quickly:

- What should I study now?
- What am I trying to remember?
- What happens after I answer?

## Desktop Feel

The desktop app should stay fast and lightweight, but it should not feel unfinished. The visual style uses a modern dark interface, clear cards, hover hints, a collapsible rail, and simple page transitions.

The goal is not to add decoration everywhere. The goal is to make the app feel intentional and easy to trust.

Dialogs should feel like part of the app. Stock system prompts are still useful for file picking, but app decisions such as profile names, reset confirmation, recording length, and error messages should use MemoryPal's own modal style.

## Mobile Feel

The mobile version should not copy the desktop layout. It should use fewer controls per screen, larger buttons, simple bottom navigation, and native phone features for recording and file picking.

The Kivy prototype is only a starting point. Its validation and save feedback should use the same calm in-app language as the desktop app, while a real mobile release should still be tested on actual phones before it is treated as finished.
