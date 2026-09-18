@echo off
setlocal

cd /d "%~dp0"

echo Cleaning MemoryPal generated build files...
echo.

for %%D in (
  "release"
  "build"
  "dist"
  ".pytest_cache"
  ".build_deps"
  "build_deps_local"
  "MemoryPal_User_Package"
  "MemoryPal_Mac_Package"
) do (
  if exist "%%~D" (
    echo Removing %%~D
    rmdir /s /q "%%~D"
  )
)

for /d /r %%D in (__pycache__) do (
  if exist "%%~fD" rmdir /s /q "%%~fD"
)

for %%F in (*.spec *.log nuitka-crash-report.xml) do (
  if exist "%%~F" (
    echo Removing %%~F
    del /f /q "%%~F"
  )
)

for /d %%D in ("%TEMP%\memorypal-*") do (
  if exist "%%~fD" (
    echo Removing %%~fD
    rmdir /s /q "%%~fD"
  )
)

for %%F in ("%TEMP%\memorypal-*") do (
  if exist "%%~fF" del /f /q "%%~fF"
)

echo.
echo Clean complete. This does not delete MemoryPal profile data or uninstall Python/Inno Setup.
exit /b 0
