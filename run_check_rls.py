
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SQL_FILE_PATH = os.path.join(os.path.dirname(__file__), "check_rls.sql")

async def check_rls():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print("\n--- RLS Status ---")
        rows = await conn.fetch("SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'daily_user_stats'")
        for r in rows:
            print(f"Table: {r['relname']}, RLS Enabled: {r['relrowsecurity']}")

        print("\n--- Policies ---")
        rows = await conn.fetch("SELECT * FROM pg_policies WHERE tablename = 'daily_user_stats'")
        if not rows:
            print("No policies found.")
        for r in rows:
            print(dict(r))

        await conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(check_rls())
