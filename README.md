# MemoryPal

This folder contains the current MemoryPal desktop app, project notes, and development history.

## What to Open

- Latest app: `latest_app/MemoryPalDesktop.py`
- Memory techniques notes: `notes/MemoryPal_Memory_Techniques.md`
- Development stages: `development_versions/`
- Version journal: `development_versions/VERSION_JOURNAL.md`
- Program outline: `development_versions/MemoryPal_Project_Outline.py`
- GitHub setup: `GITHUB_SETUP.md`
- Commit guide: `COMMIT_GUIDE.md`
- Command Prompt GitHub helper: `SETUP_GITHUB_REPO.cmd`

## How to Run the Latest App

Open a terminal in this folder and run:

```powershell
python latest_app\MemoryPalDesktop.py
```

The app stores its local data in:

```text
%USERPROFILE%\MemoryPalData
```

## What the Latest App Includes

- A modern Tkinter desktop app shell.
- A warmer app header with local-save status, softer controls, styled cue menus, and hover-highlight cards.
- In-progress page drafts are preserved while switching sections.
- A Focus mode that groups due, weak, and fresh cards into a clearer study queue.
- Dashboard recommendations for the next best study action.
- Dashboard mastery progress, due/learning/mastered chips, and a small daily-action prompt.
- Hover hints on navigation and major actions so first-time users can understand controls without a manual.
- Chunk-based capture, where each study bit is separate.
- Direct `question => answer` card creation for normal flashcard workflows.
- Separate question and answer boxes for making exact prompt-answer cards.
- Repetition now also uses separate question/title and answer boxes instead of relying on a single prompt-answer text field.
- Repetition drafts preserve staged items, typed answers, bulk notes, and start/range settings when switching pages.
- Question cards can also be saved without a stored answer for self-check prompts.
- A separate Test Lab page for testing/review and returning to the previous section.
- Test Lab preserves the typed answer for the current card if you switch away and return.
- Review cards now use Test Lab as the main answer/reveal/Smart Check/rating surface.
- Self-check quiz cards can open in Test Lab instead of expanding answers inline.
- Flashcard-style prompt and answer cards.
- Smart Check for close-enough typed responses.
- Smart Check visually highlights the suggested bucket.
- Attached cues show inside study views: text previews, image previews when supported, and clear play buttons for audio/video.
- Text, image, audio, and video attachments where they make sense.
- Text, audio, and video can be brought in as file imports.
- Text can be saved as an on-demand text note, and audio/video recording controls are included for desktop systems with optional recorder dependencies.
- Audio and video capture is decluttered into compact cue menus, with import or record chosen from the cue button instead of a separate chooser dialog.
- Set Builder cues are now compact menu buttons for text, image, audio, and video.
- Review, quiz, repetition path, associations, games, and library views.
- Puzzles now include Sequence Recall, Word Recall, Pair Recall, and Missing Item challenges.
- Quiz, Associations, and Puzzles preserve in-progress state across page switches.
- The clarified repetition pattern: start 5, range 3 gives `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Library search with All, Due, Weak, and Captures filters.
- Subtle section transition animation and cleaner labeled answer panels.
- Association tools for acronyms, mini-stories, peg lists, memory palace routes, chunk maps, and link chains.
- Skeleton-style page loading with a small spinner and placeholder rows.
- Pointer-aware page scrolling, so the mouse wheel works when the cursor is over the active section.
- Keyboard-friendly scrolling on long pages with Page Up, Page Down, Home, and End.
- Scrollable screens so buttons do not disappear below smaller windows.
- Repetition now uses one continuous scrollable page for the builder, staged items, controls, and generated rounds.
- Learning-app polish inspired by mature study products: clearer next steps, visible progress, focused review, and less cluttered mode cards.
- Softer page reveal animation and extra guide panels in practice-heavy modes.

## About the Development Stages

The development version files are reconstructed milestone prototypes, not exact historical source snapshots. They exist so you I show the development path of the project across the revisions.

Each `MemoryPal_vXX_*.py` file is now standalone, so it does not import a shared stage helper.

The newest reconstructed milestone is `MemoryPal_v29_beta_page_draft_preservation.py`, which records the page draft preservation pass before the app is prepared for a future GitHub repository.

## Mobile Version Note

A separate mobile version should be made later. That version should use native phone APIs for microphone recording, camera/video recording, file picking, permissions, storage, and large touch controls instead of trying to reuse the desktop Tkinter interface directly.
