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
            # Check Channel Types
            rows = await conn.fetch("SELECT channel_name, channel_type FROM channels WHERE guild_id = $1", GUILD_ID)
            print(f"Found {len(rows)} channels.")
            for row in rows:
                print(f"- {row['channel_name']}: '{row['channel_type']}'")
            
            # Check RLS Status
            rls_check = await conn.fetchrow("SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'channels'")
            if rls_check:
                print(f"RLS Enabled on 'channels': {rls_check['relrowsecurity']}")
            else:
                print("Could not check RLS status.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
