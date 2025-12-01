import discord
import os
import asyncio
import logging
from dotenv import load_dotenv
from database import Database

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

class FixUnknownUsersClient(discord.Client):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.fix_users()
        await self.close()

    async def fix_users(self):
        print("Starting to fix unknown users...")
        try:
            # Conecta ao banco de dados
            await self.db.connect()
            
            # Busca usuários com nome 'Unknown'
            async with self.db.pool.acquire() as conn:
                unknown_users = await conn.fetch("""
                    SELECT user_id FROM users WHERE username = 'Unknown'
                """)
                
            print(f"Found {len(unknown_users)} users with 'Unknown' username.")
            
            count = 0
            for row in unknown_users:
                user_id = row['user_id']
                try:
                    user = await self.fetch_user(user_id)
                    if user:
                        await self.db.upsert_user(user.id, user.name, user.discriminator)
                        print(f"Fixed user {user_id}: {user.name}#{user.discriminator}")
                        count += 1
                    else:
                        print(f"User {user_id} not found via API.")
                except discord.NotFound:
                    print(f"User {user_id} not found (404).")
                except Exception as e:
                    print(f"Error fetching user {user_id}: {e}")
                
                # Avoid rate limits
                await asyncio.sleep(0.5)
                
            print(f"Finished! Fixed {count} users.")
            
        except Exception as e:
            print(f"Error during fix process: {e}")
        finally:
            await self.db.disconnect()

async def main():
    if not DISCORD_TOKEN or not DATABASE_URL:
        print("Error: DISCORD_TOKEN or DATABASE_URL not found in environment variables.")
        return

    db = Database(DATABASE_URL)
    
    intents = discord.Intents.default()
    intents.members = True 
    
    client = FixUnknownUsersClient(db, intents=intents)
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
