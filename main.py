# main.py — Ponto de entrada do Bot BMIA
# Bot Híbrido: Moderação com IA + Estatísticas + Cargos + Sorteios + Jogos
#
# Estrutura do projeto:
#   config.py                  → variáveis de ambiente, constantes, timezone
#   events/discord_events.py   → handlers de eventos Discord + BotContext
#   tasks/background_tasks.py  → tarefas periódicas (cargos, pódio, resumos…)
#   tasks/moderation.py        → moderação por IA em lote
#   commands/                  → slash commands
#   utils/                     → managers (points, roles, giveaway…)
#   database.py                → camada de dados PostgreSQL

import asyncio
import logging
import traceback

import discord
import google.generativeai as genai

from config import (
    DISCORD_TOKEN,
    GEMINI_API_KEY,
    DATABASE_URL,
    RAWG_API_KEY,
    GIPHY_API_KEY,
    GEMINI_CHAT_API_KEY,
    GEMINI_CHAT_MODEL,
    DEFAULT_ALLOWED_CHANNELS,
    DEFAULT_IGNORED_VOICE_CHANNELS,
    DEFAULT_DYNAMIC_ROLES_CONFIG,
    setup_logging,
    create_intents,
)
from events.discord_events import BotContext, register_events
from tasks import background_tasks as bg
from tasks.moderation import processador_em_lote

from database import Database
from stats_collector import StatsCollector
from commands.stats_commands import StatsCommands, handle_rank_card, handle_highlights_gallery
from commands.role_commands import RoleCommands
from commands.giveaway_commands import GiveawayCommands
from commands.moderation_commands import ModerationCommands
from commands.games_commands import GamesCommands
from commands.rawg_commands import RawgCommands, setup_rawg_slash_command
from commands.gif_commands import setup_gif_slash_command
from commands.info_commands import InfoCommands
from commands.context_commands import ContextCommands
from commands.config_commands import ConfigCommands
from commands.tournament_commands import TournamentCommands, TournamentRegistrationView
from commands.reputation_commands import ReputationCommands, report_user_command, report_message_context, report_user_context
from commands.deals_commands import SteamCommands, TrackedGamesCommands
from utils.gg_deals_client import GGDealsClient
from utils.invite_tracker import InviteTracker
from utils.role_manager import RoleManager
from utils.giveaway_manager import GiveawayManager
from utils.activity_tracker import ActivityTracker
from utils.embed_sender import EmbedSender
from utils.points_manager import PointsManager
from utils.spam_detector import SpamDetector
from utils.event_monitor import EventMonitor
from utils.leaderboard_updater import LeaderboardUpdater
from utils.chat_handler import ChatHandler
from utils.telegram_notifier import TelegramNotifier
from utils.rawg_client import RawgClient
from utils.media_manager import MediaManager
from utils.giphy_client import GiphyClient

try:
    from utils.memory_manager import MemoryManager
except ImportError:
    MemoryManager = None  # type: ignore[assignment, misc]

try:
    from utils.stats_analyzer import StatsAnalyzer
except ImportError:
    StatsAnalyzer = None  # type: ignore[assignment, misc]

# ── Configuração inicial ───────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# ── Cliente Discord ────────────────────────────────────────────────────────────
class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)


client = MyClient(intents=create_intents())

# ── Contexto global do bot (substitui variáveis globais soltas) ────────────────
ctx = BotContext()
ctx.telegram = TelegramNotifier()

# Registra todos os event handlers (exceto on_ready, que fica abaixo)
register_events(client, ctx)


# ── on_ready ──────────────────────────────────────────────────────────────────
@client.event
async def on_ready() -> None:
    logger.info("🤖 Bot conectado como %s!", client.user)
    logger.info("🛡️  Moderação: análise em lotes ativada.")

    if not DATABASE_URL:
        logger.warning("⚠️  DATABASE_URL não configurada. Funcionalidades extras desativadas.")
        await ctx.telegram.log_bot_ready(str(client.user), len(client.guilds))
        return

    try:
        ctx.db = Database(DATABASE_URL)
        await ctx.db.connect()

        ctx.stats_collector = StatsCollector(ctx.db)
        ctx.role_manager = RoleManager(ctx.db, ctx.ignored_voice_channels)
        ctx.role_manager.telegram = ctx.telegram
        ctx.giveaway_manager = GiveawayManager(ctx.db)
        ctx.giveaway_manager.telegram = ctx.telegram
        ctx.activity_tracker = ActivityTracker(ctx.db)
        ctx.embed_sender = EmbedSender(ctx.db)
        ctx.points_manager = PointsManager(ctx.db, ctx.ignored_voice_channels)
        ctx.spam_detector = SpamDetector()
        ctx.event_monitor = EventMonitor(ctx.db)
        ctx.leaderboard_updater = LeaderboardUpdater(client, ctx.db)
        ctx.media_manager = MediaManager(ctx.db)
        ctx.chat_handler = ChatHandler(
            api_key=GEMINI_CHAT_API_KEY or GEMINI_API_KEY,
            model_name=GEMINI_CHAT_MODEL,
        )

        if MemoryManager:
            ctx.memory_manager = MemoryManager(ctx.db, ctx.chat_handler)
        else:
            logger.warning("MemoryManager não disponível.")

        if StatsAnalyzer:
            ctx.stats_analyzer = StatsAnalyzer(ctx.db)
        else:
            logger.warning("StatsAnalyzer não disponível.")

        ctx.invite_tracker = InviteTracker(client)
        await ctx.invite_tracker.initialize()
        ctx.rawg_client = RawgClient(api_key=RAWG_API_KEY)
        ctx.giphy_client = GiphyClient(api_key=GIPHY_API_KEY)
        ctx.gg_deals_client = GGDealsClient()

        # Pré-carrega cache de configuração para cada servidor conectado
        for guild in client.guilds:
            await ctx.get_guild_config(guild.id, refresh=True)

        # Associa ctx ao client para handlers e views acessarem
        client.ctx = ctx

        # Registra slash commands
        client.tree.add_command(StatsCommands(ctx.db, ctx.leaderboard_updater, ctx.points_manager))
        client.tree.add_command(RoleCommands(ctx.db, ctx.role_manager))
        client.tree.add_command(GiveawayCommands(ctx.db, ctx.giveaway_manager))
        client.tree.add_command(ModerationCommands(ctx.db))
        client.tree.add_command(ReputationCommands(ctx.db))
        client.tree.add_command(report_user_command)
        client.tree.add_command(report_message_context)
        client.tree.add_command(report_user_context)
        client.tree.add_command(GamesCommands(ctx.db))
        client.tree.add_command(SteamCommands(ctx.db))
        client.tree.add_command(TrackedGamesCommands(ctx.db, ctx.gg_deals_client))
        setup_rawg_slash_command(client.tree, ctx.rawg_client)
        setup_gif_slash_command(client.tree, ctx.giphy_client)
        client.tree.add_command(InfoCommands())
        client.tree.add_command(ConfigCommands(ctx.db, ctx))
        client.tree.add_command(TournamentCommands(ctx.db, ctx.points_manager))
        if ctx.memory_manager:
            client.tree.add_command(ContextCommands(ctx.db, ctx.memory_manager))

        @client.tree.command(name="rank", description="Exibe o seu Rank Card ou de outro membro (XP e Nível)")
        @discord.app_commands.describe(membro="Membro que deseja visualizar o Rank Card (opcional)")
        async def rank_slash(interaction: discord.Interaction, membro: discord.Member | None = None):
            await handle_rank_card(ctx.db, interaction, membro)

        @client.tree.command(name="perfil", description="Exibe o seu perfil com Rank Card de XP e Nível")
        @discord.app_commands.describe(membro="Membro que deseja visualizar o perfil (opcional)")
        async def perfil_slash(interaction: discord.Interaction, membro: discord.Member | None = None):
            await handle_rank_card(ctx.db, interaction, membro)

        @client.tree.command(name="destaques", description="Mostra a Retrospectiva e os Destaques do Ano do Servidor em Galeria Visual")
        @discord.app_commands.describe(ano="Ano dos destaques para consulta (padrão: ano atual)")
        async def destaques_slash(interaction: discord.Interaction, ano: int | None = None):
            await handle_highlights_gallery(ctx.db, interaction, ano)

        # Registra persistent views para torneios ativos (para botões continuarem funcionando)
        for guild in client.guilds:
            try:
                active_tourneys = await ctx.db.get_active_tournaments(guild.id)
                for t in active_tourneys:
                    client.add_view(TournamentRegistrationView(ctx.db, t["id"]))
            except Exception as tourney_view_err:
                logger.debug(f"Erro ao recuperar views de torneio: {tourney_view_err}")

        pending = [cmd.name for cmd in client.tree.get_commands()]
        logger.info("📋 Commands pending sync: %s", pending)
        await client.tree.sync()

        # Sincroniza membros e canais em cada guild
        for guild in client.guilds:
            await ctx.role_manager.sync_existing_members(guild)
            logger.info("✅ Membros sincronizados em %s", guild.name)

            count = 0
            for channel in guild.channels:
                if isinstance(
                    channel,
                    (discord.TextChannel, discord.VoiceChannel,
                     discord.StageChannel, discord.ForumChannel),
                ):
                    await ctx.db.upsert_channel(
                        channel.id, channel.name, str(channel.type), guild.id
                    )
                    count += 1
            logger.info("✅ %d canais sincronizados em %s", count, guild.name)

            if ctx.event_monitor:
                client.loop.create_task(ctx.event_monitor.sync_all_guild_events(guild))

        # Seed inicial de jogos monitorados
        INITIAL_SEED_GAMES = [
            2680010,  # The First Berserker: Khazan
            2322010,  # God of War Ragnarök
            892970,   # Valheim
            2358720,  # Black Myth: Wukong
            814380,   # Sekiro: Shadows Die Twice - GOTY Edition
            2651280,  # Marvel's Spider-Man 2
            1817190,  # Marvel's Spider-Man: Miles Morales
        ]
        for guild in client.guilds:
            try:
                existing_games = await ctx.db.get_tracked_games(guild.id)
                if not existing_games:
                    target_ch_id = ctx.allowed_channels[0] if ctx.allowed_channels else (guild.text_channels[0].id if guild.text_channels else 0)
                    for appid in INITIAL_SEED_GAMES:
                        info = await ctx.gg_deals_client.get_game_info(appid)
                        if info:
                            await ctx.db.add_tracked_game(
                                guild_id=guild.id,
                                channel_id=target_ch_id,
                                message_id=None,
                                steam_appid=info["steam_appid"],
                                game_name=info["game_name"],
                                suggested_by_id=client.user.id if client.user else 0,
                                base_price=info["base_price"],
                                current_price=info["current_price"],
                                discount_percent=info["discount_percent"],
                                historical_low_price=info["historical_low_price"],
                                best_store_name=info["best_store_name"],
                                best_store_url=info["best_store_url"],
                                header_image_url=info["header_image_url"],
                                gg_deals_url=info["gg_deals_url"]
                            )
                    logger.info(f"🌱 Seed inicial de 7 jogos cadastrado para o servidor {guild.name}.")
            except Exception as seed_err:
                logger.warning(f"Erro no seed inicial de jogos para {guild.name}: {seed_err}")

        await ctx.points_manager.recover_sessions()

        logger.info("📊 Sistema de estatísticas ativado!")
        logger.info("🏅 Sistema de cargos automáticos ativado!")
        logger.info("🎉 Sistema de sorteios ativado!")
        logger.info("🎮 Sistema de rastreamento de jogos ativado!")
        logger.info("🔥 Sistema de promoções e eventos Steam ativado!")

    except Exception as exc:
        logger.error("❌ Erro ao inicializar sistemas: %s", exc)
        traceback.print_exc()
        logger.warning("⚠️  Bot continuará apenas com moderação.")

    await ctx.telegram.log_bot_ready(str(client.user), len(client.guilds))
    logger.info("✅ Bot totalmente inicializado!")
    logger.info("-" * 40)

    # Inicia tasks em background
    loop = client.loop
    loop.create_task(processador_em_lote(ctx.buffer_mensagens, ctx.db, ctx.points_manager, ctx.telegram))
    loop.create_task(bg.collect_server_stats(client, ctx.db))
    loop.create_task(bg.check_roles_periodically(client, ctx.role_manager, ctx.dynamic_roles_config))
    loop.create_task(bg.check_expired_giveaways(client, ctx.db, ctx.giveaway_manager))
    loop.create_task(bg.check_embed_queue(client, ctx.db, ctx.embed_sender))
    loop.create_task(bg.check_monthly_podium(client, ctx.db, ctx.allowed_channels))
    loop.create_task(bg.check_context_stats(client, ctx.stats_analyzer))
    loop.create_task(bg.send_daily_summary(client, ctx.db, ctx.telegram, ctx.giveaway_manager))
    loop.create_task(bg.weekly_games_report(client, ctx.db, ctx.telegram))
    loop.create_task(bg.check_voice_points_periodically(client, ctx.points_manager))
    loop.create_task(bg.check_steam_seasonal_events_periodically(client, ctx.db))
    loop.create_task(bg.check_tracked_game_deals_periodically(client, ctx.db, getattr(ctx, 'gg_deals_client', None)))
    if ctx.leaderboard_updater:
        loop.create_task(ctx.leaderboard_updater.start_loop())


# ── Inicialização ─────────────────────────────────────────────────────────────
try:
    client.run(DISCORD_TOKEN)
finally:
    if ctx.db:
        asyncio.run(ctx.db.disconnect())