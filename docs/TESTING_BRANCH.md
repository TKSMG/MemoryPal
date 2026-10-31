# The testing branch

`testing` is one branch that holds **main plus every piece of work that is not
merged yet**, so all of it can be tried from a single install. It is only for
trying things out: nothing is released or sent to a store from it, and nothing
is merged from it into main.

## Getting the apps

Every push to `testing` builds Windows, both Macs and Android, then replaces
the pre-release called **Testing build** on the
[Releases page](https://github.com/TKSMG/MemoryPal/releases/tag/testing-build).
Its title shows the commit it was built from. Builds take about 30 minutes.

- Windows: `MemoryPal-Windows-Setup.exe`
- Mac: the `.dmg` for Apple Silicon or Intel
- Android: `MemoryPal-Android.apk` (install over the store or release copy only
  if it was signed with the same key, otherwise uninstall that one first)

To rebuild without a new push, run **Testing Builds** from the Actions tab.

Running the desktop app from source works too:

```
git fetch origin
git checkout testing
git reset --hard origin/testing
python latest_app/MemoryPalDesktop.py
```

## What is in it right now

Keep this list up to date whenever a branch is added or taken out.

| Branch | PR | What it does |
| --- | --- | --- |
| `window-glitches` | #41 | Full screen fades instead of showing half-switched frames; scroll probes for every page |
| `claude/project-thread-5t33jk` | #42 | Live AI tutor for phone Talk-back, AI on by default |
| `claude/project-thread-5khaoy` | #46 | This branch's own set-up (the Testing Builds workflow and this guide) |

## Adding new work

When a new PR is opened, merge its branch into `testing` (never the other way):

```
git fetch origin
git checkout testing
git reset --hard origin/testing
git merge --no-edit origin/<branch>
git push origin testing
```

When the PR's branch gets more commits, run the same merge again.

## Bringing it back in line with main

After PRs are merged into main, start `testing` again from main and merge in
whatever is still open:

```
git fetch origin
git checkout testing
git reset --hard origin/main
git merge --no-edit origin/<each open branch>
git push --force-with-lease origin testing
```

Then update the table above.

## Rules

- Never merge `testing` into main or into another branch. Work reaches main
  only through its own PR, after "merge it".
- If two branches clash, fix the clash in `testing` only and note it on the
  PR, so the real fix is made on the branch itself.
- Version numbers in `testing` are whatever the merged branches say; the
  release version is set when main is released.
