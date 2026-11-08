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
    {"id": "gamer_variado", "label": "Gamer Variado", "title": "GAMER VARIADO", "subtitle": "Mais Jogos Distintos Jogados no Ano", "icon": "🎲", "color": "#f43f5e", "unit": "jogos"},
    {"id": "outros_destaques", "label": "Outros Destaques", "title": "OUTROS DESTAQUES DO ANO", "subtitle": "Recordes e Menções Honrosas", "icon": "🌟", "color": "#8b5cf6"},
]

MVP_CELEBRATION_GIF_URL = (
    "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmE4cDB2ZGI3eTJlcGRleG14bzJudnFrYmZwOWZ6cnJ6cmZ5djFoMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/yLElvNqqq7kdgsKNCC/giphy.gif"
)

NEW_YEAR_CELEBRATION_GIF_URL = (
    "https://media.giphy.com/media/26tOZ42Mg6pbTUPHW/giphy.gif"
)


def build_mvp_celebration_message(guild: discord.Guild, year: int, extras: Dict[str, Any]) -> tuple[str, discord.Embed]:
    """Gera a mensagem fora do embed mencionando e parabenizando o MVP do Ano + embed discreto apenas com o GIF (sem link visível)."""
    mvp = extras.get("mvp")
    if mvp:
        content = (
            f"👑 **MVP DO ANO {year} • {guild.name}**\n"
            f"Parabéns a <@{mvp['user_id']}> (`{mvp['username']}`), o membro lendário que mais movimentou o servidor este ano, "
            f"acumulando incríveis **{mvp['value']:,} pontos** de pura presença e atividade! 🏆✨"
        )
    else:
        content = (
            f"✨ **RETROSPECTIVA DO ANO {year} • {guild.name}**\n"
            f"Parabéns a toda a comunidade por mais um ano inesquecível juntos! 🎮🚀"
        )

    gif_embed = discord.Embed(color=0x2b2d31)
    gif_embed.set_image(url=MVP_CELEBRATION_GIF_URL)
    return content, gif_embed


def build_honorable_mentions_embed(guild: discord.Guild, year: int, extras: Dict[str, Any]) -> discord.Embed:
    """Gera o embed de Menções Honrosas & Curiosidades do Ano (enviado após a virada do ano)."""
    top_media = extras.get("top_media")
    top_gif = extras.get("top_gif")
    top_emoji = extras.get("top_emoji")
    most_active_day = extras.get("most_active_day")

    embed = discord.Embed(
        title=f"🌟 Menções Honrosas & Curiosidades do Ano {year}",
        color=discord.Color.gold(),
        description="Confira os momentos mais marcantes e registros históricos da comunidade no ano que passou:"
    )

    # 1. Print / Clipe do Ano
    if top_media:
        jump_url = top_media.get("jump_url")
        if not jump_url and top_media.get("channel_id") and top_media.get("message_id") and getattr(guild, "id", None):
            jump_url = f"https://discord.com/channels/{guild.id}/{top_media['channel_id']}/{top_media['message_id']}"

        jump_link = f"[🔗 Ver Mensagem Vencedora no Discord]({jump_url})" if jump_url else ""
        media_url = top_media.get("media_url", "")
        lower_media = media_url.lower()
        is_video_or_clip = any(
            k in lower_media
            for k in [".mp4", ".mov", ".webm", "twitch.tv", "medal.tv", "youtube.com", "youtu.be", "streamable.com"]
        )
        if is_video_or_clip and media_url:
            clip_link = f"[🎬 Assistir Clipe / Mídia]({media_url})"
            jump_link = f"{jump_link} • {clip_link}" if jump_link else clip_link

        author_uid = top_media.get("user_id")
        author_name = top_media.get("username", "Desconhecido")
        author_str = f"<@{author_uid}> (`{author_name}`)" if author_uid else author_name

        reaction_str = top_media.get("reaction_summary") or f"🔥 {top_media.get('reaction_count', 0)}"
        reply_cnt = top_media.get("reply_count", 0)
        if reply_cnt and reply_cnt > 0:
            reaction_str += f" • 💬 {reply_cnt} resposta(s)"

        media_desc = (
            f"👤 **Autor:** {author_str}\n"
            f"📊 **Engajamento:** {reaction_str}\n"
            f"{jump_link}"
        ).strip()
        if top_media.get("content"):
            clean_content = str(top_media["content"]).strip()
            if clean_content and clean_content != media_url:
                media_desc = f"💬 *\"{clean_content}\"*\n" + media_desc
        embed.add_field(name="📸 Mídia • Print / Clipe do Ano", value=media_desc, inline=False)
        if media_url:
            embed.set_image(url=media_url)

    # 2. GIF do Ano
    if top_gif:
        gif_text = "O GIF que mais expressou o sentimento da galera"
        if "count" in top_gif and top_gif["count"]:
            gif_text += f" ({top_gif['count']}x no chat)"
        jump_url = top_gif.get("jump_url") or top_gif.get("first_message_url")
        if jump_url:
            gif_text += f"\n[🔗 Ver Primeira Mensagem no Discord]({jump_url})"
        embed.add_field(name="🎭 GIF Mais Marcante do Ano", value=gif_text, inline=True)

    # 3. Emoji do Ano
    if top_emoji:
        emoji_text = f"**{top_emoji.get('emoji_name', '🔥')}** ({top_emoji.get('count', 0)} reações)"
        embed.add_field(name="🤣 Emoji do Ano", value=emoji_text, inline=True)

    # 4. Dia Mais Caótico
    if most_active_day:
        day_text = (
            f"📅 **{most_active_day.get('formatted_date', most_active_day.get('date'))}**\n"
            f"💬 {most_active_day.get('total_messages', 0):,} mensagens • 🎙️ {most_active_day.get('total_voice_minutes', 0):,} min em call"
        )
        embed.add_field(name="🔥 O Dia Mais Caótico do Ano", value=day_text, inline=False)

    embed.set_footer(text=f"Retrospectiva Oficial {year} • {guild.name}")
    return embed


def build_new_year_greeting(guild: discord.Guild, new_year: int, prev_year: int, gif_url: Optional[str] = None) -> tuple[str, discord.Embed]:
    """Gera a mensagem separada de Feliz Ano Novo + embed discreto apenas com o GIF (sem link visível)."""
    chosen_gif = gif_url or NEW_YEAR_CELEBRATION_GIF_URL
    content = (
        f"🎆 **FELIZ ANO NOVO, {guild.name.upper()}! BEM-VINDO A {new_year}!** 🥂✨\n"
        f"Obrigado por cada risada, partida, call de madrugada e momento compartilhado em **{prev_year}**. "
        f"Que **{new_year}** traga ainda mais conquistas, vitórias e resenhas épicas para toda a nossa comunidade! 🚀🎉"
    )
    gif_embed = discord.Embed(color=0x2b2d31)
    gif_embed.set_image(url=chosen_gif)
    return content, gif_embed


def build_retrospective_conclusion(guild: discord.Guild, year: int, extras: Dict[str, Any]) -> tuple[str, Optional[discord.Embed]]:
    """Mantido por compatibilidade: retorna a mensagem de celebração do MVP e o embed de Menções Honrosas."""
    content, _ = build_mvp_celebration_message(guild, year, extras)
    embed = build_honorable_mentions_embed(guild, year, extras)
    return content, embed


async def enrich_retrospective_extras(
    db: Database,
    guild: discord.Guild,
    year: int,
    extras: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Garante que os extras da retrospectiva (tanto via comando quanto agendada)
    tenham a Mídia (Print/Clipe) do Ano com link da mensagem vencedora e o link do GIF do Ano,
    escaneando os canais públicos caso ainda não estejam indexados no banco.
    """
    from utils.highlights_scanner import HighlightsScanner

    # 1. Garante Mídia (Print / Clipe) do Ano com jump_url da mensagem vencedora
    top_media = extras.get("top_media")
    if not top_media or top_media.get("popularity_score", 0) <= 0:
        try:
            scanned_media = await HighlightsScanner.scan_guild_top_clip(guild, year, timeout=25.0)
            if scanned_media and (
                not top_media
                or scanned_media.get("popularity_score", 0) >= top_media.get("popularity_score", 0)
            ):
                extras["top_media"] = scanned_media
                top_media = scanned_media
                try:
                    await db.upsert_media_highlight(
                        message_id=scanned_media["message_id"],
                        guild_id=guild.id,
                        channel_id=scanned_media.get("channel_id", 0),
                        channel_name=scanned_media.get("channel_name", ""),
                        user_id=scanned_media["user_id"],
                        username=scanned_media.get("username", "Desconhecido"),
                        avatar_url=scanned_media.get("avatar_url"),
                        media_url=scanned_media["media_url"],
                        content=scanned_media.get("content", ""),
                        reaction_count=scanned_media.get("reaction_count", 0),
                        reactions_json=scanned_media.get("reactions_json", {}),
                        reply_count=scanned_media.get("reply_count", 0),
                        jump_url=scanned_media.get("jump_url"),
                        created_at=scanned_media.get("created_at_dt"),
                    )
                except Exception as db_err:
                    logger.debug("Não foi possível persistir top_media escaneada: %s", db_err)
        except Exception as scan_err:
            logger.warning("Erro ao escanear top_media para %s: %s", guild.name, scan_err)

    if top_media and not top_media.get("jump_url") and top_media.get("channel_id") and top_media.get("message_id"):
        top_media["jump_url"] = f"https://discord.com/channels/{guild.id}/{top_media['channel_id']}/{top_media['message_id']}"

    # 2. Garante link da primeira mensagem do GIF do Ano
    top_gif = extras.get("top_gif")
    if top_gif and top_gif.get("gif_url") and not (top_gif.get("jump_url") or top_gif.get("first_message_url")):
        try:
            found_jump_url = await HighlightsScanner.find_first_gif_message_url(
                guild, top_gif["gif_url"], year
            )
            if found_jump_url:
                top_gif["jump_url"] = found_jump_url
                top_gif["first_message_url"] = found_jump_url
                await db.set_gif_first_message_url(guild.id, top_gif["gif_url"], year, found_jump_url)
        except Exception as gif_err:
            logger.debug("Erro ao buscar jump_url do top_gif: %s", gif_err)

    return extras


async def handle_highlights_gallery(db: Database, interaction: discord.Interaction, year: Optional[int] = None):
    """Renderiza e envia a Retrospectiva Anual como uma Galeria de Imagens de Alta Performance."""
    await interaction.response.defer(thinking=True)

    if year is None:
        year = now_brt().year

    try:
        from utils.image_generator import HighlightsBuilder

        highlights_data = await db.get_annual_highlights_data(interaction.guild.id, year, is_automatic=False)

        files = await HighlightsBuilder.generate_all_slides_files(
            guild=interaction.guild,
            year=year,
            highlights_data=highlights_data,
            top_clip=None,
            categories=HIGHLIGHTS_CATEGORIES
        )

        if not files:
            await interaction.followup.send("❌ Não foi possível gerar os slides da retrospectiva.", ephemeral=True)
            return

        await interaction.followup.send(
            content=f"🌟 **DESTAQUES DO ANO {year} • {interaction.guild.name}**\n*Navegue pelas fotos da galeria em tela cheia abaixo:*",
            files=files
        )

        # Envia a mensagem fora do embed mencionando e parabenizando o MVP junto com o GIF de celebração (via embed discreto)
        try:
            extras = await db.get_retrospective_extras(interaction.guild.id, year, is_automatic=False)
            mvp_text, mvp_gif_embed = build_mvp_celebration_message(interaction.guild, year, extras)
            if interaction.channel:
                await interaction.channel.send(content=mvp_text, embed=mvp_gif_embed)
        except Exception as ex_err:
            logger.warning("Erro ao enviar mensagem de parabenização do MVP da retrospectiva: %s", ex_err)

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
    
    @app_commands.command(
        name="destaques",
        description="[ADMIN/TESTE] Mostra a Retrospectiva e os Destaques do Ano do Servidor em Galeria Visual"
    )
    @app_commands.describe(ano="Ano dos destaques para consulta (padrão: ano atual)")
    @app_commands.checks.has_permissions(administrator=True)
    async def destaques(self, interaction: discord.Interaction, ano: Optional[int] = None):
        """Comando administrativo de teste para exibir a Retrospectiva e Destaques do Ano."""
        await handle_highlights_gallery(self.db, interaction, ano)

    @destaques.error
    async def destaques_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handler de erro para o comando de destaques restrito a administradores."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Este comando é exclusivo para **Administradores** (teste da retrospectiva anual).",
                ephemeral=True
            )

    @app_commands.command(
        name="podio_mensal_teste",
        description="[ADMIN/TEMPORÁRIO] Gera e exibe o pódio mensal com dados em tempo real até o momento (BRT UTC-3)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def podio_mensal_teste(self, interaction: discord.Interaction):
        """Comando administrativo temporário para testar o pódio mensal em tempo real com Pillow."""
        await interaction.response.defer(thinking=True)
        try:
            from utils.image_generator import PodiumBuilder
            from config import now_brt

            now = now_brt()
            monthly_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_end = now

            month_names = {
                1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
                5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
                9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO",
            }
            month_name = month_names.get(now.month, "MÊS")
            period_text = f"{month_name} {now.year} (ATÉ O MOMENTO)"

            top_users = await self.db.get_top_users_date_range(interaction.guild.id, monthly_start, monthly_end, limit=10)
            if not top_users:
                days = (now - monthly_start).days + 1
                top_users = await self.db.get_leaderboard(10, days, interaction.guild.id)

            if not top_users:
                await interaction.followup.send("⚠️ Nenhum dado de atividade registrado para o mês atual até o momento.", ephemeral=True)
                return

            builder = PodiumBuilder()
            image_bio = await builder.generate_podium(interaction.guild, top_users, period_text=period_text)
            file = discord.File(fp=image_bio, filename=f"podio_mensal_{now.year}_{now.month:02d}_teste.png")

            await interaction.followup.send(
                content=f"🏆 **PÓDIO MENSAL EM TEMPO REAL — {period_text}**\n*(Comando administrativo temporário de avaliação)*",
                file=file
            )
        except Exception as e:
            logger.error("Erro ao gerar pódio mensal de teste: %s", e, exc_info=True)
            await interaction.followup.send(f"❌ Erro ao gerar pódio mensal de teste: {e}", ephemeral=True)

    @user_stats.error
    async def user_stats_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handler de erro para comando que requer permissões."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Você precisa de permissão de **Gerenciar Servidor** para usar este comando.",
                ephemeral=True
            )
