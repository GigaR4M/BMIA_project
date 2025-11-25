# commands/games_commands.py - Comandos Slash de Jogos/Atividades

import discord
from discord import app_commands
from database import Database
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class GamesCommands(app_commands.Group):
    """Grupo de comandos de jogos e atividades."""
    
    def __init__(self, db: Database):
        super().__init__(name="games", description="Estatísticas de jogos e atividades")
        self.db = db
    
    def format_duration(self, seconds: int) -> str:
        """Formata segundos em string legível."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}min"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}min"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"
    
    @app_commands.command(name="top", description="Jogos mais jogados no servidor")
    @app_commands.describe(
        limit="Número de jogos para mostrar (padrão: 10)",
        days="Período em dias (padrão: 30)"
    )
    async def top_games(self, interaction: discord.Interaction, 
                       limit: int = 10, days: int = 30):
        """Mostra os jogos mais jogados no servidor."""
        await interaction.response.defer()
        
        try:
            # Limita valores
            limit = max(1, min(limit, 25))
            days = max(1, min(days, 365))
            
            # Busca atividades
            activities = await self.db.get_top_activities(
                interaction.guild.id,
                limit,
                days
            )
            
            if not activities:
                await interaction.followup.send(
                    f"📊 Nenhuma atividade registrada nos últimos {days} dias."
                )
                return
            
            embed = discord.Embed(
                title="🎮 Jogos Mais Jogados",
                description=f"Top {len(activities)} jogos dos últimos {days} dias",
                color=discord.Color.purple()
            )
            
            for i, activity in enumerate(activities, 1):
                total_hours = activity['total_seconds'] // 3600
                avg_duration = self.format_duration(int(activity['avg_seconds']))
                
                embed.add_field(
                    name=f"{i}. {activity['activity_name']}",
                    value=(
                        f"⏱️ **{total_hours}h** jogadas\n"
                        f"👥 **{activity['unique_users']}** jogador(es)\n"
                        f"📊 **{activity['session_count']}** sessões\n"
                        f"⌛ Média: {avg_duration}"
                    ),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar top jogos: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar estatísticas. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="user", description="Jogos de um usuário específico")
    @app_commands.describe(
        usuario="Usuário para ver jogos (deixe vazio para ver os seus)",
        days="Período em dias (padrão: 30)"
    )
    async def user_games(self, interaction: discord.Interaction, 
                        usuario: discord.Member = None, days: int = 30):
        """Mostra os jogos de um usuário específico."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            target = usuario or interaction.user
            days = max(1, min(days, 365))
            
            # Busca atividades do usuário
            activities = await self.db.get_user_activities(
                target.id,
                interaction.guild.id,
                days
            )
            
            if not activities:
                await interaction.followup.send(
                    f"📊 {target.display_name} não tem atividades registradas nos últimos {days} dias.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🎮 Jogos de {target.display_name}",
                description=f"Atividades dos últimos {days} dias",
                color=discord.Color.blue()
            )
            
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)
            
            # Calcula total
            total_seconds = sum(a['total_seconds'] for a in activities)
            total_hours = total_seconds // 3600
            
            embed.add_field(
                name="⏱️ Tempo Total",
                value=f"**{total_hours}h** jogadas",
                inline=True
            )
            
            embed.add_field(
                name="🎮 Jogos Diferentes",
                value=f"**{len(activities)}** jogos",
                inline=True
            )
            
            # Top 10 jogos do usuário
            for i, activity in enumerate(activities[:10], 1):
                hours = activity['total_seconds'] // 3600
                avg_duration = self.format_duration(int(activity['avg_seconds']))
                
                embed.add_field(
                    name=f"{i}. {activity['activity_name']}",
                    value=(
                        f"⏱️ {hours}h | "
                        f"📊 {activity['session_count']} sessões | "
                        f"⌛ Média: {avg_duration}"
                    ),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar jogos do usuário: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar estatísticas. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="yearly", description="Retrospectiva anual de jogos")
    @app_commands.describe(year="Ano para retrospectiva (padrão: ano atual)")
    async def yearly_recap(self, interaction: discord.Interaction, year: int = None):
        """Mostra retrospectiva anual de jogos do servidor."""
        await interaction.response.defer()
        
        try:
            if year is None:
                year = datetime.now().year
            
            # Valida ano
            current_year = datetime.now().year
            if year < 2020 or year > current_year:
                await interaction.followup.send(
                    f"❌ Ano inválido! Use um ano entre 2020 e {current_year}.",
                    ephemeral=True
                )
                return
            
            # Busca atividades do ano
            activities = await self.db.get_yearly_activities(
                interaction.guild.id,
                year
            )
            
            if not activities:
                await interaction.followup.send(
                    f"📊 Nenhuma atividade registrada em {year}."
                )
                return
            
            # Agrupa por jogo
            games_data = {}
            for activity in activities:
                name = activity['activity_name']
                if name not in games_data:
                    games_data[name] = {
                        'total_seconds': 0,
                        'unique_users': set(),
                        'session_count': 0,
                        'months': set()
                    }
                
                games_data[name]['total_seconds'] += activity['total_seconds']
                games_data[name]['unique_users'].add(activity['unique_users'])
                games_data[name]['session_count'] += activity['session_count']
                games_data[name]['months'].add(activity['month'])
            
            # Ordena por tempo total
            sorted_games = sorted(
                games_data.items(),
                key=lambda x: x[1]['total_seconds'],
                reverse=True
            )
            
            embed = discord.Embed(
                title=f"🎮 Retrospectiva {year}",
                description=f"Jogos mais jogados em {interaction.guild.name}",
                color=discord.Color.gold()
            )
            
            # Estatísticas gerais
            total_games = len(sorted_games)
            total_hours = sum(g[1]['total_seconds'] for g in sorted_games) // 3600
            
            embed.add_field(
                name="📊 Resumo do Ano",
                value=(
                    f"🎮 **{total_games}** jogos diferentes\n"
                    f"⏱️ **{total_hours}h** jogadas no total"
                ),
                inline=False
            )
            
            # Top 10 jogos do ano
            for i, (name, data) in enumerate(sorted_games[:10], 1):
                hours = data['total_seconds'] // 3600
                months_played = len(data['months'])
                
                # Emoji de medalha
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                embed.add_field(
                    name=f"{medal} {name}",
                    value=(
                        f"⏱️ **{hours}h** jogadas\n"
                        f"📊 {data['session_count']} sessões\n"
                        f"📅 Jogado em {months_played} mês(es)"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"Retrospectiva de {year} • {interaction.guild.name}")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar retrospectiva: {e}")
            await interaction.followup.send(
                "❌ Erro ao gerar retrospectiva. Tente novamente.",
                ephemeral=True
            )
    
    @app_commands.command(name="stats", description="Estatísticas gerais de atividades")
    async def activity_stats(self, interaction: discord.Interaction):
        """Mostra estatísticas gerais de atividades do servidor."""
        await interaction.response.defer()
        
        try:
            # Busca top atividades de todos os tempos (último ano)
            activities = await self.db.get_top_activities(
                interaction.guild.id,
                limit=5,
                days=365
            )
            
            if not activities:
                await interaction.followup.send(
                    "📊 Nenhuma atividade registrada ainda."
                )
                return
            
            embed = discord.Embed(
                title="📊 Estatísticas de Atividades",
                description=f"Resumo do último ano em {interaction.guild.name}",
                color=discord.Color.green()
            )
            
            # Calcula totais
            total_seconds = sum(a['total_seconds'] for a in activities)
            total_hours = total_seconds // 3600
            total_sessions = sum(a['session_count'] for a in activities)
            
            embed.add_field(
                name="⏱️ Tempo Total",
                value=f"**{total_hours}h**",
                inline=True
            )
            
            embed.add_field(
                name="📊 Total de Sessões",
                value=f"**{total_sessions}**",
                inline=True
            )
            
            embed.add_field(
                name="🎮 Jogos Rastreados",
                value=f"**{len(activities)}** (top 5)",
                inline=True
            )
            
            # Top 5
            for i, activity in enumerate(activities, 1):
                hours = activity['total_seconds'] // 3600
                embed.add_field(
                    name=f"{i}. {activity['activity_name']}",
                    value=f"⏱️ {hours}h | 👥 {activity['unique_users']} jogador(es)",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar estatísticas: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar estatísticas. Tente novamente.",
                ephemeral=True
            )
