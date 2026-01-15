import asyncio
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

load_dotenv()

async def main():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not found")
        return

    db = Database(db_url)
    await db.connect()

    try:
        # Fetch the source code of the function
        query = "SELECT prosrc FROM pg_proc WHERE proname = 'get_leaderboard'"
        async with db.pool.acquire() as conn:
            source = await conn.fetchval(query)
            print("\n\n========== RPC SOURCE BEGIN ==========\n")
            print(source)
            print("\n========== RPC SOURCE END ==========\n\n")

            # Check counts
            count = await conn.fetchval("SELECT COUNT(*) FROM interaction_points")
            print(f"Total interaction_points rows: {count}")
            
            # Check points for lordpedroiii (fuzzy search if needed or just top 1)
            # Assuming getting top 1 by points
            top_user = await conn.fetchrow("""
                SELECT user_id, SUM(points) as total 
                FROM interaction_points 
                GROUP BY user_id 
                ORDER BY total DESC 
                LIMIT 1
            """)
            print(f"Top User in DB (Lifetime): {top_user}")

            # Check points for 2026
            top_user_2026 = await conn.fetchrow("""
                SELECT user_id, SUM(points) as total 
                FROM interaction_points 
                WHERE created_at >= '2026-01-01'
                GROUP BY user_id 
                ORDER BY total DESC 
                LIMIT 1
            """)
            print(f"Top User in DB (2026): {top_user_2026}")


    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
