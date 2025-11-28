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
    
    print("Adding 'error_message' column to 'embed_requests'...")
    
    try:
        async with db.pool.acquire() as conn:
            # Check if column exists
            col_exists = await conn.fetchval("""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'embed_requests' AND column_name = 'error_message'
            """)
            
            if not col_exists:
                await conn.execute("""
                    ALTER TABLE embed_requests
                    ADD COLUMN error_message TEXT;
                """)
                print("✅ Column 'error_message' added.")
            else:
                print("ℹ️ Column already exists.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
