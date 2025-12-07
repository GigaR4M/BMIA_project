# main.py - BOT HÍBRIDO: MODERAÇÃO COM IA + ESTATÍSTICAS + CARGOS + SORTEIOS + JOGOS

# --- 1. Importações ---
import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
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
from commands.games_commands import GamesCommands
from utils.role_manager import RoleManager
from utils.giveaway_manager import GiveawayManager
from utils.activity_tracker import ActivityTracker
from utils.embed_sender import EmbedSender
from utils.points_manager import PointsManager
from utils.spam_detector import SpamDetector
from utils.event_monitor import EventMonitor

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

# Configura a API do Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash-lite")

# Variáveis Globais
db = None
stats_collector = None
role_manager = None
giveaway_manager = None
activity_tracker = None
embed_sender = None
points_manager = None
spam_detector = None
event_monitor = None
buffer_mensagens = []
INTERVALO_ANALISE = 60
TAMANHO_LOTE_MINIMO = 10

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
    """Verifica e atribui cargos automáticos periodicamente."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            if role_manager:
                for guild in client.guilds:
                    assigned = await role_manager.check_all_members(guild)
                    if assigned > 0:
                        logger.info(f"🏅 {assigned} cargos atribuídos em {guild.name}")
        except Exception as e:
            logger.error(f"❌ Erro ao verificar cargos: {e}")
        
        # Verifica a cada 1 hora
        await asyncio.sleep(3600)

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

    except Exception as e:
        print("\n!!! OCORREU UM ERRO NA ANÁLISE EM LOTE !!!")
        traceback.print_exc()
        return ["NÃO"] * len(lista_de_mensagens)

async def processador_em_lote():
    """Processa mensagens em lotes para moderação por IA."""
    while True:
        await asyncio.sleep(INTERVALO_ANALISE)
        if len(buffer_mensagens) >= TAMANHO_LOTE_MINIMO:
            mensagens_para_analise = buffer_mensagens[:TAMANHO_LOTE_MINIMO]
            buffer_mensagens[:] = buffer_mensagens[TAMANHO_LOTE_MINIMO:]
            
            vereditos = await analisar_lote_com_ia(mensagens_para_analise)
            
            for msg, veredito in zip(mensagens_para_analise, vereditos):
                if veredito == "SIM":
                    try:
                        await msg.delete()
                        await msg.channel.send(f"⚠️ Mensagem de {msg.author.mention} removida por conter linguagem inadequada.", delete_after=10)
                        await db.update_message_moderation_status(msg.id, True)
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
async def on_ready():
    global db, stats_collector, role_manager, giveaway_manager, activity_tracker, embed_sender, points_manager, spam_detector, event_monitor
    
    print(f'🤖 Bot conectado como {client.user}!')
    print(f'🛡️  Moderação: Análise em lotes a cada {INTERVALO_ANALISE} segundos')
    
    # Inicializa banco de dados e sistemas
    if DATABASE_URL:
        try:
            db = Database(DATABASE_URL)
            await db.connect()
            stats_collector = StatsCollector(db)
            
            # Inicializa novos gerenciadores
            role_manager = RoleManager(db)
            giveaway_manager = GiveawayManager(db)
            activity_tracker = ActivityTracker(db)
            embed_sender = EmbedSender(db)
            points_manager = PointsManager(db)
            spam_detector = SpamDetector()
            event_monitor = EventMonitor(db)
            
            # Registra comandos
            client.tree.add_command(StatsCommands(db))
            client.tree.add_command(RoleCommands(db, role_manager))
            client.tree.add_command(GiveawayCommands(db, giveaway_manager))
            client.tree.add_command(GamesCommands(db))
            
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
    client.loop.create_task(processador_em_lote())
    client.loop.create_task(collect_server_stats())
    client.loop.create_task(check_roles_periodically())
    client.loop.create_task(check_expired_giveaways())
    client.loop.create_task(check_embed_queue())

@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Verifica Spam
    if spam_detector and spam_detector.is_spam(message.author.id):
        return

    # Adiciona pontos se estiver em canal permitido
    ALLOWED_CHANNELS = [
        1327836428524191765, # chat-principal
        1327836428524191766, # sugestao-de-jogos
        1327836428524191767, # mensagens-aleatorias
        1335674852681453650  # prints-e-clips
    ]
    if points_manager and message.channel.id in ALLOWED_CHANNELS:
        await points_manager.add_points(message.author.id, 1, 'message', message.author.name, message.author.discriminator)

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
        user = client.get_user(payload.user_id)
        username = user.name if user else "Unknown"
        discriminator = user.discriminator if user else "0000"
        await points_manager.add_points(payload.user_id, 1, 'reaction', username, discriminator)

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
    if points_manager:
        # Se começou a jogar algo
        if not before.activity and after.activity:
            points_manager.start_activity_session(after.id)
        # Se parou de jogar
        elif before.activity and not after.activity:
            await points_manager.end_activity_session(after.id)

@client.event
async def on_voice_state_update(member, before, after):
    """Rastreia atividade de voz para estatísticas."""
    if stats_collector:
        await stats_collector.on_voice_state_update(member, before, after)
    
    # Rastreia compartilhamento de tela (Go Live)
    if activity_tracker:
        await activity_tracker.on_voice_state_update(member, before, after)
    
    # Rastreia tempo de voz para pontos
    if points_manager:
        # Canais ignorados (Três mosqueteiros, AFK)
        IGNORED_VOICE_CHANNELS = [1356045946743689236, 1335352978986635468]
        
        # Entrou em canal de voz (e não é ignorado)
        if after.channel and after.channel.id not in IGNORED_VOICE_CHANNELS:
            if not before.channel: # Entrou agora
                points_manager.start_voice_session(member.id)
            elif before.channel.id in IGNORED_VOICE_CHANNELS: # Veio de canal ignorado
                points_manager.start_voice_session(member.id)
        
        # Saiu de canal de voz (ou foi para ignorado)
        if before.channel and (not after.channel or after.channel.id in IGNORED_VOICE_CHANNELS):
             if before.channel.id not in IGNORED_VOICE_CHANNELS:
                await points_manager.end_voice_session(member.id)

# --- 7. Inicialização do Bot E DO SERVIDOR WEB ---
keep_alive()  # Inicia o servidor web em segundo plano

try:
    client.run(DISCORD_TOKEN)  # Inicia o bot
finally:
    # Cleanup: fecha conexão com banco de dados
    if db:
        asyncio.run(db.disconnect())