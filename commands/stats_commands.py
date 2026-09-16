# commands/stats_commands.py - Comandos Slash de Estatísticas e Níveis

import discord
from discord import app_commands
from database import Database
from utils.embed_builder import StatsEmbedBuilder
from io import BytesIO
from typing import Optional, Any, Dict, List
import logging
from config import now_brt
from utils.highlights_scanner import HighlightsScanner
from utils.image_generator import HighlightsBuilder

logger = logging.getLogger(__name__)

HIGHLIGHTS_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": "cover",
        "label": "🏆 Capa da Retrospectiva",
        "description": "Visão geral e abertura dos Destaques do Ano",
    },
    {
        "id": "highestScore",
        "label": "⚡ MVP do Servidor",
        "description": "Maior ganho de XP e níveis no ano",
        "title": "MVP DO SERVIDOR",
        "subtitle": "Os membros mais ativos e com maior pontuação de XP acumulada",
        "icon": "⚡",
        "color": "#ffd700",
        "unit": "XP",
        "is_time": False,
    },
    {
        "id": "mostMessages",
        "label": "💬 O Tagarela",
        "description": "Mais mensagens de texto enviadas",
        "title": "O TAGARELA",
        "subtitle": "Quem mais movimentou os canais de texto do servidor",
        "icon": "💬",
        "color": "#38bdf8",
        "unit": "mensagens",
        "is_time": False,
    },
    {
        "id": "mostVoice",
        "label": "🎙️ Rei da Call",
        "description": "Mais horas acumuladas em canais de voz",
        "title": "REI DA CALL",
        "subtitle": "Mais tempo presente e conversando em canais de voz",
        "icon": "🎙️",
        "color": "#10b981",
        "unit": "",
        "is_time": True,
    },
    {
        "id": "nightOwl",
        "label": "🦉 O Corujão",
        "description": "Mais tempo em call na madrugada (00h às 06h BRT)",
        "title": "O CORUJÃO",
        "subtitle": "Guardiões da madrugada: mais tempo em call entre 00h e 06h (BRT)",
        "icon": "🦉",
        "color": "#818cf8",
        "unit": "",
        "is_time": True,
    },
    {
        "id": "longestStreaming",
        "label": "📹 Streamer da Comunidade",
        "description": "Mais tempo transmitindo tela / live no Discord",
        "title": "STREAMER DO SERVIDOR",
        "subtitle": "Quem mais compartilhou gameplay e telas ao vivo em chamadas",
        "icon": "📹",
        "color": "#f43f5e",
        "unit": "",
        "is_time": True,
    },
    {
        "id": "topGamers",
        "label": "🎮 Top Gamers",
        "description": "Mais horas registradas jogando no Discord",
        "title": "TOP GAMERS",
        "subtitle": "Os membros que mais acumularam horas de jogatina no ano",
        "icon": "🎮",
        "color": "#a855f7",
        "unit": "",
        "is_time": True,
    },
    {
        "id": "gameOfTheYear",
        "label": "🕹️ Jogo do Ano",
        "description": "O jogo mais jogado por toda a comunidade",
        "title": "JOGO DO ANO",
        "subtitle": "O título que mais uniu os membros em horas acumuladas de gameplay",
        "icon": "🕹️",
        "color": "#f59e0b",
        "unit": "",
        "is_time": True,
    },
    {
        "id": "media",
        "label": "📸 Clipe / Print do Ano",
        "description": "O momento mais reagido e votado em prints e clipes",
    },
    {
        "id": "mostReactionsReceived",
        "label": "💖 Ímã da Galera",
        "description": "Mais reações recebidas em mensagens",
        "title": "ÍMÃ DA GALERA",
        "subtitle": "Mensagens mais curtidas e aclamadas pela comunidade",
        "icon": "💖",
        "color": "#fb7185",
        "unit": "reações",
        "is_time": False,
    },
    {
        "id": "mostReactionsGiven",
        "label": "⚡ O Reativo",
        "description": "Quem mais interagiu e reagiu com emojis",
        "title": "O REATIVO",
        "subtitle": "O membro mais expressivo: distribuiu mais reações no ano",
        "icon": "⚡",
        "color": "#fbbf24",
        "unit": "reações dadas",
        "is_time": False,
    },
    {
        "id": "mediaKing",
        "label": "📁 O Mídia",
        "description": "Mais fotos, memes e anexos enviados",
        "title": "O MÍDIA",
        "subtitle": "Quem mais compartilhou memes, fotos e arquivos no chat",
        "icon": "📁",
        "color": "#ec4899",
        "unit": "anexos",
        "is_time": False,
    },
    {
        "id": "omnipresent",
        "label": "🌐 O Onipresente",
        "description": "Mais dias distintos com atividade no servidor",
        "title": "O ONIPRESENTE",
        "subtitle": "Membros com maior frequência diária no servidor durante o ano",
        "icon": "🌐",
        "color": "#06b6d4",
        "unit": "dias ativos",
        "is_time": False,
    }
]


class HighlightsSelect(discord.ui.Select):
    """Dropdown interativo para saltar diretamente para qualquer slide dos Destaques."""

    def __init__(self, current_index: int = 0):
        options = []
        for idx, cat in enumerate(HIGHLIGHTS_CATEGORIES):
            options.append(
                discord.SelectOption(
                    label=cat["label"][:100],
                    value=str(idx),
                    description=cat["description"][:100],
                    default=(idx == current_index)
                )
            )
        super().__init__(
            placeholder="📑 Selecione uma categoria dos Destaques...",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        view: HighlightsCarouselView = self.view  # type: ignore
        selected_index = int(self.values[0])
        await view.navigate_to(interaction, selected_index)


class HighlightsCarouselView(discord.ui.View):
    """Carrossel interativo com botões e dropdown para navegação dos Destaques do Ano."""

    def __init__(
        self,
        guild: Optional[discord.Guild],
        year: int,
        highlights_data: Dict[str, Any],
        top_clip: Optional[Dict[str, Any]] = None,
        author_id: Optional[int] = None,
        timeout: float = 300.0
    ):
        super().__init__(timeout=timeout)
        self.guild = guild
        self.year = year
        self.highlights_data = highlights_data
        self.top_clip = top_clip
        self.author_id = author_id
        self.current_index = 0
        self.total_slides = len(HIGHLIGHTS_CATEGORIES)
        self.cached_images: Dict[int, bytes] = {}

        self._build_components()

    def _build_components(self):
        self.clear_items()
        # Row 0: Select dropdown
        self.add_item(HighlightsSelect(current_index=self.current_index))

        # Row 1: Navigation Buttons
        first_btn = discord.ui.Button(
            label="⏮️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_index == 0),
            custom_id="btn_first",
            row=1
        )
        first_btn.callback = self._on_first_clicked
        self.add_item(first_btn)

        prev_btn = discord.ui.Button(
            label="◀️ Anterior",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_index == 0),
            custom_id="btn_prev",
            row=1
        )
        prev_btn.callback = self._on_prev_clicked
        self.add_item(prev_btn)

        page_btn = discord.ui.Button(
            label=f"{self.current_index + 1} / {self.total_slides}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id="btn_page",
            row=1
        )
        self.add_item(page_btn)

        next_btn = discord.ui.Button(
            label="Próximo ▶️",
            style=discord.ButtonStyle.primary,
            disabled=(self.current_index == self.total_slides - 1),
            custom_id="btn_next",
            row=1
        )
        next_btn.callback = self._on_next_clicked
        self.add_item(next_btn)

        last_btn = discord.ui.Button(
            label="⏭️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_index == self.total_slides - 1),
            custom_id="btn_last",
            row=1
        )
        last_btn.callback = self._on_last_clicked
        self.add_item(last_btn)

        # Se for o slide de clipe e houver jump_url válido, adiciona botão de link
        cur_cat = HIGHLIGHTS_CATEGORIES[self.current_index]
        if cur_cat["id"] == "media" and self.top_clip and self.top_clip.get("jump_url"):
            link_btn = discord.ui.Button(
                label="🔗 Ver Mensagem Original",
                url=self.top_clip["jump_url"],
                style=discord.ButtonStyle.link,
                row=2
            )
            self.add_item(link_btn)

    async def _render_current_slide(self) -> BytesIO:
        """Renderiza ou recupera do cache a imagem do slide atual."""
        if self.current_index in self.cached_images:
            buf = BytesIO(self.cached_images[self.current_index])
            buf.seek(0)
            return buf

        cat = HIGHLIGHTS_CATEGORIES[self.current_index]
        cat_id = cat["id"]

        if cat_id == "cover":
            img_buf = await HighlightsBuilder.generate_cover_slide(
                guild=self.guild,
                year=self.year,
                total_categories=self.total_slides
            )
        elif cat_id == "media":
            img_buf = await HighlightsBuilder.generate_media_slide(
                guild=self.guild,
                year=self.year,
                clip_data=self.top_clip
            )
        else:
            winners = self.highlights_data.get(cat_id, [])
            img_buf = await HighlightsBuilder.generate_category_slide(
                guild=self.guild,
                year=self.year,
                category_title=cat.get("title", cat["label"]),
                category_subtitle=cat.get("subtitle", cat["description"]),
                category_icon=cat.get("icon", "🏆"),
                theme_color=cat.get("color", "#00f0ff"),
                winners=winners,
                unit_label=cat.get("unit", ""),
                is_time=cat.get("is_time", False)
            )

        img_bytes = img_buf.getvalue()
        self.cached_images[self.current_index] = img_bytes
        buf = BytesIO(img_bytes)
        buf.seek(0)
        return buf

    async def navigate_to(self, interaction: discord.Interaction, new_index: int):
        """Atualiza o slide exibido no carrossel."""
        await interaction.response.defer()
        self.current_index = max(0, min(new_index, self.total_slides - 1))
        self._build_components()

        img_buffer = await self._render_current_slide()
        file = discord.File(fp=img_buffer, filename=f"destaques_{self.year}_{self.current_index}.png")
        await interaction.edit_original_response(attachments=[file], view=self)

    async def _on_first_clicked(self, interaction: discord.Interaction):
        await self.navigate_to(interaction, 0)

    async def _on_prev_clicked(self, interaction: discord.Interaction):
        await self.navigate_to(interaction, self.current_index - 1)

    async def _on_next_clicked(self, interaction: discord.Interaction):
        await self.navigate_to(interaction, self.current_index + 1)

    async def _on_last_clicked(self, interaction: discord.Interaction):
        await self.navigate_to(interaction, self.total_slides - 1)


async def handle_highlights_carousel(
    db: Database,
    interaction: discord.Interaction,
    year: Optional[int] = None
):
    """Gera e inicializa o carrossel interativo de Destaques do Ano."""
    await interaction.response.defer()
    target_year = year or now_brt().year

    try:
        # Busca estatísticas do banco de dados com fuso de Brasília
        stats_data = await db.get_guild_annual_highlights(interaction.guild.id, target_year, limit=5)

        # Escaneia os canais de prints/clipes para o momento mais votado
        top_clips = await HighlightsScanner.find_top_clips_and_prints(interaction.guild, target_year, limit=1)
        top_clip = top_clips[0] if top_clips else None

        view = HighlightsCarouselView(
            guild=interaction.guild,
            year=target_year,
            highlights_data=stats_data,
            top_clip=top_clip,
            author_id=interaction.user.id
        )

        initial_buf = await view._render_current_slide()
        file = discord.File(fp=initial_buf, filename=f"destaques_{target_year}_0.png")

        await interaction.followup.send(file=file, view=view)
    except Exception as e:
        logger.error(f"Erro ao inicializar carrossel de destaques para {target_year}: {e}", exc_info=True)
        await interaction.followup.send("❌ Ocorreu um erro ao gerar os Destaques do Ano. Tente novamente.", ephemeral=True)


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

    @app_commands.command(name="destaques", description="Abre o carrossel interativo dos Destaques do Ano do servidor (BMIA Wrapped)")
    @app_commands.describe(ano="Ano da retrospectiva (opcional, padrão: ano atual)")
    async def destaques(self, interaction: discord.Interaction, ano: Optional[int] = None):
        """Exibe o carrossel de Destaques do Ano."""
        await handle_highlights_carousel(self.db, interaction, ano)
    
    @user_stats.error
    async def user_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handler de erro para comando que requer permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
