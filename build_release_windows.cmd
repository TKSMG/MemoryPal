@echo off
setlocal

rem One-shot Windows release: tests, clean, app folder, installer, tester zip.
rem Run from a normal Command Prompt or PowerShell window in the project folder:
rem   .\build_release_windows.cmd

cd /d "%~dp0"

echo ============================================
echo  MemoryPal full Windows release build
echo ============================================
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

if not defined PYTHON_EXE (
  echo No usable desktop Python with Tkinter was found.
  echo Install Python 3.11+ from python.org and keep Tcl/Tk selected during setup.
  exit /b 1
)

echo [1/5] Running unit tests with %PYTHON_EXE% %PYTHON_ARGS%
"%PYTHON_EXE%" %PYTHON_ARGS% -m unittest discover -s latest_app\tests
if errorlevel 1 (
  echo.
  echo Unit tests failed. Fix them before building a tester release.
  exit /b 1
)
"%PYTHON_EXE%" %PYTHON_ARGS% -m py_compile latest_app\MemoryPalDesktop.py
if errorlevel 1 (
  echo MemoryPalDesktop.py does not compile.
  exit /b 1
)

rem Make sure the build scripts below use the same Python.
set "MEMORYPAL_PYTHON=%PYTHON_EXE%"
if defined PYTHON_ARGS set "MEMORYPAL_PYTHON="

echo.
echo [2/5] Cleaning old build output so the installer never ships a stale app
call clean_build_artifacts.cmd
if errorlevel 1 exit /b 1

echo.
echo [3/5] Building the app folder (PyInstaller)
call build_windows.cmd
if errorlevel 1 (
  echo App build failed.
  exit /b 1
)
if not exist "release\MemoryPal\MemoryPal.exe" (
  echo release\MemoryPal\MemoryPal.exe is missing after the build.
  exit /b 1
)

echo.
echo [4/5] Building the installer (Inno Setup)
call build_installer_windows.cmd
if errorlevel 1 (
  echo Installer build failed.
  exit /b 1
)

echo.
echo [5/5] Packaging for testers
call package_for_testers.cmd
if errorlevel 1 (
  echo Tester packaging failed.
  exit /b 1
)

echo.
echo ============================================
echo  Done
echo   App:        release\MemoryPal\MemoryPal.exe
echo   Installer:  release\MemoryPalSetup.exe
echo   Tester zip: release\MemoryPalTesterPackage.zip
echo ============================================
echo Before sending: install from MemoryPalSetup.exe on this PC and check
echo that the Welcome screen, a review, and Read aloud all work.
exit /b 0

:try_python
if defined PYTHON_EXE exit /b 0
set "CANDIDATE=%~1"
set "CANDIDATE_ARGS=%~2"
if "%CANDIDATE%"=="" exit /b 0
"%CANDIDATE%" %CANDIDATE_ARGS% -c "import tkinter; probe=tkinter.Tk(); probe.withdraw(); probe.destroy()" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=%CANDIDATE%"
  set "PYTHON_ARGS=%CANDIDATE_ARGS%"
)
exit /b 0
