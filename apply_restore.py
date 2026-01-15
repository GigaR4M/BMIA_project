import asyncio
import os
import sys
from dotenv import load_dotenv

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
        with open('restore_legacy_leaderboard.sql', 'r') as f:
            width_sql = f.read()
            
        async with db.pool.acquire() as conn:
            await conn.execute(width_sql)
            print("Successfully restored legacy get_leaderboard RPC")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
