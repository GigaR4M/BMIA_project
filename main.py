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


# --- 7. Inicialização do Bot E DO SERVIDOR WEB ---
keep_alive()  # Inicia o servidor web em segundo plano

try:
    client.run(DISCORD_TOKEN)  # Inicia o bot
finally:
    # Cleanup: fecha conexão com banco de dados
    if db:
        asyncio.run(db.disconnect())