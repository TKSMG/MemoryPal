"""Where the MemoryPal cloud lives (Supabase). See CLOUD_SYNC_SETUP.md.

Both values are safe to ship inside the app: the publishable key only
allows what the database's Row Level Security rules permit (each person
reaches their own rows). Never put the secret / service_role key here.

Leave them empty and the app simply shows "sync isn't set up". The
MEMORYPAL_SUPABASE_URL / MEMORYPAL_SUPABASE_KEY environment variables
override them for testing.
"""

SUPABASE_URL = ""          # e.g. "https://abcdefghijklmnop.supabase.co"
SUPABASE_PUBLISHABLE_KEY = ""  # e.g. "sb_publishable_..."
