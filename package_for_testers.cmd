@echo off
setlocal

cd /d "%~dp0"

set "PACKAGE_DIR=release\MemoryPalTesterPackage"
set "PACKAGE_ZIP=release\MemoryPalTesterPackage.zip"

if not exist "release\MemoryPalSetup.exe" if not exist "release\MemoryPal\MemoryPal.exe" (
  echo No built MemoryPal app was found.
  echo Run .\build_windows.cmd first, then .\build_installer_windows.cmd if you want the setup installer included.
  exit /b 1
)

if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%"

if exist "release\MemoryPalSetup.exe" (
  copy /y "release\MemoryPalSetup.exe" "%PACKAGE_DIR%\MemoryPalSetup.exe" >nul
)

if exist "release\MemoryPal\MemoryPal.exe" (
  xcopy /e /i /y "release\MemoryPal" "%PACKAGE_DIR%\MemoryPal" >nul
)

copy /y "README.md" "%PACKAGE_DIR%\README.md" >nul
copy /y "TESTING_CHECKLIST.md" "%PACKAGE_DIR%\TESTING_CHECKLIST.md" >nul
copy /y "BUILDING_APP.md" "%PACKAGE_DIR%\BUILDING_APP.md" >nul
copy /y "DESIGN_NOTES.md" "%PACKAGE_DIR%\DESIGN_NOTES.md" >nul

if exist "notes\MemoryPal_Memory_Techniques.md" (
  mkdir "%PACKAGE_DIR%\notes" >nul 2>nul
  copy /y "notes\MemoryPal_Memory_Techniques.md" "%PACKAGE_DIR%\notes\MemoryPal_Memory_Techniques.md" >nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path '%CD%\%PACKAGE_DIR%\*' -DestinationPath '%CD%\%PACKAGE_ZIP%' -Force"
if errorlevel 1 exit /b 1

echo Built %PACKAGE_ZIP%
exit /b 0
