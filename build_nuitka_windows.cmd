@echo off
setlocal

cd /d "%~dp0"

echo MemoryPal Nuitka Windows build
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

call :try_python py -3

if not defined PYTHON_EXE call :try_python python
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE call :try_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
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
set "WINDOWS_CONSOLE_MODE=--windows-console-mode=disable"

if not exist "%BUILD_TOOLS%" mkdir "%BUILD_TOOLS%"

"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade --target "%BUILD_TOOLS%" -r requirements-build.txt
if errorlevel 1 exit /b 1

set "PYTHONPATH=%BUILD_TOOLS%;%PYTHONPATH%"
set "MEMORYPAL_ICON=%TEMP%\memorypal-icon.ico"

"%PYTHON_EXE%" %PYTHON_ARGS% -c "from pathlib import Path; import sys; sys.path.insert(0, r'latest_app'); from memorypal.icon import ensure_icon_file; ensure_icon_file(Path(r'%MEMORYPAL_ICON%'))"
if errorlevel 1 exit /b 1

if not exist release mkdir release

"%PYTHON_EXE%" %PYTHON_ARGS% -m nuitka ^
  --assume-yes-for-downloads ^
  --onefile ^
  --enable-plugin=tk-inter ^
  --output-dir=release ^
  --output-filename=MemoryPal.exe ^
  --company-name="MemoryPal" ^
  --product-name="MemoryPal" ^
  --file-description="MemoryPal desktop memory trainer" ^
  --product-version="0.36.0" ^
  --file-version="0.36.0" ^
  --windows-icon-from-ico="%MEMORYPAL_ICON%" ^
  %WINDOWS_CONSOLE_MODE% ^
  latest_app\MemoryPalDesktop.py

if errorlevel 1 exit /b 1

echo.
echo Built release\MemoryPal.exe
exit /b 0

:try_python
if defined PYTHON_EXE exit /b 0
set "CANDIDATE=%~1"
set "CANDIDATE_ARGS=%~2"
if "%CANDIDATE%"=="" exit /b 0
"%CANDIDATE%" %CANDIDATE_ARGS% -c "import sys, tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy(); print(sys.executable)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=%CANDIDATE%"
  set "PYTHON_ARGS=%CANDIDATE_ARGS%"
)
exit /b 0
