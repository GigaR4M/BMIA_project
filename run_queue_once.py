import discord
import asyncio
import os
from dotenv import load_dotenv
from database import Database
from utils.embed_sender import EmbedSender
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import dotenv_values

env_path = os.path.join(os.path.dirname(__file__), '.env')
print(f"Loading .env from: {env_path}")
config = dotenv_values(env_path)

DISCORD_TOKEN = config.get('DISCORD_TOKEN')
DATABASE_URL = config.get('DATABASE_URL')

intents = discord.Intents.default()
intents.guilds = True

client = discord.Client(intents=intents)

async def main():
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN is missing")
    if not DATABASE_URL:
        print("Error: DATABASE_URL is missing")
    
    if not DISCORD_TOKEN or not DATABASE_URL:
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    embed_sender = EmbedSender(db)
    
    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        print("Processing embed queue...")
        try:
            await embed_sender.process_pending_requests(client)
            print("Queue processing finished.")
        except Exception as e:
            print(f"Error processing queue: {e}")
        
        await client.close()
        await db.disconnect()

    try:
        await client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        await client.close()
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
