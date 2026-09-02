@echo off
setlocal

cd /d "%~dp0"

echo MemoryPal PyInstaller fallback build
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
  echo A Python install without Tkinter cannot build this app into a working EXE.
  exit /b 1
)

echo Using Python: %PYTHON_EXE% %PYTHON_ARGS%

set "BUILD_TOOLS=%TEMP%\memorypal-pyinstaller-tools"
set "TEMP_BUILD=%TEMP%\memorypal-pyinstaller-build-%RANDOM%-%RANDOM%"

if not exist "%BUILD_TOOLS%" mkdir "%BUILD_TOOLS%"

"%PYTHON_EXE%" %PYTHON_ARGS% -m pip install --upgrade --target "%BUILD_TOOLS%" -r requirements-build.txt
if errorlevel 1 exit /b 1

set "PYTHONPATH=%BUILD_TOOLS%;%PYTHONPATH%"

mkdir "%TEMP_BUILD%"
mkdir "%TEMP_BUILD%\release"
copy /Y "latest_app\MemoryPalDesktop.py" "%TEMP_BUILD%\MemoryPalDesktop.py" >nul
if errorlevel 1 exit /b 1

"%PYTHON_EXE%" %PYTHON_ARGS% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name MemoryPal ^
  --distpath "%TEMP_BUILD%\release" ^
  --workpath "%TEMP_BUILD%\build" ^
  --specpath "%TEMP_BUILD%\build" ^
  "%TEMP_BUILD%\MemoryPalDesktop.py"

if errorlevel 1 exit /b 1

if not exist release mkdir release
copy /Y "%TEMP_BUILD%\release\MemoryPal.exe" "release\MemoryPal.exe" >nul
if errorlevel 1 (
  echo Built EXE, but could not copy it into the project folder.
  echo Temp EXE: "%TEMP_BUILD%\release\MemoryPal.exe"
  exit /b 1
)

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
