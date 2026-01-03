import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
GUILD_ID = 1327836427915886643

async def repro():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print("\n--- Test 1: p_start_date = NULL (Default 30 days) ---")
        try:
            # We must explicitly cast NULL in python-asyncpg or it infers type. 
            # In SQL: get_top_users_by_voice(..., NULL)
            rows = await conn.fetch("SELECT * FROM get_top_users_by_voice($1, 30, 5, NULL)", GUILD_ID)
            print(f"Result count: {len(rows)}")
            for r in rows: print(f"{r['username']}: {r['total_minutes']}m")
        except Exception as e:
            print(f"FAIL Test 1: {e}")

        print("\n--- Test 2: p_start_date = String (Client format) ---")
        try:
            # Sending ISO string. Postgres should auto-cast to timestamptz
            iso_date = "2026-01-01T00:00:00-03:00"
            rows = await conn.fetch("SELECT * FROM get_top_users_by_voice($1, 365, 5, $2)", GUILD_ID, iso_date)
            print(f"Result count: {len(rows)}")
            for r in rows: print(f"{r['username']}: {r['total_minutes']}m")
        except Exception as e:
            print(f"FAIL Test 2: {e}")

        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(repro())
