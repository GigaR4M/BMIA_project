# stats_collector.py - Módulo de Coleta de Estatísticas

import discord
from database import Database
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StatsCollector:
    """Coletor de estatísticas para eventos do Discord."""
    
    def __init__(self, db: Database):
        """
        Inicializa o coletor de estatísticas.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
        self.cache = {}  # Cache para reduzir writes no banco
    
    async def on_message(self, message: discord.Message, was_moderated: bool = False):
        """
        Coleta dados de uma mensagem.
        
        Args:
            message: Mensagem do Discord
            was_moderated: Se a mensagem foi moderada/removida
        """
        # Ignora mensagens de bots
        if message.author.bot:
            try:
                await self.db.upsert_user(
                    user_id=message.author.id,
                    username=message.author.name,
                    discriminator=message.author.discriminator,
                    is_bot=True
                )
            except Exception as e:
                logger.error(f"❌ Erro ao registrar bot {message.author.name}: {e}")
            return
        
        # Ignora mensagens sem guild (DMs)
        if not message.guild:
            return
        
        try:
            # Atualiza usuário
            await self.db.upsert_user(
                user_id=message.author.id,
                username=message.author.name,
                discriminator=message.author.discriminator,
                is_bot=False
            )
            
            # Atualiza canal
            await self.db.upsert_channel(
                channel_id=message.channel.id,
                channel_name=message.channel.name,
                channel_type=str(message.channel.type),
                guild_id=message.guild.id
            )
            
            # Registra mensagem
            await self.db.insert_message(
                message_id=message.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
                guild_id=message.guild.id,
                content_length=len(message.content),
                has_attachments=len(message.attachments) > 0,
                has_embeds=len(message.embeds) > 0,
                was_moderated=was_moderated
            )
            
            logger.debug(f"📊 Estatísticas coletadas: mensagem de {message.author.name}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar estatísticas de mensagem: {e}")
    
    async def on_voice_state_update(self, member: discord.Member, 
                                    before: discord.VoiceState, 
                                    after: discord.VoiceState):
        """
        Coleta dados de atividade de voz.
        
        Args:
            member: Membro do Discord
            before: Estado de voz anterior
            after: Estado de voz atual
        """
        # Ignora bots
        if member.bot:
            try:
                await self.db.upsert_user(
                    user_id=member.id,
                    username=member.name,
                    discriminator=member.discriminator,
                    is_bot=True
                )
            except Exception as e:
                logger.error(f"❌ Erro ao registrar bot de voz {member.name}: {e}")
            return
        
        try:
            # Atualiza usuário
            await self.db.upsert_user(
                user_id=member.id,
                username=member.name,
                discriminator=member.discriminator,
                is_bot=False
            )
            
            # Usuário entrou em um canal de voz
            if before.channel is None and after.channel is not None:
                await self.db.upsert_channel(
                    channel_id=after.channel.id,
                    channel_name=after.channel.name,
                    channel_type="voice",
                    guild_id=after.channel.guild.id
                )
                
                await self.db.insert_voice_join(
                    user_id=member.id,
                    channel_id=after.channel.id,
                    guild_id=after.channel.guild.id
                )
                
                logger.debug(f"🎤 {member.name} entrou no canal de voz {after.channel.name}")
            
            # Usuário saiu de um canal de voz
            elif before.channel is not None and after.channel is None:
                await self.db.update_voice_leave(
                    user_id=member.id,
                    channel_id=before.channel.id
                )
                
                logger.debug(f"🎤 {member.name} saiu do canal de voz {before.channel.name}")
            
            # Usuário mudou de canal (sai de um e entra em outro)
            elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
                # Registra saída do canal anterior
                await self.db.update_voice_leave(
                    user_id=member.id,
                    channel_id=before.channel.id
                )
                
                # Registra entrada no novo canal
                await self.db.upsert_channel(
                    channel_id=after.channel.id,
                    channel_name=after.channel.name,
                    channel_type="voice",
                    guild_id=after.channel.guild.id
                )
                
                await self.db.insert_voice_join(
                    user_id=member.id,
                    channel_id=after.channel.id,
                    guild_id=after.channel.guild.id
                )
                
                logger.debug(f"🎤 {member.name} mudou de {before.channel.name} para {after.channel.name}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao coletar estatísticas de voz: {e}")
    
    async def mark_message_as_moderated(self, message_id: int):
        """
        Marca uma mensagem como moderada no banco de dados.
        
        Args:
            message_id: ID da mensagem que foi moderada
        """
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE messages 
                    SET was_moderated = TRUE 
                    WHERE message_id = $1
                """, message_id)
                
            logger.debug(f"🚫 Mensagem {message_id} marcada como moderada")
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar mensagem como moderada: {e}")
