"""Where the MemoryPal cloud lives (Supabase). See docs/CLOUD_SYNC_SETUP.md.

Both values are safe to ship inside the app: the publishable key only
allows what the database's Row Level Security rules permit (each person
reaches their own rows). Never put the secret / service_role key here.

Leave them empty and the app simply shows "sync isn't set up". The
MEMORYPAL_SUPABASE_URL / MEMORYPAL_SUPABASE_KEY environment variables
override them for testing.
"""

SUPABASE_URL = "https://wgfaryxbwritolayuydh.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_2dZ7rq2PQ9oCMG7bMMWhUQ_am1Zh1E6"

# The published Terms of Use and Privacy Policy (drafts: TERMS_OF_USE.md and
# PRIVACY_POLICY.md). Account sign-up links to them; app stores require the
# privacy policy before an app with accounts is published.
# Until they have a home of their own, they're read from the public repository.
TERMS_URL = "https://github.com/TKSMG/MemoryPal/blob/main/TERMS_OF_USE.md"
PRIVACY_URL = "https://github.com/TKSMG/MemoryPal/blob/main/PRIVACY_POLICY.md"

# The CAPTCHA check page (site/verify/, published by .github/workflows/pages.yml).
# Signing in, creating an account and emailing a code open it first, so bots
# can't mass-create accounts. Empty turns the check off. The
# MEMORYPAL_CAPTCHA_URL environment variable overrides it ("" turns it off).
CAPTCHA_URL = "https://tksmg.github.io/MemoryPal/verify/"

# Google Drive sync (latest_app/memorypal/drive.py): the OAuth client of type
# "Desktop app" in MemoryPal's Google Cloud project. The release build writes
# both values into google_client.py (kept out of the repository) from the
# GOOGLE_DESKTOP_CLIENT_ID variable and GOOGLE_DESKTOP_CLIENT_SECRET secret.
# Empty means this copy keeps syncing through the MemoryPal cloud. The
# MEMORYPAL_GOOGLE_CLIENT_ID / MEMORYPAL_GOOGLE_CLIENT_SECRET environment
# variables override them for testing.
try:
    from .google_client import CLIENT_ID as GOOGLE_DESKTOP_CLIENT_ID, CLIENT_SECRET as GOOGLE_DESKTOP_CLIENT_SECRET
except ImportError:
    GOOGLE_DESKTOP_CLIENT_ID = GOOGLE_DESKTOP_CLIENT_SECRET = ""
