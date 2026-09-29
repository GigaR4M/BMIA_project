# 🤖 BMIA — Bot Híbrido com Inteligência Artificial para Discord

> **Moderação por IA • Sistema de XP & Gamificação • Torneios & Chaveamentos Visuais • Rastreamento de Jogos & Ofertas Steam • Segurança & Reputação • Cargos Automáticos • Sorteios • Memória Contextual**

O **BMIA** é um bot completo e moderno para Discord desenvolvido em Python, integrando modelos de última geração (**Google Gemini 2.5 Flash**) com **PostgreSQL (Supabase)** e geradores visuais dinâmicos via **Pillow**. Criado para transformar comunidades com moderação inteligente, engajamento gamificado e automações avançadas.

---

## 📑 Índice

- [✨ Funcionalidades](#-funcionalidades)
- [🔧 Tecnologias & Arquitetura](#-tecnologias--arquitetura)
- [⚙️ Pré-requisitos & Instalação](#️-pré-requisitos--instalação)
- [🔑 Variáveis de Ambiente](#-variáveis-de-ambiente)
- [📖 Comandos Disponíveis](#-comandos-disponíveis)
  - [⚡ XP, Níveis & Estatísticas (`/stats`, `/rank`, `/perfil`, `/destaques`)](#-xp-níveis--estatísticas)
  - [🏆 Torneios & Campeonatos (`/torneio`)](#-torneios--campeonatos)
  - [🛡️ Segurança, Reputação & Denúncias (`/seguranca`, `/report`, Context Menus)](#️-segurança-reputação--denúncias)
  - [🎮 Jogos & Atividades (`/games`, `/destaques`)](#-jogos--atividades)
  - [🏷️ Ofertas Steam & Festivais (`/jogos`, `/steam`)](#️-ofertas-steam--festivais)
  - [🌐 Catálogo de Jogos RAWG (`/jogo`)](#-catálogo-de-jogos-rawg)
  - [🏅 Cargos Automáticos por Tempo (`/autorole`)](#-cargos-automáticos-por-tempo)
  - [🎉 Sorteios / Giveaways (`/giveaway`)](#-sorteios--giveaways)
  - [🧠 Contexto & Memória da IA (`/context`)](#-contexto--memória-da-ia)
  - [⚙️ Configurações Administrativas (`/config`, `/moderacao`)](#️-configurações-administrativas)
  - [🎭 Diversão & GIFs (`/gif`, `/danca`)](#-diversão--gifs)
  - [ℹ️ Informações Gerais (`/info`)](#ℹ️-informações-gerais)
- [📁 Estrutura do Projeto](#-estrutura-do-projeto)
- [🧪 Testes Automatizados](#-testes-automatizados)
- [🚀 Deploy & Produção](#-deploy--produção)
- [🔒 Privacidade & Boas Práticas](#-privacidade--boas-práticas)

---

## ✨ Funcionalidades

### 🛡️ Moderação Automática com IA (Google Gemini)
- **Análise em lote assíncrona** a cada intervalo configurável (otimização de cota de API).
- Detecção de toxicidade, assédio, discurso de ódio, spam e conteúdo impróprio.
- Remoção automática de mensagens ofensivas com alertas educativos e logs para a moderação.
- Ativação/desativação dinâmica por servidor via `/config moderacao`.

### ⚡ Sistema de XP, Níveis & Gamificação
- **Pontuação multifatorial:**
  - **Chat de Texto:** XP diferenciado por mensagens curtas e longas, bônus para replies.
  - **Chat de Voz & Streaming:** XP por minuto em call, bônus de galera (2+ membros) e bônus por transmissão ao vivo.
  - **Jogos em Call & Sinergia:** Bônus de XP ao jogar o mesmo título simultaneamente com amigos.
  - **Reanimação de Chat (Chat Revival):** Bônus especial de +15 XP ao reativar canais inativos há mais de 1 semana.
- **Rank Card Visual Personalizado:** Renderização de cartões em canvas (`Pillow`) com avatar, nível, barra de progresso, posição no ranking e estatísticas vitais (`/rank`, `/perfil`).
- Leaderboard anual persistente e rankings com sincronização periódica.

### 🏆 Torneios & Campeonatos
- **Formatos:** 1v1 (Individual), 2v2 (Duplas), 3v3 (Trios) e 5v5 (Equipes).
- **Tipos de Disputa:** Mata-Mata Simples (*Single Elimination*), Eliminação Dupla (*Double Elimination*), Pontos Corridos / Liga (*Round Robin*), Sistema Suíço (*Swiss*), Fase de Grupos + Playoffs e Corrida/FFA.
- **Capacidade:** Suporte rigoroso de **2 a 32 participantes**.
- **Geradores Visuais Dinâmicos:**
  - Imagem oficial de chaveamento / bracket renderizada em alta qualidade.
  - Tabela visual oficial de classificação da liga com pontos, vitórias, empates, derrotas e saldo.
- **Automações:** Modais visuais para criação e inserção de placares, check-in, criação automática de *Discord Scheduled Events*, avanço automático de vencedores e Hall da Fama com distribuição de XP.

### 🔒 Segurança, Reputação & Dossiê
- **Dossiê de Segurança Completo (`/seguranca dossie`):** Visão 360° para a Staff com histórico de infrações, advertências, mutes, bans anteriores, mensagens moderadas e convite de entrada (*invite tracker*).
- **Cálculo de Trust Score (0 a 100):** Algoritmo ponderado baseado em tempo de conta, tempo no servidor, sinais do Discord e penalidades por infrações.
- **Sistema de Denúncias (Reports):** Comando `/report` com modal interativo e suporte a **Context Menus (clique direito)** em mensagens e usuários, despachando painel de ação interativo para o canal da Staff.

### 🎮 Rastreamento de Jogos & Retrospectiva Visual
- Monitoramento de presença em tempo real (tempo de jogo individual e coletivo).
- Rankings dos jogos mais populares no servidor.
- **Galeria Visual de Destaques (`/destaques`):** Geração de painéis em imagem com a retrospectiva anual da comunidade.

### 🏷️ Ofertas da Steam & Monitoramento de Preços
- Integração com **GG.deals API** e Steam API.
- Monitoramento de lista de desejos comunitária com alertas de desconto e detecção de **menor preço histórico**.
- Calendário oficial de festivais e grandes promoções sazonais da Steam (`/steam eventos`).

### 🌐 Catálogo de Jogos RAWG
- Busca de jogos com **Autocomplete em tempo real** via API do RAWG.
- Ficha técnica completa: notas do Metacritic, classificação etária, plataformas, requisitos de sistema e botões com links diretos para lojas oficiais.

### 🏅 Cargos Automáticos por Tempo
- Atribuição automática de patentes conforme o tempo de permanência no servidor (ex: Recruta → General).
- Sincronização automática para membros novos e existentes.

### 🎉 Sorteios (Giveaways)
- Criação interativa via `/giveaway create` com tempos flexíveis (`10m`, `2h`, `3d`, `1w`).
- Entrada com reação 🎉, sorteio automático após encerramento e suporte a re-sorteio (`/giveaway reroll`).

### 🧠 Memória & Contexto Personalizável da IA
- Configuração de tema do servidor, tom de conversa (ex: formal, bem-humorado, gamer) e regras para o assistente IA através do grupo `/context`.
- Perfis de usuário com preferências de interação e memória contextual.

### 📱 Notificador Telegram
- Envio opcional de logs operacionais, alertas de moderação e status de inicialização para um chat privado ou canal do Telegram.

---

## 🔧 Tecnologias & Arquitetura

```
               ┌─────────────────────────────────────────────────────┐
               │                    DISCORD BOT                      │
               │                   (discord.py)                      │
               └──────────┬───────────────────────────┬──────────────┘
                          │                           │
              ┌───────────▼────────────┐  ┌───────────▼─────────────┐
              │      Google Gemini     │  │   PostgreSQL (Supabase) │
              │   (Moderação & Chat)   │  │   (asyncpg connection)  │
              └────────────────────────┘  └─────────────────────────┘
                          │                           │
              ┌───────────▼────────────┐  ┌───────────▼─────────────┐
              │     RAWG / GG.deals    │  │   Pillow Image Engine   │
              │  (Metadados & Ofertas) │  │  (Brackets/Tabelas/Ranks)│
              └────────────────────────┘  └─────────────────────────┘
```

- **Linguagem:** Python 3.10+
- **Framework Discord:** [discord.py 2.x](https://github.com/Rapptz/discord.py)
- **Inteligência Artificial:** Google Generative AI (`gemini-2.5-flash`)
- **Banco de Dados:** PostgreSQL hospedado no [Supabase](https://supabase.com) com driver assíncrono [asyncpg](https://github.com/MagicStack/asyncpg)
- **Processamento de Imagens:** [Pillow (PIL)](https://python-pillow.org/)
- **APIs Externas:** RAWG Video Games Database, GG.deals, GIPHY, Telegram Bot API
- **Testes:** pytest & pytest-asyncio

---

## ⚙️ Pré-requisitos & Instalação

### 1. Pré-requisitos
- Python 3.10 ou superior instalado.
- Conta no [Discord Developer Portal](https://discord.com/developers/applications) com uma aplicação e bot criados.
- Chave de API do Google Gemini obtida no [Google AI Studio](https://aistudio.google.com/app/apikey).
- Projeto criado no [Supabase](https://supabase.com).
- *(Opcional)* Chaves de API para RAWG, GIPHY e Telegram Bot.

### 2. Clonagem e Dependências

```bash
# Clone o repositório
git clone https://github.com/GigaR4M/BMIA_project.git
cd BMIA_project

# Crie e ative o ambiente virtual
python -m venv .venv

# No Windows:
.\.venv\Scripts\activate

# No Linux/Mac:
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

### 3. Habilitação de Privileged Gateway Intents

No [Discord Developer Portal](https://discord.com/developers/applications):
1. Selecione sua aplicação e vá na aba **Bot**.
2. Na seção **Privileged Gateway Intents**, habilite:
   - ✅ **Presence Intent** (essencial para monitorar jogos jogados)
   - ✅ **Server Members Intent** (essencial para cargos automáticos, segurança e dossiês)
   - ✅ **Message Content Intent** (essencial para moderação com IA e XP de texto)

---

## 🔑 Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (use o `.env.example` como referência):

```ini
# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_TOKEN=seu_discord_bot_token_aqui

# ── Google Gemini ──────────────────────────────────────────────────────────────
GEMINI_API_KEY=sua_chave_gemini_aqui
GEMINI_CHAT_API_KEY=sua_chave_gemini_chat_aqui   # Opcional (usa GEMINI_API_KEY se vazio)
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_MODERATION_MODEL=gemini-2.5-flash

# ── Banco de Dados (Supabase PostgreSQL) ───────────────────────────────────────
DATABASE_URL=postgresql://postgres.xxxx:senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres

# ── APIs Opcionais ─────────────────────────────────────────────────────────────
RAWG_API_KEY=sua_chave_rawg_aqui               # https://rawg.io/apidocs
GIPHY_API_KEY=sua_chave_giphy_aqui             # https://developers.giphy.com/
TELEGRAM_BOT_TOKEN=seu_token_telegram          # Telegram Notifier
TELEGRAM_CHAT_ID=seu_chat_id_telegram
```

---

## 📖 Comandos Disponíveis

### ⚡ XP, Níveis & Estatísticas

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/rank [membro]` | Exibe o Rank Card visual oficial com nível, XP e progresso | Todos |
| `/perfil [membro]` | Alias para `/rank` | Todos |
| `/destaques [ano]` | Exibe a Retrospectiva Visual de Destaques do ano do servidor | Todos |
| `/stats me [dias]` | Mostra estatísticas pessoais detalhadas e ficha de XP | Todos |
| `/stats user @usuario [dias]` | Consulta estatísticas detalhadas de outro membro | Todos |
| `/stats server [dias]` | Estatísticas gerais de atividade do servidor | Todos |
| `/stats top [limite] [dias]` | Ranking dos usuários mais ativos em mensagens | Todos |
| `/stats channels [limite] [dias]` | Ranking dos canais mais movimentados | Todos |
| `/stats leaderboard [limite] [ano]` | Ranking competitivo de XP e Níveis | Todos |
| `/stats setup_leaderboard` | Configura mensagem de leaderboard persistente com auto-atualização | Admin |
| `/stats xp_adicionar @membro <quant>` | Adiciona pontos/XP manualmente a um membro | Admin |
| `/stats xp_remover @membro <quant>` | Remove pontos/XP de um membro | Admin |

---

### 🏆 Torneios & Campeonatos (`/torneio`)

> Limite de participantes: **2 a 32 vagas**.

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/torneio criar` | Abre assistente para criar novo torneio com embed e botões de inscrição | Gerenciar Servidor |
| `/torneio formulario` | Abre modal interativo com todos os campos de configuração | Gerenciar Servidor |
| `/torneio status <id>` | Exibe detalhes, regras e lista de inscritos de um torneio | Todos |
| `/torneio listar [status]` | Lista todos os torneios abertos ou recentes do servidor | Todos |
| `/torneio sortear <id>` | Realiza o sorteio aleatório das chaves ou da tabela de jogos | Gerenciar Servidor |
| `/torneio chaveamento <id>` | Gera a **imagem oficial do Bracket/Chaveamento** em mata-mata | Todos |
| `/torneio tabela <id>` | Gera a **imagem oficial da Tabela de Classificação** da liga | Todos |
| `/torneio rodadas <id>` | Exibe calendário completo de confrontos e resultados da liga | Todos |
| `/torneio resultado <id>` | Abre modal para envio e validação rápida de placar | Gerenciar Servidor |
| `/torneio partida <id> <rodada> <p1> <p2> <vit>` | Registra resultado e avança o chaveamento | Gerenciar Servidor |
| `/torneio participante_adicionar <id> @membro` | Inscreve manualmente um competidor | Gerenciar Servidor |
| `/torneio participante_remover <id> @membro` | Remove participante mantendo a integridade | Gerenciar Servidor |
| `/torneio participante_substituir <id> @antigo @novo` | Substitui jogador sem resetar chaveamento | Gerenciar Servidor |
| `/torneio evento_vincular <id> <data_hora>` | Cria evento agendado oficial no Discord (*Scheduled Event*) | Gerenciar Servidor |
| `/torneio encerrar <id>` | Conclui o campeonato e distribui XP/pontos de premiação | Gerenciar Servidor |
| `/torneio cancelar <id>` | Cancela o torneio com confirmação de segurança | Gerenciar Servidor |
| `/torneio halldafama [limite]` | Exibe o ranking dos maiores campeões de torneios | Todos |

---

### 🛡️ Segurança, Reputação & Denúncias

| Comando / Ação | Descrição | Permissão |
|----------------|-----------|-----------|
| `/seguranca dossie @membro` | Dossiê 360° de segurança, Trust Score, histórico e infrações | Gerenciar Mensagens |
| `/report @membro` | Abre modal com categorias para denunciar usuário à Staff | Todos |
| **Clique Direito na Mensagem** → `Apps` → `Reportar Mensagem` | Denuncia mensagem específica com anexo de provas | Todos |
| **Clique Direito no Usuário** → `Apps` → `Reportar Usuário` | Denuncia o perfil diretamente pelo Discord | Todos |

---

### 🎮 Jogos & Atividades (`/games`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/games top [limite] [dias]` | Jogos mais jogados no servidor por horas acumuladas | Todos |
| `/games user [@membro] [dias]` | Jogos mais jogados por um usuário específico | Todos |
| `/games yearly [ano]` | Retrospectiva anual dos games mais jogados | Todos |
| `/games stats` | Estatísticas gerais de telemetria e presença de jogos | Todos |

---

### 🏷️ Ofertas Steam & Festivais

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/steam eventos [limite]` | Calendário de festivais e grandes promoções sazonais da Steam | Todos |
| `/jogos monitorados` | Lista de desejos da comunidade com checagem de menores preços | Todos |
| `/jogos adicionar <link_ou_id>` | Adiciona jogo da Steam para rastrear quedas de preço e ofertas | Todos |
| `/jogos remover <link_ou_id>` | Remove jogo da lista de monitoramento | Admin |
| `/jogos verificar` | Força verificação imediata de promoções em todos os jogos | Admin |

---

### 🌐 Catálogo de Jogos RAWG (`/jogo`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/jogo <nome> [plataforma] [detalhes]` | Busca instantânea com autocomplete, ficha técnica e links de compra | Todos |

---

### 🏅 Cargos Automáticos por Tempo (`/autorole`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/autorole add <cargo> <dias>` | Cadastra cargo automático desbloqueado por tempo de servidor | Gerenciar Cargos |
| `/autorole remove <cargo>` | Remove configuração de cargo automático | Gerenciar Cargos |
| `/autorole list` | Lista patentes e requisitos configurados | Todos |
| `/autorole check [@membro]` | Consulta tempo no servidor e próximo cargo a ser alcançado | Todos |
| `/autorole sync` | Executa sincronização forçada de patentes para todos os membros | Admin |
| `/autorole explicar` | Guia com regras de obtenção de cargos especiais | Todos |

---

### 🎉 Sorteios / Giveaways (`/giveaway`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/giveaway create <premio> <duracao> [vencedores]` | Cria sorteio oficial com reação e timer | Gerenciar Servidor |
| `/giveaway end <message_id>` | Encerra imediatamente um sorteio ativo | Gerenciar Servidor |
| `/giveaway reroll <message_id> [qtd]` | Rola novos vencedores para um sorteio encerrado | Gerenciar Servidor |
| `/giveaway list` | Lista todos os sorteios em andamento | Todos |
| `/giveaway delete <message_id>` | Cancela e remove o sorteio | Gerenciar Servidor |

---

### 🧠 Contexto & Memória da IA (`/context`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/context theme <texto>` | Define a temática do servidor que guia a IA | Admin |
| `/context rules <texto>` | Registra regras de conduta para o bot responder com contexto | Admin |
| `/context tone <texto>` | Define a personalidade e o tom das respostas da IA | Admin |
| `/context view` | Exibe o perfil de contexto ativo do servidor | Admin |
| `/context reset_user` | Reseta as preferências individuais e memória de curto prazo do usuário | Todos |

---

### ⚙️ Configurações Administrativas (`/config`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/config ver` | Painel com a configuração atual do bot no servidor | Admin |
| `/config moderacao <ativar>` | Ativa ou desativa a moderação por IA | Admin |
| `/config canal-moderacao <canal>` | Define o canal de envio de alertas e denúncias da Staff | Admin |
| `/config canal-pontos-adicionar <canal>` | Inclui canal de texto na lista permitida de XP | Admin |
| `/config canal-pontos-remover <canal>` | Remove canal de texto da lista de XP | Admin |
| `/config canais-pontos-listar` | Lista canais configurados que concedem XP | Admin |
| `/config voz-ignorar-adicionar <canal>` | Ignora canal de voz específico para pontuação | Admin |
| `/config voz-ignorar-remover <canal>` | Reativa canal de voz para pontuação de XP | Admin |

---

### 🎭 Diversão & GIFs

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/gif <busca>` | Pesquisa e envia GIFs animados do GIPHY | Todos |
| `/danca` | BMIA executa sua dança característica | Todos |

---

### ℹ️ Informações Gerais (`/info`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/info sistema_xp` | Guia detalhado explicando as regras de ganho de XP e níveis | Todos |
| `/info sistema_pontos` | Alias informativo do sistema de progressão | Todos |

---

## 📁 Estrutura do Projeto

```
BMIA_project/
├── commands/                   # Grupos de Slash Commands
│   ├── config_commands.py      # Configurações do bot (/config)
│   ├── context_commands.py     # Memória e personalização da IA (/context)
│   ├── deals_commands.py       # Promoções Steam e ofertas monitoradas (/steam, /jogos)
│   ├── games_commands.py       # Telemetria e rankings de jogos (/games)
│   ├── gif_commands.py         # GIFs animados e dança (/gif, /danca)
│   ├── giveaway_commands.py    # Sorteios (/giveaway)
│   ├── info_commands.py        # Comandos informativos (/info)
│   ├── moderation_commands.py  # Controles de moderação por IA
│   ├── rawg_commands.py        # Catálogo RAWG com autocomplete (/jogo)
│   ├── reputation_commands.py  # Dossiê de segurança, reports e context menus
│   ├── role_commands.py        # Patentes e cargos automáticos (/autorole)
│   ├── stats_commands.py       # XP, Níveis, Leaderboard e Rank Cards (/stats, /rank)
│   └── tournament_commands.py  # Sistema completo de torneios (/torneio)
├── events/
│   └── discord_events.py       # Gerenciador central de eventos Discord & BotContext
├── tasks/
│   ├── background_tasks.py     # Tarefas periódicas em segundo plano (XP, roles, podio)
│   └── moderation.py           # Processador em lote de moderação por IA
├── utils/                      # Módulos utilitários, clientes de API e geradores
│   ├── activity_tracker.py     # Rastreamento de tempo de presença em jogos
│   ├── ai_tools.py             # Integrações com Google Gemini
│   ├── chat_handler.py         # Processamento de chat conversacional
│   ├── embed_builder.py        # Construtor padronizado de Embeds
│   ├── event_monitor.py        # Monitor de eventos sazonais
│   ├── gg_deals_client.py      # Cliente de consulta à API do GG.deals
│   ├── giphy_client.py         # Cliente de busca do GIPHY
│   ├── giveaway_manager.py     # Gerenciamento de ciclo de vida de sorteios
│   ├── highlights_scanner.py   # Scanner de destaques e retrospectiva
│   ├── image_generator.py      # Gerador visual (Brackets, Tabelas de Liga, Rank Cards)
│   ├── invite_tracker.py       # Rastreamento de links de convite utilizados
│   ├── leaderboard_updater.py  # Atualizador assíncrono do leaderboard
│   ├── media_manager.py        # Gerenciador de mídias e cache
│   ├── memory_manager.py       # Gerenciador de memória de longo e curto prazo da IA
│   ├── points_manager.py       # Regras e distribuição de XP / Gamificação
│   ├── rawg_client.py          # Cliente da API RAWG Video Games
│   ├── reputation_manager.py   # Algoritmo de cálculo do Trust Score
│   ├── role_manager.py         # Atribuição e checagem de patentes
│   ├── spam_detector.py        # Detecção de mensagens repetitivas
│   ├── stats_analyzer.py       # Análise estatística de engajamento
│   └── telegram_notifier.py    # Notificações e logs via Telegram
├── migrations/                 # Migrações SQL e scripts de banco
├── tests/                      # Bateria de testes automatizados com pytest
├── config.py                   # Configurações globais e carregamento do .env
├── database.py                 # Camada de persistência assíncrona PostgreSQL
├── main.py                     # Inicialização do bot e registro da CommandTree
├── requirements.txt            # Dependências Python do projeto
├── DEPLOY.md                   # Guia de deploy em nuvem (ShardCloud/Render/VPS)
└── README.md                   # Documentação oficial do projeto
```

---

## 🧪 Testes Automatizados

O projeto conta com suite de testes automatizados com `pytest` e `pytest-asyncio`.

Para executar todos os testes:

```bash
# Executa toda a suite de testes
pytest

# Executa com relatório detalhado
pytest -v

# Executa testes específicos de torneios ou reputação
pytest tests/test_tournament.py
pytest tests/test_reputation.py
```

---

## 🚀 Deploy & Produção

O bot está preparado para rodar continuamente em VPS (Ubuntu/Debian), ShardCloud ou Render:

1. **Configuração do PostgreSQL:** Utilize uma instância Supabase ou banco PostgreSQL dedicado. As tabelas necessárias são migradas e estruturadas automaticamente pelo [database.py](database.py).
2. **Variáveis de Ambiente:** Preencha o `.env` ou configure as variáveis no painel da plataforma de hospedagem.
3. **Execução em Segundo Plano:**
   ```bash
   python main.py
   ```
4. Para mais detalhes passo a passo sobre hospedagem em nuvem, consulte o [DEPLOY.md](DEPLOY.md).

---

## 🔒 Privacidade & Boas Práticas

- **Proteção de Dados:** Conteúdo de mensagens é processado temporariamente em memória para moderação e pontuação, não sendo persistido em texto bruto no banco de dados.
- **Transparência:** Estatísticas pessoais e dossiês de segurança possuem visibilidade restrita e controle rigoroso de permissões (`ephemeral: True`).
- **Segurança de Acesso:** Comandos administrativos e de moderação exigem permissões nativas do Discord (`Administrator`, `Manage Guild`, `Manage Messages`).

---

<div align="center">
  <sub>Desenvolvido com dedicação utilizando <strong>discord.py</strong>, <strong>Google Gemini</strong>, <strong>PostgreSQL</strong> e <strong>Pillow</strong>.</sub>
</div>
