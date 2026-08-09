# GitHub Setup For MemoryPal

This folder is ready to become the root of the GitHub repository.

Because this Codex environment cannot write Git metadata folders, run the setup locally on your computer.

If PowerShell says scripts are not allowed, do not use a `.ps1` file. This package now includes a Command Prompt helper instead:

```powershell
cd "C:\Users\hp\Documents\Codex\2026-06-08\files-mentioned-by-the-user-memorypalpackages\MemoryPal Newest"
.\SETUP_GITHUB_REPO.cmd
```

If Windows asks what app to use, run it from Command Prompt instead:

```cmd
cd /d "C:\Users\hp\Documents\Codex\2026-06-08\files-mentioned-by-the-user-memorypalpackages\MemoryPal Newest"
SETUP_GITHUB_REPO.cmd
```

The no-script manual method is below.

## 1. Open The Project Folder

```powershell
cd "C:\Users\hp\Documents\Codex\2026-06-08\files-mentioned-by-the-user-memorypalpackages\MemoryPal Newest"
```

## 2. Create The Local Git Repo

Replace the name and email with the GitHub identity you want shown on commits.

```powershell
git init
git branch -M main
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git commit -m "Initial MemoryPal app and development history"
```

## 3. Create The GitHub Repo

On GitHub, create a new empty repository.

Recommended name:

```text
memorypal
```

Do not add a README, license, or `.gitignore` on GitHub because this project already has those project files locally.

## 4. Connect And Push

Replace `YOUR-USERNAME` with your GitHub username.

```powershell
git remote add origin https://github.com/YOUR-USERNAME/memorypal.git
git push -u origin main
```

Git Credential Manager may open a browser window for login. Sign in there, then return to PowerShell.

If `git push` says the repository was not found, create the empty GitHub repo first, then run the push command again.

## If Push Says Remote Contains Work

If Git shows:

```text
Updates were rejected because the remote contains work that you do not have locally.
```

Run:

```cmd
git pull origin main --allow-unrelated-histories
git push -u origin main
```

If Git opens a merge message editor, save and close it. If Git reports a conflict, ask Codex before continuing.

## If Git Says Dubious Ownership

If Git shows a message like `detected dubious ownership`, run this once:

```cmd
git config --global --add safe.directory "C:/Users/hp/Documents/Codex/2026-06-08/files-mentioned-by-the-user-memorypalpackages/MemoryPal Newest"
```

Then run the setup helper again:

```cmd
SETUP_GITHUB_REPO.cmd
```

## Milestone Workflow

When a major feature is added:

```powershell
git status
git add .
git commit -m "Add short milestone description"
git push
```

For this project, keep adding standalone milestone files under:

```text
development_versions/
```

Also update:

```text
README.md
development_versions/README_development_stages.md
development_versions/VERSION_JOURNAL.md
notes/MemoryPal_Memory_Techniques.md
```

## Current Latest Milestone

The current latest milestone is:

```text
development_versions/MemoryPal_v29_beta_page_draft_preservation.py
```

The current app file is:

```text
latest_app/MemoryPalDesktop.py
```
