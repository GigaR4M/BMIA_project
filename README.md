# 🤖 BMIA - Bot de Moderação com IA para Discord

Este é um bot para Discord projetado para moderar canais de texto automaticamente. Ele utiliza a API do Google Gemini para analisar mensagens em lotes, identificando e removendo conteúdo ofensivo, assédio ou discurso de ódio.

## ✨ Como Funciona

O bot opera em um ciclo contínuo para otimizar o uso da API e evitar analisar cada mensagem individualmente:

1.  **Coleta de Mensagens:** O bot "escuta" o chat e adiciona todas as novas mensagens a um buffer (uma lista temporária).
2.  **Análise em Lote:** A cada 15 segundos (`INTERVALO_ANALISE`), o bot envia o lote completo de mensagens coletadas para a API do Google Gemini.
3.  **Veredito da IA:** A IA analisa todas as mensagens e retorna um veredito (ex: "1:NÃO, 2:SIM, 3:NÃO").
4.  **Ação de Moderação:** O bot processa os vereditos. Mensagens marcadas como "SIM" (ofensivas) são removidas do canal, e um aviso temporário é enviado ao autor da mensagem.
5.  **Keep-Alive:** O projeto inclui um pequeno servidor web Flask para garantir que o bot permaneça online em plataformas de hospedagem gratuitas (como Render ou Replit).

## 🔧 Tecnologias Utilizadas

* [Python 3](https://www.python.org/)
* [discord.py](https://discordpy.readthedocs.io/en/stable/): Para a integração com a API do Discord.
* [google-generativeai](https://pypi.org/project/google-generativeai/): Para acesso à API do Gemini.
* [python-dotenv](https://pypi.org/project/python-dotenv/): Para gerenciamento de chaves de API e segredos.
* [Flask](https://flask.palletsprojects.com/en/3.0.x/): Para criar o servidor web "keep-alive".

## ⚙️ Configuração e Instalação

Siga estes passos para configurar e executar o bot em seu próprio ambiente.

### 1. Pré-requisitos

* Você precisa ter o [Python 3.10](https://www.python.org/downloads/) ou superior instalado.
* Uma conta no [Discord](https://discord.com/) com um bot configurado.
    * Obtenha seu `DISCORD_TOKEN` no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications).
    * Certifique-se de ativar as "Privileged Gateway Intents" (especialmente `Message Content Intent`) para o seu bot.
* Uma chave de API do [Google Gemini](https://aistudio.google.com/app/apikey).
    * Obtenha sua `GEMINI_API_KEY` no Google AI Studio.

### 2. Instalação

1.  **Clone o repositório:**
    ```bash
    git clone (https://github.com/GigaR4M/BMIA_project.git)
    cd SEU-REPOSITORIO
    ```

2.  **Crie um ambiente virtual:**
    (Recomendado para isolar as dependências)
    ```bash
    # Windows
    python -m venv .venv
    .\.venv\Scripts\activate

    # macOS / Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configuração das Variáveis de Ambiente

Crie um arquivo chamado `.env` na pasta principal do projeto. Este arquivo guardará suas chaves secretas e **não** deve ser enviado para o GitHub (o `.gitignore` já está configurado para isso).

Copie o conteúdo abaixo para o seu arquivo `.env` e substitua pelos seus valores:

```ini
# Arquivo .env
# Substitua pelos seus valores reais

# Token do seu Bot no Portal de Desenvolvedores do Discord
DISCORD_TOKEN=SEU_TOKEN_DO_BOT_AQUI

# Chave de API do Google AI Studio (Gemini)
GEMINI_API_KEY=SUA_CHAVE_DE_API_DO_GEMINI_AQUI
