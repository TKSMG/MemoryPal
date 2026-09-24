@echo off
setlocal

cd /d "%~dp0"

set "PACKAGE_DIR=release\MemoryPalTesterPackage"
set "PACKAGE_ZIP=release\MemoryPalTesterPackage.zip"

if not exist "release\MemoryPalSetup.exe" if not exist "release\MemoryPal\MemoryPal.exe" (
  echo No built MemoryPal app was found.
  echo Run .\build_release_windows.cmd, or .\build_windows.cmd then .\build_installer_windows.cmd.
  exit /b 1
)

if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
if exist "%PACKAGE_ZIP%" del /f /q "%PACKAGE_ZIP%"
mkdir "%PACKAGE_DIR%"

rem Tester-facing files only. Build and design notes stay in the repository.
if exist "release\MemoryPalSetup.exe" (
  copy /y "release\MemoryPalSetup.exe" "%PACKAGE_DIR%\MemoryPalSetup.exe" >nul
)

rem Portable fallback for testers who cannot run the installer.
if exist "release\MemoryPal\MemoryPal.exe" (
  xcopy /e /i /y "release\MemoryPal" "%PACKAGE_DIR%\MemoryPal" >nul
)

copy /y "TESTER_START_HERE.md" "%PACKAGE_DIR%\TESTER_START_HERE.md" >nul
copy /y "TESTING_CHECKLIST.md" "%PACKAGE_DIR%\TESTING_CHECKLIST.md" >nul
copy /y "README.md" "%PACKAGE_DIR%\README.md" >nul

if exist "notes\MemoryPal_Memory_Techniques.md" (
  mkdir "%PACKAGE_DIR%\notes" >nul 2>nul
  copy /y "notes\MemoryPal_Memory_Techniques.md" "%PACKAGE_DIR%\notes\MemoryPal_Memory_Techniques.md" >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%CD%\%PACKAGE_DIR%\*' -DestinationPath '%CD%\%PACKAGE_ZIP%' -Force"
if errorlevel 1 exit /b 1

echo Built %PACKAGE_ZIP%
exit /b 0
