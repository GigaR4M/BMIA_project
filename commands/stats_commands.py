# commands/stats_commands.py - Comandos Slash de Estatísticas

import discord
from discord import app_commands
from database import Database
from utils.embed_builder import StatsEmbedBuilder
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class StatsCommands(app_commands.Group):
    """Grupo de comandos de estatísticas."""
    
    
    def __init__(self, db: Database, leaderboard_updater: Any = None):
        super().__init__(name="stats", description="Comandos de estatísticas do servidor")
        self.db = db
        self.leaderboard_updater = leaderboard_updater
        self.embed_builder = StatsEmbedBuilder()
    
    @app_commands.command(name="setup_leaderboard", description="Configura um leaderboard persistente neste canal")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_leaderboard(self, interaction: discord.Interaction):
        """Cria e fixa uma mensagem de leaderboard que se atualiza automaticamente."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Envia mensagem inicial
            embed = discord.Embed(
                title="📊 Leaderboard em Construção",
                description="O ranking será gerado em instantes...",
                color=discord.Color.gold()
            )
            message = await interaction.channel.send(embed=embed)
            
            # Tenta fixar (pin) a mensagem
            try:
                await message.pin(reason="Leaderboard de Pontos")
            except Exception:
                pass # Ignora se falhar pin (pode não ter permissão ou canal cheio)

            # Salva no banco
            await self.db.upsert_leaderboard_config(
                interaction.guild.id, 
                interaction.channel.id, 
                message.id
            )
            
            # Força atualização imediata se o updater estiver disponível
            if self.leaderboard_updater:
                config = {
                    'guild_id': interaction.guild.id,
                    'channel_id': interaction.channel.id,
                    'message_id': message.id
                }
                await self.leaderboard_updater.update_guild(config)
                
            await interaction.followup.send(
                f"✅ Leaderboard configurado com sucesso no canal {interaction.channel.mention}!",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Erro ao configurar leaderboard: {e}")
            await interaction.followup.send(
                "❌ Erro ao configurar leaderboard. Verifique minhas permissões.",
                ephemeral=True
            )
    
    @app_commands.command(name="server", description="Estatísticas gerais do servidor")
    @app_commands.describe(days="Número de dias para análise (padrão: 30)")
    async def server_stats(self, interaction: discord.Interaction, days: int = 30):
        """Mostra estatísticas gerais do servidor."""
        await interaction.response.defer()
        
        try:
            stats = await self.db.get_server_stats(interaction.guild.id, days)
            embed = self.embed_builder.build_server_stats(stats, interaction.guild.name)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do servidor: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar estatísticas. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @app_commands.command(name="me", description="Suas estatísticas pessoais e ficha de pontos")
    @app_commands.describe(days="Número de dias para análise (padrão: Ano Atual)")
    async def my_stats(self, interaction: discord.Interaction, days: Optional[int] = None):
        """Mostra estatísticas pessoais e auditoria de pontos."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Se days não for especificado, calcula dias desde o início do ano
            if days is None:
                from datetime import datetime
                now = datetime.now()
                start_of_year = datetime(now.year, 1, 1)
                days = (now - start_of_year).days + 1
            
            stats = await self.db.get_user_stats(
                interaction.user.id, 
                interaction.guild.id, 
                days
            )
            embed = self.embed_builder.build_user_stats(
                stats, 
                interaction.user.name,
                interaction.user.avatar.url if interaction.user.avatar else None
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do usuário: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar suas estatísticas. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @app_commands.command(name="user", description="Estatísticas de um usuário específico")
    @app_commands.describe(
        user="Usuário para ver estatísticas",
        days="Número de dias para análise (padrão: Ano Atual)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def user_stats(self, interaction: discord.Interaction, 
                        user: discord.Member, days: Optional[int] = None):
        """Mostra estatísticas de um usuário específico (apenas admins)."""
        await interaction.response.defer()
        
        try:
            if days is None:
                from datetime import datetime
                now = datetime.now()
                start_of_year = datetime(now.year, 1, 1)
                days = (now - start_of_year).days + 1

            stats = await self.db.get_user_stats(user.id, interaction.guild.id, days)
            embed = self.embed_builder.build_user_stats(
                stats, 
                user.name,
                user.avatar.url if user.avatar else None
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do usuário: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar estatísticas. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @app_commands.command(name="top", description="Top usuários mais ativos")
    @app_commands.describe(
        limit="Número de usuários para mostrar (padrão: 10)",
        days="Número de dias para análise (padrão: 30)"
    )
    async def top_users(self, interaction: discord.Interaction, 
                       limit: int = 10, days: int = 30):
        """Mostra os usuários mais ativos por mensagens."""
        await interaction.response.defer()
        
        try:
            # Limita entre 1 e 25
            limit = max(1, min(limit, 25))
            
            top_users = await self.db.get_top_users_by_messages(
                interaction.guild.id, 
                limit, 
                days
            )
            embed = self.embed_builder.build_top_users(top_users, days)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar top usuários: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar ranking. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @app_commands.command(name="channels", description="Canais mais ativos")
    @app_commands.describe(
        limit="Número de canais para mostrar (padrão: 10)",
        days="Número de dias para análise (padrão: 30)"
    )
    async def top_channels(self, interaction: discord.Interaction, 
                          limit: int = 10, days: int = 30):
        """Mostra os canais mais ativos."""
        await interaction.response.defer()
        
        try:
            # Limita entre 1 e 25
            limit = max(1, min(limit, 25))
            
            top_channels = await self.db.get_top_channels(
                interaction.guild.id, 
                limit, 
                days
            )
            embed = self.embed_builder.build_top_channels(top_channels, days)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar top canais: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar canais. Tente novamente mais tarde.",
                ephemeral=True
            )

    @app_commands.command(name="leaderboard", description="Mostra o ranking de pontos de interação")
    @app_commands.describe(
        limit="Número de usuários para mostrar (padrão: 10)",
        days="Número de dias para análise (padrão: Ano Atual)"
    )
    async def leaderboard(self, interaction: discord.Interaction, limit: int = 10, days: Optional[int] = None):
        """Mostra o leaderboard de pontos."""
        await interaction.response.defer()
        
        try:
            limit = max(1, min(limit, 25))
            
            # Se days não for especificado, calcula dias desde o início do ano
            if days is None:
                from datetime import datetime
                now = datetime.now()
                start_of_year = datetime(now.year, 1, 1)
                days = (now - start_of_year).days + 1
            
            leaderboard = await self.db.get_leaderboard(limit, days)
            embed = self.embed_builder.build_leaderboard(leaderboard)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar leaderboard: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar leaderboard. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @user_stats.error
    async def user_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handler de erro para comando que requer permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
