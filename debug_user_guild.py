import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
TARGET_USER = "thi4g03072"

async def debug():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # Get ID
        user_id = await conn.fetchval("SELECT user_id FROM users WHERE username = $1", TARGET_USER)
        if not user_id:
            print("User not found")
            return

        print(f"User: {TARGET_USER} ({user_id})")
        
        # Group by GUILD and CHANNEL for 2026
        rows = await conn.fetch("""
            SELECT 
                guild_id,
                channel_id,
                SUM(duration_seconds) as secs
            FROM voice_activity
            WHERE user_id = $1
              AND joined_at >= '2026-01-01 00:00:00-03'
            GROUP BY guild_id, channel_id
            ORDER BY guild_id
        """, user_id)
        
        print("\n--- 2026 Voice Activity Breakdown ---")
        for r in rows:
            print(f"Guild {r['guild_id']} | Channel {r['channel_id']} | Time: {r['secs']/60:.1f} min ({r['secs']}s)")
            
        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(debug())
