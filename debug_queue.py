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
    
    print("Checking 'embed_requests' table (Last 5)...")
    
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM embed_requests ORDER BY created_at DESC LIMIT 5")
            print(f"Found {len(rows)} requests.")
            for row in rows:
                cid = str(row['channel_id'])
                print(f"[{row['status']}] ID={row['id']} Ch={cid} (Len={len(cid)}) Err={row.get('error_message')}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
