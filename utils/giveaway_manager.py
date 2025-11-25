# utils/giveaway_manager.py - Gerenciador de Sorteios

import discord
from database import Database
from datetime import datetime, timedelta
import logging
import random
from typing import Optional, List

logger = logging.getLogger(__name__)


class GiveawayManager:
    """Gerenciador de sorteios (giveaways) para o servidor."""
    
    def __init__(self, db: Database):
        """
        Inicializa o gerenciador de sorteios.
        
        Args:
            db: Instância do gerenciador de banco de dados
        """
        self.db = db
        self.GIVEAWAY_EMOJI = "🎉"
    
    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """
        Converte string de duração para timedelta.
        Formatos aceitos: 1h, 30m, 2d, 1w
        
        Args:
            duration_str: String de duração (ex: "1h", "30m", "2d")
            
        Returns:
            timedelta ou None se inválido
        """
        try:
            duration_str = duration_str.lower().strip()
            
            if duration_str.endswith('m'):
                minutes = int(duration_str[:-1])
                return timedelta(minutes=minutes)
            elif duration_str.endswith('h'):
                hours = int(duration_str[:-1])
                return timedelta(hours=hours)
            elif duration_str.endswith('d'):
                days = int(duration_str[:-1])
                return timedelta(days=days)
            elif duration_str.endswith('w'):
                weeks = int(duration_str[:-1])
                return timedelta(weeks=weeks)
            else:
                return None
                
        except ValueError:
            return None
    
    def format_duration(self, td: timedelta) -> str:
        """
        Formata timedelta para string legível.
        
        Args:
            td: timedelta para formatar
            
        Returns:
            String formatada (ex: "2 dias, 3 horas")
        """
        total_seconds = int(td.total_seconds())
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} dia{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
        
        return ", ".join(parts) if parts else "menos de 1 minuto"
    
    def create_giveaway_embed(self, prize: str, ends_at: datetime, 
                             host: discord.Member, entry_count: int = 0) -> discord.Embed:
        """
        Cria embed para mensagem de sorteio.
        
        Args:
            prize: Prêmio do sorteio
            ends_at: Data/hora de término
            host: Quem criou o sorteio
            entry_count: Número de participantes
            
        Returns:
            Embed do Discord
        """
        embed = discord.Embed(
            title="🎉 SORTEIO! 🎉",
            description=f"**Prêmio:** {prize}",
            color=discord.Color.gold(),
            timestamp=ends_at
        )
        
        time_remaining = ends_at - datetime.now()
        embed.add_field(
            name="⏰ Termina em",
            value=self.format_duration(time_remaining),
            inline=True
        )
        
        embed.add_field(
            name="👥 Participantes",
            value=str(entry_count),
            inline=True
        )
        
        embed.add_field(
            name="📝 Como Participar",
            value=f"Reaja com {self.GIVEAWAY_EMOJI} para participar!",
            inline=False
        )
        
        embed.set_footer(
            text=f"Criado por {host.display_name}",
            icon_url=host.avatar.url if host.avatar else None
        )
        
        return embed
    
    async def create_giveaway(self, channel: discord.TextChannel, prize: str,
                             duration: timedelta, winner_count: int,
                             host: discord.Member) -> Optional[int]:
        """
        Cria um novo sorteio.
        
        Args:
            channel: Canal onde criar o sorteio
            prize: Prêmio do sorteio
            duration: Duração do sorteio
            winner_count: Número de vencedores
            host: Quem está criando o sorteio
            
        Returns:
            ID do sorteio criado ou None se falhar
        """
        try:
            ends_at = datetime.now() + duration
            
            # Cria embed
            embed = self.create_giveaway_embed(prize, ends_at, host)
            
            # Envia mensagem
            message = await channel.send(embed=embed)
            
            # Adiciona reação
            await message.add_reaction(self.GIVEAWAY_EMOJI)
            
            # Salva no banco de dados
            giveaway_id = await self.db.create_giveaway(
                guild_id=channel.guild.id,
                channel_id=channel.id,
                message_id=message.id,
                prize=prize,
                winner_count=winner_count,
                host_user_id=host.id,
                ends_at=ends_at
            )
            
            logger.info(f"✅ Sorteio criado: {prize} (ID: {giveaway_id})")
            return giveaway_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar sorteio: {e}")
            return None
    
    async def end_giveaway(self, giveaway_id: int, client: discord.Client) -> List[discord.Member]:
        """
        Finaliza um sorteio e seleciona vencedores.
        
        Args:
            giveaway_id: ID do sorteio
            client: Cliente do Discord
            
        Returns:
            Lista de membros vencedores
        """
        try:
            # Busca informações do sorteio
            giveaway = await self.db.get_giveaway(giveaway_id)
            
            if not giveaway or giveaway['ended']:
                logger.warning(f"⚠️ Sorteio {giveaway_id} não encontrado ou já finalizado")
                return []
            
            # Busca participantes
            entry_ids = await self.db.get_giveaway_entries(giveaway_id)
            
            if not entry_ids:
                logger.warning(f"⚠️ Sorteio {giveaway_id} sem participantes")
                await self.db.end_giveaway(giveaway_id)
                return []
            
            # Seleciona vencedores
            winner_count = min(giveaway['winner_count'], len(entry_ids))
            winner_ids = random.sample(entry_ids, winner_count)
            
            # Busca objetos Member
            guild = client.get_guild(giveaway['guild_id'])
            if not guild:
                logger.error(f"❌ Servidor {giveaway['guild_id']} não encontrado")
                return []
            
            winners = []
            for user_id in winner_ids:
                member = guild.get_member(user_id)
                if member:
                    winners.append(member)
            
            # Marca como finalizado
            await self.db.end_giveaway(giveaway_id)
            
            # Atualiza mensagem
            try:
                channel = guild.get_channel(giveaway['channel_id'])
                if channel:
                    message = await channel.fetch_message(giveaway['message_id'])
                    
                    embed = discord.Embed(
                        title="🎉 SORTEIO FINALIZADO! 🎉",
                        description=f"**Prêmio:** {giveaway['prize']}",
                        color=discord.Color.red(),
                        timestamp=datetime.now()
                    )
                    
                    winner_mentions = ", ".join([w.mention for w in winners])
                    embed.add_field(
                        name="🏆 Vencedor(es)",
                        value=winner_mentions if winners else "Nenhum participante",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="👥 Total de Participantes",
                        value=str(len(entry_ids)),
                        inline=True
                    )
                    
                    await message.edit(embed=embed)
                    
                    # Anuncia vencedores
                    if winners:
                        await channel.send(
                            f"🎊 Parabéns {winner_mentions}! Você{'s' if len(winners) > 1 else ''} "
                            f"ganhou: **{giveaway['prize']}**!"
                        )
                        
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar mensagem do sorteio: {e}")
            
            logger.info(f"✅ Sorteio {giveaway_id} finalizado com {len(winners)} vencedor(es)")
            return winners
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar sorteio: {e}")
            return []
    
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """
        Handler para quando alguém adiciona reação em um sorteio.
        
        Args:
            reaction: Reação adicionada
            user: Usuário que adicionou a reação
        """
        # Ignora bots
        if user.bot:
            return
        
        # Verifica se é a reação correta
        if str(reaction.emoji) != self.GIVEAWAY_EMOJI:
            return
        
        try:
            # Verifica se a mensagem é um sorteio
            giveaway = await self.db.get_giveaway_by_message(reaction.message.id)
            
            if not giveaway or giveaway['ended']:
                return
            
            # Adiciona participante
            await self.db.add_giveaway_entry(giveaway['giveaway_id'], user.id)
            
            # Atualiza contagem no embed
            entry_count = await self.db.get_giveaway_entry_count(giveaway['giveaway_id'])
            
            host = reaction.message.guild.get_member(giveaway['host_user_id'])
            embed = self.create_giveaway_embed(
                giveaway['prize'],
                giveaway['ends_at'],
                host,
                entry_count
            )
            
            await reaction.message.edit(embed=embed)
            
            logger.debug(f"✅ {user.name} entrou no sorteio {giveaway['giveaway_id']}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar reação de sorteio: {e}")
    
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        """
        Handler para quando alguém remove reação de um sorteio.
        
        Args:
            reaction: Reação removida
            user: Usuário que removeu a reação
        """
        # Ignora bots
        if user.bot:
            return
        
        # Verifica se é a reação correta
        if str(reaction.emoji) != self.GIVEAWAY_EMOJI:
            return
        
        try:
            # Verifica se a mensagem é um sorteio
            giveaway = await self.db.get_giveaway_by_message(reaction.message.id)
            
            if not giveaway or giveaway['ended']:
                return
            
            # Remove participante
            await self.db.remove_giveaway_entry(giveaway['giveaway_id'], user.id)
            
            # Atualiza contagem no embed
            entry_count = await self.db.get_giveaway_entry_count(giveaway['giveaway_id'])
            
            host = reaction.message.guild.get_member(giveaway['host_user_id'])
            embed = self.create_giveaway_embed(
                giveaway['prize'],
                giveaway['ends_at'],
                host,
                entry_count
            )
            
            await reaction.message.edit(embed=embed)
            
            logger.debug(f"✅ {user.name} saiu do sorteio {giveaway['giveaway_id']}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar remoção de reação: {e}")
