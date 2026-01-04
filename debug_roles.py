import asyncio
import os
from dotenv import load_dotenv
from database import Database
from datetime import datetime

load_dotenv()

async def debug():
    db = Database(os.getenv('DATABASE_URL'))
    await db.connect()
    
    print("\n--- RPC Definition: get_highlight_most_distinct_games ---")
    try:
        defn = await db.pool.fetchval("SELECT pg_get_functiondef('get_highlight_most_distinct_games'::regproc)")
        print(defn)
    except Exception as e:
        print(f"Error fetching gamer RPC: {e}")

    await db.disconnect()

asyncio.run(debug())
