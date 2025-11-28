import asyncio
import os
from dotenv import load_dotenv
from database import Database

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    print("Resetting failed requests to pending...")
    
    try:
        async with db.pool.acquire() as conn:
            await conn.execute("UPDATE embed_requests SET status = 'pending', error_message = NULL WHERE status = 'failed'")
            print("Done.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
