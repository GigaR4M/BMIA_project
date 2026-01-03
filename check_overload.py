import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def check_overload():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print("Checking for overloaded get_top_users_by_voice:")
        rows = await conn.fetch("""
            SELECT oid, proname, pg_get_function_identity_arguments(oid) as args 
            FROM pg_proc 
            WHERE proname = 'get_top_users_by_voice'
        """)
        
        for r in rows:
            print(f"OID: {r['oid']} | Args: {r['args']}")

        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(check_overload())
