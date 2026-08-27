@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.11+ and enable "Add Python to PATH".
  exit /b 1
)

python -m pip install -r requirements-desktop.txt
if errorlevel 1 exit /b 1

if not exist release mkdir release

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name MemoryPal ^
  --distpath release ^
  --workpath build ^
  latest_app\MemoryPalDesktop.py

if errorlevel 1 exit /b 1

echo.
echo Built release\MemoryPal.exe
