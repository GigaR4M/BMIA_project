import asyncio
import os
import sys
from datetime import datetime, timedelta
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
        # Get target user (lordpedroiii)
        target_id = 312389956045897731
        
        ranges = {
            "7 Days": 7,
            "30 Days": 30,
            "90 Days": 90,
            "1 Year": 365,
            "All Time": None
        }
        
        print(f"Checking points for user: {target_id}")
        
        for name, days in ranges.items():
            if days:
                cutoff = datetime.now() - timedelta(days=days)
                query = "SELECT SUM(points) FROM interaction_points WHERE user_id = $1 AND created_at >= $2"
                points = await db.pool.fetchval(query, target_id, cutoff)
            else:
                query = "SELECT SUM(points) FROM interaction_points WHERE user_id = $1"
                points = await db.pool.fetchval(query, target_id)
                
            print(f"{name}: {points}")
            
        # Check "Since Jan 1 2025" (Last Year Start)
        jan1_2025 = datetime(2025, 1, 1)
        pts_2025 = await db.pool.fetchval("SELECT SUM(points) FROM interaction_points WHERE user_id = $1 AND created_at >= $2", target_id, jan1_2025)
        print(f"Since Jan 1, 2025: {pts_2025}")

        # Check "Since Month Start"
        now = datetime.now()
        month_start = datetime(now.year, now.month, 1)
        pts_month = await db.pool.fetchval("SELECT SUM(points) FROM interaction_points WHERE user_id = $1 AND created_at >= $2", target_id, month_start)
        print(f"Since Month Start ({month_start.date()}): {pts_month}")

    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
