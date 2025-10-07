# main.py

# --- 1. Importações ---
# Importamos as bibliotecas necessárias para o projeto.
import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv

# --- 2. Configuração Inicial ---
# Carrega as variáveis de ambiente (nossas chaves) do arquivo .env
load_dotenv()

# Pega o token do Discord e a chave da API do Gemini do ambiente
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configura a API do Google Gemini com a nossa chave
genai.configure(api_key=GEMINI_API_KEY)

# Configura o modelo de IA que vamos usar.
# Safety settings são ajustados para permitir que a IA analise conteúdo potencialmente ofensivo
# sem ser bloqueada por seus próprios filtros.
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name="models/gemini-pro-latest",
    generation_config=generation_config,
    safety_settings=safety_settings
)

# --- 3. Configuração do Cliente do Discord ---
# Definimos as "intenções" (intents) do bot. Isso diz ao Discord quais tipos de eventos nosso bot quer receber.
# Precisamos de 'guilds' (servidores) e 'messages' (mensagens) e 'message_content' para ler as mensagens.
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

# Criamos o cliente do bot com as intenções definidas
client = discord.Client(intents=intents)


# --- 4. Função de Análise com IA ---
# Esta função assíncrona envia a mensagem para a IA e retorna a análise.
async def analisar_mensagem_com_ia(mensagem):
    """
    Envia o texto para a API do Gemini e pergunta se é ofensivo.
    Retorna "SIM" se for ofensivo, "NÃO" caso contrário.
    """
    try:
        # Este é o "prompt", a instrução que damos para a IA.
        # Somos bem específicos para garantir que a resposta seja simples de processar.
        prompt = f"""
        Analise a seguinte mensagem de um chat e determine se ela contém discurso de ódio, assédio, bullying, conteúdo sexual explícito ou qualquer forma de linguagem ofensiva.
        Responda APENAS com "SIM" se a mensagem for ofensiva, ou "NÃO" se não for.

        Mensagem: "{mensagem}"

        Análise:
        """

        # Envia o prompt para o modelo de IA
        response = model.generate_content(prompt)

        # Retorna a resposta da IA (removendo espaços em branco)
        return response.text.strip()

    except Exception as e:
        # Se algo der errado na comunicação com a IA, registramos o erro e retornamos "NÃO" por segurança.
        print(f"Erro ao analisar com a IA: {e}")
        return "NÃO"


# --- 5. Eventos do Bot ---
# O evento 'on_ready' é chamado quando o bot se conecta com sucesso ao Discord.
@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}!')
    print('Pronto para moderar conversas.')
    print('------')


# O evento 'on_message' é chamado toda vez que uma nova mensagem é enviada em um canal que o bot pode ver.
@client.event
async def on_message(message):
    # Ignora mensagens enviadas pelo próprio bot para evitar um loop infinito.
    if message.author == client.user:
        return

    # Imprime no console a mensagem recebida para acompanhamento
    print(f"Mensagem de {message.author} no canal #{message.channel}: {message.content}")

    # Chama nossa função para analisar a mensagem com a IA
    resultado_analise = await analisar_mensagem_com_ia(message.content)
    print(f"Resultado da análise da IA: {resultado_analise}")

    # Se a IA respondeu com "SIM", a mensagem é considerada ofensiva.
    if "SIM" in resultado_analise.upper():
        try:
            # 1. Apaga a mensagem original
            await message.delete()

            # 2. Envia uma mensagem de aviso no canal, marcando o autor.
            aviso = (
                f"Olá {message.author.mention}, sua mensagem foi removida por violar as diretrizes da comunidade. "
                f"Por favor, mantenha um ambiente respeitoso para todos."
            )
            await message.channel.send(aviso)

            print(f"Mensagem ofensiva de {message.author} foi removida.")

        except discord.Forbidden:
            print(f"Erro: Não tenho permissão para apagar mensagens no canal #{message.channel}.")
        except Exception as e:
            print(f"Ocorreu um erro ao moderar a mensagem: {e}")


# --- 6. Inicialização do Bot ---
# Esta linha inicia o bot, usando o token que configuramos.
client.run(DISCORD_TOKEN)