import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def fix_constraint():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connected.")
        
        # Drop the constraint to allow any text value (as per schema definition in code)
        # Or we could update it, but dropping is safer to avoid future maintenance issues 
        # since the code doesn't define it.
        try:
            print("Attempting to drop constraint 'interaction_points_interaction_type_check'...")
            # We use IF EXISTS to avoid error if it was already removed
            await conn.execute("ALTER TABLE interaction_points DROP CONSTRAINT IF EXISTS interaction_points_interaction_type_check")
            print("Constraint dropped successfully (if it existed).")
        except Exception as e:
            print(f"Error dropping constraint: {e}")
            
        await conn.close()
        print("Connection closed.")
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_constraint())
