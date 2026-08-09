@echo off
setlocal

echo MemoryPal GitHub setup
echo.

set /p GIT_NAME=Git commit name: 
set /p GIT_EMAIL=Git commit email: 
set /p GITHUB_USERNAME=GitHub username: 
set /p REPO_NAME=Repository name [memorypal]: 

if "%REPO_NAME%"=="" set REPO_NAME=memorypal

echo.
echo Setting up local Git repository...

set SAFE_DIR=%CD:\=/%
git config --global --add safe.directory "%SAFE_DIR%"
if errorlevel 1 goto error

if not exist ".git" (
    git init
    if errorlevel 1 goto error
)

git branch -M main
if errorlevel 1 goto error

git config user.name "%GIT_NAME%"
if errorlevel 1 goto error

git config user.email "%GIT_EMAIL%"
if errorlevel 1 goto error

git add .
if errorlevel 1 goto error

git rev-parse --verify HEAD >nul 2>nul
if errorlevel 1 (
    git commit -m "Initial MemoryPal app and development history"
) else (
    git commit -m "Update MemoryPal project files"
)
if errorlevel 1 goto error

set REMOTE_URL=https://github.com/%GITHUB_USERNAME%/%REPO_NAME%.git

git remote get-url origin >nul 2>nul
if errorlevel 1 (
    git remote add origin "%REMOTE_URL%"
) else (
    git remote set-url origin "%REMOTE_URL%"
)
if errorlevel 1 goto error

echo.
echo Pushing to %REMOTE_URL%
git push -u origin main
if errorlevel 1 goto error

echo.
echo Done. Git may open a browser login through Git Credential Manager.
pause
exit /b 0

:error
echo.
echo Something failed. Check the message above, then try the manual commands in GITHUB_SETUP.md.
pause
exit /b 1
