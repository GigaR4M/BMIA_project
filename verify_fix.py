import asyncio
import os
from dotenv import load_dotenv
from database import Database
import json

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
# Use the known valid channel ID
CHANNEL_ID = 1328515426342146058 
GUILD_ID = 1327836427915886643

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    print("Inserting test embed request...")
    
    embed_data = {
        "title": "Verification Test",
        "description": "This is a test from the verification script.",
        "color": "#00ff00"
    }
    
    try:
        async with db.pool.acquire() as conn:
            # Insert request
            row = await conn.fetchrow("""
                INSERT INTO embed_requests (guild_id, channel_id, message_data, status)
                VALUES ($1, $2, $3, 'pending')
                RETURNING id
            """, GUILD_ID, CHANNEL_ID, json.dumps(embed_data))
            
            request_id = row['id']
            print(f"Inserted Request ID: {request_id}")
            
            # Wait for bot to process
            print("Waiting 60 seconds for bot to process...")
            await asyncio.sleep(60)
            
            # Check status
            status_row = await conn.fetchrow("SELECT status, error_message FROM embed_requests WHERE id = $1", request_id)
            print(f"Final Status: {status_row['status']}")
            if status_row['error_message']:
                print(f"Error: {status_row['error_message']}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
