
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def verify_new_funcs():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # Pick a guild
        guild_id = 1327836427915886643 # From previous log
        
        print("\n--- Testing get_daily_voice_stats ---")
        rows = await conn.fetch("SELECT * FROM get_daily_voice_stats($1, 30)", guild_id)
        for row in rows[:3]:
            print(dict(row))
            
        print("\n--- Testing get_top_users_by_messages ---")
        rows = await conn.fetch("SELECT * FROM get_top_users_by_messages($1, 30, 3)", guild_id)
        for row in rows:
            print(dict(row))

        await conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(verify_new_funcs())
