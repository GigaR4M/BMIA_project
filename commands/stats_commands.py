# commands/stats_commands.py - Comandos Slash de Estatísticas e Níveis

import discord
from discord import app_commands
from database import Database
from utils.embed_builder import StatsEmbedBuilder
from typing import Optional, Any, List, Dict
import logging
from config import now_brt

logger = logging.getLogger(__name__)

HIGHLIGHTS_CATEGORIES = [
    {"id": "cover", "label": "Capa", "title": "DESTAQUES DO ANO", "subtitle": "Apresentação Oficial", "icon": "✨", "color": "#00f0ff"},
    {"id": "mvp", "label": "MVP", "title": "O MVP DO ANO", "subtitle": "Maior Acúmulo de XP e Pontos", "icon": "👑", "color": "#ffd700", "unit": "XP"},
    {"id": "tagarela", "label": "Tagarela", "title": "O TAGARELA", "subtitle": "Mais Mensagens de Texto Enviadas", "icon": "💬", "color": "#38bdf8", "unit": "msgs"},
    {"id": "rei_da_call", "label": "Rei da Call", "title": "REI DA CALL", "subtitle": "Maior Tempo Conectado em Canais de Voz", "icon": "🎙️", "color": "#a855f7", "is_time": True},
    {"id": "corujao", "label": "O Corujão", "title": "O CORUJÃO", "subtitle": "Mais Horas em Voz na Madrugada (01h-05h BRT)", "icon": "🦉", "color": "#6366f1", "is_time": True},
    {"id": "streamer", "label": "Streamer", "title": "STREAMER DO SERVIDOR", "subtitle": "Maior Tempo em Transmissão / Ao Vivo", "icon": "📺", "color": "#ec4899", "is_time": True},
    {"id": "top_gamers", "label": "Top Gamers", "title": "TOP GAMERS", "subtitle": "Maior Tempo Jogado no Ano", "icon": "🎮", "color": "#22c55e", "is_time": True},
    {"id": "jogo_do_ano", "label": "Jogo do Ano", "title": "JOGO DO ANO", "subtitle": "Jogos Mais Populares da Comunidade", "icon": "🕹️", "color": "#eab308", "is_time": True},
    {"id": "media", "label": "Clipe do Ano", "title": "CLIPE / PRINT DO ANO", "subtitle": "Momento Mais Popular da Comunidade", "icon": "📸", "color": "#f43f5e"},
    {"id": "outros_destaques", "label": "Outros Destaques", "title": "OUTROS DESTAQUES DO ANO", "subtitle": "Recordes e Menções Honrosas", "icon": "🌟", "color": "#8b5cf6"},
]


async def handle_highlights_gallery(db: Database, interaction: discord.Interaction, year: Optional[int] = None):
    """Renderiza e envia a Retrospectiva Anual como uma Galeria de Imagens de Alta Performance."""
    await interaction.response.defer(thinking=True)

    if year is None:
        year = now_brt().year

    try:
        from utils.highlights_scanner import HighlightsScanner
        from utils.image_generator import HighlightsBuilder

        top_clip = await HighlightsScanner.scan_guild_top_clip(interaction.guild, year, timeout=3.0)
        highlights_data = await db.get_annual_highlights_data(interaction.guild.id, year)

        files = await HighlightsBuilder.generate_all_slides_files(
            guild=interaction.guild,
            year=year,
            highlights_data=highlights_data,
            top_clip=top_clip,
            categories=HIGHLIGHTS_CATEGORIES
        )

        if not files:
            await interaction.followup.send("❌ Não foi possível gerar os slides da retrospectiva.", ephemeral=True)
            return

        await interaction.followup.send(
            content=f"🌟 **DESTAQUES DO ANO {year} • {interaction.guild.name}**\n*Navegue pelas fotos da galeria em tela cheia abaixo:*",
            files=files
        )

    except Exception as e:
        logger.error("❌ Erro ao gerar galeria de Destaques do Ano: %s", e, exc_info=True)
        await interaction.followup.send(
            "❌ Ocorreu um erro ao processar a Retrospectiva Anual. Tente novamente mais tarde.",
            ephemeral=True
        )


async def handle_rank_card(db: Database, interaction: discord.Interaction, membro: Optional[discord.Member] = None):
    """Gera e envia o Rank Card em imagem de alta fidelidade."""
    await interaction.response.defer()
    target = membro or interaction.user
    if target.bot:
        await interaction.followup.send("❌ Bots não possuem Rank Card ou progressão de níveis.", ephemeral=True)
        return

    try:
        from utils.level_manager import get_level_progress
        from utils.image_generator import RankCardBuilder

        total_xp = await db.get_user_current_total_points(target.id, interaction.guild.id)
        level_data = get_level_progress(total_xp)
        
        server_rank = await db.get_user_rank_position(target.id, interaction.guild.id)
        
        # Estatísticas de uso
        user_stats = await db.get_user_stats(target.id, interaction.guild.id, 365)
        total_msgs = user_stats.get('total_messages', 0)
        voice_mins = user_stats.get('voice_minutes', 0)

        builder = RankCardBuilder()
        img_buffer = await builder.generate_rank_card(
            member=target,
            level_data=level_data,
            server_rank=server_rank,
            messages_count=total_msgs,
            voice_minutes=voice_mins,
            guild_name=interaction.guild.name
        )

        file = discord.File(fp=img_buffer, filename=f"rank_{target.id}.png")
        await interaction.followup.send(file=file)
    except Exception as e:
        logger.error(f"Erro ao gerar Rank Card para {target.id}: {e}", exc_info=True)
        await interaction.followup.send("❌ Ocorreu um erro ao gerar o Rank Card. Tente novamente.", ephemeral=True)


class StatsCommands(app_commands.Group):
    """Grupo de comandos de estatísticas e XP."""
    
    def __init__(self, db: Database, leaderboard_updater: Any = None, points_manager: Any = None):
        super().__init__(name="stats", description="Comandos de estatísticas e XP do servidor")
        self.db = db
        self.leaderboard_updater = leaderboard_updater
        self.points_manager = points_manager
        self.embed_builder = StatsEmbedBuilder()

    @app_commands.command(name="rank", description="Exibe o Rank Card de XP e nível de um membro")
    @app_commands.describe(membro="Membro que deseja visualizar o Rank Card (opcional)")
    async def rank(self, interaction: discord.Interaction, membro: Optional[discord.Member] = None):
        await handle_rank_card(self.db, interaction, membro)

    async def _add_xp_logic(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        xp: int,
        motivo: Optional[str] = "Premiação Manual"
    ):
        await interaction.response.defer()
        if xp <= 0:
            await interaction.followup.send("❌ A quantidade de XP deve ser maior que zero.", ephemeral=True)
            return

        if membro.bot:
            await interaction.followup.send("❌ Não é possível conceder XP a bots.", ephemeral=True)
            return

        try:
            avatar_url = str(membro.display_avatar.url) if hasattr(membro, 'display_avatar') else None
            if self.points_manager:
                await self.points_manager.add_points(
                    membro.id,
                    xp,
                    "manual_reward",
                    interaction.guild.id,
                    membro.name,
                    membro.discriminator,
                    membro.bot,
                    avatar_url=avatar_url,
                    channel=interaction.channel
                )
            else:
                await self.db.upsert_user(membro.id, membro.name, membro.discriminator, membro.bot, avatar_url=avatar_url)
                await self.db.add_interaction_point(membro.id, xp, "manual_reward", interaction.guild.id)

            total = await self.db.get_user_current_total_points(membro.id, interaction.guild.id)
            embed = discord.Embed(
                title="✨ XP Adicionado com Sucesso!",
                description=f"🎉 **+{xp:,} XP** foram adicionados para {membro.mention}!\n\n"
                            f"📝 **Motivo:** {motivo}\n"
                            f"⚡ **Novo Total de XP:** `{total:,} XP`",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Operação realizada por {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao adicionar XP manual para {membro.id}: {e}")
            await interaction.followup.send("❌ Erro ao adicionar XP ao membro.", ephemeral=True)

    async def _remove_xp_logic(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        xp: int,
        motivo: Optional[str] = "Penalidade Manual"
    ):
        await interaction.response.defer()
        if xp <= 0:
            await interaction.followup.send("❌ A quantidade de XP deve ser maior que zero.", ephemeral=True)
            return

        try:
            if self.points_manager:
                await self.points_manager.remove_points(
                    membro.id,
                    xp,
                    interaction.guild.id,
                    reason=motivo
                )
            else:
                await self.db.add_interaction_point(membro.id, -xp, "penalty", interaction.guild.id)

            total = await self.db.get_user_current_total_points(membro.id, interaction.guild.id)
            embed = discord.Embed(
                title="⚠️ XP Removido",
                description=f"🔻 **-{xp:,} XP** foram removidos de {membro.mention}.\n\n"
                            f"📝 **Motivo:** {motivo}\n"
                            f"⚡ **Novo Total de XP:** `{total:,} XP`",
                color=discord.Color.orange()
            )
            embed.set_footer(text=f"Operação realizada por {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao remover XP de {membro.id}: {e}")
            await interaction.followup.send("❌ Erro ao remover XP do membro.", ephemeral=True)

    @app_commands.command(name="xp_adicionar", description="Adiciona XP manualmente a um membro (Apenas Administradores)")
    @app_commands.describe(
        membro="Membro que receberá o XP",
        xp="Quantidade de XP a adicionar",
        motivo="Motivo da premiação/adição (opcional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def xp_adicionar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        xp: int,
        motivo: Optional[str] = "Premiação Manual"
    ):
        await self._add_xp_logic(interaction, membro, xp, motivo)

    @app_commands.command(name="pontos_adicionar", description="[Alias] Adiciona XP/pontos a um membro (Apenas Administradores)")
    @app_commands.describe(
        membro="Membro que receberá os pontos/XP",
        pontos="Quantidade de pontos/XP a adicionar",
        motivo="Motivo da premiação/adição (opcional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def pontos_adicionar(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        pontos: int,
        motivo: Optional[str] = "Premiação Manual"
    ):
        await self._add_xp_logic(interaction, membro, pontos, motivo)

    @app_commands.command(name="xp_remover", description="Remove XP de um membro (Apenas Administradores)")
    @app_commands.describe(
        membro="Membro que terá o XP removido",
        xp="Quantidade de XP a remover",
        motivo="Motivo da remoção (opcional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def xp_remover(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        xp: int,
        motivo: Optional[str] = "Penalidade Manual"
    ):
        await self._remove_xp_logic(interaction, membro, xp, motivo)

    @app_commands.command(name="pontos_remover", description="[Alias] Remove pontos/XP de um membro (Apenas Administradores)")
    @app_commands.describe(
        membro="Membro que terá os pontos removidos",
        pontos="Quantidade de pontos a remover",
        motivo="Motivo da remoção (opcional)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def pontos_remover(
        self,
        interaction: discord.Interaction,
        membro: discord.Member,
        pontos: int,
        motivo: Optional[str] = "Penalidade Manual"
    ):
        await self._remove_xp_logic(interaction, membro, pontos, motivo)


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
                await message.pin(reason="Leaderboard de XP")
            except Exception:
                pass

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
    
    @app_commands.command(name="me", description="Suas estatísticas pessoais e ficha de XP/Nível")
    @app_commands.describe(days="Número de dias para análise (padrão: Ano Atual)")
    async def my_stats(self, interaction: discord.Interaction, days: Optional[int] = None):
        """Mostra estatísticas pessoais e auditoria de XP."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if days is None:
                now = now_brt()
                start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
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
                now = now_brt()
                start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
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
    
    @app_commands.command(name="top", description="Top usuários mais ativos por mensagens")
    @app_commands.describe(
        limit="Número de usuários para mostrar (padrão: 10)",
        days="Número de dias para análise (padrão: 30)"
    )
    async def top_users(self, interaction: discord.Interaction, 
                       limit: int = 10, days: int = 30):
        """Mostra os usuários mais ativos por mensagens."""
        await interaction.response.defer()
        
        try:
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

    @app_commands.command(name="leaderboard", description="Mostra o ranking de XP e níveis")
    @app_commands.describe(
        limit="Número de usuários para mostrar (padrão: 10)",
        days="Número de dias para análise (padrão: Ano Atual)"
    )
    async def leaderboard(self, interaction: discord.Interaction, limit: int = 10, days: Optional[int] = None):
        """Mostra o leaderboard de XP."""
        await interaction.response.defer()
        
        try:
            limit = max(1, min(limit, 25))
            
            if days is None:
                now = now_brt()
                start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                days = (now - start_of_year).days + 1

            leaderboard = await self.db.get_leaderboard(limit, days, interaction.guild.id)
            embed = self.embed_builder.build_leaderboard(leaderboard)
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erro ao buscar leaderboard: {e}")
            await interaction.followup.send(
                "❌ Erro ao buscar leaderboard. Tente novamente mais tarde.",
                ephemeral=True
            )
    
    @app_commands.command(name="destaques", description="Mostra a Retrospectiva e os Destaques do Ano do Servidor em Galeria Visual")
    @app_commands.describe(ano="Ano dos destaques para consulta (padrão: ano atual)")
    async def destaques(self, interaction: discord.Interaction, ano: Optional[int] = None):
        """Comando slash para exibir a Retrospectiva e Destaques do Ano."""
        await handle_highlights_gallery(self.db, interaction, ano)

    @user_stats.error
    async def user_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handler de erro para comando que requer permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
