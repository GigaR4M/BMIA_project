import asyncio
import os
from dotenv import load_dotenv
import asyncpg

async def apply_sql():
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return

    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Use absolute path or correct relative path
        file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bmia-dashboard', 'supabase_new_stats.sql')
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()

        await conn.execute(sql)
        print("✅ SQL applied successfully")
        
        await conn.close()
    except Exception as e:
        print(f"❌ Error applying SQL: {e}")

if __name__ == "__main__":
    asyncio.run(apply_sql())
