# main.py ??? Ponto de entrada do Bot BMIA
# Bot H??brido: Modera????o com IA + Estat??sticas + Cargos + Sorteios + Jogos
#
# Estrutura do projeto:
#   config.py                  ??? vari??veis de ambiente, constantes, timezone
#   events/discord_events.py   ??? handlers de eventos Discord + BotContext
#   tasks/background_tasks.py  ??? tarefas peri??dicas (cargos, p??dio, resumos???)
#   tasks/moderation.py        ??? modera????o por IA em lote
#   commands/                  ??? slash commands
#   utils/                     ??? managers (points, roles, giveaway???)
#   database.py                ??? camada de dados PostgreSQL

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

# ?????? Configura????o inicial ?????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
setup_logging()
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

# ?????? Cliente Discord ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
class BMIAClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
        self.ctx = BotContext()
        self.ctx.telegram = TelegramNotifier()
        self.tree.on_error = self.on_tree_error

    async def on_tree_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError) -> None:
        """Trata erros globais dos comandos de barra da Tree."""
        if isinstance(error, discord.app_commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.NotFound) and getattr(original, "code", None) == 10062:
                cmd_name = interaction.command.name if interaction.command else "desconhecido"
                logger.warning("Interação do comando '%s' expirou antes do defer/resposta (10062 Unknown Interaction).", cmd_name)
                return
            if isinstance(original, discord.InteractionResponded):
                cmd_name = interaction.command.name if interaction.command else "desconhecido"
                logger.debug("Interação do comando '%s' já havia sido respondida.", cmd_name)
                return

        cmd_name = interaction.command.name if interaction.command else "desconhecido"
        logger.error("Erro não tratado no comando '%s': %s", cmd_name, error, exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro ao processar este comando.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Ocorreu um erro ao processar este comando.", ephemeral=True)
        except Exception:
            pass

    # setup_hook e chamado UMA VEZ antes do gateway (correto para registrar commands e tasks)
    async def setup_hook(self) -> None:
        # Registra event handlers
        register_events(self, self.ctx)

        import os
        dashboard_url = os.getenv("DASHBOARD_URL") or os.getenv("DASHBOARD_RENDER_URL")
        render_secret = os.getenv("INTERNAL_RENDER_SECRET") or os.getenv("NEXTAUTH_SECRET")
        if dashboard_url:
            if render_secret:
                logger.info("✅ Vercel Dashboard configurada: %s", dashboard_url)
            else:
                logger.warning("DASHBOARD_URL presente, mas INTERNAL_RENDER_SECRET ausente. A Vercel pode falhar.")
        else:
            logger.warning("DASHBOARD_URL ausente no .env! O bot renderizara localmente.")

        if not DATABASE_URL:
            logger.warning("DATABASE_URL nao configurada. Funcionalidades extras desativadas.")
            return

        try:
            # Banco de dados
            self.ctx.db = Database(DATABASE_URL)
            await self.ctx.db.connect()

            # Managers
            self.ctx.stats_collector     = StatsCollector(self.ctx.db)
            self.ctx.role_manager        = RoleManager(self.ctx.db, self.ctx.ignored_voice_channels)
            self.ctx.role_manager.telegram = self.ctx.telegram
            self.ctx.giveaway_manager    = GiveawayManager(self.ctx.db)
            self.ctx.giveaway_manager.telegram = self.ctx.telegram
            self.ctx.activity_tracker    = ActivityTracker(self.ctx.db)
            self.ctx.embed_sender        = EmbedSender(self.ctx.db)
            self.ctx.points_manager      = PointsManager(self.ctx.db, self.ctx.ignored_voice_channels)
            self.ctx.spam_detector       = SpamDetector()
            self.ctx.event_monitor       = EventMonitor(self.ctx.db)
            self.ctx.leaderboard_updater = LeaderboardUpdater(self, self.ctx.db)
            self.ctx.media_manager       = MediaManager(self.ctx.db)
            self.ctx.chat_handler        = ChatHandler(
                api_key=GEMINI_CHAT_API_KEY or GEMINI_API_KEY,
                model_name=GEMINI_CHAT_MODEL,
            )
            self.ctx.rawg_client         = RawgClient(api_key=RAWG_API_KEY)
            self.ctx.giphy_client        = GiphyClient(api_key=GIPHY_API_KEY)
            self.ctx.gg_deals_client     = GGDealsClient()

            if MemoryManager:
                self.ctx.memory_manager = MemoryManager(self.ctx.db, self.ctx.chat_handler)
            else:
                logger.warning("MemoryManager nao disponivel.")

            if StatsAnalyzer:
                self.ctx.stats_analyzer = StatsAnalyzer(self.ctx.db)
            else:
                logger.warning("StatsAnalyzer nao disponivel.")

            # Slash Commands
            self.tree.add_command(StatsCommands(self.ctx.db, self.ctx.leaderboard_updater, self.ctx.points_manager))
            self.tree.add_command(RoleCommands(self.ctx.db, self.ctx.role_manager))
            self.tree.add_command(GiveawayCommands(self.ctx.db, self.ctx.giveaway_manager))
            self.tree.add_command(ModerationCommands(self.ctx.db))
            self.tree.add_command(ReputationCommands(self.ctx.db))
            self.tree.add_command(report_user_command)
            self.tree.add_command(report_message_context)
            self.tree.add_command(report_user_context)
            self.tree.add_command(GamesCommands(self.ctx.db))
            self.tree.add_command(SteamCommands(self.ctx.db))
            self.tree.add_command(TrackedGamesCommands(self.ctx.db, self.ctx.gg_deals_client))
            setup_rawg_slash_command(self.tree, self.ctx.rawg_client)
            setup_gif_slash_command(self.tree, self.ctx.giphy_client)
            self.tree.add_command(InfoCommands())
            self.tree.add_command(ConfigCommands(self.ctx.db, self.ctx))
            self.tree.add_command(TournamentCommands(self.ctx.db, self.ctx.points_manager))

            if self.ctx.memory_manager:
                self.tree.add_command(ContextCommands(self.ctx.db, self.ctx.memory_manager))

            @self.tree.command(name="rank", description="Exibe o seu Rank Card ou de outro membro (XP e Nivel)")
            @discord.app_commands.describe(membro="Membro que deseja visualizar o Rank Card (opcional)")
            async def rank_slash(interaction: discord.Interaction, membro: discord.Member | None = None):
                await handle_rank_card(self.ctx.db, interaction, membro)

            @self.tree.command(name="perfil", description="Exibe o seu perfil com Rank Card de XP e Nivel")
            @discord.app_commands.describe(membro="Membro que deseja visualizar o perfil (opcional)")
            async def perfil_slash(interaction: discord.Interaction, membro: discord.Member | None = None):
                await handle_rank_card(self.ctx.db, interaction, membro)

            @self.tree.command(name="destaques", description="Mostra a Retrospectiva e os Destaques do Ano do Servidor em Galeria Visual")
            @discord.app_commands.describe(ano="Ano dos destaques para consulta (padrao: ano atual)")
            async def destaques_slash(interaction: discord.Interaction, ano: int | None = None):
                await handle_highlights_gallery(self.ctx.db, interaction, ano)

            pending = [cmd.name for cmd in self.tree.get_commands()]
            logger.info("Commands pending sync: %s", pending)
            await self.tree.sync()

            # Background Tasks - registradas UMA vez aqui (nao em on_ready)
            loop = asyncio.get_event_loop()
            loop.create_task(processador_em_lote(self.ctx.buffer_mensagens, self.ctx.db, self.ctx.points_manager, self.ctx.telegram), name="bmia-moderacao-em-lote")
            loop.create_task(bg.collect_server_stats(self, self.ctx.db), name="bmia-collect-stats")
            loop.create_task(bg.check_roles_periodically(self, self.ctx.role_manager, self.ctx.dynamic_roles_config), name="bmia-check-roles")
            loop.create_task(bg.check_expired_giveaways(self, self.ctx.db, self.ctx.giveaway_manager), name="bmia-giveaways")
            loop.create_task(bg.check_embed_queue(self, self.ctx.db, self.ctx.embed_sender), name="bmia-embed-queue")
            loop.create_task(bg.check_monthly_podium(self, self.ctx.db, self.ctx.allowed_channels), name="bmia-monthly-podium")
            loop.create_task(bg.check_context_stats(self, self.ctx.stats_analyzer), name="bmia-context-stats")
            loop.create_task(bg.send_daily_summary(self, self.ctx.db, self.ctx.telegram, self.ctx.giveaway_manager), name="bmia-daily-summary")
            loop.create_task(bg.weekly_games_report(self, self.ctx.db, self.ctx.telegram), name="bmia-weekly-games")
            loop.create_task(bg.check_voice_points_periodically(self, self.ctx.points_manager), name="bmia-voice-points")
            loop.create_task(bg.check_steam_seasonal_events_periodically(self, self.ctx.db), name="bmia-steam-events")
            loop.create_task(bg.check_tracked_game_deals_periodically(self, self.ctx.db, getattr(self.ctx, "gg_deals_client", None)), name="bmia-game-deals")

            if self.ctx.leaderboard_updater:
                loop.create_task(self.ctx.leaderboard_updater.start_loop(), name="bmia-leaderboard")

            logger.info("setup_hook: todos os sistemas inicializados com sucesso.")

        except Exception as exc:
            logger.error("Erro em setup_hook ao inicializar sistemas: %s", exc)
            import traceback; traceback.print_exc()
            logger.warning("Bot continuara apenas com moderacao basica.")


    async def on_ready(self) -> None:
        """
        Disparado sempre que o bot (re)conecta ao gateway.
        Apenas operacoes que requerem guilds: sync de membros/canais, views, seeds.
        Managers e tasks ja foram inicializados no setup_hook.
        """
        logger.info("Bot conectado como %s!", self.user)

        if not self.ctx.db:
            logger.warning("Banco de dados nao inicializado.")
            await self.ctx.telegram.log_bot_ready(str(self.user), len(self.guilds))
            return

        try:
            for guild in self.guilds:
                await self.ctx.get_guild_config(guild.id, refresh=True)

            for guild in self.guilds:
                try:
                    active_tourneys = await self.ctx.db.get_active_tournaments(guild.id)
                    for t in active_tourneys:
                        self.add_view(TournamentRegistrationView(self.ctx.db, t["id"]))
                except Exception as tourney_view_err:
                    logger.debug("Erro ao recuperar views de torneio: %s", tourney_view_err)

            self.ctx.invite_tracker = InviteTracker(self)
            await self.ctx.invite_tracker.initialize()

            for guild in self.guilds:
                await self.ctx.role_manager.sync_existing_members(guild)
                logger.info("Membros sincronizados em %s", guild.name)

                count = 0
                for channel in guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel)):
                        await self.ctx.db.upsert_channel(channel.id, channel.name, str(channel.type), guild.id)
                        count += 1
                logger.info("%d canais sincronizados em %s", count, guild.name)

                if self.ctx.event_monitor:
                    asyncio.get_event_loop().create_task(
                        self.ctx.event_monitor.sync_all_guild_events(guild),
                        name=f"bmia-event-sync-{guild.id}"
                    )

            INITIAL_SEED_GAMES = [2680010, 2322010, 892970, 2358720, 814380, 2651280, 1817190]
            for guild in self.guilds:
                try:
                    existing_games = await self.ctx.db.get_tracked_games(guild.id)
                    if not existing_games:
                        target_ch_id = (
                            self.ctx.allowed_channels[0]
                            if self.ctx.allowed_channels
                            else (guild.text_channels[0].id if guild.text_channels else 0)
                        )
                        for appid in INITIAL_SEED_GAMES:
                            info = await self.ctx.gg_deals_client.get_game_info(appid)
                            if info:
                                await self.ctx.db.add_tracked_game(
                                    guild_id=guild.id, channel_id=target_ch_id, message_id=None,
                                    steam_appid=info["steam_appid"], game_name=info["game_name"],
                                    suggested_by_id=self.user.id if self.user else 0,
                                    base_price=info["base_price"], current_price=info["current_price"],
                                    discount_percent=info["discount_percent"],
                                    historical_low_price=info["historical_low_price"],
                                    best_store_name=info["best_store_name"], best_store_url=info["best_store_url"],
                                    header_image_url=info["header_image_url"], gg_deals_url=info["gg_deals_url"]
                                )
                        logger.info("Seed inicial de jogos para %s.", guild.name)
                except Exception as seed_err:
                    logger.warning("Erro no seed para %s: %s", guild.name, seed_err)

            await self.ctx.points_manager.recover_sessions()

        except Exception as exc:
            logger.error("Erro em on_ready: %s", exc)
            import traceback; traceback.print_exc()

        await self.ctx.telegram.log_bot_ready(str(self.user), len(self.guilds))
        logger.info("Bot totalmente pronto!")
        logger.info("-" * 40)


client = BMIAClient(intents=create_intents())

try:
    client.run(DISCORD_TOKEN)
finally:
    if client.ctx.db:
        try:
            asyncio.run(client.ctx.db.disconnect())
        except RuntimeError:
            pass
