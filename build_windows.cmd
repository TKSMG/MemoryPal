@echo off
setlocal

cd /d "%~dp0"
call "%~dp0build_pyinstaller_windows.cmd"
exit /b %ERRORLEVEL%
