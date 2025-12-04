import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def list_functions():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        print("Connected.")

        rows = await conn.fetch("""
            SELECT proname, proargtypes::regtype[] as args
            FROM pg_proc
            WHERE proname = 'get_leaderboard'
        """)

        print(f"Found {len(rows)} functions:")
        for row in rows:
            print(f"Function: {row['proname']}, Args: {row['args']}")

        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_functions())
