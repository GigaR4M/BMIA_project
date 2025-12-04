import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def verify_leaderboard():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        print("Connected to database.")

        print("Fetching leaderboard (top 50)...")
        rows = await conn.fetch("SELECT * FROM get_leaderboard(50)")
        
        found_carl = False
        print("\nLeaderboard:")
        for row in rows:
            print(f"Rank: {row['rank']}, User: {row['username']}, Points: {row['total_points']}")
            if "Carl-bot" in row['username']:
                found_carl = True

        print("-" * 30)
        if found_carl:
            print("❌ FAILURE: Carl-bot is still on the leaderboard.")
        else:
            print("✅ SUCCESS: Carl-bot is NOT on the leaderboard.")

        await conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(verify_leaderboard())
