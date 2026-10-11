"""Where the MemoryPal cloud lives (Supabase). See CLOUD_SYNC_SETUP.md.

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
TERMS_URL = ""             # e.g. "https://memorypal.app/terms"
PRIVACY_URL = ""           # e.g. "https://memorypal.app/privacy"
