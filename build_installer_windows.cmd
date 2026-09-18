@echo off
setlocal

cd /d "%~dp0"

echo MemoryPal Windows installer build
echo.

set "ISCC_EXE="

call :find_iscc

if not defined ISCC_EXE (
  echo Inno Setup compiler ISCC.exe was not found.
  where winget.exe >nul 2>nul
  if errorlevel 1 (
    echo winget was not found, so this script cannot install Inno Setup automatically.
    echo Install Inno Setup 7 or 6 from https://jrsoftware.org/isdl.php, then run this file again.
    echo Or set INNO_SETUP_PATH to the full path of ISCC.exe.
    echo The installer script is at installer\inno\MemoryPal.iss
    exit /b 1
  )
  choice /M "Install the Inno Setup compiler for the current user with winget now"
  if errorlevel 2 (
    echo Installer build cancelled.
    echo You can install it later with:
    echo winget install --id JRSoftware.InnoSetup.7 -e -s winget -i
    echo or:
    echo winget install --id JRSoftware.InnoSetup -e -s winget -i
    exit /b 1
  )
  winget install --id JRSoftware.InnoSetup.7 -e -s winget -i --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Inno Setup 7 install did not complete. Trying Inno Setup 6...
    winget install --id JRSoftware.InnoSetup -e -s winget -i --accept-package-agreements --accept-source-agreements
    if errorlevel 1 exit /b 1
  )
  call :find_iscc
  if not defined ISCC_EXE (
    echo Inno Setup was installed, but ISCC.exe was not found in the normal folders.
    echo Set INNO_SETUP_PATH to the full path of ISCC.exe, then run this file again.
    exit /b 1
  )
)

if not exist "release\MemoryPal\MemoryPal.exe" (
  echo release\MemoryPal\MemoryPal.exe was not found. Building the app first...
  call build_windows.cmd
  if errorlevel 1 exit /b 1
)

echo Using Inno Setup: %ISCC_EXE%
"%ISCC_EXE%" "installer\inno\MemoryPal.iss"
if errorlevel 1 exit /b 1

echo.
echo Built release\MemoryPalSetup.exe
exit /b 0

:find_iscc
if defined ISCC_EXE exit /b 0
if defined INNO_SETUP_PATH if exist "%INNO_SETUP_PATH%" set "ISCC_EXE=%INNO_SETUP_PATH%"
for %%I in (ISCC.exe) do if not "%%~$PATH:I"=="" if not defined ISCC_EXE set "ISCC_EXE=%%~$PATH:I"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
exit /b 0
