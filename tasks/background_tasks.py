# tasks/background_tasks.py — Tarefas em Segundo Plano
"""
Todas as tarefas assíncronas periódicas extraídas do main.py.
Cada função recebe via parâmetro os managers necessários (sem variáveis globais).
"""

import asyncio
import logging
import traceback
import re
from typing import Optional, Dict, List, Any

import discord

from config import now_brt, utcnow
from datetime import timedelta

logger = logging.getLogger(__name__)


# ── Estatísticas do Servidor ───────────────────────────────────────────────────
async def collect_server_stats(client: discord.Client, db) -> None:
    """Coleta a contagem de membros de cada guild a cada 1 hora."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if db:
                for guild in client.guilds:
                    await db.update_daily_member_count(guild.id, guild.member_count)
                    logger.info(
                        "📊 Estatísticas atualizadas para %s: %d membros",
                        guild.name, guild.member_count,
                    )
        except Exception as exc:
            logger.error("❌ Erro ao coletar estatísticas do servidor: %s", exc)
        await asyncio.sleep(3600)


# ── Verificação de Cargos ──────────────────────────────────────────────────────
async def check_roles_periodically(
    client: discord.Client,
    role_manager,
    dynamic_roles_config: dict,
) -> None:
    """Verifica e atribui cargos automáticos e dinâmicos a cada 1 hora."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if role_manager:
                for guild in client.guilds:
                    assigned = await role_manager.check_all_members(guild)
                    if assigned > 0:
                        logger.info(
                            "🏅 %d cargos por tempo atribuídos em %s",
                            assigned, guild.name,
                        )
                    role_manager.set_dynamic_role_ids(dynamic_roles_config)
                    await role_manager.sync_dynamic_roles(guild)
        except Exception as exc:
            logger.error("❌ Erro ao verificar cargos: %s", exc)
        await asyncio.sleep(3600)


# ── Pódio Mensal / Anual ───────────────────────────────────────────────────────
async def check_monthly_podium(
    client: discord.Client,
    db,
    allowed_channels: list[int],
) -> None:
    """Verifica e envia periodicamente o pódio mensal e anual para cada servidor."""
    await client.wait_until_ready()
    from utils.image_generator import PodiumBuilder

    month_names = {
        1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
        5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
        9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO",
    }

    while not client.is_closed():
        try:
            if db:
                now = now_brt()

                # 1. PÓDIO MENSAL (do mês anterior concluído)
                last_month_end = now.replace(day=1) - timedelta(days=1)
                m_num = last_month_end.month
                y_num = last_month_end.year
                monthly_identifier = f"{y_num}-{m_num:02d}"
                monthly_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                monthly_end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                monthly_title = f"🏆 PÓDIO DE {month_names.get(m_num, '')}/{y_num} 🏆"
                monthly_label = f"{month_names.get(m_num, '')} {y_num}"

                # 2. PÓDIO ANUAL (do ano anterior concluído)
                prev_year = now.year - 1
                yearly_identifier = str(prev_year)
                yearly_start = now.replace(year=prev_year, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                yearly_end = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                yearly_title = f"👑 HALL DA FAMA • PÓDIO ANUAL DE {prev_year} 👑"
                yearly_label = f"HALL DA FAMA {prev_year}"

                for guild in client.guilds:
                    # Encontra canal de destino do servidor
                    guild_config = await db.get_guild_config(guild.id)
                    g_allowed = (guild_config.get("allowed_channels") if guild_config else None) or allowed_channels

                    target_channel = None
                    if g_allowed:
                        for ch_id in g_allowed:
                            ch = guild.get_channel(ch_id)
                            if ch and hasattr(ch, "permissions_for") and ch.permissions_for(guild.me).send_messages:
                                target_channel = ch
                                break

                    if not target_channel and guild.system_channel:
                        if guild.system_channel.permissions_for(guild.me).send_messages:
                            target_channel = guild.system_channel

                    if not target_channel:
                        for ch in guild.text_channels:
                            if ch.permissions_for(guild.me).send_messages:
                                target_channel = ch
                                break

                    if not target_channel:
                        logger.warning("⚠️ Nenhum canal com permissão de envio para pódio em %s", guild.name)
                        continue

                    # Verifica e envia Pódio Mensal
                    if not await db.check_periodic_leaderboard_sent(guild.id, "MONTHLY", monthly_identifier):
                        logger.info("Gerando pódio mensal (%s) para %s...", monthly_identifier, guild.name)
                        top_users = await db.get_top_users_date_range(guild.id, monthly_start, monthly_end, limit=10)

                        if top_users:
                            builder = PodiumBuilder()
                            image_bio = await builder.generate_podium(guild, top_users, period_text=monthly_label)
                            file = discord.File(fp=image_bio, filename="podium_mensal.png")
                            await target_channel.send(
                                f"**{monthly_title}**\nParabéns aos membros mais ativos e dedicados do mês! 🎉⚡",
                                file=file,
                            )
                            await db.log_periodic_leaderboard_sent(guild.id, "MONTHLY", monthly_identifier)
                            logger.info("✅ Pódio mensal enviado para %s", guild.name)
                        else:
                            await db.log_periodic_leaderboard_sent(guild.id, "MONTHLY", monthly_identifier)
                            logger.info("Sem dados suficientes para pódio mensal em %s", guild.name)

                    # Verifica e envia Pódio Anual, Destaques e Celebração (Abordagem C: a partir de 21/12 ou Janeiro)
                    should_check_yearly = (now.month == 12 and now.day >= 21) or (now.month == 1)
                    if should_check_yearly:
                        retrospective_year = now.year if (now.month == 12) else (now.year - 1)
                        yearly_target_id = str(retrospective_year)
                        if not await db.check_periodic_leaderboard_sent(guild.id, "YEARLY", yearly_target_id):
                            logger.info("Gerando retrospectiva anual de gala (%s) para %s...", yearly_target_id, guild.name)
                            start_dt, end_dt = db.get_retrospective_period(retrospective_year, is_automatic=True)
                            top_yearly = await db.get_top_users_date_range(guild.id, start_dt, end_dt, limit=10)

                            if top_yearly:
                                builder = PodiumBuilder()
                                image_bio = await builder.generate_podium(guild, top_yearly, period_text=f"HALL DA FAMA {retrospective_year}")
                                file = discord.File(fp=image_bio, filename="podium_anual.png")
                                await target_channel.send(
                                    f"**👑 HALL DA FAMA • PÓDIO ANUAL DE {retrospective_year} 👑**\nParabéns às lendas do servidor em {retrospective_year}! 🏆👑",
                                    file=file,
                                )

                            # Envia também a galeria de Destaques do Ano
                            try:
                                from utils.image_generator import HighlightsBuilder
                                from commands.stats_commands import HIGHLIGHTS_CATEGORIES, build_retrospective_conclusion

                                h_data = await db.get_annual_highlights_data(guild.id, retrospective_year, is_automatic=True, start_dt=start_dt, end_dt=end_dt)
                                h_files = await HighlightsBuilder.generate_all_slides_files(
                                    guild=guild,
                                    year=retrospective_year,
                                    highlights_data=h_data,
                                    top_clip=None,
                                    categories=HIGHLIGHTS_CATEGORIES
                                )
                                if h_files:
                                    await target_channel.send(
                                        f"🌟 **DESTAQUES DO ANO {retrospective_year} • {guild.name}**\n*Confira os maiores recordes e destaques da comunidade:*",
                                        files=h_files
                                    )

                                # Envia a mensagem conclusiva especial com MVP, Print do Ano, GIF e curiosidades
                                extras = await db.get_retrospective_extras(guild.id, retrospective_year, is_automatic=True, start_dt=start_dt, end_dt=end_dt)
                                conclusion_text, conclusion_embed = build_retrospective_conclusion(guild, retrospective_year, extras)
                                await target_channel.send(content=conclusion_text, embed=conclusion_embed)

                            except Exception as h_err:
                                logger.warning("Erro ao enviar galeria de destaques no background: %s", h_err)

                            await db.log_periodic_leaderboard_sent(guild.id, "YEARLY", yearly_target_id)
                            logger.info("✅ Retrospectiva de gala e destaques anuais concluídos para %s", guild.name)

        except Exception as exc:
            logger.error("❌ Erro no check_monthly_podium: %s", exc)
            traceback.print_exc()
        await asyncio.sleep(3600)



# ── Resumo Diário (Telegram) ───────────────────────────────────────────────────
async def send_daily_summary(
    client: discord.Client,
    db,
    telegram,
    giveaway_manager,
) -> None:
    """Envia resumo diário de atividade para o Telegram à meia-noite BRT."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            # Calcula segundos até meia-noite BRT
            now_brt_dt = now_brt()
            next_midnight = (now_brt_dt + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            seconds_until_midnight = (next_midnight - now_brt_dt).total_seconds()
            logger.info(
                "⏰ Resumo diário em %.1fh (meia-noite BRT)",
                seconds_until_midnight / 3600,
            )
            await asyncio.sleep(seconds_until_midnight)

            if not db:
                continue

            for guild in client.guilds:
                try:
                    stats = await db.get_server_stats(guild.id, days=1)
                    top_users = await db.get_top_users_by_messages(guild.id, limit=3, days=1)

                    medals = ["🥇", "🥈", "🥉"]
                    top_str = "\n".join(
                        f"{medals[i]} {u.get('username', 'Desconhecido')} — {u.get('message_count', 0)} msgs"
                        for i, u in enumerate(top_users)
                    ) or "Sem dados"

                    giveaways_today = 0
                    if giveaway_manager:
                        try:
                            active = await db.get_active_giveaways(guild.id)
                            now_utc = utcnow()
                            giveaways_today = sum(
                                1 for g in (active or [])
                                if g.get("ended") and g.get("ends_at")
                                and (now_utc - g["ends_at"]).total_seconds() < 86400
                            )
                        except Exception:
                            giveaways_today = 0

                    day_str = now_brt().strftime("%d/%m/%Y")
                    message = (
                        f"📋 <b>Resumo Diário — {day_str}</b>\n"
                        f"🏠 {guild.name}\n\n"
                        f"💬 Mensagens: {stats.get('total_messages', 0)}\n"
                        f"👥 Usuários ativos: {stats.get('active_users', 0)}\n"
                        f"🛡️ Mensagens moderadas: {stats.get('moderated_messages', 0)}\n"
                        f"🎉 Sorteios encerrados: {giveaways_today}\n"
                        f"🏰 Total de membros: {guild.member_count}\n\n"
                        f"<b>🏅 Top 3 do dia:</b>\n{top_str}"
                    )
                    await telegram.send(message)
                    logger.info("✅ Resumo diário enviado para Telegram — %s", guild.name)

                except Exception as exc:
                    logger.error("❌ Erro no resumo diário para %s: %s", guild.name, exc)

        except Exception as exc:
            logger.error("❌ Erro geral no send_daily_summary: %s", exc)
            await asyncio.sleep(60)


# ── Ranking Semanal de Jogos (Telegram) ───────────────────────────────────────
async def weekly_games_report(client: discord.Client, db, telegram) -> None:
    """Envia ranking semanal de jogos toda segunda-feira à meia-noite BRT."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            now_brt_dt = now_brt()
            days_until_monday = (7 - now_brt_dt.weekday()) % 7 or 7
            next_monday = (now_brt_dt + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            seconds_to_wait = (next_monday - now_brt_dt).total_seconds()
            logger.info("🎮 Relatório semanal de jogos em %.1fh", seconds_to_wait / 3600)
            await asyncio.sleep(seconds_to_wait)

            if not db:
                continue

            for guild in client.guilds:
                try:
                    games = await db.get_top_activities(guild.id, limit=5, days=7)
                    await telegram.log_top_games(guild, games, period_days=7)
                    logger.info("✅ Relatório semanal de jogos enviado — %s", guild.name)
                except Exception as exc:
                    logger.error(
                        "❌ Erro no relatório semanal de jogos para %s: %s", guild.name, exc
                    )
        except Exception as exc:
            logger.error("❌ Erro geral no weekly_games_report: %s", exc)
            await asyncio.sleep(60)


# ── Sorteios Expirados ─────────────────────────────────────────────────────────
async def check_expired_giveaways(
    client: discord.Client, db, giveaway_manager
) -> None:
    """Verifica e finaliza sorteios expirados a cada 30 segundos."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if giveaway_manager and db:
                expired = await db.get_expired_giveaways()
                for giveaway in expired:
                    await giveaway_manager.end_giveaway(giveaway["giveaway_id"], client)
                    logger.info("🎉 Sorteio finalizado automaticamente: %s", giveaway["prize"])
        except Exception as exc:
            logger.error("❌ Erro ao verificar sorteios expirados: %s", exc)
        await asyncio.sleep(30)


# ── Fila de Embeds ─────────────────────────────────────────────────────────────
async def check_embed_queue(client: discord.Client, db, embed_sender) -> None:
    """Processa a fila de embeds pendentes a cada 5 segundos."""
    await client.wait_until_ready()
    logger.info("check_embed_queue iniciado.")
    while not client.is_closed():
        try:
            if embed_sender and db:
                await embed_sender.process_pending_requests(client)
            else:
                logger.debug("embed_sender=%s, db=%s", embed_sender, db)
        except Exception as exc:
            logger.error("❌ Erro ao verificar fila de embeds: %s", exc)
        await asyncio.sleep(5)


# ── Estatísticas de Contexto ───────────────────────────────────────────────────
async def check_context_stats(client: discord.Client, stats_analyzer) -> None:
    """Atualiza estatísticas de contexto (ranks, jogos) a cada 6 horas."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if stats_analyzer:
                await stats_analyzer.execute_analysis_loop(client.guilds)
        except Exception as exc:
            logger.error("❌ Erro ao atualizar estatísticas de contexto: %s", exc)
        await asyncio.sleep(21600)


# ── Pontos de Voz ─────────────────────────────────────────────────────────────
async def check_voice_points_periodically(
    client: discord.Client, points_manager
) -> None:
    """Atribui pontos de voz/atividade a cada 60 segundos."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if points_manager:
                await points_manager.execute_points_loop(client.guilds)
        except Exception as exc:
            logger.error("❌ Erro no loop de pontos periódicos: %s", exc)
        await asyncio.sleep(60)


# ── Promoções e Eventos Sazonais da Steam ──────────────────────────────────────
def find_gaming_announcement_channel(guild: discord.Guild, config: Optional[dict] = None) -> Optional[discord.TextChannel]:
    """
    Encontra o melhor canal público para anúncios de jogos, eventos e promoções.
    Prioridade:
    1. Canal configurado explicitamente pelo admin (deals_channel_id via /config canal-jogos).
    2. Canais temáticos de games/ofertas (ex: sugestao-de-jogos, games-gratis).
    3. Canais principais de bate-papo da comunidade (allowed_channels, ex: #chat-principal).
    4. Canal público de sistema (system_channel) seguro.
    Nunca envia para canais de moderação, administração, logs ou staff.
    """
    if not guild:
        return None

    # Palavras-chave proibidas para anúncios públicos
    STAFF_KEYWORDS = ["admin", "adm", "mod", "staff", "log", "audit", "privado", "denuncia", "denúncia", "regras"]

    def _normalize(name: Any) -> str:
        if not isinstance(name, str):
            name = str(name or "")
        import unicodedata
        nfkd = unicodedata.normalize('NFKD', name)
        ascii_text = ''.join(c for c in nfkd if not unicodedata.combining(c))
        return re.sub(r'[^a-zA-Z0-9]', '', ascii_text).lower()

    def is_staff_channel(ch_name: Any) -> bool:
        norm = _normalize(ch_name)
        return any(k in norm for k in ["admin", "adm", "mod", "staff", "log", "audit", "privado", "denuncia", "regras"])

    # 1. Canal explicitamente configurado pelo usuário (/config canal-jogos)
    if config and config.get("deals_channel_id"):
        ch = guild.get_channel(config["deals_channel_id"])
        if ch and hasattr(ch, "permissions_for") and ch.permissions_for(guild.me).send_messages and not is_staff_channel(getattr(ch, "name", "")):
            return ch

    # Palavras-chave de canais prioritários para jogos e promoções
    GAMING_KEYWORDS = [
        "sugestaodejogos", "gamesgratis", "jogosgratis",
        "steam", "promocoes", "ofertas",
        "noticias", "anuncios", "novidades"
    ]

    # 2. Procura canais temáticos de games/notícias onde o bot possa enviar
    for keyword in GAMING_KEYWORDS:
        for ch in guild.text_channels:
            if not (hasattr(ch, "permissions_for") and ch.permissions_for(guild.me).send_messages):
                continue
            norm_name = _normalize(getattr(ch, "name", ""))
            if keyword in norm_name and not is_staff_channel(getattr(ch, "name", "")):
                return ch

    # 3. Procura nos allowed_channels configurados (canais principais de interação)
    if config:
        allowed = config.get("allowed_channels", [])
        for ch_id in allowed:
            ch = guild.get_channel(ch_id)
            if ch and hasattr(ch, "permissions_for") and ch.permissions_for(guild.me).send_messages and not is_staff_channel(getattr(ch, "name", "")):
                return ch

    # 4. System channel seguro (desde que não seja de moderação/staff)
    if guild.system_channel and hasattr(guild.system_channel, "permissions_for") and guild.system_channel.permissions_for(guild.me).send_messages and not is_staff_channel(getattr(guild.system_channel, "name", "")):
        return guild.system_channel

    # 5. Qualquer canal público seguro sem ser de moderação/staff
    for ch in guild.text_channels:
        if hasattr(ch, "permissions_for") and ch.permissions_for(guild.me).send_messages and not is_staff_channel(getattr(ch, "name", "")):
            return ch

    return None


async def check_steam_seasonal_events_periodically(client: discord.Client, db) -> None:
    """Verifica e notifica o início de grandes promoções e festivais da Steam às 14:00 BRT."""
    import zoneinfo
    brt_zone = zoneinfo.ZoneInfo("America/Sao_Paulo")

    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if db:
                due_events = await db.get_due_steam_events_for_notification()
                for event in due_events:
                    start_dt = event["start_time"]
                    end_dt = event["end_time"]
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=brt_zone)
                    if end_dt.tzinfo is None:
                        end_dt = end_dt.replace(tzinfo=brt_zone)

                    start_str = start_dt.astimezone(brt_zone).strftime("%d/%m/%Y às %H:%M BRT")
                    end_str = end_dt.astimezone(brt_zone).strftime("%d/%m/%Y às %H:%M BRT")

                    embed = discord.Embed(
                        title=f"🔥 Começou: {event['event_name']} na Steam!",
                        description=(
                            f"O evento oficial da Steam já está no ar com milhares de descontos!\n\n"
                            f"📆 **Duração:** {start_str} até {end_str}\n"
                            f"🛒 **Acesse a loja:** [Steam Store](https://store.steampowered.com/)\n"
                        ),
                        color=discord.Color.from_rgb(26, 61, 92)
                    )
                    if event.get("description"):
                        embed.description += f"\n_{event['description']}_\n"
                    if event.get("banner_url"):
                        embed.set_image(url=event["banner_url"])

                    embed.set_footer(text="Notificação automática de eventos da Steam | BMIA")

                    for guild in client.guilds:
                        config = await db.get_guild_config(guild.id)
                        channel_to_send = find_gaming_announcement_channel(guild, config)

                        if channel_to_send:
                            try:
                                await channel_to_send.send(embed=embed)
                            except Exception as send_err:
                                logger.warning(f"Não foi possível enviar alerta de evento Steam em {guild.name}: {send_err}")

                    await db.mark_steam_event_notified(event["id"], "start")
                    logger.info(f"📢 Alerta do evento Steam '{event['event_name']}' disparado com sucesso.")
        except Exception as exc:
            logger.error("❌ Erro ao verificar eventos sazonais da Steam: %s", exc)
        await asyncio.sleep(300)


async def check_tracked_game_deals_periodically(client: discord.Client, db, gg_client=None) -> None:
    """Verifica periodicamente os jogos monitorados para alertar sobre novas promoções."""
    from utils.gg_deals_client import GGDealsClient
    if gg_client is None:
        gg_client = GGDealsClient()

    await client.wait_until_ready()
    # Espera 2 minutos antes da primeira checagem para dar tempo de inicializar
    await asyncio.sleep(120)

    while not client.is_closed():
        try:
            if db:
                games = await db.get_all_tracked_games(is_active=True)
                for game in games:
                    appid = game["steam_appid"]
                    info = await gg_client.get_game_info(appid)
                    if not info:
                        continue

                    # Atualiza dados no banco
                    await db.update_tracked_game_price(
                        game_id=game["id"],
                        current_price=info["current_price"],
                        discount_percent=info["discount_percent"],
                        historical_low_price=info["historical_low_price"],
                        best_store_name=info["best_store_name"],
                        best_store_url=info["best_store_url"],
                        header_image_url=info["header_image_url"]
                    )

                    # Verifica se deve alertar: Desconto ativo e preço caiu em relação à última notificação
                    discount = info["discount_percent"]
                    last_notified_price = game.get("last_notified_price")
                    should_notify = False

                    if discount > 0:
                        # Notifica se nunca foi notificado OU se o preço caiu ainda mais desde a última notificação
                        if last_notified_price is None or info["current_price"] < last_notified_price:
                            should_notify = True

                    if should_notify:
                        guild = client.get_guild(game["guild_id"])
                        if guild:
                            channel = guild.get_channel(game["channel_id"])
                            if not channel:
                                config = await db.get_guild_config(guild.id)
                                channel = find_gaming_announcement_channel(guild, config)

                            if channel and channel.permissions_for(guild.me).send_messages:
                                embed = discord.Embed(
                                    title=f"🔥 Promoção Detectada: {info['game_name']}!",
                                    description=(
                                        f"O jogo sugerido está com **-{discount}% de desconto**!\n\n"
                                        f"💵 **Preço Atual:** R$ {info['current_price']:.2f} ~~(R$ {info['base_price']:.2f})~~\n"
                                        f"🛒 **Melhor Preço em:** [{info['best_store_name']}]({info['best_store_url']})\n"
                                    ),
                                    color=discord.Color.gold()
                                )
                                if info["historical_low_price"] > 0 and info["current_price"] <= info["historical_low_price"]:
                                    embed.description += "⭐ **ATENÇÃO: Este é o MENOR PREÇO HISTÓRICO registrado!**\n"
                                if info.get("header_image_url"):
                                    embed.set_image(url=info["header_image_url"])

                                embed.set_footer(text="Monitor de Ofertas Steam | BMIA")
                                try:
                                    target_msg = None
                                    if game.get("message_id"):
                                        try:
                                            target_msg = await channel.fetch_message(game["message_id"])
                                        except Exception:
                                            target_msg = None

                                    if target_msg:
                                        await target_msg.reply(embed=embed, mention_author=True)
                                    else:
                                        suggester_mention = f"<@{game['suggested_by_id']}> " if game.get("suggested_by_id") and game["suggested_by_id"] > 0 else ""
                                        await channel.send(content=suggester_mention if suggester_mention else None, embed=embed)
                                    await db.mark_tracked_game_notified(game["id"], info["current_price"])
                                except Exception as send_err:
                                    logger.warning(f"Erro ao enviar alerta de promoção para {game['game_name']}: {send_err}")
                    
                    # Pausa rápida entre consultas para respeitar rate limits
                    await asyncio.sleep(2)
        except Exception as exc:
            logger.error("❌ Erro no loop de monitoramento de promoções de jogos: %s", exc)
        await asyncio.sleep(1800)

