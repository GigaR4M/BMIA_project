
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = 1327836427915886643

async def check_integrity():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # 1. Check Orphaned Stats (stats with user_id not in users)
        print("--- Checking for orphaned stats ---")
        orphans = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM daily_user_stats s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE u.user_id IS NULL AND s.guild_id = $1
        """, GUILD_ID)
        print(f"Orphaned stat rows: {orphans}")

        # 2. Check Bot Status of Stats
        print("\n--- Checking Bot stats ---")
        bot_stats = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM daily_user_stats s
            JOIN users u ON s.user_id = u.user_id
            WHERE u.is_bot = TRUE AND s.guild_id = $1
        """, GUILD_ID)
        
        non_bot_stats = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM daily_user_stats s
            JOIN users u ON s.user_id = u.user_id
            WHERE u.is_bot = FALSE AND s.guild_id = $1
        """, GUILD_ID)
        
        print(f"Stats for Bots: {bot_stats}")
        print(f"Stats for Humans: {non_bot_stats}")
        
        if non_bot_stats == 0:
            print("WARNING: All stats are for bots or orphans! This explains empty dashboard.")

        await conn.close()
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(check_integrity())
