# main.py - BOT HÍBRIDO: MODERAÇÃO COM IA + ESTATÍSTICAS + CARGOS + SORTEIOS + JOGOS

# --- 1. Importações ---
import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core.exceptions import ResourceExhausted
import asyncio
import traceback
import logging
from flask import Flask
from threading import Thread
from database import Database
from stats_collector import StatsCollector
from commands.stats_commands import StatsCommands
from commands.role_commands import RoleCommands
from commands.giveaway_commands import GiveawayCommands
from commands.moderation_commands import ModerationCommands
from commands.games_commands import GamesCommands
from commands.info_commands import InfoCommands
from utils.role_manager import RoleManager
from utils.giveaway_manager import GiveawayManager
from utils.activity_tracker import ActivityTracker
from utils.embed_sender import EmbedSender
from commands.context_commands import ContextCommands
from utils.points_manager import PointsManager
from utils.spam_detector import SpamDetector
from utils.event_monitor import EventMonitor
from utils.leaderboard_updater import LeaderboardUpdater
from utils.image_generator import PodiumBuilder

from utils.chat_handler import ChatHandler
from utils.telegram_notifier import TelegramNotifier
import re

# Import Memory Manager
# Note: Ideally this should be imported from utils.memory_manager but we need to ensure the file exists and is importable.
# Assuming standard structure.
try:
    from utils.memory_manager import MemoryManager
except ImportError:
    # If not found yet (race condition in dev), define a dummy or wait.
    MemoryManager = None
    logger.warning("Could not import MemoryManager.")

try:
    from utils.stats_analyzer import StatsAnalyzer
except ImportError:
    StatsAnalyzer = None
    logger.warning("Could not import StatsAnalyzer.")

# ... existing code ...

from datetime import datetime, timedelta

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 2a. Configuração do Servidor Web (Keep-Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "Servidor do bot está ativo."

def run_flask():
    # Usa a porta 10000, padrão do Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# Carrega variáveis de ambiente
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')
GEMINI_CHAT_API_KEY = os.getenv('GEMINI_CHAT_API_KEY')
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.5-flash')

# Configura a API do Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemma-3-27b-it")

# Variáveis Globais
db = None
stats_collector = None
role_manager = None
giveaway_manager = None
activity_tracker = None
embed_sender = None
points_manager = None
embed_sender = None
points_manager = None
spam_detector = None
event_monitor = None
leaderboard_updater = None
chat_handler = None
chat_handler = None
memory_manager = None
stats_analyzer = None
telegram = TelegramNotifier()
buffer_mensagens = []
INTERVALO_ANALISE = 60
TAMANHO_LOTE_MINIMO = 10

# --- Constantes de Canais ---
ALLOWED_CHANNELS = [
    1327836428524191765, # chat-principal
    1327836428524191766, # sugestao-de-jogos
    1327836428524191767, # mensagens-aleatorias
    1335674852681453650  # prints-e-clips
]

IGNORED_VOICE_CHANNELS = [
    1356045946743689236, # Três mosqueteiros
    1335352978986635468  # AFK
]

DYNAMIC_ROLES_CONFIG = {
    'top_1': 1457429534210261167,
    'top_2': 1457429841103290643,
    'top_3': 1457430517145403547,
    'voz': 1457430624217596026,
    'streamer': 1457430749329232036,
    'mensagens': 1457430923825123440,
    'toxico': 1457430992993259695,
    'gamer': 1457431074073350215,
    'camaleao': 1457431198862282763,
    'maratonista': 1457431299374579722
}

# Configuração do Cliente do Discord
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.voice_states = True  # Necessário para estatísticas de voz
intents.members = True  # Necessário para informações de membros
intents.presences = True  # Necessário para rastrear jogos/atividades

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)

client = MyClient(intents=intents)

# --- Tarefas em Segundo Plano ---

async def collect_server_stats():
    """Coleta estatísticas do servidor periodicamente."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if db:
                for guild in client.guilds:
                    # Atualiza contagem de membros
                    await db.update_daily_member_count(guild.id, guild.member_count)
                    logger.info(f"📊 Estatísticas atualizadas para {guild.name}: {guild.member_count} membros")
        except Exception as e:
            logger.error(f"❌ Erro ao coletar estatísticas do servidor: {e}")
        
        # Espera 1 hora antes da próxima atualização
        await asyncio.sleep(3600)

async def check_roles_periodically():
    """Verifica e atribui cargos automáticos e dinâmicos periodicamente."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if role_manager:
                for guild in client.guilds:
                    # 1. Cargos Automáticos (Tempo de casa)
                    assigned = await role_manager.check_all_members(guild)
                    if assigned > 0:
                        logger.info(f"🏅 {assigned} cargos por tempo atribuídos em {guild.name}")
                    
                    # 2. Cargos Dinâmicos (Estatísticas do Ano)
                    role_manager.set_dynamic_role_ids(DYNAMIC_ROLES_CONFIG)
                    await role_manager.sync_dynamic_roles(guild)

        except Exception as e:
            logger.error(f"❌ Erro ao verificar cargos: {e}")
        
        # Verifica a cada 1 hora
        await asyncio.sleep(3600)

async def check_monthly_podium():
    """Verifica se é dia 1 e envia o podium mensal/anual."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if db:
                # Usa timezone Brasil para determinar o dia certo
                now = datetime.now() - timedelta(hours=3) # Ajuste simples UTC-3 se o servidor estiver UTC, mas melhor usar pytz se possivel. 
                # Assumindo servidor local ou UTC. Se servidor for UTC:
                # O ideal é usar datetime.now() do sistema e assumir configuração correta ou converter.
                # O código original usa: (NOW() AT TIME ZONE 'America/Sao_Paulo') no banco.
                # Vamos simplificar e usar datetime.now() local do bot.
                
                # Se for dia 1
                if now.day == 1:
                    # Determina o período
                    if now.month == 1:
                        # Podium Anual (Ano anterior)
                        period_type = 'YEARLY'
                        year = now.year - 1
                        period_identifier = str(year)
                        start_date = datetime(year, 1, 1) + timedelta(hours=3)
                        end_date = datetime(now.year, 1, 1) + timedelta(hours=3)
                        title = f"🏆 PODIUM DE {year} 🏆"
                    else:
                        # Podium Mensal (Mês anterior)
                        period_type = 'MONTHLY'
                        # Primeiro dia deste mês - 1 dia = último dia do mês anterior
                        last_month_end = now.replace(day=1) - timedelta(days=1)
                        month_num = last_month_end.month
                        year_num = last_month_end.year
                        period_identifier = f"{year_num}-{month_num:02d}"
                        start_date = last_month_end.replace(day=1) + timedelta(hours=3) # dia 1 do mês anterior
                        end_date = now.replace(day=1) + timedelta(hours=3) # dia 1 deste mês (exclusive)
                        
                        month_names = {
                            1: "JANEIRO", 2: "FEVEREIRO", 3: "MARÇO", 4: "ABRIL",
                            5: "MAIO", 6: "JUNHO", 7: "JULHO", 8: "AGOSTO",
                            9: "SETEMBRO", 10: "OUTUBRO", 11: "NOVEMBRO", 12: "DEZEMBRO"
                        }
                        title = f"🏆 PODIUM DE {month_names.get(month_num, '')}/{year_num} 🏆"

                    # Itera por todas as guilds
                    for guild in client.guilds:
                        # Verifica se já enviou
                        if not await db.check_periodic_leaderboard_sent(guild.id, period_type, period_identifier):
                            logger.info(f"Gerando podium {period_type} para {guild.name}...")
                            
                            # Busca Top 10 (era Top 3)
                            top_users = await db.get_top_users_date_range(guild.id, start_date, end_date, limit=10)
                            
                            if top_users:
                                # Gera Imagem
                                builder = PodiumBuilder()
                                image_bio = await builder.generate_podium(guild, top_users)
                                
                                # Envia no Chat Principal
                                target_channel = None
                                for channel_id in ALLOWED_CHANNELS:
                                    channel = guild.get_channel(channel_id)
                                    if channel:
                                        target_channel = channel
                                        break
                                
                                if target_channel:
                                    file = discord.File(fp=image_bio, filename="podium.png")
                                    await target_channel.send(f"**{title}**\nParabéns aos mais ativos do período! 🎉", file=file)
                                    await db.log_periodic_leaderboard_sent(guild.id, period_type, period_identifier)
                                    logger.info(f"✅ Podium enviado para {guild.name}")
                                else:
                                    logger.warning(f"⚠️ Sem canal permitido para podium em {guild.name}")
                            else:
                                # Marca como enviado para não repetir sem dados
                                await db.log_periodic_leaderboard_sent(guild.id, period_type, period_identifier)
                                logger.info(f"Sem dados para podium em {guild.name}")

        except Exception as e:
            logger.error(f"❌ Erro no check_monthly_podium: {e}")
            traceback.print_exc()
        
        # Verifica a cada 1 hora
        await asyncio.sleep(3600)

async def send_daily_summary():
    """Envia um resumo diário de atividade do servidor para o Telegram à meia-noite (BRT)."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            # Calcula quantos segundos faltam para meia-noite BRT (UTC-3)
            now_utc = datetime.utcnow()
            now_brt = now_utc - timedelta(hours=3)

            # Próxima meia-noite BRT
            next_midnight = now_brt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (next_midnight - now_brt).total_seconds()

            logger.info(f"⏰ Resumo diário em {seconds_until_midnight/3600:.1f}h (meia-noite BRT)")
            await asyncio.sleep(seconds_until_midnight)

            if not db:
                continue

            for guild in client.guilds:
                try:
                    # --- Mensagens e moderação do dia (1 dia) ---
                    stats = await db.get_server_stats(guild.id, days=1)

                    # --- Top 3 usuários mais ativos ---
                    top_users = await db.get_top_users_by_messages(guild.id, limit=3, days=1)
                    top_str = ""
                    medals = ["🥇", "🥈", "🥉"]
                    for i, u in enumerate(top_users):
                        name = u.get('username', 'Desconhecido')
                        msgs = u.get('message_count', 0)
                        top_str += f"{medals[i]} {name} — {msgs} msgs\n"
                    if not top_str:
                        top_str = "Sem dados"

                    # --- Sorteios encerrados no dia ---
                    giveaways_today = 0
                    if giveaway_manager:
                        try:
                            active = await db.get_active_giveaways(guild.id)
                            # Conta sorteios que encerraram nas últimas 24h
                            giveaways_today = len([
                                g for g in (active or [])
                                if g.get('ended') and
                                   g.get('ends_at') and
                                   (datetime.utcnow() - g['ends_at']).total_seconds() < 86400
                            ])
                        except Exception:
                            giveaways_today = 0

                    # --- Monta resumo ---
                    day_str = (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y")
                    summary = {
                        'messages_today': stats.get('total_messages', 0),
                        'active_members': stats.get('active_users', 0),
                        'moderated': stats.get('moderated_messages', 0),
                        'voice_hours': 'N/A',  # requer query extra se necessário
                        'top_user': top_str.strip(),
                        'giveaways': giveaways_today,
                        'members_total': guild.member_count,
                        'day': day_str,
                    }

                    message = (
                        f"📋 <b>Resumo Diário — {summary['day']}</b>\n"
                        f"🏠 {guild.name}\n\n"
                        f"💬 Mensagens: {summary['messages_today']}\n"
                        f"👥 Usuários ativos: {summary['active_members']}\n"
                        f"🛡️ Mensagens moderadas: {summary['moderated']}\n"
                        f"🎉 Sorteios encerrados: {summary['giveaways']}\n"
                        f"🏰 Total de membros: {summary['members_total']}\n\n"
                        f"<b>🏅 Top 3 do dia:</b>\n{summary['top_user']}"
                    )
                    await telegram.send(message)
                    logger.info(f"✅ Resumo diário enviado para Telegram — {guild.name}")

                except Exception as e:
                    logger.error(f"❌ Erro no resumo diário para {guild.name}: {e}")

        except Exception as e:
            logger.error(f"❌ Erro geral no send_daily_summary: {e}")
            await asyncio.sleep(60)  # aguarda 1 min antes de tentar calcular horário novamente

async def weekly_games_report():
    """Envia ranking semanal de jogos toda segunda-feira à meia-noite (BRT)."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            now_brt = datetime.utcnow() - timedelta(hours=3)

            # Próxima segunda-feira à meia-noite BRT
            days_until_monday = (7 - now_brt.weekday()) % 7 or 7
            next_monday = (now_brt + timedelta(days=days_until_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            seconds_to_wait = (next_monday - now_brt).total_seconds()

            logger.info(f"🎮 Relatório semanal de jogos em {seconds_to_wait/3600:.1f}h")
            await asyncio.sleep(seconds_to_wait)

            if not db:
                continue

            for guild in client.guilds:
                try:
                    games = await db.get_top_activities(guild.id, limit=5, days=7)
                    await telegram.log_top_games(guild, games, period_days=7)
                    logger.info(f"✅ Relatório semanal de jogos enviado — {guild.name}")
                except Exception as e:
                    logger.error(f"❌ Erro no relatório semanal de jogos para {guild.name}: {e}")

        except Exception as e:
            logger.error(f"❌ Erro geral no weekly_games_report: {e}")
            await asyncio.sleep(60)

async def check_expired_giveaways():
    """Verifica e finaliza sorteios expirados."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if giveaway_manager and db:
                expired = await db.get_expired_giveaways()
                for giveaway in expired:
                    await giveaway_manager.end_giveaway(giveaway['giveaway_id'], client)
                    logger.info(f"🎉 Sorteio finalizado automaticamente: {giveaway['prize']}")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar sorteios expirados: {e}")
        # Verifica a cada 30 segundos
        await asyncio.sleep(30)

async def check_embed_queue():
    """Verifica e envia embeds da fila."""
    await client.wait_until_ready()
    print("DEBUG: check_embed_queue started")
    while not client.is_closed():
        try:
            if embed_sender and db:
                # print("DEBUG: Processing embed queue...")
                await embed_sender.process_pending_requests(client)
            else:
                print(f"DEBUG: embed_sender={embed_sender}, db={db}")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar fila de embeds: {e}")
        
        # Verifica a cada 5 segundos
        await asyncio.sleep(5)

async def check_context_stats():
    """Atualiza estatísticas de contexto (ranks, jogos) periodicamente."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if stats_analyzer:
                await stats_analyzer.execute_analysis_loop(client.guilds)
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar estatísticas de contexto: {e}")
        
        # Executa a cada 6 horas (21600 segundos)
        await asyncio.sleep(21600)

async def analisar_lote_com_ia(lista_de_mensagens):
    print(f"-> Analisando um lote de {len(lista_de_mensagens)} mensagens...")
    if not lista_de_mensagens:
        return []

    try:
        prompt_para_ia = "Analise cada uma das seguintes mensagens de um chat, numeradas de 1 a N. Determine se alguma delas contém linguagem ofensiva, assédio ou discurso de ódio. Responda com o veredito para cada mensagem no formato '1:VEREDITO, 2:VEREDITO, ...'. Use 'SIM' para ofensiva e 'NÃO' para não ofensiva.\n\n"
        for i, msg in enumerate(lista_de_mensagens, 1):
            prompt_para_ia += f"{i}: \"{msg.content}\"\n"

        response = await model.generate_content_async(prompt_para_ia)
        vereditos_texto = response.text.strip().upper()
        print(f"-> Resposta da IA (lote): {vereditos_texto}")

        resultados_finais = []
        partes = vereditos_texto.split(',')
        for parte in partes:
            if "SIM" in parte:
                resultados_finais.append("SIM")
            else:
                resultados_finais.append("NÃO")

        while len(resultados_finais) < len(lista_de_mensagens):
            resultados_finais.append("NÃO")

        return resultados_finais

    except ResourceExhausted as e:
        logger.warning(f"⚠️ Cota da API do Gemini excedida. Ignorando lote de {len(lista_de_mensagens)} mensagens. Tente novamente mais tarde.")
        return ["NÃO"] * len(lista_de_mensagens)
    except Exception as e:
        print("\n!!! OCORREU UM ERRO NA ANÁLISE EM LOTE !!!")
        traceback.print_exc()
        return ["NÃO"] * len(lista_de_mensagens)

async def processador_em_lote():
    """Processa mensagens em lotes para moderação por IA, respeitando configurações por guild."""
    while True:
        await asyncio.sleep(INTERVALO_ANALISE)
        if len(buffer_mensagens) > 0:
            # Processa o que tiver no buffer, limitado ao tamanho do lote
            qtd_para_processar = min(len(buffer_mensagens), TAMANHO_LOTE_MINIMO)
            
            # Pega o chunk original
            chunk_original = buffer_mensagens[:qtd_para_processar]
            # Remove do buffer global
            buffer_mensagens[:] = buffer_mensagens[qtd_para_processar:]
            
            mensagens_filtradas = []
            
            # Cache simples para não consultar o banco repetidamente no mesmo lote
            guild_status_cache = {}

            if db:
                for msg in chunk_original:
                    if msg.guild:
                        gid = msg.guild.id
                        if gid not in guild_status_cache:
                            guild_status_cache[gid] = await db.is_ai_moderation_enabled(gid)
                        
                        if guild_status_cache[gid]:
                            mensagens_filtradas.append(msg)
                    else:
                        # Ignora DMs ou sem guild
                        pass
            else:
                # Se sem DB, assume ativado ou segurança? Melhor não processar se DB caiu
                mensagens_filtradas = chunk_original

            if not mensagens_filtradas:
                continue
            
            vereditos = await analisar_lote_com_ia(mensagens_filtradas)
            
            for msg, veredito in zip(mensagens_filtradas, vereditos):
                if veredito == "SIM":
                    try:
                        await msg.delete()
                        await msg.channel.send(f"⚠️ Mensagem de {msg.author.mention} removida por conter linguagem inadequada.", delete_after=10)
                        await db.update_message_moderation_status(msg.id, True)
                        
                        # Notifica no Telegram
                        await telegram.log_message_deleted(
                            guild=msg.guild,
                            channel=msg.channel,
                            author=msg.author,
                            content=msg.content,
                            reason="Moderação por IA"
                        )
                        
                        # Remove os pontos que o usuário ganhou por essa mensagem
                        if points_manager:
                            points_to_remove = 1
                            if len(msg.content) >= 10:
                                points_to_remove = 2
                            # Se era reply, tira +1? Difícil saber aqui sem checar msg.reference antes de deletar.
                            # Vamos simplificar e remover o base calculate.
                            if msg.reference:
                                points_to_remove += 1
                                
                            if msg.guild:
                                await points_manager.remove_points(msg.author.id, points_to_remove, msg.guild.id, "moderation_deletion")

                    except discord.Forbidden:
                        logger.warning(f"Sem permissão para deletar mensagem em {msg.channel.name}")
                    except Exception as e:
                        logger.error(f"Erro ao processar mensagem moderada: {e}")
                else:
                    await db.update_message_moderation_status(msg.id, False)

# --- Eventos do Discord ---

@client.event
async def on_scheduled_event_create(event):
    if event_monitor:
        await event_monitor.on_scheduled_event_create(event)

@client.event
async def on_scheduled_event_update(before, after):
    if event_monitor:
        await event_monitor.on_scheduled_event_update(before, after)

@client.event
async def on_scheduled_event_delete(event):
    if event_monitor:
        await event_monitor.on_scheduled_event_delete(event)

@client.event
async def on_scheduled_event_user_add(event, user):
    if event_monitor:
        await event_monitor.on_scheduled_event_user_add(event, user)

@client.event
async def on_scheduled_event_user_remove(event, user):
    if event_monitor:
        await event_monitor.on_scheduled_event_user_remove(event, user)

@client.event
async def on_member_join(member):
    await telegram.log_member_join(member)

@client.event
async def on_member_remove(member):
    await telegram.log_member_leave(member)

@client.event
async def on_ready():
    global db, stats_collector, role_manager, giveaway_manager, activity_tracker, embed_sender, points_manager, spam_detector, event_monitor, leaderboard_updater, chat_handler, memory_manager, stats_analyzer
    
    print(f'🤖 Bot conectado como {client.user}!')
    print(f'🛡️  Moderação: Análise em lotes a cada {INTERVALO_ANALISE} segundos')
    
    # Inicializa banco de dados e sistemas
    if DATABASE_URL:
        try:
            db = Database(DATABASE_URL)
            await db.connect()
            stats_collector = StatsCollector(db)
            
            # Inicializa novos gerenciadores
            role_manager = RoleManager(db, IGNORED_VOICE_CHANNELS)
            role_manager.telegram = telegram
            giveaway_manager = GiveawayManager(db)
            giveaway_manager.telegram = telegram
            activity_tracker = ActivityTracker(db)
            embed_sender = EmbedSender(db)
            points_manager = PointsManager(db, IGNORED_VOICE_CHANNELS)
            spam_detector = SpamDetector()
            event_monitor = EventMonitor(db)
            leaderboard_updater = LeaderboardUpdater(client, db)
            chat_handler = ChatHandler(api_key=GEMINI_CHAT_API_KEY or GEMINI_API_KEY, model_name=GEMINI_CHAT_MODEL)
            if MemoryManager:
                memory_manager = MemoryManager(db, chat_handler)
            else:
                logger.warning("Memory Manager not initialized because class is missing.")
            
            if StatsAnalyzer:
                stats_analyzer = StatsAnalyzer(db)
            else:
                logger.warning("Stats Analyzer not initialized.")
            
            # Registra comandos
            client.tree.add_command(StatsCommands(db, leaderboard_updater))
            client.tree.add_command(RoleCommands(db, role_manager))
            client.tree.add_command(GiveawayCommands(db, giveaway_manager))
            client.tree.add_command(ModerationCommands(db))
            client.tree.add_command(GamesCommands(db))
            client.tree.add_command(InfoCommands())
            
            if memory_manager:
                client.tree.add_command(ContextCommands(db, memory_manager))
            
            # Debug commands before sync
            pending_commands = [cmd.name for cmd in client.tree.get_commands()]
            logger.info(f"📋 Commands pending sync: {pending_commands}")
            
            await client.tree.sync()
            
            print('📊 Sistema de estatísticas ativado!')
            print('🏅 Sistema de cargos automáticos ativado!')
            print('🎉 Sistema de sorteios ativado!')
            print('🎮 Sistema de rastreamento de jogos ativado!')
            
            # Sincroniza membros existentes em todos os servidores
            for guild in client.guilds:
                await role_manager.sync_existing_members(guild)
                logger.info(f'✅ Membros sincronizados em {guild.name}')
                
                # Sincroniza canais
                count = 0
                for channel in guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel, discord.ForumChannel)):
                        channel_type = str(channel.type)
                        await db.upsert_channel(channel.id, channel.name, channel_type, guild.id)
                        count += 1
                logger.info(f'✅ {count} canais sincronizados em {guild.name}')
            
            # Recupera sessões de voz ativas
            await points_manager.recover_sessions()
            
        except Exception as e:
            logger.error(f'❌ Erro ao inicializar sistemas: {e}')
            logger.warning('⚠️  Bot continuará apenas com moderação')
    else:
        logger.warning('⚠️  DATABASE_URL não configurada. Funcionalidades extras desativadas.')
    
    print('✅ Bot totalmente inicializado!')
    print('------')
    await telegram.log_bot_ready(str(client.user), len(client.guilds))
    client.loop.create_task(processador_em_lote())
    client.loop.create_task(collect_server_stats())
    client.loop.create_task(check_roles_periodically())
    client.loop.create_task(check_expired_giveaways())
    client.loop.create_task(check_embed_queue())
    client.loop.create_task(check_monthly_podium())
    client.loop.create_task(check_context_stats())
    client.loop.create_task(send_daily_summary())
    client.loop.create_task(weekly_games_report())
    if leaderboard_updater:
        client.loop.create_task(leaderboard_updater.start_loop())
    
    # Inicia loop de verificação de pontos (voz/atividade)
    client.loop.create_task(check_voice_points_periodically())
    
async def check_voice_points_periodically():
    """Loop para verificar e atribuir pontos de voz/atividade a cada 60s."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if points_manager:
                await points_manager.execute_points_loop(client.guilds)
        except Exception as e:
            logger.error(f"❌ Erro no loop de pontos periódicos: {e}")
        
        await asyncio.sleep(60)

@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    if spam_detector and spam_detector.is_spam(message.author.id):
        return

    # Chat Response for Mentions
    if client.user.mentioned_in(message) and not message.mention_everyone:
        if chat_handler:
            async with message.channel.typing():
                try:
                    # 1. Resolver menções na mensagem atual
                    # Função auxiliar para substituir <@id> por @nome
                    def resolve_mentions_in_text(text, guild):
                        if not text or not guild: return text
                        def replace(match):
                            uid = int(match.group(1))
                            member = guild.get_member(uid)
                            return f"@{member.display_name}" if member else f"@{uid}"
                        return re.sub(r'<@!?(\d+)>', replace, text)

                    resolved_content = resolve_mentions_in_text(message.content, message.guild)

                    # 2. Obter mensagens de histórico e tratar menções nelas também
                    history_msgs = [msg async for msg in message.channel.history(limit=10, before=message)]
                    history_msgs.reverse()
                    
                    # Pré-processar histórico para resolver nomes
                    processed_history_msgs = []
                    for h_msg in history_msgs:
                        # Clona ou modifica o content apenas para o histórico da IA
                        # Hack: Substituir o content do objeto Message não é ideal, 
                        # mas format_history lê .content. Vamos criar objetos dummy ou modificar in-place (arriscado?)
                        # Melhor: ChatHandler.format_history aceitar strings ou nós fazermos o parse antes.
                        # Vamos modificar o .content no objeto da lista (não afeta o discord em si, é memória local)
                        h_msg.content = resolve_mentions_in_text(h_msg.content, message.guild)
                        processed_history_msgs.append(h_msg)

                    formatted_history = chat_handler.format_history(processed_history_msgs, client.user)
                    
                    # 3. Construir System Prompt com Contexto Avançado
                    system_instruction = "Você é o BMIA, um bot assistente." # Default
                    if memory_manager and message.guild:
                         context_block = await memory_manager.get_relevant_context(message.guild, message.author, resolved_content, mentions=message.mentions)
                         system_instruction = f"""
                         Você é o Bot Oficial do servidor {message.guild.name}.
                         Sua identidade é BMIA (Bot de Monitoramento e Inteligência Artificial).
                         
                         {context_block}
                         
                         INSTRUÇÕES GERAIS:
                         1. Responda como um membro participante do servidor, não como uma IA distante.
                         2. Use o contexto acima para personalizar sua resposta.
                         3. Não use respostas muito longas e procure manter um tom mais coloquial e menos formal.
                         4. Se houver memórias relevantes, use-as se fizer sentido.
                         """

                    # 4. Gerar resposta
                    response_text = await chat_handler.generate_response(resolved_content, history=formatted_history, system_instruction=system_instruction)
                    
                    # 5. Processamento de Memória (Background)
                    if memory_manager and message.guild:
                         client.loop.create_task(
                             memory_manager.process_message_for_memory(message.guild.id, message.author.id, resolved_content, response_text)
                         )

                    # Discord limit is 2000 chars. Helper to chunk:
                    if len(response_text) > 2000:
                        chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                        for chunk in chunks:
                            await message.reply(chunk)
                    else:
                        await message.reply(response_text)
                except Exception as e:
                    logger.error(f"Error calling ChatHandler: {e}")
                    await message.reply("Desculpe, tive um problema ao tentar responder.")

    # Adiciona pontos se estiver em canal permitido
    # Adiciona pontos se estiver em canal permitido
    if points_manager and message.channel.id in ALLOWED_CHANNELS:
        # Lógica de pontos atualizada
        points = 1
        interaction_type = 'message'
        
        # Mensagens curtas (<= 10 chars) têm limite diário de 30 pontos
        if len(message.content) <= 10:
            interaction_type = 'message_short'
            # Verifica quantos pontos já ganhou hoje com mensagens curtas
            if message.guild:
                daily_points = await db.get_daily_points(message.author.id, 'message_short', message.guild.id)
                if daily_points >= 30:
                    points = 0
                    print(f"🚫 {message.author.name} atingiu o limite diário de pontos por mensagens curtas.")
        # Mensagens longas (> 10 chars) valem 2 pontos
        else: # > 10
            points = 2
            interaction_type = 'message_long'
        
        if points > 0:
            # Bônus por resposta (Replying to someone)
            if message.reference:
                # Verifica se não é resposta para si mesmo ou bot (idealmente)
                # Como message.reference.resolved pode ser nulo se mensagem original foi deletada, usamos try/catch
                try:
                    if message.reference.cached_message:
                         ref_msg = message.reference.cached_message
                         if ref_msg.author.id != message.author.id and not ref_msg.author.bot:
                             points += 1
                    else:
                        # Se não tá no cache, assumimos que vale o ponto extra se existir ref
                        points += 1
                except:
                    pass

            if message.guild:
                await points_manager.add_points(message.author.id, points, interaction_type, message.guild.id, message.author.name, message.author.discriminator)

    # Adiciona ao buffer de moderação
    buffer_mensagens.append(message)
    print(f"Mensagem de {message.author} adicionada ao buffer (Tamanho atual: {len(buffer_mensagens)})")
    
    # Coleta estatísticas (se ativado)
    if stats_collector:
        await stats_collector.on_message(message)

@client.event
async def on_raw_reaction_add(payload):
    """Handler para reações adicionadas (sorteios e pontos)."""
    if payload.member.bot:
        return

    # Pontos por reação
    if points_manager:
        if payload.channel_id in ALLOWED_CHANNELS:
            # Ponto para quem reagiu
            user_reactor = client.get_user(payload.user_id)
            if user_reactor:
                username = user_reactor.name
                discriminator = user_reactor.discriminator
                if payload.guild_id:
                    await points_manager.add_points(payload.user_id, 1, 'reaction_given', payload.guild_id, username, discriminator)
            
            # Ponto para o autor da mensagem
            try:
                channel = client.get_channel(payload.channel_id)
                # Tenta pegar do cache ou fetch
                message = await channel.fetch_message(payload.message_id) 
                # Evita farm em si mesmo
                if message.author.id != payload.user_id:
                     if payload.guild_id:
                        await points_manager.add_points(message.author.id, 1, 'reaction_received', payload.guild_id, message.author.name, message.author.discriminator, message.author.bot)
            except Exception as e:
                logger.error(f"Erro ao dar ponto de reação para autor: {e}")

    if giveaway_manager:
        try:
            channel = client.get_channel(payload.channel_id)
            if channel:
                message = await channel.fetch_message(payload.message_id)
                reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
                if reaction:
                    await giveaway_manager.on_reaction_add(reaction, payload.member)
        except Exception as e:
            logger.error(f"❌ Erro ao processar reação: {e}")

@client.event
async def on_presence_update(before, after):
    """Rastreia mudanças de atividade/jogos."""
    if activity_tracker:
        await activity_tracker.on_presence_update(before, after)
    
    # Rastreia tempo de atividade para pontos
    # REMOVIDO: Pontos de atividade agora são verificados periodicamente em check_voice_points_periodically
    pass

@client.event
async def on_voice_state_update(member, before, after):
    """Rastreia atividade de voz para estatísticas."""
    if stats_collector:
        await stats_collector.on_voice_state_update(member, before, after)
    
    # Rastreia compartilhamento de tela (Go Live)
    if activity_tracker:
        await activity_tracker.on_voice_state_update(member, before, after)
    
    # Rastreia tempo de voz para pontos
    # REMOVIDO: Pontos de voz agora são verificados periodicamente em check_voice_points_periodically
    pass

# --- 7. Inicialização do Bot E DO SERVIDOR WEB ---
keep_alive()  # Inicia o servidor web em segundo plano

try:
    client.run(DISCORD_TOKEN)  # Inicia o bot
finally:
    # Cleanup: fecha conexão com banco de dados
    if db:
        asyncio.run(db.disconnect())