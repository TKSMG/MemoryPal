# MemoryPal Recovery Package

This folder is the recovered working package for MemoryPal.

The original `outputs` folder was empty when this recovery was made, so the latest app here is a rebuilt single-file Python version based on the requirements and revision history from this project.

## What to Open

- Latest app: `latest_app/MemoryPalDesktop.py`
- Human notesheet: `notes/MemoryPal_Memory_Techniques_Human_Notesheet.md`
- Development stages: `development_versions/`
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
- Chunk-based capture, where each study bit is separate.
- Flashcard-style prompt and answer cards.
- Smart Check for close-enough typed responses.
- Text, image, audio, and video attachments where they make sense.
- Review, quiz, repetition path, associations, games, and library views.
- The clarified repetition pattern: start 5, range 3 gives `5`, `5-4`, `5-4-3`, then `3-2-1`.
- Scrollable screens so buttons do not disappear below smaller windows.

## About the Development Stages

The development version files are reconstructed milestone prototypes, not exact historical source snapshots. They exist so you can show the development path of the project across the revisions that were requested.
