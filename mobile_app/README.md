# MemoryPal Mobile Prototype

This folder is the starting point for a future iOS and Android version of MemoryPal.

The desktop app should stay in Tkinter for the PC version. The mobile app needs its own interface because phones need larger touch targets, native file picking, microphone permissions, camera permissions, and a simpler navigation pattern.

## What This Prototype Includes

- A touch-friendly dashboard.
- Capture for separate question and answer cards.
- In-app validation and confirmation dialogs for the capture flow.
- Review with prompt, answer, Smart Check, and reveal.
- Repetition path using the same `5`, `5-4`, `5-4-3`, `3-2-1` idea.
- A simple resources screen for notes, audio, images, and video.

## Run Locally

```powershell
python -m pip install -r ..\requirements-mobile.txt
python MemoryPalMobile.py
```

## Packaging Direction

Android should use Buildozer on Linux or WSL.

iOS should use Kivy-iOS on macOS with Xcode.

This prototype is not the final mobile app yet. It is the first shared-code direction for phone testing.
