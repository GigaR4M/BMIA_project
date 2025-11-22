# main.py - BOT HÍBRIDO: MODERAÇÃO COM IA + ESTATÍSTICAS

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

# Inicializa sistema de estatísticas (será conectado no on_ready)
db = None
stats_collector = None


# --- 4. Função de Análise com IA (Versão em Lote) ---
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
        print("-----------------------------------------\n")
        return ["NÃO"] * len(lista_de_mensagens)


# --- 5. Eventos do Bot ---
@client.event
async def on_ready():
    global db, stats_collector
    
    print(f'🤖 Bot conectado como {client.user}!')
    print(f'🛡️  Moderação: Análise em lotes a cada {INTERVALO_ANALISE} segundos')
    
    # Inicializa banco de dados e estatísticas
    if DATABASE_URL:
        try:
            db = Database(DATABASE_URL)
            await db.connect()
            stats_collector = StatsCollector(db)
            
            # Registra comandos de estatísticas
            client.tree.add_command(StatsCommands(db))
            await client.tree.sync()
            
            print('📊 Sistema de estatísticas ativado!')
        except Exception as e:
            logger.error(f'❌ Erro ao inicializar estatísticas: {e}')
            logger.warning('⚠️  Bot continuará apenas com moderação')
    else:
        logger.warning('⚠️  DATABASE_URL não configurada. Estatísticas desativadas.')
    
    print('✅ Bot totalmente inicializado!')
    print('------')
    client.loop.create_task(processador_em_lote())


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


# --- 6. Novo Evento: Rastreamento de Voz ---
@client.event
async def on_voice_state_update(member, before, after):
    """Rastreia atividade de voz para estatísticas."""
    if stats_collector:
        await stats_collector.on_voice_state_update(member, before, after)


# --- 7. Inicialização do Bot E DO SERVIDOR WEB ---
keep_alive()  # Inicia o servidor web em segundo plano

try:
    client.run(DISCORD_TOKEN)  # Inicia o bot
finally:
    # Cleanup: fecha conexão com banco de dados
    if db:
        asyncio.run(db.disconnect())