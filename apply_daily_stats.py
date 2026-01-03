import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SQL_FILE_PATH = os.path.join(os.path.dirname(__file__), "migration_daily_stats.sql")

async def apply_daily_stats_migration():
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment variables.")
        return

    if not os.path.exists(SQL_FILE_PATH):
        print(f"Error: SQL file not found at {SQL_FILE_PATH}")
        return

    try:
        print(f"Reading SQL from {SQL_FILE_PATH}...")
        with open(SQL_FILE_PATH, "r", encoding="utf-8") as f:
            sql_content = f.read()

        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        print("Connected to database.")

        print("Executing SQL script...")
        await conn.execute(sql_content)
        print("SQL script executed successfully.")

        await conn.close()
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(apply_daily_stats_migration())
