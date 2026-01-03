
import asyncio
import os
from database import Database
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def verify_python_methods():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found.")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    try:
        guild_id = 1327836427915886643
        user_id = 465689386742424868 # From previous log
        
        print("\n--- Testing get_top_users_by_messages ---")
        top_users = await db.get_top_users_by_messages(guild_id, limit=3, days=30)
        for user in top_users:
            print(user)
            
        print("\n--- Testing get_detailed_user_stats ---")
        stats = await db.get_detailed_user_stats(user_id, guild_id, days=30)
        print(f"Total Messages: {stats['total_messages']}")
        print(f"Voice Minutes: {stats['voice_minutes']}")
        
        print("\n--- Testing get_messages_per_day ---")
        days_stats = await db.get_messages_per_day(guild_id, days=7)
        for d in days_stats:
            print(d)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(verify_python_methods())
