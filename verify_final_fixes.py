import asyncio
import os
import asyncpg
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def verify():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        guild_id = 1327836427915886643 
        
        # 1. Verify Streaming with new Activity Types
        print("\n--- Verifying Longest Streaming (Including 'screen_share') ---")
        rows = await conn.fetch("SELECT * FROM get_highlight_longest_streaming($1)", guild_id)
        if rows:
            for r in rows:
                print(f"User: {r['username']}, Time: {r['value_seconds']}s ({r['value_seconds']/3600:.1f}h)")
        else:
            print("No streaming data found.")

        # 2. Verify Voice Consistency with Explicit Timestamp
        print("\n--- Verifying Voice Stats Consistency ---")
        
        # Highlights (Uses strict get_start_of_year() - immutable in DB)
        print("Highlights (get_highlight_most_voice_time):")
        h_rows = await conn.fetch("SELECT * FROM get_highlight_most_voice_time($1, 5)", guild_id)
        h_stats = {}
        for r in h_rows:
             print(f"User: {r['username']}, Time: {r['value_seconds']}s")
             h_stats[r['username']] = r['value_seconds']

        # Users Page (Passing 2026-01-01 ISO String as the frontend does)
        # Frontend sends: "2026-01-01T00:00:00.000Z" (Usually) or Local?
        # If user set Year '2026', start date is likely start of year in UTC or Local.
        # Let's test with strict ISO string simulating frontend request
        target_date = datetime(2026, 1, 1, 0, 0, 0).isoformat() + "-03:00" # Simulating Local Start
        
        print(f"\nUsers Page (get_top_users_by_voice) with start_date='{target_date}':")
        # Note: We pass the string and let asyncpg/postgres handle the cast to timestamptz
        # If our fix works, this should map correctly to the start of the year in DB without shifting.
        
        u_rows = await conn.fetch("SELECT * FROM get_top_users_by_voice($1, 365, 10, $2)", guild_id, datetime.fromisoformat(target_date))
        
        print(f"\n{'User':<15} | {'Minutes':<8} | {'Hours':<8}")
        print("-" * 35)
        for r in u_rows:
            user = r['username']
            mins = r['total_minutes']
            hours = f"{mins/60:.1f}h"
            print(f"{user:<15} | {mins:<8} | {hours:<8}")

        await conn.close()

    except Exception as e:
        print(f"❌ Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
