import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def migrate_points_guild():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        # statement_cache_size=0 needed for pgbouncer compatibility in some envs
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print("Checking if guild_id column exists in interaction_points...")
        # Check if column exists
        row = await conn.fetchrow("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='interaction_points' AND column_name='guild_id'
        """)

        if not row:
            print("Adding guild_id column to interaction_points...")
            # Add column as NULLable first (for existing records)
            await conn.execute("ALTER TABLE interaction_points ADD COLUMN guild_id BIGINT")
            print("Column added.")
            
            # Create index for performance
            print("Creating index on guild_id...")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_interaction_points_guild ON interaction_points(guild_id)")
            print("Index created.")
        else:
            print("Column guild_id already exists.")

        print("Migration completed.")
        await conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_points_guild())
