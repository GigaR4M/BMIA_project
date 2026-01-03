import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

TARGET_FUNCTIONS = [
    'get_top_users_by_voice'
]

async def get_funcs():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        with open("sql_verify_voice.txt", "w", encoding="utf-8") as f:
            for func_name in TARGET_FUNCTIONS:
                f.write(f"\n--- {func_name} ---\n")
                row = await conn.fetchrow("SELECT oid FROM pg_proc WHERE proname = $1 LIMIT 1", func_name)
                
                if row:
                    oid = row['oid']
                    definition = await conn.fetchval("SELECT pg_get_functiondef($1)", oid)
                    f.write(definition + "\n")
                    print(definition)
                else:
                    f.write(f"Function {func_name} not found.\n")

        await conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_funcs())
