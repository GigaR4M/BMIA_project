import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def inspect_funcs():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        rows = await conn.fetch("SELECT proname, proargtypes, proargtypes::regtype[] FROM pg_proc WHERE proname = 'get_leaderboard'")
        print(f"Found {len(rows)} function(s) named 'get_leaderboard':")
        for r in rows:
            print(f"Name: {r['proname']}, ArgTypes: {r['proargtypes']}, ArgTypeNames: {r['proargtypes::regtype[]']}")
        
        await conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_funcs())
