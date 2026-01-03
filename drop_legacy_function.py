import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

DROP_CMD = """
DROP FUNCTION IF EXISTS public.get_top_users_by_voice(bigint, integer, integer, timestamp without time zone);
"""

async def fix_duplicate():
    if not DATABASE_URL:
        print("DATABASE_URL not found.")
        return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Dropping legacy function (without time zone)...")
        await conn.execute(DROP_CMD)
        print("✅ Dropped successfully.")
        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_duplicate())
