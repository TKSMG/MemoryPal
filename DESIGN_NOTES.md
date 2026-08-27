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

## Main UX Goals

The app should always answer three questions quickly:

- What should I study now?
- What am I trying to remember?
- What happens after I answer?

## Desktop Feel

The desktop app should stay fast and lightweight, but it should not feel unfinished. The visual style uses a modern dark interface, clear cards, hover hints, a collapsible rail, and simple page transitions.

The goal is not to add decoration everywhere. The goal is to make the app feel intentional and easy to trust.

## Mobile Feel

The mobile version should not copy the desktop layout. It should use fewer controls per screen, larger buttons, simple bottom navigation, and native phone features for recording and file picking.

The Kivy prototype is only a starting point. A real mobile release should be tested on actual phones before it is treated as finished.
