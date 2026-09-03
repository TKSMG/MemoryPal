# Building MemoryPal

MemoryPal is currently a Python/Tkinter desktop app. The recommended Windows build path uses Nuitka because it can package Tkinter with its `tk-inter` plugin and gives the project a clearer release workflow.

## Desktop Requirements

Install Python 3.11 or newer from the official Python website. During install, keep Tcl/Tk selected and enable the option that adds Python to PATH.

The desktop app uses `platformdirs` for the local data folder. Optional packages unlock document extraction, image previews, recording, spoken cues, and speech-to-text experiments:

```powershell
python -m pip install -r requirements-desktop.txt
```

The same dependencies can also be installed from `pyproject.toml`:

```powershell
python -m pip install -e ".[documents,image-previews,media,speech]"
```

Speech-to-text is optional. `SpeechRecognition` supports the prototype transcription flow, and microphone dictation may also need `PyAudio`, which can require a normal Windows Python setup. The default recognizer used in the prototype may need an internet connection.

The Windows build tools are listed separately:

```powershell
python -m pip install -r requirements-build.txt
```

Or from the project config:

```powershell
python -m pip install -e ".[build]"
```

## Build The Windows App

From the project folder:

```powershell
build_windows.cmd
```

The main build command calls `build_nuitka_windows.cmd`. If the build succeeds, the app appears here:

```text
release\MemoryPal.exe
```

The script checks that Python can import `tkinter` and open a hidden Tk window before packaging. This matters because an EXE made with a Python installation that does not include Tkinter can open with an error such as `No module named 'tkinter'`.

The build scripts generate the MemoryPal icon from source code before packaging. Nuitka and PyInstaller both receive that `.ico`, so the finished Windows app should use the MemoryPal mark instead of the default Python/Tk icon. The repository also keeps reusable icon exports in `assets/` for previews, README use, and later packaging polish.

If an older `release\MemoryPal.exe` already shows that Tkinter error, delete it and run `build_windows.cmd` again after installing a normal Python build with Tcl/Tk. The current script is designed to stop before creating that broken kind of EXE.

The `release` folder is ignored by Git on purpose. Source code, documentation, and build instructions belong in the repository; the `.exe` is better attached later as a GitHub Release file or downloaded from a GitHub Actions artifact.

## GitHub Actions Build

The repository includes this workflow:

```text
.github\workflows\build-windows.yml
```

GitHub can build the Windows executable on push to `main` or from the manual **Run workflow** button in the Actions tab. The finished file is uploaded as an artifact named `MemoryPal-Windows`.

This is the cleanest option when a local computer has Python path issues, PowerShell policy restrictions, or a Python installation without working Tkinter support.

## Fallback PyInstaller Build

The previous PyInstaller build is still available:

```powershell
build_pyinstaller_windows.cmd
```

Use it only as a fallback. It keeps the same Tkinter preflight check and writes the finished app to `release\MemoryPal.exe` when successful.

## Why The EXE Might Not Build Locally

The Codex workspace can compile the source, but the bundled Python environment may not always be a full desktop Python install with working Tkinter packaging support. The build scripts test Tkinter before packaging so they do not create a broken EXE.

If the script says no usable desktop Python was found, install Python 3.11 or newer from python.org, keep Tcl/Tk selected, and enable the PATH option during setup. Then run the build command again from a normal Command Prompt or PowerShell window opened inside the project folder.

## Mobile Direction

The `mobile_app/` folder contains a Kivy prototype for Android and iOS. It is not a finished App Store or Play Store app yet, but it gives the mobile version a real starting point with touch-friendly screens and the same MemoryPal workflow.

Android packaging should be done with Buildozer on Linux or WSL. iOS packaging should be done on macOS with Kivy-iOS and Xcode.
