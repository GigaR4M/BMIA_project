
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = 1327836427915886643

async def inspect():
    if not DATABASE_URL:
        return

    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    
    print("--- Date Range in daily_user_stats ---")
    row = await conn.fetchrow("""
        SELECT MIN(date), MAX(date), COUNT(*) 
        FROM daily_user_stats 
        WHERE guild_id = $1
    """, GUILD_ID)
    print(f"Min: {row[0]}, Max: {row[1]}, Count: {row[2]}")

    print("\n--- Sample Rows ---")
    rows = await conn.fetch("""
        SELECT date, messages_count, voice_seconds 
        FROM daily_user_stats 
        WHERE guild_id = $1 
        ORDER BY date DESC 
        LIMIT 5
    """, GUILD_ID)
    for r in rows:
        print(dict(r))

    print("\n--- Current DB Time ---")
    now_db = await conn.fetchval("SELECT CURRENT_DATE")
    print(f"DB Current Date: {now_db}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect())
