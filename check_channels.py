import asyncio
import os
from dotenv import load_dotenv
from database import Database

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
GUILD_ID = 1327836427915886643

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    print(f"Checking channels for Guild ID: {GUILD_ID}")
    
    try:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT channel_id, channel_name, guild_id FROM channels LIMIT 50")
            print(f"Found {len(rows)} channels.")
            for row in rows:
                print(f"ID: {row['channel_id']} - {row['channel_name']} (Guild: {row['guild_id']})")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
