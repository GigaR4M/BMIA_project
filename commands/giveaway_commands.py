# commands/giveaway_commands.py - Comandos Slash de Sorteios

import discord
from discord import app_commands
from database import Database
from utils.giveaway_manager import GiveawayManager
import logging
from datetime import datetime
from config import now_brt


logger = logging.getLogger(__name__)


class GiveawayCommands(app_commands.Group):
    """Grupo de comandos de sorteios."""
    
    def __init__(self, db: Database, giveaway_manager: GiveawayManager):
        super().__init__(name="giveaway", description="Gerenciar sorteios no servidor")
        self.db = db
        self.giveaway_manager = giveaway_manager
    
    @app_commands.command(name="create", description="Cria um novo sorteio")
    @app_commands.describe(
        premio="O que será sorteado",
        duracao="Duração do sorteio (ex: 1h, 30m, 2d, 1w)",
        vencedores="Número de vencedores (padrão: 1)",
        imagem="Imagem opcional para o sorteio"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_giveaway(self, interaction: discord.Interaction, 
                             premio: str, duracao: str, vencedores: int = 1,
                             imagem: discord.Attachment = None):
        """Cria um novo sorteio."""
        await interaction.response.defer()
        
        try:
            # Valida número de vencedores
            if vencedores < 1 or vencedores > 20:
                await interaction.followup.send(
                    "❌ O número de vencedores deve estar entre 1 e 20!",
                    ephemeral=True
                )
                return
            
            # Parse duração
            duration_td = self.giveaway_manager.parse_duration(duracao)
            
            if not duration_td:
                await interaction.followup.send(
                    "❌ Formato de duração inválido! Use: `1h`, `30m`, `2d`, `1w`",
                    ephemeral=True
                )
                return
            
            # Cria sorteio
            image_url = imagem.url if imagem else None
            
            giveaway_id = await self.giveaway_manager.create_giveaway(
                channel=interaction.channel,
                prize=premio,
                duration=duration_td,
                winner_count=vencedores,
                host=interaction.user,
                image_url=image_url
            )
            
            if giveaway_id:
                await interaction.followup.send(
                    f"✅ Sorteio criado com sucesso! 🎉",
                    ephemeral=True
                )
                logger.info(f"✅ Sorteio criado por {interaction.user.name}: {premio}")
            else:
                await interaction.followup.send(
                    "❌ Erro ao criar sorteio. Tente novamente.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar sorteio: {e}")
            await interaction.followup.send(
                "❌ Erro ao criar sorteio. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="end", description="Finaliza um sorteio manualmente")
    @app_commands.describe(message_id="ID da mensagem do sorteio")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def end_giveaway(self, interaction: discord.Interaction, message_id: str):
        """Finaliza um sorteio manualmente."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Converte para int
            try:
                msg_id = int(message_id)
            except ValueError:
                await interaction.followup.send(
                    "❌ ID de mensagem inválido!",
                    ephemeral=True
                )
                return
            
            # Busca sorteio
            giveaway = await self.db.get_giveaway_by_message(msg_id)
            
            if not giveaway:
                await interaction.followup.send(
                    "❌ Sorteio não encontrado!",
                    ephemeral=True
                )
                return
            
            if giveaway['ended']:
                await interaction.followup.send(
                    "❌ Este sorteio já foi finalizado!",
                    ephemeral=True
                )
                return
            
            # Finaliza sorteio
            winners = await self.giveaway_manager.end_giveaway(
                giveaway['giveaway_id'],
                interaction.client
            )
            
            if winners:
                await interaction.followup.send(
                    f"✅ Sorteio finalizado! {len(winners)} vencedor(es) selecionado(s).",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "✅ Sorteio finalizado, mas não havia participantes.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar sorteio: {e}")
            await interaction.followup.send(
                "❌ Erro ao finalizar sorteio. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="reroll", description="Sorteia novos vencedores")
    @app_commands.describe(
        message_id="ID da mensagem do sorteio",
        quantidade="Número de novos vencedores (padrão: 1)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reroll_giveaway(self, interaction: discord.Interaction, 
                             message_id: str, quantidade: int = 1):
        """Sorteia novos vencedores para um sorteio já finalizado."""
        await interaction.response.defer()
        
        try:
            # Converte para int
            try:
                msg_id = int(message_id)
            except ValueError:
                await interaction.followup.send(
                    "❌ ID de mensagem inválido!",
                    ephemeral=True
                )
                return
            
            # Busca sorteio
            giveaway = await self.db.get_giveaway_by_message(msg_id)
            
            if not giveaway:
                await interaction.followup.send(
                    "❌ Sorteio não encontrado!",
                    ephemeral=True
                )
                return
            
            if not giveaway['ended']:
                await interaction.followup.send(
                    "❌ Este sorteio ainda não foi finalizado! Use `/giveaway end` primeiro.",
                    ephemeral=True
                )
                return
            
            # Busca participantes
            entry_ids = await self.db.get_giveaway_entries(giveaway['giveaway_id'])
            
            if not entry_ids:
                await interaction.followup.send(
                    "❌ Este sorteio não teve participantes!",
                    ephemeral=True
                )
                return
            
            # Valida quantidade
            if quantidade < 1 or quantidade > len(entry_ids):
                await interaction.followup.send(
                    f"❌ Quantidade inválida! Deve estar entre 1 e {len(entry_ids)}.",
                    ephemeral=True
                )
                return
            
            # Seleciona novos vencedores
            import random
            winner_ids = random.sample(entry_ids, quantidade)
            
            winners = []
            for user_id in winner_ids:
                member = interaction.guild.get_member(user_id)
                if member:
                    winners.append(member)
            
            if winners:
                winner_mentions = ", ".join([w.mention for w in winners])
                await interaction.followup.send(
                    f"🎊 Novo(s) vencedor(es) do sorteio **{giveaway['prize']}**: {winner_mentions}!"
                )
            else:
                await interaction.followup.send(
                    "❌ Não foi possível encontrar os membros vencedores.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"❌ Erro ao re-sortear: {e}")
            await interaction.followup.send(
                "❌ Erro ao sortear novos vencedores. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="list", description="Lista todos os sorteios ativos")
    async def list_giveaways(self, interaction: discord.Interaction):
        """Lista todos os sorteios ativos do servidor."""
        await interaction.response.defer()
        
        try:
            giveaways = await self.db.get_active_giveaways(interaction.guild.id)
            
            if not giveaways:
                await interaction.followup.send(
                    "📋 Não há sorteios ativos no momento."
                )
                return
            
            embed = discord.Embed(
                title="🎉 Sorteios Ativos",
                description=f"Total: {len(giveaways)} sorteio(s)",
                color=discord.Color.gold()
            )
            
            for giveaway in giveaways:
                channel = interaction.guild.get_channel(giveaway['channel_id'])
                channel_mention = channel.mention if channel else "Canal desconhecido"
                
                entry_count = await self.db.get_giveaway_entry_count(giveaway['giveaway_id'])
                
                time_left = giveaway['ends_at'] - now_brt()

                time_str = self.giveaway_manager.format_duration(time_left)
                
                embed.add_field(
                    name=f"🎁 {giveaway['prize']}",
                    value=(
                        f"**Canal:** {channel_mention}\n"
                        f"**Termina em:** {time_str}\n"
                        f"**Participantes:** {entry_count}\n"
                        f"**Message ID:** `{giveaway['message_id']}`"
                    ),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar sorteios: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar sorteios. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="delete", description="Cancela e deleta um sorteio")
    @app_commands.describe(message_id="ID da mensagem do sorteio")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def delete_giveaway(self, interaction: discord.Interaction, message_id: str):
        """Cancela e deleta um sorteio."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Converte para int
            try:
                msg_id = int(message_id)
            except ValueError:
                await interaction.followup.send(
                    "❌ ID de mensagem inválido!",
                    ephemeral=True
                )
                return
            
            # Busca sorteio
            giveaway = await self.db.get_giveaway_by_message(msg_id)
            
            if not giveaway:
                await interaction.followup.send(
                    "❌ Sorteio não encontrado!",
                    ephemeral=True
                )
                return
            
            # Deleta do banco de dados
            await self.db.delete_giveaway(giveaway['giveaway_id'])
            
            # Tenta deletar a mensagem
            try:
                channel = interaction.guild.get_channel(giveaway['channel_id'])
                if channel:
                    message = await channel.fetch_message(msg_id)
                    await message.delete()
            except:
                pass  # Ignora se não conseguir deletar a mensagem
            
            await interaction.followup.send(
                "✅ Sorteio cancelado e deletado!",
                ephemeral=True
            )
            
            logger.info(f"✅ Sorteio deletado: {giveaway['prize']}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao deletar sorteio: {e}")
            await interaction.followup.send(
                "❌ Erro ao deletar sorteio. Tente novamente.",
                ephemeral=True
            )
    
    # Error handlers
    @create_giveaway.error
    @end_giveaway.error
    @reroll_giveaway.error
    @delete_giveaway.error
    async def giveaway_command_error(self, interaction: discord.Interaction, 
                                    error: app_commands.AppCommandError):
        """Handler de erro para comandos que requerem permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
