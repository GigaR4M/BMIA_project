# 🤖 BMIA - Bot Híbrido para Discord: Moderação com IA + Estatísticas + Cargos + Sorteios + Jogos

Bot completo para Discord que combina **moderação automática com IA**, **sistema de estatísticas**, **cargos automáticos por tempo**, **sorteios** e **rastreamento de jogos**. Utiliza Google Gemini para análise de mensagens e PostgreSQL (Supabase) para armazenamento de dados.

## ✨ Funcionalidades

### 🛡️ Moderação Automática com IA
- Análise em lote de mensagens a cada 15 segundos
- Detecção de linguagem ofensiva, assédio e discurso de ódio
- Remoção automática de conteúdo inadequado
- Avisos temporários aos usuários

### 📊 Sistema de Estatísticas
- Rastreamento automático de mensagens e atividade de voz
- Comandos slash modernos (`/stats`)
- Estatísticas do servidor, usuários e canais
- Rankings de usuários mais ativos
- Dados armazenados em PostgreSQL (Supabase)

### 🏅 Cargos Automáticos por Tempo
- Atribuição automática de cargos baseada no tempo no servidor
- Sistema de patentes configurável (Recruta → General)
- Verificação periódica e atribuição automática
- Comandos para gerenciar e visualizar configurações

### 🎉 Sistema de Sorteios (Giveaways)
- Criação de sorteios com duração personalizável
- Participação via reação 🎉
- Seleção automática de vencedores
- Comandos para gerenciar, finalizar e re-sortear
- Verificação automática de sorteios expirados

### 🎮 Rastreamento de Jogos e Atividades
- Monitoramento automático de jogos jogados
- Estatísticas de tempo jogado por jogo
- Retrospectiva anual de jogos mais populares
- Rankings de jogos mais jogados no servidor
- Estatísticas individuais por usuário

## 🔧 Tecnologias

- **Python 3.10+**
- **discord.py** - API do Discord
- **Google Gemini** - IA para moderação
- **PostgreSQL (Supabase)** - Banco de dados gratuito
- **asyncpg** - Driver PostgreSQL assíncrono
- **Flask** - Servidor keep-alive

## ⚙️ Instalação

### 1. Pré-requisitos

- Python 3.10 ou superior
- Conta Discord com bot configurado ([Portal de Desenvolvedores](https://discord.com/developers/applications))
  - Ative **Message Content Intent** e **Server Members Intent**
- Chave API do Google Gemini ([Google AI Studio](https://aistudio.google.com/app/apikey))
- Conta Supabase ([supabase.com](https://supabase.com))

### 2. Clone e Configure

```bash
# Clone o repositório
git clone https://github.com/GigaR4M/BMIA_project.git
cd BMIA_project

# Crie ambiente virtual
python -m venv .venv

# Ative o ambiente virtual
# Windows:
.\.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instale dependências
pip install -r requirements.txt
```

### 3. Configure Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```ini
# Token do Bot Discord
DISCORD_TOKEN=seu_token_aqui

# Chave API do Gemini
GEMINI_API_KEY=sua_chave_aqui

# Connection String do Supabase (PostgreSQL)
DATABASE_URL=postgresql://postgres:senha@db.xxxxx.supabase.co:5432/postgres
```

### 4. Configure o Supabase

1. Crie conta em [supabase.com](https://supabase.com)
2. Crie novo projeto (região: South America - São Paulo)
3. Vá em **Project Settings** → **Database**
4. Copie a **Connection String (URI)**
5. Cole no `.env` como `DATABASE_URL`

O bot criará as tabelas automaticamente na primeira execução!

### 5. Configure Permissões do Bot no Discord

1. Acesse o [Discord Developer Portal](https://discord.com/developers/applications)
2. Selecione seu bot
3. Vá em **Bot** → **Privileged Gateway Intents**
4. Ative os seguintes intents:
   - ✅ **Presence Intent** (para rastrear jogos)
   - ✅ **Server Members Intent** (para informações de membros)
   - ✅ **Message Content Intent** (para moderação)

### 6. Configure Cargos Automáticos (Opcional)

Após criar os cargos manualmente no Discord:

```bash
python setup_roles.py
```

Siga as instruções para configurar as patentes automaticamente.

**Patentes padrão:**
- Recruta: 0-7 dias
- Soldado: 7-28 dias
- Sargento: 28-91 dias
- Tenente: 91-182 dias
- Capitão: 182-365 dias
- Major: 365-730 dias
- Coronel: 730-1095 dias
- General: 1095+ dias

### 7. Execute o Bot

```bash
python main.py
```

## 📖 Comandos Disponíveis

### Comandos de Estatísticas (`/stats`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/stats server [days]` | Estatísticas gerais do servidor | Todos |
| `/stats me [days]` | Suas estatísticas pessoais | Todos |
| `/stats user @usuario [days]` | Estatísticas de um usuário | Admin |
| `/stats top [limit] [days]` | Ranking de usuários mais ativos | Todos |
| `/stats channels [limit] [days]` | Canais mais ativos | Todos |

### Comandos de Cargos Automáticos (`/autorole`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/autorole add <cargo> <dias>` | Adiciona cargo automático | Gerenciar Cargos |
| `/autorole remove <cargo>` | Remove cargo automático | Gerenciar Cargos |
| `/autorole list` | Lista cargos configurados | Todos |
| `/autorole check [@membro]` | Verifica status de um membro | Todos |
| `/autorole sync` | Sincroniza membros existentes | Administrador |

### Comandos de Sorteios (`/giveaway`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/giveaway create <premio> <duracao> [vencedores]` | Cria novo sorteio | Gerenciar Servidor |
| `/giveaway end <message_id>` | Finaliza sorteio manualmente | Gerenciar Servidor |
| `/giveaway reroll <message_id> [quantidade]` | Sorteia novos vencedores | Gerenciar Servidor |
| `/giveaway list` | Lista sorteios ativos | Todos |
| `/giveaway delete <message_id>` | Cancela e deleta sorteio | Gerenciar Servidor |

**Formato de duração:** `1h` (horas), `30m` (minutos), `2d` (dias), `1w` (semanas)

### Comandos de Jogos (`/games`)

| Comando | Descrição | Permissão |
|---------|-----------|-----------|
| `/games top [limit] [days]` | Jogos mais jogados no servidor | Todos |
| `/games user [@usuario] [days]` | Jogos de um usuário específico | Todos |
| `/games yearly [year]` | Retrospectiva anual de jogos | Todos |
| `/games stats` | Estatísticas gerais de atividades | Todos |

**Parâmetros opcionais:**
- `days`: Período em dias (padrão: 30)
- `limit`: Quantidade de resultados (padrão: 10, máx: 25)
- `year`: Ano para retrospectiva (padrão: ano atual)

## 🚀 Deploy (ShardCloud/Render)

O bot inclui servidor Flask para manter-se ativo em plataformas gratuitas:

1. Faça push do código para GitHub
2. Conecte ao ShardCloud ou Render
3. Configure as variáveis de ambiente no painel
4. O bot iniciará automaticamente!

## 📁 Estrutura do Projeto

```
BMIA_project/
├── main.py                 # Arquivo principal do bot
├── database.py             # Gerenciador PostgreSQL
├── stats_collector.py      # Coletor de estatísticas
├── commands/
│   └── stats_commands.py   # Comandos slash
├── utils/
│   └── embed_builder.py    # Construtor de embeds
├── requirements.txt        # Dependências
├── .env                    # Variáveis de ambiente (não commitar!)
└── .env.example            # Template de configuração
```

## 🔒 Privacidade

- Estatísticas são agregadas e anônimas por padrão
- Estatísticas pessoais só visíveis para o próprio usuário ou admins
- Nenhum conteúdo de mensagens é armazenado, apenas metadados
- Mensagens moderadas são marcadas mas não salvas

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📄 Licença

Este projeto é open source. Use livremente!

## 🆘 Suporte

Problemas? Abra uma issue no GitHub!

---

**Desenvolvido com ❤️ usando Google Gemini e Supabase**
