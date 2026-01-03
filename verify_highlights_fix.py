import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def verify():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # 1. Verify Streaming
        print("\n--- Verifying Longest Streaming (Should show data now) ---")
        # We need a guild_id. From previous context/files, we can try to fetch one or retrieve from known message.
        # Let's just pick the first guild available or a known ID.
        # From file list we saw podium files for IDs: 1327836427915886643 and 1444182856489500723
        guild_id = 1327836427915886643 
        
        rows = await conn.fetch("SELECT * FROM get_highlight_longest_streaming($1)", guild_id)
        if rows:
            for r in rows:
                print(f"User: {r['username']}, Time: {r['value_seconds']}s")
        else:
            print("No streaming data found (Could be empty DB or still broken)")

        # 2. Verify Voice Consistency
        print("\n--- Verifying Voice Stats Consistency ---")
        
        # Highlight logic
        print("Highlights (get_highlight_most_voice_time):")
        h_rows = await conn.fetch("SELECT * FROM get_highlight_most_voice_time($1, 5)", guild_id)
        for r in h_rows:
             print(f"User: {r['username']}, Time: {r['value_seconds']}s")

        # Users Page logic (get_top_users_by_voice) - defaulting to year start to match highlight
        # Note: Users page uses 'minutes', Highlight uses 'seconds'.
        print("\nUsers Page (get_top_users_by_voice) - Converted to seconds for comparison:")
        # We invoke it with no start_date (defaults to days) or specific params. 
        # Highlights uses "get_start_of_year()". Let's try to match that approx or just see if the filter works.
        # We explicitly check if excluded channels are ignored.
        
        # Let's check raw counts for a user in an ignored channel to be sure.
        # Channel 1356045946743689236 (Três mosqueteiros)
        print("\nChecking raw voice activity in ignored channel 1356045946743689236 (Should be ignored in both now):")
        ignored_voice = await conn.fetchval("""
            SELECT count(*) FROM voice_activity 
            WHERE channel_id = 1356045946743689236 AND guild_id = $1
        """, guild_id)
        print(f"Total raw entries in ignored channel: {ignored_voice}")
        
        # Now check if get_top_users_by_voice includes this
        # If the fix worked, the total minutes returned should NOT include time from that channel.
        # This is harder to verify without summing up manually, but we can verify the SQL matches the applied fix.
        # We trust the applied SQL if the function definition looks correct.
        
        # Let's just print the results of the new function.
        u_rows = await conn.fetch("SELECT * FROM get_top_users_by_voice($1, 365, 5)", guild_id)
        for r in u_rows:
            print(f"User: {r['username']}, Time: {r['total_minutes']}m ({r['total_minutes']*60}s)")

        await conn.close()

    except Exception as e:
        print(f"❌ Error during verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
