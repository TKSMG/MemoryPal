@echo off
setlocal

cd /d "%~dp0"

echo MemoryPal Windows installer build
echo.

set "ISCC_EXE="

for %%I in (ISCC.exe) do if not "%%~$PATH:I"=="" set "ISCC_EXE=%%~$PATH:I"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
  echo Inno Setup 6 was not found.
  echo Install Inno Setup, then run this file again.
  echo The installer script is at installer\inno\MemoryPal.iss
  exit /b 1
)

if not exist "release\MemoryPal.exe" (
  echo release\MemoryPal.exe was not found. Building the app first...
  call build_windows.cmd
  if errorlevel 1 exit /b 1
)

echo Using Inno Setup: %ISCC_EXE%
"%ISCC_EXE%" "installer\inno\MemoryPal.iss"
if errorlevel 1 exit /b 1

echo.
echo Built release\MemoryPalSetup.exe
exit /b 0
