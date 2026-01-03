
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def verify_stats():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        row_count = await conn.fetchval("SELECT COUNT(*) FROM daily_user_stats")
        print(f"Total rows in daily_user_stats: {row_count}")
        
        sample = await conn.fetch("SELECT * FROM daily_user_stats LIMIT 5")
        for row in sample:
            print(dict(row))
            
        await conn.close()

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(verify_stats())
