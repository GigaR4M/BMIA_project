
import os
from dotenv import load_dotenv

load_dotenv()

print("--- Available Environment Variables ---")
keys = [k for k in os.environ.keys() if "SUPABASE" in k or "URL" in k]
for k in keys:
    print(k)
