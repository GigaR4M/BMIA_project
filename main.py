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

# Importações do sistema de estatísticas
from database import Database
from stats_collector import StatsCollector
from commands.stats_commands import StatsCommands

# Importações dos novos sistemas
from utils.role_manager import RoleManager
from utils.giveaway_manager import GiveawayManager
from utils.activity_tracker import ActivityTracker
from commands.role_commands import RoleCommands
from commands.giveaway_commands import GiveawayCommands
from commands.giveaway_commands import GiveawayCommands
from commands.games_commands import GamesCommands
from utils.embed_sender import EmbedSender

# --- 2. Configuração Inicial e Constantes ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')  # Connection string do Supabase

INTERVALO_ANALISE = 15
buffer_mensagens = []

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


# Configura a API do Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash-lite")

# Configuração do Cliente do Discord
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.voice_states = True  # Necessário para estatísticas de voz
intents.members = True  # Necessário para informações de membros
intents.presences = True  # Necessário para rastrear jogos/atividades

# Usa CommandTree para suportar slash commands
class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = discord.app_commands.CommandTree(self)
    
    async def setup_hook(self):
        # Registra comandos slash
        await self.tree.sync()
        logger.info("Comandos slash sincronizados")

client = MyClient(intents=intents)

# Inicializa sistemas (serão conectados no on_ready)
db = None
stats_collector = None
role_manager = None
giveaway_manager = None
giveaway_manager = None
activity_tracker = None
embed_sender = None


# --- 4. Função de Análise com IA (Versão em Lote) ---
async def analisar_lote_com_ia(lista_de_mensagens):
    print(f"-> Analisando um lote de {len(lista_de_mensagens)} mensagens...")
    if not lista_de_mensagens:
        return []

    try:
        prompt_para_ia = "Analise cada uma das seguintes mensagens de um chat, numeradas de 1 a N. Determine se alguma delas contém linguagem ofensiva, assédio ou discurso de ódio. Responda com o veredito para cada mensagem no formato '1:VEREDITO, 2:VEREDITO, ...'. Use 'SIM' para ofensiva e 'NÃO' para não ofensiva.\\n\\n"
        for i, msg in enumerate(lista_de_mensagens, 1):
            prompt_para_ia += f"{i}: \"{msg.content}\"\\n"

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
        print("\\n!!! OCORREU UM ERRO NA ANÁLISE EM LOTE !!!")
        traceback.print_exc()
        print("-----------------------------------------\\n")
        return ["NÃO"] * len(lista_de_mensagens)


# --- 5. Eventos do Bot ---
@client.event
async def on_ready():
    global db, stats_collector, role_manager, giveaway_manager, activity_tracker
    
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
            giveaway_manager = GiveawayManager(db)
            activity_tracker = ActivityTracker(db)
            embed_sender = EmbedSender(db)
            
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
    client.loop.create_task(collect_server_stats())
    client.loop.create_task(check_roles_periodically())
    client.loop.create_task(check_expired_giveaways())
    client.loop.create_task(check_embed_queue())


@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Adiciona ao buffer de moderação
    buffer_mensagens.append(message)
    print(f"Mensagem de {message.author} adicionada ao buffer (Tamanho atual: {len(buffer_mensagens)})")
    
    # Coleta estatísticas (se ativado)
    if stats_collector:
        await stats_collector.on_message(message)


@client.event
async def on_member_join(member):
    """Registra entrada de novo membro para sistema de cargos."""
    if role_manager:
        await role_manager.register_member_join(member)


@client.event
async def on_raw_reaction_add(payload):
    """Handler para reações adicionadas (sorteios)."""
    if giveaway_manager and not payload.member.bot:
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
async def on_raw_reaction_remove(payload):
    """Handler para reações removidas (sorteios)."""
    if giveaway_manager:
        try:
            channel = client.get_channel(payload.channel_id)
            guild = client.get_guild(payload.guild_id)
            if channel and guild:
                message = await channel.fetch_message(payload.message_id)
                user = await guild.fetch_member(payload.user_id)
                if not user.bot:
                    reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
                    if reaction:
                        await giveaway_manager.on_reaction_remove(reaction, user)
        except Exception as e:
            logger.error(f"❌ Erro ao processar remoção de reação: {e}")


@client.event
async def on_presence_update(before, after):
    """Rastreia mudanças de atividade/jogos."""
    if activity_tracker:
        await activity_tracker.on_presence_update(before, after)


@client.event
async def on_voice_state_update(member, before, after):
    """Rastreia atividade de voz para estatísticas."""
    if stats_collector:
        await stats_collector.on_voice_state_update(member, before, after)


# --- NOVO: O Processador em Lote ---
async def processador_em_lote():
    while True:
        await asyncio.sleep(INTERVALO_ANALISE)
        if buffer_mensagens:
            mensagens_para_analisar = list(buffer_mensagens)
            buffer_mensagens.clear()
            vereditos = await analisar_lote_com_ia(mensagens_para_analisar)

            for msg, veredito in zip(mensagens_para_analisar, vereditos):
                if veredito == "SIM":
                    print(f"Ofensa encontrada na mensagem de {msg.author}: '{msg.content}'. Removendo...")
                    try:
                        # Marca como moderada nas estatísticas ANTES de deletar
                        if stats_collector:
                            await stats_collector.mark_message_as_moderated(msg.id)
                        
                        await msg.delete()
                        aviso = (
                            f"Ei {msg.author.mention}, uma de suas mensagens recentes foi removida por violar as diretrizes da comunidade."
                        )
                        await msg.channel.send(aviso, delete_after=10)
                    except Exception as e:
                        print(f"Falha ao moderar mensagem de {msg.author}. Erro: {e}")


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
    global db, stats_collector, role_manager, giveaway_manager, activity_tracker
    
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
            giveaway_manager = GiveawayManager(db)
            activity_tracker = ActivityTracker(db)
            embed_sender = EmbedSender(db)
            
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
    client.loop.create_task(collect_server_stats())
    client.loop.create_task(check_roles_periodically())
    client.loop.create_task(check_expired_giveaways())
    client.loop.create_task(check_embed_queue())


@client.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Adiciona ao buffer de moderação
    buffer_mensagens.append(message)
    print(f"Mensagem de {message.author} adicionada ao buffer (Tamanho atual: {len(buffer_mensagens)})")
    
    # Coleta estatísticas (se ativado)
    if stats_collector:
        await stats_collector.on_message(message)


@client.event
async def on_member_join(member):
    """Registra entrada de novo membro para sistema de cargos."""
    if role_manager:
        await role_manager.register_member_join(member)


@client.event
async def on_raw_reaction_add(payload):
    """Handler para reações adicionadas (sorteios)."""
    if giveaway_manager and not payload.member.bot:
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
async def on_raw_reaction_remove(payload):
    """Handler para reações removidas (sorteios)."""
    if giveaway_manager:
        try:
            channel = client.get_channel(payload.channel_id)
            guild = client.get_guild(payload.guild_id)
            if channel and guild:
                message = await channel.fetch_message(payload.message_id)
                user = await guild.fetch_member(payload.user_id)
                if not user.bot:
                    reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
                    if reaction:
                        await giveaway_manager.on_reaction_remove(reaction, user)
        except Exception as e:
            logger.error(f"❌ Erro ao processar remoção de reação: {e}")


@client.event
async def on_presence_update(before, after):
    """Rastreia mudanças de atividade/jogos."""
    if activity_tracker:
        await activity_tracker.on_presence_update(before, after)


@client.event
async def on_voice_state_update(member, before, after):
    """Rastreia atividade de voz para estatísticas."""
    if stats_collector:
        await stats_collector.on_voice_state_update(member, before, after)


# --- NOVO: O Processador em Lote ---
async def processador_em_lote():
    while True:
        await asyncio.sleep(INTERVALO_ANALISE)
        if buffer_mensagens:
            mensagens_para_analisar = list(buffer_mensagens)
            buffer_mensagens.clear()
            vereditos = await analisar_lote_com_ia(mensagens_para_analisar)

            for msg, veredito in zip(mensagens_para_analisar, vereditos):
                if veredito == "SIM":
                    print(f"Ofensa encontrada na mensagem de {msg.author}: '{msg.content}'. Removendo...")
                    try:
                        # Marca como moderada nas estatísticas ANTES de deletar
                        if stats_collector:
                            await stats_collector.mark_message_as_moderated(msg.id)
                        
                        await msg.delete()
                        aviso = (
                            f"Ei {msg.author.mention}, uma de suas mensagens recentes foi removida por violar as diretrizes da comunidade."
                        )
                        await msg.channel.send(aviso, delete_after=10)
                    except Exception as e:
                        print(f"Falha ao moderar mensagem de {msg.author}. Erro: {e}")


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
    while not client.is_closed():
        try:
            if embed_sender and db:
                await embed_sender.process_pending_requests(client)
        except Exception as e:
            logger.error(f"❌ Erro ao verificar fila de embeds: {e}")
        
        # Verifica a cada 5 segundos
        await asyncio.sleep(5)


# --- 7. Inicialização do Bot E DO SERVIDOR WEB ---
keep_alive()  # Inicia o servidor web em segundo plano

try:
    client.run(DISCORD_TOKEN)  # Inicia o bot
finally:
    # Cleanup: fecha conexão com banco de dados
    if db:
        asyncio.run(db.disconnect())