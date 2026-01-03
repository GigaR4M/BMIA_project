
import asyncio
import os
import asyncpg
from dotenv import load_dotenv
import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = 1327836427915886643  # Known guild ID

async def debug_funcs():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # 1. Check raw table data
        print("--- Checking daily_user_stats content ---")
        count = await conn.fetchval("SELECT COUNT(*) FROM daily_user_stats WHERE guild_id = $1", GUILD_ID)
        print(f"Rows in daily_user_stats for guild {GUILD_ID}: {count}")
        
        if count == 0:
            print("WARNING: No data found. Backfill might have missed this guild.")
            
        # 2. Test get_daily_message_stats with explicit casting
        # Trying to mimic Supabase call: params passed as JSON-like named args? 
        # Asyncpg uses positional args ($1, $2...). 
        # The frontend passes: p_guild_id (string), p_days (int), p_timezone (string), p_start_date (null)
        
        print("\n--- Testing get_daily_message_stats (Positional) ---")
        try:
            rows = await conn.fetch("""
                SELECT * FROM get_daily_message_stats(
                    p_guild_id := $1, 
                    p_days := $2, 
                    p_timezone := $3, 
                    p_start_date := $4
                )
            """, GUILD_ID, 30, 'America/Sao_Paulo', None)
            
            print(f"Rows returned: {len(rows)}")
            for row in rows[:3]:
                print(dict(row))
        except Exception as e:
            print(f"Error calling get_daily_message_stats: {e}")

        # 3. Test get_top_users_by_messages
        print("\n--- Testing get_top_users_by_messages ---")
        try:
            rows = await conn.fetch("""
                SELECT * FROM get_top_users_by_messages(
                    p_guild_id := $1, 
                    p_days := $2, 
                    p_limit := $3, 
                    p_start_date := $4
                )
            """, GUILD_ID, 30, 10, None)
            
            print(f"Rows returned: {len(rows)}")
            for row in rows[:3]:
                print(dict(row))
        except Exception as e:
            print(f"Error calling get_top_users_by_messages: {e}")

        await conn.close()
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_funcs())
