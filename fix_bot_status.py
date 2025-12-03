import asyncio
import discord
import os
from dotenv import load_dotenv
from database import Database
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente
load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')

class BotStatusFixer(discord.Client):
    def __init__(self, db: Database):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.db = db

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.fix_bot_status()
        await self.close()

    async def fix_bot_status(self):
        logger.info("Starting bot status fix...")
        
        try:
            # Conecta ao banco
            await self.db.connect()
            
            # Busca todos os usuários do banco
            async with self.db.pool.acquire() as conn:
                users = await conn.fetch("SELECT user_id, username FROM users")
                logger.info(f"Found {len(users)} users in database.")
                
                updated_count = 0
                bot_count = 0
                
                for user_row in users:
                    user_id = user_row['user_id']
                    username = user_row['username']
                    
                    try:
                        # Tenta buscar o usuário no Discord
                        user = await self.fetch_user(user_id)
                        is_bot = user.bot
                        
                        if is_bot:
                            bot_count += 1
                            logger.info(f"🤖 Bot found: {username} ({user_id})")
                        
                        # Atualiza o status no banco
                        await self.db.upsert_user(
                            user_id=user_id,
                            username=user.name,
                            discriminator=user.discriminator,
                            is_bot=is_bot
                        )
                        updated_count += 1
                        
                        if updated_count % 10 == 0:
                            logger.info(f"Processed {updated_count}/{len(users)} users...")
                            
                    except discord.NotFound:
                        logger.warning(f"User {username} ({user_id}) not found in Discord.")
                    except Exception as e:
                        logger.error(f"Error processing user {username} ({user_id}): {e}")
                
                logger.info(f"Finished! Processed {updated_count} users. Found {bot_count} bots.")
                
        except Exception as e:
            logger.error(f"Critical error: {e}")
        finally:
            await self.db.disconnect()

async def main():
    if not DISCORD_TOKEN or not DATABASE_URL:
        logger.error("Missing DISCORD_TOKEN or DATABASE_URL in .env")
        return

    db = Database(DATABASE_URL)
    client = BotStatusFixer(db)
    await client.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
