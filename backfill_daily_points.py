import asyncio
import os
import logging
from database import Database
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BackfillPoints")

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not found.")
    exit(1)

async def backfill_daily_points():
    logger.info("Starting backfill of daily_user_stats.total_points...")
    
    db = Database(DATABASE_URL)
    await db.connect()
    
    try:
        async with db.pool.acquire() as conn:
            # 1. Get count of rows to be updated (rows with 0 total_points or all? 
            # The user asked to populate, presumably it's empty or needs fixing. 
            # We will update ALL rows to be safe and ensure consistency).
            
            count_before = await conn.fetchval("SELECT COUNT(*) FROM daily_user_stats")
            logger.info(f"Targeting {count_before} rows in daily_user_stats.")
            
            # 2. Execute Update
            # The query calculates the cumulative sum of points for each user/guild up to the specific date (inclusive)
            # using Sao Paulo timezone for the cut-off.
            
            # NOTE: daily_user_stats.date is type DATE.
            # interaction_points.created_at is TIMESTAMP (UTC usually).
            # We convert interaction_points.created_at to Sao Paulo DATE.
            
            query = """
            WITH CalculatedPoints AS (
                SELECT 
                    dus.guild_id,
                    dus.user_id,
                    dus.date,
                    (
                        SELECT COALESCE(SUM(p.points), 0)
                        FROM interaction_points p
                        WHERE p.user_id = dus.user_id
                          AND p.guild_id = dus.guild_id
                          -- Convert UTC creation time to Sao Paulo date
                          AND (p.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::DATE <= dus.date
                    ) as calculated_total
                FROM daily_user_stats dus
            )
            UPDATE daily_user_stats
            SET 
                total_points = cp.calculated_total,
                updated_at = NOW()
            FROM CalculatedPoints cp
            WHERE daily_user_stats.guild_id = cp.guild_id
              AND daily_user_stats.user_id = cp.user_id
              AND daily_user_stats.date = cp.date
              -- Optimization: Only update if different
              AND daily_user_stats.total_points IS DISTINCT FROM cp.calculated_total;
            """
            
            logger.info("Executing UPDATE query... this might take a moment.")
            result = await conn.execute(query)
            logger.info(f"Update completed. Result: {result}")
            
            # 3. Verification Sample
            logger.info("Verifying a random sample...")
            sample = await conn.fetch("""
                SELECT guild_id, user_id, date, total_points 
                FROM daily_user_stats 
                ORDER BY RANDOM() 
                LIMIT 5
            """)
            
            for row in sample:
                g_id = row['guild_id']
                u_id = row['user_id']
                dt = row['date']
                stored_points = row['total_points']
                
                # Manual recalc
                calc_points = await conn.fetchval("""
                    SELECT COALESCE(SUM(points), 0)
                    FROM interaction_points
                    WHERE user_id = $1 AND guild_id = $2
                      AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::DATE <= $3
                """, u_id, g_id, dt)
                
                status = "✅ MATCH" if stored_points == calc_points else f"❌ MISMATCH (Calc: {calc_points})"
                logger.info(f"User {u_id} on {dt}: Stored={stored_points} | {status}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await db.disconnect()
        logger.info("Database connection closed.")

if __name__ == "__main__":
    asyncio.run(backfill_daily_points())
