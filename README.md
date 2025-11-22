# 🤖 BMIA - Bot Híbrido para Discord: Moderação com IA + Estatísticas

Bot híbrido para Discord que combina **moderação automática com IA** e **sistema completo de estatísticas**. Utiliza Google Gemini para análise de mensagens e PostgreSQL (Supabase) para rastreamento de atividades.

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

### 5. Execute o Bot

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

**Parâmetros opcionais:**
- `days`: Período em dias (padrão: 30)
- `limit`: Quantidade de resultados (padrão: 10, máx: 25)

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
