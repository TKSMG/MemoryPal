# Building MemoryPal

MemoryPal is currently a Python/Tkinter desktop app. The easiest shipping path for PC is a Windows `.exe` made with PyInstaller.

## Desktop Requirements

Install Python 3.11 or newer from the official Python website. During install, enable the option that adds Python to PATH.

Then install the optional packages:

```powershell
python -m pip install -r requirements-desktop.txt
```

Speech-to-text is optional. `SpeechRecognition` supports the prototype transcription flow, and microphone dictation may also need `PyAudio`, which can require a normal Windows Python setup. The default recognizer used in the prototype may need an internet connection.

## Build The Windows App

From the project folder:

```powershell
build_windows.cmd
```

If the build succeeds, the app appears here:

```text
release\MemoryPal.exe
```

The `release` folder is ignored by Git on purpose. The source code and build instructions belong in the repository; the `.exe` is better attached later as a GitHub Release file.

## Why The EXE Might Not Build Here

The Codex workspace can compile the source, but the bundled Python environment may not be a full desktop Python install with working Tkinter packaging support. If the local build fails here, run the same build command from a normal Windows Python installation.

## Mobile Direction

The `mobile_app/` folder contains a Kivy prototype for Android and iOS. It is not a finished App Store or Play Store app yet, but it gives the mobile version a real starting point with touch-friendly screens and the same MemoryPal workflow.

Android packaging should be done with Buildozer on Linux or WSL. iOS packaging should be done on macOS with Kivy-iOS and Xcode.
