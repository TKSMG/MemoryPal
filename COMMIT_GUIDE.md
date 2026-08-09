# MemoryPal Commit Guide

Use this when preparing the project for a college application or portfolio review.

## Suggested First Commit

```text
Initial MemoryPal app and development history
```

This commit should include:

- Latest runnable app in `latest_app/`.
- All reconstructed version files in `development_versions/`.
- README, version history, journal, and notes.
- GitHub setup files.

## Suggested Future Commit Style

Use short, human-readable messages:

```text
Improve Test Lab media cue previews
Add page draft preservation
Polish dashboard visual design
Expand memory puzzle modes
```

## Version File Rule

When the app reaches a meaningful milestone, add a standalone file named like:

```text
MemoryPal_v30_beta_short_feature_name.py
```

Then update the README, development stages, version journal, and notesheet.

## What Not To Commit

Do not commit local runtime data:

- `MemoryPalData/`
- `attachments/`
- `memorypal-data.json`
- `__pycache__/`
- `.pyc` files
