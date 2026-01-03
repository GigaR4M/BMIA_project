import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

CHANNEL_IDS = [
    1327836428524191769, # The 10h channel
    1335352978986635468  # The AFK channel
]

async def check_channel_guilds():
    if not DATABASE_URL: return
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        print("Checking Channel Guilds:")
        for cid in CHANNEL_IDS:
            row = await conn.fetchrow("SELECT guild_id, channel_name FROM channels WHERE channel_id = $1", cid)
            if row:
                print(f"Channel {cid} ({row['channel_name']}) -> Guild {row['guild_id']}")
            else:
                # Try finding it in voice_activity if not in channels table
                row2 = await conn.fetchrow("SELECT guild_id FROM voice_activity WHERE channel_id = $1 LIMIT 1", cid)
                if row2:
                    print(f"Channel {cid} (from activity) -> Guild {row2['guild_id']}")
                else:
                    print(f"Channel {cid} not found.")
                    
        await conn.close()
    except Exception as e:
        print(e)

if __name__ == "__main__":
    asyncio.run(check_channel_guilds())
