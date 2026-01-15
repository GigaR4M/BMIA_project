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
        # Check specific user
        uid = 312389956045897731
        rows = await db.pool.fetch("SELECT * FROM users WHERE user_id = $1", uid)
        print(f"Rows for user {uid}: {len(rows)}")
        for r in rows:
            print(dict(r))

        # Check constraint
        # Query pg_indexes or similar
        indexes = await db.pool.fetch("SELECT * FROM pg_indexes WHERE tablename = 'users'")
        print("\nIndexes on users table:")
        for idx in indexes:
            print(idx['indexdef'])

        # Fix if duplicates found
        if len(rows) > 1:
            print("\nFound duplicates! Attempting to delete...")
            # Delete all but the latest
            # Since user_id isn't unique, we need ctid
            keep_ctid = await db.pool.fetchval("""
                SELECT ctid FROM users WHERE user_id = $1 ORDER BY last_seen DESC LIMIT 1
            """, uid)
            
            await db.pool.execute("""
                DELETE FROM users 
                WHERE user_id = $1 AND ctid != $2
            """, uid, keep_ctid)
            
            print("Deleted duplicates for this user.")
            
            # Check if global issue
            dupes = await db.pool.fetchval("""
                SELECT count(*) FROM (
                    SELECT user_id, count(*) 
                    FROM users 
                    GROUP BY user_id 
                    HAVING count(*) > 1
                ) sub
            """)
            print(f"Users with duplicates: {dupes}")

    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
