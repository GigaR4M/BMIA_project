
import asyncio
import os
import asyncpg
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def backfill_daily_stats():
    if not DATABASE_URL:
        logger.error("DATABASE_URL not found in environment variables.")
        return

    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        logger.info("Connected to database.")

        logger.info("Starting backfill process...")
        
        # 1. Backfill Messages
        logger.info("Backfilling messages...")
        # We group by the Brazil date of created_at
        await conn.execute("""
            INSERT INTO daily_user_stats (guild_id, user_id, date, messages_count, updated_at)
            SELECT 
                guild_id,
                user_id,
                DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') as msg_date,
                COUNT(*) as msg_count,
                NOW()
            FROM messages
            GROUP BY guild_id, user_id, msg_date
            ON CONFLICT (guild_id, user_id, date)
            DO UPDATE SET 
                messages_count = EXCLUDED.messages_count,
                updated_at = NOW();
        """)
        logger.info("Messages backfilled.")

        # 2. Backfill Voice Activity
        logger.info("Backfilling voice activity...")
        # We group by the Brazil date of joined_at
        await conn.execute("""
            WITH voice_sums AS (
                SELECT 
                    guild_id,
                    user_id,
                    DATE(joined_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo') as voice_date,
                    SUM(duration_seconds) as total_seconds
                FROM voice_activity
                WHERE duration_seconds IS NOT NULL AND duration_seconds > 0
                GROUP BY guild_id, user_id, voice_date
            )
            INSERT INTO daily_user_stats (guild_id, user_id, date, voice_seconds, updated_at)
            SELECT 
                guild_id, 
                user_id, 
                voice_date, 
                total_seconds, 
                NOW()
            FROM voice_sums
            ON CONFLICT (guild_id, user_id, date)
            DO UPDATE SET 
                voice_seconds = EXCLUDED.voice_seconds,
                updated_at = NOW();
        """)
        logger.info("Voice activity backfilled.")

        await conn.close()
        logger.info("Backfill complete.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(backfill_daily_stats())
