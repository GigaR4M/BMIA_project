import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def fix_bot_status():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connected to database.")

        # Check for all Carl-bot instances
        rows = await conn.fetch("SELECT * FROM users WHERE username ILIKE '%Carl-bot%'")
        if rows:
            print(f"Found {len(rows)} users matching 'Carl-bot':")
            for row in rows:
                print(f"ID: {row['user_id']}, Username: {row['username']}, Is Bot: {row['is_bot']}")
        else:
            print("Carl-bot not found in database.")

        # Optional: Update other known bots or generic 'bot' names if needed
        # await conn.execute("UPDATE users SET is_bot = TRUE WHERE username ILIKE '%bot%' AND is_bot = FALSE")

        await conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(fix_bot_status())
