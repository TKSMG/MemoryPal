# Building MemoryPal

MemoryPal is currently a Python/Tkinter desktop app. The current recommended Windows tester build path uses PyInstaller in app-folder mode because it opens reliably on this machine. Nuitka remains available as an alternate path until the current local runtime issue is resolved.

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

The default tester build intentionally stays lighter than the full optional desktop setup. File imports, document notes, image previews, and the main memory tools are kept in the normal package path; desktop audio recording, webcam recording, speech recognition, and offline text-to-speech should be treated as optional extras unless a media-enabled build is made on purpose.

For low-end tester machines, keep using the normal app-folder build instead of a self-extracting one-file EXE. The app-folder build avoids unpacking work on every launch, keeps optional media libraries out of startup, and lets MemoryPal load its checked-in icon/logo assets directly.

The Windows build tools are listed separately:

```powershell
python -m pip install -r requirements-build.txt
```

Or from the project config:

```powershell
python -m pip install -e ".[build]"
```

## Clean Before Rebuilding

To clear old local build output and MemoryPal-named temp build folders:

```powershell
.\clean_build_artifacts.cmd
```

This cleanup keeps source files, documentation, Git history, and saved profile data. It does not uninstall Python, Inno Setup, or other system tools.

If an old installed copy of MemoryPal needs to be removed before testing a new installer, uninstall MemoryPal from Windows Settings first. Keep `%LOCALAPPDATA%\MemoryPal` if tester data should survive; remove that folder only when a full data reset is intended.

## Build The Windows App

If the computer has multiple Python installs, point the build at the one that can open Tkinter:

```powershell
$env:MEMORYPAL_PYTHON = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
```

From the project folder:

```powershell
.\build_windows.cmd
```

The main build command calls `build_pyinstaller_windows.cmd`. If the build succeeds, the app appears here:

```text
release\MemoryPal\MemoryPal.exe
```

The build excludes large optional media stacks such as OpenCV, `sounddevice`, and `pyttsx3` from the default tester package. Those libraries are loaded on demand in source runs, but leaving them out of the packaged tester build keeps normal startup faster and avoids bundling features that many testers may not use.

The script checks that Python can import `tkinter` and open a hidden Tk window before packaging. This matters because an EXE made with a Python installation that does not include Tkinter can open with an error such as `No module named 'tkinter'`.

The build scripts generate the MemoryPal icon from source code before packaging. PyInstaller receives that `.ico`, and the checked-in `assets/` folder is bundled into the app folder. That keeps the finished Windows app on the MemoryPal mark and prevents installed copies from generating a fresh icon during startup.

If an older build already shows that Tkinter error, delete the old `release` folder and run `.\build_windows.cmd` again after installing a normal Python build with Tcl/Tk. The current script is designed to stop before creating that broken kind of package.

If the build log mentions `pythoncore-3.14-64` and says Tcl/Tk folders were not found, that Python install is the lightweight PythonCore runtime rather than a full desktop install. The build scripts now skip that runtime automatically when possible. If needed, force the full Python install before building:

```powershell
$env:MEMORYPAL_PYTHON = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
.\build_windows.cmd
```

The `release` folder is ignored by Git on purpose. Source code, documentation, and build instructions belong in the repository; the `.exe` is better attached later as a GitHub Release file or downloaded from a GitHub Actions artifact.

## GitHub Actions Build

The repository includes these workflows:

```text
.github\workflows\build-windows.yml
```

GitHub can build the Windows app folder and installer on push to `main` or from the manual **Run workflow** button in the Actions tab. Finished files are uploaded as the `MemoryPal-Windows` artifact.

This is the cleanest option when a local computer has Python path issues, PowerShell policy restrictions, or a Python installation without working Tkinter support.

## Build The Installer

The repository includes an Inno Setup script:

```text
installer\inno\MemoryPal.iss
```

After `release\MemoryPal\MemoryPal.exe` exists, run:

```powershell
.\build_installer_windows.cmd
```

The script looks for the Inno Setup command-line compiler, compiles the installer, and writes:

```text
release\MemoryPalSetup.exe
```

The installer uses a per-user install location under local app data, so testers can install MemoryPal without needing administrator access.

The installer shows normal setup choices for install location, Start Menu folder, optional desktop shortcut, and launch-after-install.

If Inno Setup is missing, `.\build_installer_windows.cmd` can offer to install it with `winget`. The script checks `INNO_SETUP_PATH`, PATH, the per-user install folder, and Program Files before asking to install anything.

If Inno Setup is installed in a custom folder, set the compiler path before running the installer build:

```powershell
$env:INNO_SETUP_PATH = "C:\Path\To\Inno Setup 7\ISCC.exe"
.\build_installer_windows.cmd
```

## Package For Testers

After building the app and, ideally, the installer, the helper below creates a tester zip:

```powershell
.\package_for_testers.cmd
```

It writes:

```text
release\MemoryPalTesterPackage.zip
```

For normal testers, send:

```text
release\MemoryPalSetup.exe
README.md
TESTING_CHECKLIST.md
```

For a no-installer portable test, zip the whole folder below with the tester notes:

```text
release\MemoryPal\
README.md
TESTING_CHECKLIST.md
```

## Build The macOS App

macOS packages must be created on macOS because the `.app` bundle is platform-specific. The Windows repository keeps the desktop source ready for a future macOS packaging pass, but the current supported installer flow is Windows.

## Alternate Nuitka Build

The Nuitka build is still available for future testing:

```powershell
.\build_nuitka_windows.cmd
```

Use it only as an alternate path until its local runtime issue is understood. It keeps the same Tkinter preflight check and writes the finished app folder to `release\MemoryPal\MemoryPal.exe` when successful.

## Why The EXE Might Not Build Locally

The Codex workspace can compile the source, but the bundled Python environment may not always be a full desktop Python install with working Tkinter packaging support. The build scripts test Tkinter before packaging so they do not create a broken EXE.

If the script says no usable desktop Python was found, install Python 3.11 or newer from python.org, keep Tcl/Tk selected, and enable the PATH option during setup. Then run the build command again from a normal Command Prompt or PowerShell window opened inside the project folder.

## Mobile Direction

The `mobile_app/` folder contains a Kivy prototype for Android and iOS. It is not a finished App Store or Play Store app yet, but it gives the mobile version a real starting point with touch-friendly screens and the same MemoryPal workflow.

Android packaging should be done with Buildozer on Linux or WSL. iOS packaging should be done on macOS with Kivy-iOS and Xcode.
