import discord
import os
import logging
from dotenv import load_dotenv
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_tree")

# Load environment
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Minimal Client
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    
    logger.info("Fetching remote commands...")
    # Fetch global commands
    commands = await tree.fetch_commands()
    logger.info(f"Remote Global Commands ({len(commands)}): {[c.name for c in commands]}")
    
    # Iterate over guilds if needed, but 'info' seems global in main.py
    for guild in client.guilds:
        try:
             guild_commands = await tree.fetch_commands(guild=guild)
             logger.info(f"Remote Guild Commands for {guild.name} ({len(guild_commands)}): {[c.name for c in guild_commands]}")
        except Exception as e:
            logger.warning(f"Could not fetch commands for guild {guild.name}: {e}")

    # Prompt for action
    print("\nOptions:")
    print("1. Sync Global Commands (clears guild commands if they conflict globally? No, but typically we sync global)")
    print("2. Clear All Global Commands (Dangerous)")
    print("3. Exit")
    
    try:
        choice = await asyncio.to_thread(input, "Enter choice: ")
        if choice == '1':
            logger.info("Syncing global commands...")
            # Note: This script doesn't have the commands registered locally, so syncing expects an empty tree!
            # If we want to sync the ACTUAL commands, we'd need to import them here.
            # But wait, the user's main.py HAS the commands. 
            # This script is mostly to INSPECT what is currently there.
            # actually, if we want to FIX it, we arguably want to run main.py.
            # But let's just inspect first.
            print("To sync commands, please run 'main.py'. This script is for inspection only to avoid circular imports.")
            
        elif choice == '2':
            logger.info("Clearing all global commands...")
            # tree.clear_commands(guild=None) 
            # await tree.sync()
            print("Clear logic commented out for safety. If you really want this, uncomment in code.")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    
    await client.close()

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
