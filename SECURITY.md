# Security

## Reporting a problem

If you find a security or privacy problem in MemoryPal (the desktop app, the phone app, the
CAPTCHA page or the `ai` server function), please **don't open a public issue**. Instead:

- use GitHub's private report: **Security → Report a vulnerability** on this repository, or
- email **memorypal09@gmail.com** with "Security" in the subject.

Say what you found, how to reproduce it, and which version you used (the bottom of Settings on the phone, Settings →
Storage and backups on the computer). You'll get a reply within 7 days. Please give me a reasonable time to fix it before you
share it publicly.

## Supported versions

Only the newest release (on the
[latest release page](https://github.com/TKSMG/MemoryPal/releases/latest) and in the app
stores) gets security fixes.

## What's in scope

- Anything that lets someone read or change another person's account, AI allowance or synced data.
- Leaked keys or secrets in the apps, the repository or the releases.
- Ways around the sign-in check, the two-step sign-in or the AI limits.

The Supabase URL and its `sb_publishable_` key, the Cloudflare Turnstile site key and the
Google desktop OAuth client in the installers are public by design.
