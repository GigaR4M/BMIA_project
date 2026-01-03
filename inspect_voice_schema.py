import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
TARGET_USER = "thi4g03072"

async def inspect_data():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # 1. Check Schema
        print("\n--- Table Schema: voice_activity ---")
        rows = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'voice_activity'
        """)
        for r in rows:
            print(f"{r['column_name']}: {r['data_type']}")
            
        # 2. Check Raw Sessions around New Year (UTC vs Local interpretation)
        user_id = await conn.fetchval("SELECT user_id FROM users WHERE username = $1", TARGET_USER)
        print(f"\n--- Sessions for {TARGET_USER} ({user_id}) ---")
        
        # Fetch raw timestamps
        sessions = await conn.fetch("""
            SELECT channel_id, joined_at, duration_seconds
            FROM voice_activity
            WHERE user_id = $1
            AND joined_at BETWEEN '2025-12-31 18:00:00' AND '2026-01-02 00:00:00'
            ORDER BY joined_at
        """, user_id)
        
        total_dur = 0
        for s in sessions:
            ts = s['joined_at']
            dur = s['duration_seconds']
            print(f"Start: {ts} (Type: {type(ts)}) | Duration: {dur}s ({dur/60:.1f}m)")
            total_dur += dur
            
        print(f"Total shown: {total_dur/3600:.2f} hours")

        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(inspect_data())
