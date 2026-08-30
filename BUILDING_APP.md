# Building MemoryPal

MemoryPal is currently a Python/Tkinter desktop app. The easiest shipping path for PC is a Windows `.exe` made with PyInstaller.

## Desktop Requirements

Install Python 3.11 or newer from the official Python website. During install, enable the option that adds Python to PATH.

The app can run with Python's standard library. Optional packages unlock document extraction, image previews, recording, spoken cues, and speech-to-text experiments:

```powershell
python -m pip install -r requirements-desktop.txt
```

Speech-to-text is optional. `SpeechRecognition` supports the prototype transcription flow, and microphone dictation may also need `PyAudio`, which can require a normal Windows Python setup. The default recognizer used in the prototype may need an internet connection.

The `.exe` build only needs the build requirements:

```powershell
python -m pip install -r requirements-build.txt
```

## Build The Windows App

From the project folder:

```powershell
build_windows.cmd
```

If the build succeeds, the app appears here:

```text
release\MemoryPal.exe
```

The build script checks that Python can import `tkinter` before packaging. This matters because an EXE made with a Python installation that does not include Tkinter will open with an error such as `No module named 'tkinter'`.

If an older `release\MemoryPal.exe` already shows that Tkinter error, delete it and run `build_windows.cmd` again after installing a normal Python build with Tcl/Tk. The current script is designed to stop before creating that broken kind of EXE.

The `release` folder is ignored by Git on purpose. The source code and build instructions belong in the repository; the `.exe` is better attached later as a GitHub Release file.

The build script installs packaging tools into `%TEMP%\memorypal-build-tools`, builds from a temporary `%TEMP%\memorypal-py-build-*` folder, and then copies the finished file into `release\MemoryPal.exe`. The `release` folder is ignored by Git.

If the copy step is blocked by a restricted workspace, the script prints the temporary EXE path. On a normal Windows folder, the copy step should place the file in `release` automatically.

## Why The EXE Might Not Build Here

The Codex workspace can compile the source, but the bundled Python environment may not always be a full desktop Python install with working Tkinter packaging support. The build script tests Tkinter before packaging so it does not create a broken EXE. If Codex cannot run a Tkinter-capable Python directly, run the same build command from a normal Command Prompt or PowerShell window.

If the script says no usable desktop Python was found, install Python 3.11 or newer from python.org, keep Tcl/Tk selected, and enable the PATH option during setup.

## Mobile Direction

The `mobile_app/` folder contains a Kivy prototype for Android and iOS. It is not a finished App Store or Play Store app yet, but it gives the mobile version a real starting point with touch-friendly screens and the same MemoryPal workflow.

Android packaging should be done with Buildozer on Linux or WSL. iOS packaging should be done on macOS with Kivy-iOS and Xcode.
