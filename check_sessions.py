import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
TARGET_USER = "thi4g03072"

async def check_sessions():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        user_id = await conn.fetchval("SELECT user_id FROM users WHERE username = $1", TARGET_USER)
        if not user_id: return

        print(f"Sessions for {TARGET_USER} ({user_id}) around New Year:")
        rows = await conn.fetch("""
            SELECT channel_id, joined_at, left_at, duration_seconds 
            FROM voice_activity 
            WHERE user_id = $1 
            ORDER BY joined_at DESC
            LIMIT 10
        """, user_id)
        
        for r in rows:
            print(f"Channel {r['channel_id']} | Start: {r['joined_at']} | Duration: {r['duration_seconds']/60:.1f} min")

        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(check_sessions())
