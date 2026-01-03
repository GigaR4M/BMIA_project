
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def list_funcs():
    if not DATABASE_URL:
        return

    conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
    
    params = ['get_daily_message_stats', 'get_top_users_by_messages', 'get_daily_voice_stats', 'get_top_users_by_voice']
    
    print("--- Existing Function Signatures ---")
    rows = await conn.fetch("""
        SELECT 
            p.proname, 
            pg_get_function_arguments(p.oid) as arguments
        FROM pg_proc p 
        JOIN pg_namespace n ON p.pronamespace = n.oid 
        WHERE n.nspname = 'public' 
          AND p.proname = ANY($1)
    """, params)
    
    for r in rows:
        print(f"Function: {r['proname']}")
        print(f"  Args: {r['arguments']}")
        print("-" * 20)

    await conn.close()

if __name__ == "__main__":
    asyncio.run(list_funcs())
