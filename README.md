# MemoryPal Recovery Package

This folder is the recovered working package for MemoryPal.

The original `outputs` folder was empty when this recovery was made, so the latest app here is a rebuilt single-file Python version based on the requirements and revision history from this project.

## What to Open

- Latest app: `latest_app/MemoryPalDesktop.py`
- Human notesheet: `notes/MemoryPal_Memory_Techniques_Human_Notesheet.md`
- Development stages: `development_versions/`
- Version journal: `development_versions/VERSION_JOURNAL.md`
- Readable program outline: `development_versions/MemoryPalDesktop_readable_outline.py`

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
- A Focus mode that groups due, weak, and fresh cards into a clearer study queue.
- Dashboard recommendations for the next best study action.
- Chunk-based capture, where each study bit is separate.
- Direct `question => answer` card creation for normal flashcard workflows.
- Separate question and answer boxes for making exact prompt-answer cards.
- Flashcard-style prompt and answer cards.
- Smart Check for close-enough typed responses.
- Text, image, audio, and video attachments where they make sense.
- Text, audio, and video can be brought in as file imports.
- Text can be saved as an on-demand text note, and audio/video recording controls are included for desktop systems with optional recorder dependencies.
- Review, quiz, repetition path, associations, games, and library views.
- The clarified repetition pattern: start 5, range 3 gives `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Library search with All, Due, Weak, and Captures filters.
- Subtle section transition animation and cleaner labeled answer panels.
- Scrollable screens so buttons do not disappear below smaller windows.

## About the Development Stages

The development version files are reconstructed milestone prototypes, not exact historical source snapshots. They exist so I can show the development path of the project across the revisions that were requested.

Each `MemoryPal_vXX_*.py` file is now standalone, so it does not import a shared stage helper.

## Mobile Version Note

A separate mobile version should be made later. That version should use native phone APIs for microphone recording, camera/video recording, file picking, permissions, storage, and large touch controls instead of trying to reuse the desktop Tkinter interface directly.
