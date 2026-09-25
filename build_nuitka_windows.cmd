@echo off
setlocal

cd /d "%~dp0"

echo MemoryPal Nuitka Windows build
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

if defined MEMORYPAL_PYTHON call :try_python "%MEMORYPAL_PYTHON%"

if not defined PYTHON_EXE call :try_python python
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE call :try_python py -3.13
if not defined PYTHON_EXE call :try_python py -3.12
if not defined PYTHON_EXE call :try_python py -3.11
if not defined PYTHON_EXE call :try_python py -3
if not defined PYTHON_EXE call :try_python py -3.14
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if not defined PYTHON_EXE call :try_python "C:\Program Files\Python313\python.exe"
if not defined PYTHON_EXE call :try_python "C:\Program Files\Python312\python.exe"
if not defined PYTHON_EXE call :try_python "C:\Program Files\Python311\python.exe"
if not defined PYTHON_EXE call :try_python "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not defined PYTHON_EXE (
  echo No usable desktop Python with Tkinter was found.
  echo Install Python 3.11+ from python.org and keep Tcl/Tk selected during setup.
  echo A Python install without Tkinter cannot build MemoryPal into a working EXE.
  exit /b 1
)

echo Using Python: %PYTHON_EXE% %PYTHON_ARGS%

set "BUILD_TOOLS=%TEMP%\memorypal-nuitka-tools"
set "TEMP_BUILD=%TEMP%\memorypal-nuitka-build-%RANDOM%-%RANDOM%"
set "WINDOWS_CONSOLE_MODE=--windows-console-mode=disable"
set "TK_ENV_CMD=%TEMP%\memorypal-tk-env-%RANDOM%-%RANDOM%.cmd"

if exist "%BUILD_TOOLS%" rmdir /s /q "%BUILD_TOOLS%"
if not exist "%BUILD_TOOLS%" mkdir "%BUILD_TOOLS%"
if not exist "%TEMP_BUILD%" mkdir "%TEMP_BUILD%"

"%PYTHON_EXE%" %PYTHON_ARGS% -c "from pathlib import Path; import sys, tkinter; probe=tkinter.Tk(); probe.withdraw(); probe.destroy(); root=Path(sys.base_prefix)/'tcl'; tcl=next((p for p in root.glob('tcl*') if (p/'init.tcl').exists()), None); tk=next((p for p in root.glob('tk*') if (p/'tk.tcl').exists()), None); assert tcl and tk, f'Tcl/Tk folders were not found under {root}'; print(f'set \"TCL_LIBRARY={tcl}\"'); print(f'set \"TK_LIBRARY={tk}\"')" > "%TK_ENV_CMD%"
if errorlevel 1 (
  echo Could not find Tcl/Tk library folders for the selected Python.
  echo Reinstall Python 3.11+ from python.org and keep Tcl/Tk selected during setup.
  exit /b 1
)
call "%TK_ENV_CMD%"
del "%TK_ENV_CMD%" >nul 2>nul
echo Tcl library: %TCL_LIBRARY%
echo Tk library: %TK_LIBRARY%

"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade --target "%BUILD_TOOLS%" -r requirements-build.txt
if errorlevel 1 exit /b 1

set "PYTHONPATH=%BUILD_TOOLS%;%PYTHONPATH%"
set "MEMORYPAL_ICON=%TEMP%\memorypal-icon.ico"

"%PYTHON_EXE%" %PYTHON_ARGS% -c "from pathlib import Path; import sys; sys.path.insert(0, r'latest_app'); from memorypal.icon import ensure_icon_file; ensure_icon_file(Path(r'%MEMORYPAL_ICON%'))"
if errorlevel 1 exit /b 1

if not exist release mkdir release

"%PYTHON_EXE%" %PYTHON_ARGS% -m nuitka ^
  --assume-yes-for-downloads ^
  --standalone ^
  --enable-plugin=tk-inter ^
  --include-data-dir=assets=assets ^
  --include-module=pypdf ^
  --nofollow-import-to=sounddevice,cv2,pyttsx3,SpeechRecognition,pyaudio,pyaudioop,numpy ^
  --output-dir="%TEMP_BUILD%" ^
  --output-filename=MemoryPal.exe ^
  --company-name="MemoryPal" ^
  --product-name="MemoryPal" ^
  --file-description="MemoryPal desktop memory trainer" ^
  --product-version="0.44.0" ^
  --file-version="0.44.0" ^
  --windows-icon-from-ico="%MEMORYPAL_ICON%" ^
  --tcl-library-dir="%TCL_LIBRARY%" ^
  --tk-library-dir="%TK_LIBRARY%" ^
  %WINDOWS_CONSOLE_MODE% ^
  latest_app\MemoryPalDesktop.py

if errorlevel 1 exit /b 1

set "BUILT_APP_DIR="
if exist "%TEMP_BUILD%\MemoryPal.dist\MemoryPal.exe" set "BUILT_APP_DIR=%TEMP_BUILD%\MemoryPal.dist"
if not defined BUILT_APP_DIR if exist "%TEMP_BUILD%\MemoryPalDesktop.dist\MemoryPal.exe" set "BUILT_APP_DIR=%TEMP_BUILD%\MemoryPalDesktop.dist"

if not defined BUILT_APP_DIR (
  echo Nuitka finished, but the app folder was not found.
  echo Build output folder: "%TEMP_BUILD%"
  exit /b 1
)

if exist "release\MemoryPal" rmdir /s /q "release\MemoryPal"
xcopy /E /I /Y "%BUILT_APP_DIR%" "release\MemoryPal" >nul
if errorlevel 1 (
  echo Built app folder, but could not copy it into the project folder.
  echo Temp app folder: "%BUILT_APP_DIR%"
  exit /b 1
)

echo.
echo Built release\MemoryPal\MemoryPal.exe
exit /b 0

:try_python
if defined PYTHON_EXE exit /b 0
set "CANDIDATE=%~1"
set "CANDIDATE_ARGS=%~2"
if "%CANDIDATE%"=="" exit /b 0
"%CANDIDATE%" %CANDIDATE_ARGS% -c "from pathlib import Path; import sys, tkinter; probe=tkinter.Tk(); probe.withdraw(); probe.destroy(); root=Path(sys.base_prefix)/'tcl'; tcl=next((p for p in root.glob('tcl*') if (p/'init.tcl').exists()), None); tk=next((p for p in root.glob('tk*') if (p/'tk.tcl').exists()), None); assert tcl and tk; print(sys.executable)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=%CANDIDATE%"
  set "PYTHON_ARGS=%CANDIDATE_ARGS%"
)
exit /b 0
