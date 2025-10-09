# main.py

# --- 1. Importações ---
import discord
import os
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio  # <<< NOVO: Importamos asyncio para a tarefa em segundo plano
import traceback

# --- 2. Configuração Inicial e Constantes ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# --- Constantes para o Processamento em Lote --- # <<< NOVO
INTERVALO_ANALISE = 15  # Segundos. O bot analisará as mensagens a cada 15 segundos.
buffer_mensagens = []  # O buffer para guardar as mensagens.

# Configura a API do Google Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(model_name="models/gemini-2.0-flash-lite")  # Usando o modelo que decidimos

# Configuração do Cliente do Discord
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True
client = discord.Client(intents=intents)


# --- 4. Função de Análise com IA (Versão em Lote) --- # <<< ALTERADO
async def analisar_lote_com_ia(lista_de_mensagens):
    print(f"-> Analisando um lote de {len(lista_de_mensagens)} mensagens...")

    # Se a lista estiver vazia, não faz nada.
    if not lista_de_mensagens:
        return []

    try:
        # 1. Monta o prompt para a IA
        # Instruímos a IA a analisar um conjunto de mensagens e retornar de forma estruturada.
        prompt_para_ia = "Analise cada uma das seguintes mensagens de um chat, numeradas de 1 a N. Determine se alguma delas contém linguagem ofensiva, assédio ou discurso de ódio. Responda com o veredito para cada mensagem no formato '1:VEREDITO, 2:VEREDITO, ...'. Use 'SIM' para ofensiva e 'NÃO' para não ofensiva.\n\n"

        # Adiciona cada mensagem ao prompt
        for i, msg in enumerate(lista_de_mensagens, 1):
            prompt_para_ia += f"{i}: \"{msg.content}\"\n"

        # 2. Envia o prompt único para o modelo
        response = await model.generate_content_async(prompt_para_ia)

        # 3. Processa a resposta da IA
        vereditos_texto = response.text.strip().upper()
        print(f"-> Resposta da IA (lote): {vereditos_texto}")

        # Constrói uma lista de resultados. Ex: ["NÃO", "SIM", "NÃO"]
        resultados_finais = []
        partes = vereditos_texto.split(',')
        for parte in partes:
            if "SIM" in parte:
                resultados_finais.append("SIM")
            else:
                resultados_finais.append("NÃO")

        # Garante que temos um resultado para cada mensagem enviada
        while len(resultados_finais) < len(lista_de_mensagens):
            resultados_finais.append("NÃO")

        return resultados_finais

    except Exception as e:
        print("\n!!! OCORREU UM ERRO NA ANÁLISE EM LOTE !!!")
        traceback.print_exc()
        print("-----------------------------------------\n")
        # Retorna "NÃO" para todas as mensagens em caso de erro
        return ["NÃO"] * len(lista_de_mensagens)


# --- 5. Eventos do Bot ---

# O on_ready agora inicia nossa tarefa em segundo plano
@client.event
async def on_ready():
    print(f'Bot conectado como {client.user}!')
    print(f'Pronto para moderar conversas em lotes a cada {INTERVALO_ANALISE} segundos.')
    print('------')
    # Inicia o processador em segundo plano
    client.loop.create_task(processador_em_lote())


# O on_message agora é muito mais simples: apenas coleta as mensagens
@client.event
async def on_message(message):
    # Ignora mensagens de bots
    if message.author.bot:
        return

    # Adiciona a mensagem ao buffer para análise futura
    buffer_mensagens.append(message)
    print(f"Mensagem de {message.author} adicionada ao buffer (Tamanho atual: {len(buffer_mensagens)})")


# --- NOVO: O Processador em Lote ---
async def processador_em_lote():
    while True:
        # 1. Espera o intervalo definido
        await asyncio.sleep(INTERVALO_ANALISE)

        # 2. Se houver mensagens no buffer, processa
        if buffer_mensagens:
            # Cria uma cópia do buffer e o limpa imediatamente
            # para não perder mensagens que chegam durante a análise
            mensagens_para_analisar = list(buffer_mensagens)
            buffer_mensagens.clear()

            # 3. Envia o lote para a IA
            vereditos = await analisar_lote_com_ia(mensagens_para_analisar)

            # 4. Itera sobre as mensagens e seus respectivos vereditos
            for msg, veredito in zip(mensagens_para_analisar, vereditos):
                if veredito == "SIM":
                    print(f"Ofensa encontrada na mensagem de {msg.author}: '{msg.content}'. Removendo...")
                    try:
                        await msg.delete()
                        aviso = (
                            f"Ei {msg.author.mention}, uma de suas mensagens recentes foi removida por violar as diretrizes da comunidade."
                        )
                        await msg.channel.send(aviso, delete_after=10)
                    except Exception as e:
                        print(f"Falha ao moderar mensagem de {msg.author}. Erro: {e}")


# --- 6. Inicialização do Bot ---
client.run(DISCORD_TOKEN)