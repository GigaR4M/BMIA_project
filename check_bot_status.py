import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Error: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
    exit(1)

supabase = create_client(url, key)

# Search for Carl-bot
response = supabase.table("users").select("*").ilike("username", "%Carl-bot%").execute()

if response.data:
    print("Found users matching 'Carl-bot':")
    for user in response.data:
        print(f"ID: {user.get('user_id')}, Username: {user.get('username')}, Is Bot: {user.get('is_bot')}")
else:
    print("No user found matching 'Carl-bot'")
