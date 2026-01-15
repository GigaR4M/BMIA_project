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
        # 1. Get Guild ID (assuming active one)
        guilds = await db.pool.fetch("SELECT DISTINCT guild_id FROM interaction_points LIMIT 1")
        if not guilds:
            print("No guilds found")
            return
        guild_id = guilds[0]['guild_id']
        print(f"Checking Guild: {guild_id}")

        # 2. Find lordpedroiii or top user
        user = await db.pool.fetchrow("""
            SELECT u.user_id, u.username, SUM(ip.points) as raw_sum
            FROM interaction_points ip
            JOIN users u ON ip.user_id = u.user_id
            WHERE ip.guild_id = $1
            GROUP BY u.user_id, u.username
            ORDER BY raw_sum DESC
            LIMIT 1
        """, guild_id)
        
        if not user:
            print("No user found")
            return
            
        print(f"Top User Raw Sum (SQL): {user['username']} ({user['user_id']}) = {user['raw_sum']}")

        # 3. Call get_leaderboard RPC
        rpc_result = await db.pool.fetch("""
            SELECT * FROM get_leaderboard($1, 5, NULL, NULL)
            WHERE user_id = $2
        """, guild_id, user['user_id'])
        
        if rpc_result:
            print(f"RPC get_leaderboard Result: {rpc_result[0]['total_points']}")
        else:
            print("RPC returned no rows for user")

        # 4. Check for multiple entries in users table?
        user_count = await db.pool.fetchval("SELECT COUNT(*) FROM users WHERE user_id = $1", user['user_id'])
        print(f"User rows in 'users' table: {user_count}")

    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
