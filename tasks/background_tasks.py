# tasks/background_tasks.py — Tarefas em Segundo Plano
"""
Todas as tarefas assíncronas periódicas extraídas do main.py.
Cada função recebe via parâmetro os managers necessários (sem variáveis globais).
"""

import asyncio
import logging
import traceback

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

                    # Verifica e envia Pódio Anual e Destaques (se virou o ano)
                    if now.month == 1:
                        if not await db.check_periodic_leaderboard_sent(guild.id, "YEARLY", yearly_identifier):
                            logger.info("Gerando pódio anual e destaques (%s) para %s...", yearly_identifier, guild.name)
                            top_yearly = await db.get_top_users_date_range(guild.id, yearly_start, yearly_end, limit=10)

                            if top_yearly:
                                builder = PodiumBuilder()
                                image_bio = await builder.generate_podium(guild, top_yearly, period_text=yearly_label)
                                file = discord.File(fp=image_bio, filename="podium_anual.png")
                                await target_channel.send(
                                    f"**{yearly_title}**\nParabéns às lendas do servidor em {prev_year}! 🏆👑",
                                    file=file,
                                )

                            # Envia também a galeria de Destaques do Ano
                            try:
                                from utils.image_generator import HighlightsBuilder
                                from commands.stats_commands import HIGHLIGHTS_CATEGORIES

                                h_data = await db.get_annual_highlights_data(guild.id, prev_year)
                                h_files = await HighlightsBuilder.generate_all_slides_files(
                                    guild=guild,
                                    year=prev_year,
                                    highlights_data=h_data,
                                    top_clip=None,
                                    categories=HIGHLIGHTS_CATEGORIES
                                )
                                if h_files:
                                    await target_channel.send(
                                        f"🌟 **DESTAQUES DO ANO {prev_year} • {guild.name}**\n*Confira os maiores recordes e destaques da comunidade:*",
                                        files=h_files
                                    )
                            except Exception as h_err:
                                logger.warning("Erro ao enviar galeria de destaques no background: %s", h_err)

                            await db.log_periodic_leaderboard_sent(guild.id, "YEARLY", yearly_identifier)
                            logger.info("✅ Pódio e destaques anuais concluídos para %s", guild.name)

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
