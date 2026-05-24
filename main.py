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
from commands.stats_commands import StatsCommands
from commands.role_commands import RoleCommands
from commands.giveaway_commands import GiveawayCommands
from commands.moderation_commands import ModerationCommands
from commands.games_commands import GamesCommands
from commands.info_commands import InfoCommands
from commands.context_commands import ContextCommands
from commands.config_commands import ConfigCommands
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

        # Carrega configuração de canais/cargos do banco (se existir)
        for guild in client.guilds:
            guild_config = await ctx.db.get_guild_config(guild.id)
            if guild_config:
                if guild_config.get("allowed_channels"):
                    ctx.allowed_channels = guild_config["allowed_channels"]
                if guild_config.get("ignored_voice_channels"):
                    ctx.ignored_voice_channels = guild_config["ignored_voice_channels"]
                if guild_config.get("dynamic_roles_config"):
                    ctx.dynamic_roles_config = guild_config["dynamic_roles_config"]

        # Fallback para defaults se banco não tiver configuração
        if not ctx.allowed_channels:
            ctx.allowed_channels = list(DEFAULT_ALLOWED_CHANNELS)
        if not ctx.ignored_voice_channels:
            ctx.ignored_voice_channels = list(DEFAULT_IGNORED_VOICE_CHANNELS)
        if not ctx.dynamic_roles_config:
            ctx.dynamic_roles_config = dict(DEFAULT_DYNAMIC_ROLES_CONFIG)

        # Registra slash commands
        client.tree.add_command(StatsCommands(ctx.db, ctx.leaderboard_updater))
        client.tree.add_command(RoleCommands(ctx.db, ctx.role_manager))
        client.tree.add_command(GiveawayCommands(ctx.db, ctx.giveaway_manager))
        client.tree.add_command(ModerationCommands(ctx.db))
        client.tree.add_command(GamesCommands(ctx.db))
        client.tree.add_command(InfoCommands())
        client.tree.add_command(ConfigCommands(ctx.db, ctx))
        if ctx.memory_manager:
            client.tree.add_command(ContextCommands(ctx.db, ctx.memory_manager))

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

        await ctx.points_manager.recover_sessions()

        logger.info("📊 Sistema de estatísticas ativado!")
        logger.info("🏅 Sistema de cargos automáticos ativado!")
        logger.info("🎉 Sistema de sorteios ativado!")
        logger.info("🎮 Sistema de rastreamento de jogos ativado!")

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
    if ctx.leaderboard_updater:
        loop.create_task(ctx.leaderboard_updater.start_loop())


# ── Inicialização ─────────────────────────────────────────────────────────────
try:
    client.run(DISCORD_TOKEN)
finally:
    if ctx.db:
        asyncio.run(ctx.db.disconnect())