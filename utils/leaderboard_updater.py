# utils/leaderboard_updater.py
import discord
import asyncio
import logging
from datetime import datetime
from database import Database
from utils.embed_builder import StatsEmbedBuilder

logger = logging.getLogger(__name__)

class LeaderboardUpdater:
    def __init__(self, client: discord.Client, db: Database):
        self.client = client
        self.db = db
        self.embed_builder = StatsEmbedBuilder()
        self.interval = 900  # 15 minutes

    async def start_loop(self):
        """Inicia o loop de atualização do leaderboard."""
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                await self.update_all()
            except Exception as e:
                logger.error(f"❌ Erro no loop de atualização do leaderboard: {e}")
            
            await asyncio.sleep(self.interval)

    async def update_all(self):
        """Atualiza todos os leaderboards configurados."""
        configs = await self.db.get_leaderboard_configs()
        for config in configs:
            try:
                await self.update_guild(config)
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar leaderboard para guild {config['guild_id']}: {e}")

    async def update_guild(self, config):
        """Atualiza o leaderboard de um servidor específico."""
        guild_id = config['guild_id']
        channel_id = config['channel_id']
        message_id = config['message_id']

        guild = self.client.get_guild(guild_id)
        if not guild:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            # Mensagem foi deletada, remover config
            await self.db.delete_leaderboard_config(guild_id)
            return
        except discord.Forbidden:
            logger.warning(f"Sem permissão para ler mensagem no canal {channel.name}")
            return

        # Calcular dias desde o inicio do ano
        now = datetime.now()
        start_of_year = datetime(now.year, 1, 1)
        days = (now - start_of_year).days + 1

        # Buscar dados atuais
        leaderboard = await self.db.get_leaderboard(limit=10, days=days, guild_id=guild_id)
        new_embed = self.embed_builder.build_leaderboard(leaderboard) # Assumes default title logic if not passed? 
        # Actually build_leaderboard might need title adjustment or verification.
        # Let's check embed_builder.py content first? I haven't read it.
        # But based on stats_commands.py: embed = self.embed_builder.build_leaderboard(leaderboard)
        
        # Comparar conteúdo para evitar edições desnecessárias
        if message.embeds:
            current_embed = message.embeds[0]
            if self._is_content_equal(current_embed, new_embed):
                return

        await message.edit(embed=new_embed)
        # Update last_updated timestamp in DB if we wanted to track it strictly, 
        # but the table updates automatically on upsert. Here we are just editing.
        # Maybe we should touch the DB record to show it's active? Not strictly necessary.

    def _is_content_equal(self, embed1: discord.Embed, embed2: discord.Embed) -> bool:
        """Compara dois embeds simplificadamente."""
        return (
            embed1.title == embed2.title and
            embed1.description == embed2.description and
            len(embed1.fields) == len(embed2.fields) and
            all(f1.name == f2.name and f1.value == f2.value for f1, f2 in zip(embed1.fields, embed2.fields))
        )
