import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

TARGET_USER = "thi4g03072"

async def debug_user():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print(f"--- Debugging User: {TARGET_USER} ---")
        
        # 1. Get User ID
        user_id = await conn.fetchval("SELECT user_id FROM users WHERE username = $1", TARGET_USER)
        if not user_id:
            print("User not found.")
            return
        print(f"User ID: {user_id}")
        
        # 2. Get Raw Voice Activity for 2026
        rows = await conn.fetch("""
            SELECT 
                channel_id, 
                SUM(duration_seconds) as total_seconds,
                SUM(duration_seconds)/60 as total_minutes
            FROM voice_activity 
            WHERE user_id = $1 
              AND joined_at >= '2026-01-01 00:00:00-03'
            GROUP BY channel_id
        """, user_id)
        
        print("\n--- Breakdown by Channel (2026) ---")
        total_calc = 0
        excluded_ids = [1356045946743689236, 1335352978986635468]
        
        for r in rows:
            cid = r['channel_id']
            status = "EXCLUDED" if cid in excluded_ids else "VALID"
            if cid is None: status = "NULL (VALID?)"
            
            print(f"Channel {cid}: {r['total_minutes']} min ({r['total_seconds']}s) - {status}")
            total_calc += r['total_seconds']

        print(f"\nTotal Raw Seconds: {total_calc}")
        print(f"Total Raw Minutes: {total_calc/60}")
        
        # 3. Check Streaming Activity
        print("\n--- Streaming Activity (Any time) ---")
        s_rows = await conn.fetch("""
            SELECT activity_name, activity_type, duration_seconds, started_at 
            FROM user_activities 
            WHERE user_id = $1 AND (activity_type LIKE '%stream%' OR activity_type LIKE '%screen%')
        """, user_id)
        for r in s_rows:
            print(f"Activity: {r['activity_name']} ({r['activity_type']}) - {r['duration_seconds']}s - {r['started_at']}")

        await conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_user())
