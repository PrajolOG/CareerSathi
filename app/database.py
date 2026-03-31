import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env file")

# Create the Supabase client
supabase: Client = create_client(url, key)

# Admin role client (uses service role key, bypasses RLS)
service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase_admin: Client = create_client(url, service_key) if service_key else None