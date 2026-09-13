# database.py - Módulo de Gerenciamento do Banco de Dados PostgreSQL

import asyncpg
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    """Gerenciador de banco de dados PostgreSQL para estatísticas do bot."""
    
    def __init__(self, database_url: str):
        """
        Inicializa o gerenciador de banco de dados.
        
        Args:
            database_url: Connection string do PostgreSQL (formato: postgresql://user:pass@host:port/db)
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        self.has_vector = True
    
    async def connect(self):
        """Cria o connection pool e inicializa o schema."""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                statement_cache_size=0  # Desabilita prepared statements para compatibilidade com pgbouncer
            )
            logger.info("✅ Conectado ao banco de dados PostgreSQL")
            await self.initialize_schema()
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao banco de dados: {e}")
            raise
    
    async def disconnect(self):
        """Fecha o connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Conexão com banco de dados fechada")
    
    async def initialize_schema(self):
        """Cria as tabelas necessárias se não existirem."""
        async with self.pool.acquire() as conn:
            # Tabela de usuários
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT NOT NULL,
                    discriminator TEXT,
                    is_bot BOOLEAN DEFAULT FALSE,
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_seen TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Adiciona coluna is_bot se não existir (migração manual)
            try:
                await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_bot BOOLEAN DEFAULT FALSE")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao tentar adicionar coluna is_bot: {e}")

            
            # Tabela de canais
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id BIGINT PRIMARY KEY,
                    channel_name TEXT NOT NULL,
                    channel_type TEXT,
                    guild_id BIGINT NOT NULL,
                    first_seen TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Tabela de mensagens
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id BIGINT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    channel_id BIGINT NOT NULL REFERENCES channels(channel_id),
                    guild_id BIGINT NOT NULL,
                    content_length INTEGER,
                    has_attachments BOOLEAN DEFAULT FALSE,
                    has_embeds BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    was_moderated BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Tabela de atividade de voz
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS voice_activity (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    channel_id BIGINT NOT NULL REFERENCES channels(channel_id),
                    guild_id BIGINT NOT NULL,
                    joined_at TIMESTAMP NOT NULL,
                    left_at TIMESTAMP,
                    duration_seconds INTEGER,
                    was_muted BOOLEAN DEFAULT FALSE,
                    was_deafened BOOLEAN DEFAULT FALSE
                )
            """)
            
            # Tabela de estatísticas diárias agregadas
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    date DATE NOT NULL,
                    total_messages INTEGER DEFAULT 0,
                    total_users INTEGER DEFAULT 0,
                    total_voice_minutes INTEGER DEFAULT 0,
                    most_active_channel_id BIGINT,
                    most_active_user_id BIGINT,
                    server_member_count INTEGER DEFAULT 0,
                    UNIQUE(guild_id, date)
                )
            """)
            
            # Tabela de datas de entrada de membros
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS member_join_dates (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    joined_at TIMESTAMP NOT NULL,
                    last_checked TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            
            # Tabela de configuração de cargos automáticos
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS auto_role_config (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    days_required INTEGER NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(guild_id, role_id)
                )
            """)

            # Tabela de configurações do servidor (guild_settings)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    ai_moderation_enabled BOOLEAN DEFAULT TRUE,
                    allowed_channels BIGINT[] DEFAULT '{}',
                    ignored_voice_channels BIGINT[] DEFAULT '{}',
                    announcement_channel_id BIGINT,
                    dynamic_roles_config JSONB DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Migrações: adiciona colunas novas se a tabela já existia
            for col_def in [
                "allowed_channels BIGINT[] DEFAULT '{}'",
                "ignored_voice_channels BIGINT[] DEFAULT '{}'",
                "announcement_channel_id BIGINT",
                "dynamic_roles_config JSONB DEFAULT '{}'",
            ]:
                col_name = col_def.split()[0]
                try:
                    await conn.execute(
                        f"ALTER TABLE guild_settings ADD COLUMN IF NOT EXISTS {col_def}"
                    )
                except Exception as e:
                    logger.warning(
                        "⚠️ Erro ao adicionar coluna guild_settings.%s: %s", col_name, e
                    )

            
            # Tabela de sorteios
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS giveaways (
                    giveaway_id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT UNIQUE,
                    prize TEXT NOT NULL,
                    winner_count INTEGER DEFAULT 1,
                    host_user_id BIGINT NOT NULL,
                    ends_at TIMESTAMP NOT NULL,
                    ended BOOLEAN DEFAULT FALSE,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Adiciona coluna image_url se não existir (migração manual)
            try:
                await conn.execute("ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS image_url TEXT")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao tentar adicionar coluna image_url: {e}")
            
            # Tabela de participantes de sorteios
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS giveaway_entries (
                    giveaway_id INTEGER NOT NULL REFERENCES giveaways(giveaway_id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    entered_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (giveaway_id, user_id)
                )
            """)
            
            # Tabela de atividades de usuários (jogos/presença)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_activities (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    guild_id BIGINT NOT NULL,
                    activity_name TEXT NOT NULL,
                    activity_type TEXT,
                    started_at TIMESTAMP NOT NULL,
                    ended_at TIMESTAMP,
                    duration_seconds INTEGER
                )
            """)

            
            # Tabela de pontos de interação
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS interaction_points (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    points INTEGER NOT NULL,
                    interaction_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Tabela de configuração do leaderboard persistente
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS leaderboard_config (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    last_updated TIMESTAMP DEFAULT NOW()
                )
            """)

            # Tabela de log de podium periódico (mensal/anual)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS periodic_leaderboard_log (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    period_type TEXT NOT NULL,
                    period_identifier TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(guild_id, period_type, period_identifier)
                )
            """)

            # Tabela de eventos agendados
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_events (
                    event_id BIGINT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_time TIMESTAMP WITH TIME ZONE,
                    end_time TIMESTAMP WITH TIME ZONE,
                    status TEXT NOT NULL,
                    creator_id BIGINT,
                    entity_type TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Tabela de participantes de eventos (interessados e presença confirmada)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS event_participants (
                    event_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'interested',
                    joined_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (event_id, user_id)
                )
            """)

            # Tabela de torneios
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tournaments (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    name TEXT NOT NULL,
                    game_name TEXT NOT NULL,
                    format TEXT DEFAULT '1v1',
                    max_participants INTEGER DEFAULT 16,
                    prize TEXT,
                    start_time TIMESTAMP WITH TIME ZONE,
                    status TEXT DEFAULT 'open',
                    winner_id BIGINT,
                    second_place_id BIGINT,
                    third_place_id BIGINT,
                    channel_id BIGINT,
                    message_id BIGINT,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Tabela de participantes de torneios
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_participants (
                    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'registered',
                    seed_number INTEGER,
                    registered_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (tournament_id, user_id)
                )
            """)

            # Tabela de partidas do chaveamento
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tournament_matches (
                    id SERIAL PRIMARY KEY,
                    tournament_id INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
                    round_name TEXT NOT NULL,
                    match_number INTEGER NOT NULL,
                    team_a_ids BIGINT[],
                    team_b_ids BIGINT[],
                    score_a INTEGER DEFAULT 0,
                    score_b INTEGER DEFAULT 0,
                    winner_team_ids BIGINT[],
                    status TEXT DEFAULT 'pending',
                    next_match_number INTEGER,
                    next_match_slot TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (tournament_id, match_number)
                )
            """)

            # Colunas adicionais se não existirem
            try:
                await conn.execute("ALTER TABLE tournament_participants ADD COLUMN IF NOT EXISTS seed_number INTEGER")
                await conn.execute("ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS is_shuffled BOOLEAN DEFAULT FALSE")
                await conn.execute("ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS final_score TEXT")
            except Exception as e:
                logger.debug(f"Colunas de torneio já existentes ou migração ignorada: {e}")


            
            # Índices para melhor performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_activity(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_guild ON voice_activity(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_guild_date ON daily_stats(guild_id, date)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_guild ON tournaments(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tournaments_status ON tournaments(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tournament_participants_user ON tournament_participants(user_id)")
            
            # Índices para novas tabelas
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_member_join_guild ON member_join_dates(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_auto_role_guild ON auto_role_config(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_guild ON giveaways(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_giveaways_ended ON giveaways(ended, ends_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_user ON user_activities(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_guild ON user_activities(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_name ON user_activities(activity_name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_started ON user_activities(started_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_interaction_points_user ON interaction_points(user_id)")

            
            # ==================== ADVANCED CONTEXT SYSTEM SCHEMAS ====================

            # Habilitar extensão pgvector (se disponível no ambiente)
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                logger.info("✅ Extensão 'vector' habilitada/verificada.")
                self.has_vector = True
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível habilitar a extensão 'vector'. Semantic search pode falhar: {e}")
                self.has_vector = False

            # Tabela de Contexto Global do Servidor
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS server_contexts (
                    guild_id BIGINT PRIMARY KEY,
                    theme TEXT,
                    rules TEXT,
                    tone TEXT,
                    extras TEXT, -- JSON string
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Tabela de Perfil Comportamental do Usuário
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_bot_profiles (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    nickname_preference TEXT,
                    tone_preference TEXT,
                    interaction_summary TEXT,
                    computed_stats TEXT DEFAULT '{}', -- JSON string (SQLite/Postgres compat simple) or JSONB
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            
            # Migration check: Ensure computed_stats exists if table already existed
            try:
                await conn.execute("ALTER TABLE user_bot_profiles ADD COLUMN IF NOT EXISTS computed_stats TEXT DEFAULT '{}'")
            except Exception:
                pass # Ignore if fails/exists

            # Tabela de Memórias de Longo Prazo
            # Tenta criar com embedding vector(768) - dimensão padrão do text-embedding-004 do Gemini é 768
            if self.has_vector:
                try:
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS bot_memories (
                            id SERIAL PRIMARY KEY,
                            guild_id BIGINT NOT NULL,
                            user_id BIGINT, -- Pode ser NULL para memória global do servidor
                            content TEXT NOT NULL,
                            embedding vector(768), 
                            keywords TEXT[],
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    # Índice HNSW para busca vetorial rápida (se a tabela foi criada com vector)
                    await conn.execute("""
                       CREATE INDEX IF NOT EXISTS idx_bot_memories_embedding 
                       ON bot_memories USING hnsw (embedding vector_cosine_ops)
                    """)
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao criar tabela bot_memories com vector. Criando sem vector: {e}")
                    self.has_vector = False
            
            if not self.has_vector:
                # Fallback sem vector
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS bot_memories (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT,
                        content TEXT NOT NULL,
                        keywords TEXT[],
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)

            # ==================== SECURITY: ENABLE RLS ====================
            # Enable Row Level Security on internal tables to prevent public access via PostgREST
            # The bot connects as a superuser/owner (or with BYPASSRLS), so it will still have access.
            try:
                await conn.execute("""
                    ALTER TABLE IF EXISTS server_contexts ENABLE ROW LEVEL SECURITY;
                    ALTER TABLE IF EXISTS user_bot_profiles ENABLE ROW LEVEL SECURITY;
                    ALTER TABLE IF EXISTS bot_memories ENABLE ROW LEVEL SECURITY;
                """)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao habilitar RLS nas tabelas: {e}")

            logger.info("✅ Schema do banco de dados inicializado")
    
    # ==================== INSERÇÃO DE DADOS ====================
    
    async def upsert_user(self, user_id: int, username: str, discriminator: str = None, is_bot: bool = False):
        """Insere ou atualiza um usuário."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, discriminator, is_bot, last_seen)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    username = CASE WHEN EXCLUDED.username != 'Unknown' THEN EXCLUDED.username ELSE users.username END,
                    discriminator = CASE WHEN EXCLUDED.discriminator != '0000' THEN EXCLUDED.discriminator ELSE users.discriminator END,
                    is_bot = EXCLUDED.is_bot,
                    last_seen = NOW()
            """, user_id, username, discriminator, is_bot)
            
    async def add_interaction_point(self, user_id: int, points: int, interaction_type: str, guild_id: int):
        """Adiciona pontos de interação para um usuário."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO interaction_points (user_id, points, interaction_type, guild_id)
                VALUES ($1, $2, $3, $4)
            """, user_id, points, interaction_type, guild_id)
    
    async def upsert_channel(self, channel_id: int, channel_name: str, channel_type: str, guild_id: int):
        """Insere ou atualiza um canal."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO channels (channel_id, channel_name, channel_type, guild_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (channel_id) 
                DO UPDATE SET 
                    channel_name = EXCLUDED.channel_name,
                    channel_type = EXCLUDED.channel_type
            """, channel_id, channel_name, channel_type, guild_id)
    
    async def insert_message(self, message_id: int, user_id: int, channel_id: int, 
                            guild_id: int, content_length: int, has_attachments: bool = False,
                            has_embeds: bool = False, was_moderated: bool = False):
        """Registra uma nova mensagem."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO messages (message_id, user_id, channel_id, guild_id, 
                                     content_length, has_attachments, has_embeds, was_moderated)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (message_id) DO NOTHING
            """, message_id, user_id, channel_id, guild_id, content_length, 
               has_attachments, has_embeds, was_moderated)

    async def update_message_moderation_status(self, message_id: int, was_moderated: bool):
        """Atualiza o status de moderação de uma mensagem."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE messages
                SET was_moderated = $1
                WHERE message_id = $2
            """, was_moderated, message_id)
    
    async def insert_voice_join(self, user_id: int, channel_id: int, guild_id: int):
        """Registra entrada em canal de voz."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO voice_activity (user_id, channel_id, guild_id, joined_at)
                VALUES ($1, $2, $3, NOW())
            """, user_id, channel_id, guild_id)
    
    async def update_voice_leave(self, user_id: int, channel_id: int):
        """Atualiza saída de canal de voz."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE voice_activity
                SET left_at = NOW(),
                    duration_seconds = EXTRACT(EPOCH FROM (NOW() - joined_at))::INTEGER
                WHERE user_id = $1 
                  AND channel_id = $2 
                  AND left_at IS NULL
            """, user_id, channel_id)

    async def get_open_voice_sessions(self) -> List[Dict[str, Any]]:
        """Retorna todas as sessões de voz abertas (sem left_at)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, joined_at
                FROM voice_activity
                WHERE left_at IS NULL
            """)
            return [dict(row) for row in rows]

    async def update_daily_member_count(self, guild_id: int, member_count: int):
        """Atualiza a contagem de membros do dia."""
        async with self.pool.acquire() as conn:
            try:
                # Use Brazil timezone (America/Sao_Paulo) instead of server timezone
                result = await conn.execute("""
                    INSERT INTO daily_stats (guild_id, date, server_member_count)
                    VALUES ($1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::DATE, $2)
                    ON CONFLICT (guild_id, date)
                    DO UPDATE SET server_member_count = EXCLUDED.server_member_count
                """, guild_id, member_count)
                logger.info(f"✅ Contagem de membros atualizada: guild_id={guild_id}, count={member_count}, result={result}")
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar contagem de membros: {e}")
                raise

    async def update_daily_user_stats(self, user_id: int, guild_id: int, 
                                     messages_increment: int = 0, 
                                     voice_seconds_increment: int = 0, 
                                     total_points_snapshot: int = None):
        """
        Atualiza as estatísticas diárias do usuário (mensagens, voz, pontos totais).
        Respeita o fuso horário de São Paulo (UTC-3) para definir 'hoje'.
        """
        async with self.pool.acquire() as conn:
            try:
                # Define 'Today' in Sao Paulo Timezone
                # We use Postgres 'AT TIME ZONE' to ensure DB consistency
                
                # Logic: Isert or Update.
                # If total_points_snapshot is provided, update it. Otherwise keep existing.
                # Increment messages/voice.
                
                insert_points = total_points_snapshot if total_points_snapshot is not None else 0 
                
                await conn.execute(f"""
                    INSERT INTO daily_user_stats (
                        guild_id, user_id, date, 
                        messages_count, voice_seconds, total_points, 
                        created_at, updated_at
                    )
                    VALUES (
                        $2, $1, (NOW() AT TIME ZONE 'America/Sao_Paulo')::DATE,
                        $3, $4, $5, 
                        NOW(), NOW()
                    )
                    ON CONFLICT (guild_id, user_id, date) 
                    DO UPDATE SET
                        messages_count = daily_user_stats.messages_count + EXCLUDED.messages_count,
                        voice_seconds = daily_user_stats.voice_seconds + EXCLUDED.voice_seconds,
                        total_points = CASE WHEN $6 THEN EXCLUDED.total_points ELSE daily_user_stats.total_points END,
                        updated_at = NOW()
                """, user_id, guild_id, messages_increment, voice_seconds_increment, 
                   insert_points, total_points_snapshot is not None)

            except Exception as e:
                logger.error(f"❌ Erro ao atualizar daily_user_stats: {e}")

    
    # ==================== CONSULTAS DE ESTATÍSTICAS ====================
    
    async def get_server_stats(self, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """Retorna estatísticas gerais do servidor."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total de mensagens
            total_messages = await conn.fetchval("""
                SELECT COUNT(*) FROM messages 
                WHERE guild_id = $1 AND created_at >= $2
            """, guild_id, cutoff_date)
            
            # Usuários únicos ativos
            active_users = await conn.fetchval("""
                SELECT COUNT(DISTINCT user_id) FROM messages 
                WHERE guild_id = $1 AND created_at >= $2
            """, guild_id, cutoff_date)
            
            # Canais ativos
            active_channels = await conn.fetchval("""
                SELECT COUNT(DISTINCT channel_id) FROM messages 
                WHERE guild_id = $1 AND created_at >= $2
            """, guild_id, cutoff_date)
            
            # Mensagens moderadas
            moderated_messages = await conn.fetchval("""
                SELECT COUNT(*) FROM messages 
                WHERE guild_id = $1 AND created_at >= $2 AND was_moderated = TRUE
            """, guild_id, cutoff_date)
            
            return {
                'total_messages': total_messages,
                'active_users': active_users,
                'active_channels': active_channels,
                'moderated_messages': moderated_messages,
                'period_days': days
            }
    
    async def get_top_users_by_messages(self, guild_id: int, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna os usuários mais ativos por mensagens (excluindo bots)."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    u.user_id,
                    u.username,
                    COALESCE(SUM(s.messages_count), 0) as message_count
                FROM users u
                JOIN daily_user_stats s ON u.user_id = s.user_id
                WHERE s.guild_id = $1 
                  AND s.date >= $2::DATE
                  AND u.is_bot = FALSE
                GROUP BY u.user_id, u.username
                ORDER BY message_count DESC
                LIMIT $3
            """, guild_id, cutoff_date, limit)
            
            return [dict(row) for row in rows]
    
    async def get_top_users_by_voice(self, guild_id: int, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna os usuários mais ativos em canais de voz (excluindo bots)."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    u.user_id,
                    u.username,
                    COALESCE(SUM(s.voice_seconds), 0) as total_seconds
                FROM users u
                JOIN daily_user_stats s ON u.user_id = s.user_id
                WHERE s.guild_id = $1 
                  AND s.date >= $2::DATE
                  AND u.is_bot = FALSE
                GROUP BY u.user_id, u.username
                ORDER BY total_seconds DESC
                LIMIT $3
            """, guild_id, cutoff_date, limit)
            
            return [dict(row) for row in rows]

    async def get_game_top_users(self, guild_id: int, game_name: str, limit: int = 5, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna os usuários que mais jogaram um determinado jogo/atividade no servidor."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    u.user_id,
                    u.username,
                    a.activity_name,
                    COALESCE(SUM(a.duration_seconds), 0) as total_seconds,
                    COUNT(*) as session_count
                FROM user_activities a
                JOIN users u ON a.user_id = u.user_id
                WHERE a.guild_id = $1 
                  AND a.activity_name ILIKE $2
                  AND a.started_at >= $3
                  AND a.duration_seconds IS NOT NULL
                  AND a.activity_type = 'playing'
                  AND u.is_bot = FALSE
                GROUP BY u.user_id, u.username, a.activity_name
                ORDER BY total_seconds DESC
                LIMIT $4
            """, guild_id, f"%{game_name.strip()}%", cutoff_date, limit)
            
            return [dict(row) for row in rows]

    async def find_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Busca usuário pelo nome de usuário aproximado."""
        async with self.pool.acquire() as conn:
            clean_name = username.strip().lstrip("@")
            row = await conn.fetchrow("""
                SELECT user_id, username, discriminator, is_bot
                FROM users
                WHERE username ILIKE $1 AND is_bot = FALSE
                ORDER BY last_seen DESC
                LIMIT 1
            """, f"%{clean_name}%")
            return dict(row) if row else None

    async def get_top_channels(self, guild_id: int, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna os canais mais ativos."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    c.channel_id,
                    c.channel_name,
                    COUNT(m.message_id) as message_count
                FROM channels c
                JOIN messages m ON c.channel_id = m.channel_id
                WHERE m.guild_id = $1 AND m.created_at >= $2
                GROUP BY c.channel_id, c.channel_name
                ORDER BY message_count DESC
                LIMIT $3
            """, guild_id, cutoff_date, limit)
            
            return [dict(row) for row in rows]
    
    async def get_user_stats(self, user_id: int, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """Retorna estatísticas de um usuário específico."""
        return await self.get_detailed_user_stats(user_id, guild_id, days)

    async def get_daily_points(self, user_id: int, interaction_type: str, guild_id: int) -> int:
        """Retorna a quantidade de pontos que um usuário ganhou hoje para um tipo específico."""
        async with self.pool.acquire() as conn:
            # Use data baseada no timezone do Brasil (-3) para 'hoje'
            total = await conn.fetchval("""
                SELECT COALESCE(SUM(points), 0)
                FROM interaction_points
                WHERE user_id = $1 
                  AND interaction_type = $2
                  AND guild_id = $3
                  AND created_at >= ((NOW() AT TIME ZONE 'America/Sao_Paulo')::DATE AT TIME ZONE 'America/Sao_Paulo')
            """, user_id, interaction_type, guild_id)
            return total

    async def get_user_current_total_points(self, user_id: int, guild_id: int) -> int:
        """Retorna o total de pontos acumulados do usuário."""
        async with self.pool.acquire() as conn:
            total = await conn.fetchval("""
                SELECT COALESCE(SUM(points), 0)
                FROM interaction_points
                WHERE user_id = $1 AND guild_id = $2
            """, user_id, guild_id)
            return total


    async def get_top_users_date_range(self, guild_id: int, start_date: datetime, end_date: datetime, limit: int = 3) -> List[Dict[str, Any]]:
        """Retorna os top usuários por pontos num intervalo de datas."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    u.user_id,
                    u.username,
                    u.discriminator,
                    COALESCE(SUM(ip.points), 0) as total_points
                FROM interaction_points ip
                JOIN users u ON ip.user_id = u.user_id
                WHERE ip.guild_id = $1 
                  AND ip.created_at >= $2
                  AND ip.created_at < $3
                GROUP BY u.user_id, u.username, u.discriminator
                ORDER BY total_points DESC
                LIMIT $4
            """, guild_id, start_date, end_date, limit)
            return [dict(row) for row in rows]

    async def check_periodic_leaderboard_sent(self, guild_id: int, period_type: str, period_identifier: str) -> bool:
        """Verifica se o podium já foi enviado para esse período."""
        async with self.pool.acquire() as conn:
            val = await conn.fetchval("""
                SELECT 1 FROM periodic_leaderboard_log
                WHERE guild_id = $1 AND period_type = $2 AND period_identifier = $3
            """, guild_id, period_type, period_identifier)
            return val is not None

    async def log_periodic_leaderboard_sent(self, guild_id: int, period_type: str, period_identifier: str):
        """Registra que o podium foi enviado."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO periodic_leaderboard_log (guild_id, period_type, period_identifier)
                VALUES ($1, $2, $3)
            """, guild_id, period_type, period_identifier)


    async def get_detailed_user_stats(self, user_id: int, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas de um usuário específico para auditoria."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 1. Total de mensagens
            total_messages = await conn.fetchval("""
                SELECT COALESCE(SUM(messages_count), 0) FROM daily_user_stats
                WHERE user_id = $1 AND guild_id = $2 AND date >= $3::DATE
            """, user_id, guild_id, cutoff_date)
            
            # 2. Tempo em voz (minutos)
            voice_minutes = await conn.fetchval("""
                SELECT COALESCE(SUM(voice_seconds), 0) / 60 
                FROM daily_user_stats
                WHERE user_id = $1 AND guild_id = $2 AND date >= $3::DATE
            """, user_id, guild_id, cutoff_date)
            
            # 3. Pontos Totais (Auditados)
            # Soma pontos da tabela de pontos de interação
            total_points = await conn.fetchval("""
                SELECT COALESCE(SUM(points), 0)
                FROM interaction_points
                WHERE user_id = $1 AND created_at >= $2
                  AND ($3::bigint IS NULL OR guild_id = $3 OR guild_id IS NULL)
            """, user_id, cutoff_date, guild_id)

            # 4. Detalhamento dos pontos (por tipo)
            points_breakdown = await conn.fetch("""
                SELECT interaction_type, COALESCE(SUM(points), 0) as points
                FROM interaction_points
                WHERE user_id = $1 AND created_at >= $2
                  AND ($3::bigint IS NULL OR guild_id = $3 OR guild_id IS NULL)
                GROUP BY interaction_type
            """, user_id, cutoff_date, guild_id)

            # 5. Tempo total em jogos (minutos)
            game_minutes = await conn.fetchval("""
                SELECT COALESCE(SUM(duration_seconds), 0) / 60
                FROM user_activities
                WHERE user_id = $1 AND guild_id = $2 AND started_at >= $3
                  AND activity_type = 'playing'
            """, user_id, guild_id, cutoff_date)

            # 6. Canais de Texto Favoritos
            top_text_channels = await conn.fetch("""
                SELECT c.channel_name, COUNT(*) as count
                FROM messages m
                JOIN channels c ON m.channel_id = c.channel_id
                WHERE m.user_id = $1 AND m.guild_id = $2 AND m.created_at >= $3
                GROUP BY c.channel_name
                ORDER BY count DESC
                LIMIT 3
            """, user_id, guild_id, cutoff_date)

            # 7. Canais de Voz Favoritos
            top_voice_channels = await conn.fetch("""
                SELECT c.channel_name, COALESCE(SUM(v.duration_seconds), 0)/60 as minutes
                FROM voice_activity v
                JOIN channels c ON v.channel_id = c.channel_id
                WHERE v.user_id = $1 AND v.guild_id = $2 AND v.joined_at >= $3
                GROUP BY c.channel_name
                ORDER BY minutes DESC
                LIMIT 3
            """, user_id, guild_id, cutoff_date)

            # 8. Atividade Favorita
            top_activities = await conn.fetch("""
                SELECT activity_name, COALESCE(SUM(duration_seconds), 0)/60 as minutes
                FROM user_activities
                WHERE user_id = $1 AND guild_id = $2 AND started_at >= $3
                  AND activity_type = 'playing'
                GROUP BY activity_name
                ORDER BY minutes DESC
                LIMIT 3
            """, user_id, guild_id, cutoff_date)

            
            return {
                'total_messages': total_messages,
                'voice_minutes': int(voice_minutes) if voice_minutes else 0,
                'game_minutes': int(game_minutes) if game_minutes else 0,
                'total_points': total_points,
                'points_breakdown': {row['interaction_type']: row['points'] for row in points_breakdown},
                'top_text_channels': [dict(row) for row in top_text_channels],
                'top_voice_channels': [dict(row) for row in top_voice_channels],
                'top_activities': [dict(row) for row in top_activities],
                'period_days': days
            }

    async def set_ai_moderation(self, guild_id: int, enabled: bool):
        """Ativa ou desativa a moderação por IA para um servidor."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, ai_moderation_enabled, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (guild_id) 
                DO UPDATE SET ai_moderation_enabled = $2, updated_at = NOW()
            """, guild_id, enabled)

    async def is_ai_moderation_enabled(self, guild_id: int) -> bool:
        """Verifica se a moderação por IA está ativa para um servidor."""
        async with self.pool.acquire() as conn:
            enabled = await conn.fetchval("""
                SELECT ai_moderation_enabled FROM guild_settings
                WHERE guild_id = $1
            """, guild_id)
            # Default True se não existir configuração
            return enabled if enabled is not None else True

    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        """Retorna toda a configuração de um servidor (canais, cargos, etc.)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    ai_moderation_enabled,
                    allowed_channels,
                    ignored_voice_channels,
                    announcement_channel_id,
                    dynamic_roles_config
                FROM guild_settings
                WHERE guild_id = $1
            """, guild_id)
            if not row:
                return {}
            
            dyn_roles = row["dynamic_roles_config"]
            if isinstance(dyn_roles, str):
                try:
                    dyn_roles = json.loads(dyn_roles)
                except json.JSONDecodeError:
                    dyn_roles = {}
            elif dyn_roles is None:
                dyn_roles = {}

            return {
                "ai_moderation_enabled": row["ai_moderation_enabled"],
                "allowed_channels": list(row["allowed_channels"] or []),
                "ignored_voice_channels": list(row["ignored_voice_channels"] or []),
                "announcement_channel_id": row["announcement_channel_id"],
                "dynamic_roles_config": dict(dyn_roles),
            }

    async def set_allowed_channels(
        self, guild_id: int, channel_ids: List[int]
    ) -> None:
        """Persiste a lista de canais permitidos para pontuação de um servidor."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, allowed_channels, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (guild_id)
                DO UPDATE SET allowed_channels = $2, updated_at = NOW()
            """, guild_id, channel_ids)

    async def set_ignored_voice_channels(
        self, guild_id: int, channel_ids: List[int]
    ) -> None:
        """Persiste a lista de canais de voz ignorados de um servidor."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, ignored_voice_channels, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (guild_id)
                DO UPDATE SET ignored_voice_channels = $2, updated_at = NOW()
            """, guild_id, channel_ids)

    async def set_dynamic_roles(
        self, guild_id: int, roles_config: Dict[str, int]
    ) -> None:
        """Persiste a configuração de cargos dinâmicos de um servidor."""
        import json
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, dynamic_roles_config, updated_at)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (guild_id)
                DO UPDATE SET dynamic_roles_config = $2::jsonb, updated_at = NOW()
            """, guild_id, json.dumps(roles_config))

    
    async def get_messages_per_day(self, guild_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna contagem de mensagens por dia."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    date,
                    SUM(messages_count) as message_count
                FROM daily_user_stats
                WHERE guild_id = $1 AND date >= $2::DATE
                GROUP BY date
                ORDER BY date
            """, guild_id, cutoff_date)
            
            return [dict(row) for row in rows]
    
    async def get_hourly_activity(self, guild_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Retorna atividade por hora do dia (para heatmap)."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    EXTRACT(HOUR FROM (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'))::INTEGER as hour,
                    COUNT(*) as message_count
                FROM messages
                WHERE guild_id = $1 AND created_at >= $2
                GROUP BY hour
                ORDER BY hour
            """, guild_id, cutoff_date)
            
            return [dict(row) for row in rows]
    
    # ==================== DYNAMIC ROLES QUERIES ====================

    async def get_top_users_total_points_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna a lista de usuários empatados com a maior pontuação no ano."""
        # Nota: Pontos são calculados na tabela interaction_points. Ignored channels já são filtrados na inserção dos pontos.
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            # Buscar maior pontuação primeiro
            max_points = await conn.fetchval("""
                SELECT COALESCE(SUM(points), 0) as total
                FROM interaction_points
                WHERE guild_id = $1 
                  AND created_at >= $2 AND created_at < $3
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT 1
            """, guild_id, start_date, end_date)
            
            if not max_points:
                return []
                
            # Buscar todos com essa pontuação
            rows = await conn.fetch("""
                SELECT user_id
                FROM interaction_points
                WHERE guild_id = $1 
                  AND created_at >= $2 AND created_at < $3
                GROUP BY user_id
                HAVING COALESCE(SUM(points), 0) = $4
            """, guild_id, start_date, end_date, max_points)
            
            return [r['user_id'] for r in rows]

    async def get_top_users_total_points_rank(self, guild_id: int, year: int, rank: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários num determinado Rank (1, 2, 3...) de pontos."""
        # Essa query é mais complexa pois precisa lidar com empates no rank anterior.
        # Vamos usar DENSE_RANK()
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserPoints AS (
                    SELECT user_id, COALESCE(SUM(points), 0) as total
                    FROM interaction_points
                    WHERE guild_id = $1 AND created_at >= $2 AND created_at < $3
                    GROUP BY user_id
                ),
                RankedUsers AS (
                    SELECT user_id, total, DENSE_RANK() OVER (ORDER BY total DESC) as rk
                    FROM UserPoints
                )
                SELECT user_id FROM RankedUsers WHERE rk = $4
            """, guild_id, start_date, end_date, rank)
            
            return [r['user_id'] for r in rows]

    async def get_top_users_voice_time_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários com maior tempo de voz no ano."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            ignored = ignored_channels if ignored_channels else []

            # Subquery para filtrar canais
            channel_filter = ""
            if ignored:
                channel_filter = "AND channel_id != ALL($4::bigint[])"

            query = f"""
                WITH UserVoice AS (
                    SELECT user_id, SUM(duration_seconds) as total_seconds
                    FROM voice_activity
                    WHERE guild_id = $1 
                      AND joined_at >= $2 AND joined_at < $3
                      {channel_filter}
                    GROUP BY user_id
                ),
                MaxVoice AS (
                    SELECT MAX(total_seconds) as max_val FROM UserVoice
                )
                SELECT uv.user_id 
                FROM UserVoice uv, MaxVoice mv 
                WHERE uv.total_seconds = mv.max_val AND mv.max_val > 0
            """
            
            args = [guild_id, start_date, end_date]
            if ignored:
                args.append(ignored)
                
            rows = await conn.fetch(query, *args)
            return [r['user_id'] for r in rows]

    async def get_top_users_streaming_time_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com maior tempo de streaming (game_time type 'streaming' ou 'screen_share')."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserStream AS (
                    SELECT user_id, SUM(duration_seconds) as total_seconds
                    FROM user_activities
                    WHERE guild_id = $1 
                      AND (activity_type = 'streaming' OR activity_type = 'screen_share' OR activity_name = 'Screen Share')
                      AND started_at >= $2 AND started_at < $3
                    GROUP BY user_id
                ),
                MaxStream AS (
                    SELECT MAX(total_seconds) as max_val FROM UserStream
                )
                SELECT us.user_id 
                FROM UserStream us, MaxStream ms 
                WHERE us.total_seconds = ms.max_val AND ms.max_val > 0
            """, guild_id, start_date, end_date)
            
            return [r['user_id'] for r in rows]

    async def get_top_users_messages_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários com maior número de mensagens."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            ignored = ignored_channels if ignored_channels else []
            
            channel_filter = ""
            if ignored:
                channel_filter = "AND channel_id != ALL($4::bigint[])"

            query = f"""
                WITH UserMsgs AS (
                    SELECT user_id, COUNT(*) as total_msgs
                    FROM messages
                    WHERE guild_id = $1 
                      AND created_at >= $2 AND created_at < $3
                      {channel_filter}
                    GROUP BY user_id
                ),
                MaxMsgs AS (
                    SELECT MAX(total_msgs) as max_val FROM UserMsgs
                )
                SELECT um.user_id 
                FROM UserMsgs um, MaxMsgs mm 
                WHERE um.total_msgs = mm.max_val AND mm.max_val > 0
            """
            args = [guild_id, start_date, end_date]
            if ignored:
                args.append(ignored)
                
            rows = await conn.fetch(query, *args)
            return [r['user_id'] for r in rows]

    async def get_top_users_moderated_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com mais mensagens moderadas."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserMod AS (
                    SELECT user_id, COUNT(*) as total_mod
                    FROM messages
                    WHERE guild_id = $1 
                      AND created_at >= $2 AND created_at < $3
                      AND was_moderated = TRUE
                    GROUP BY user_id
                ),
                MaxMod AS (
                    SELECT MAX(total_mod) as max_val FROM UserMod
                )
                SELECT um.user_id 
                FROM UserMod um, MaxMod mm 
                WHERE um.total_mod = mm.max_val AND mm.max_val > 0
            """, guild_id, start_date, end_date)
            return [r['user_id'] for r in rows]

    async def get_top_users_game_time_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com maior tempo jogado (any activity not streaming/listening etc if distinct)."""
        # Assumindo activity_type 'playing'
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserGame AS (
                    SELECT user_id, SUM(duration_seconds) as total_seconds
                    FROM user_activities
                    WHERE guild_id = $1 
                      AND activity_type = 'playing'
                      AND started_at >= $2 AND started_at < $3
                    GROUP BY user_id
                ),
                MaxGame AS (
                    SELECT MAX(total_seconds) as max_val FROM UserGame
                )
                SELECT ug.user_id 
                FROM UserGame ug, MaxGame mg 
                WHERE ug.total_seconds = mg.max_val AND mg.max_val > 0
            """, guild_id, start_date, end_date)
            return [r['user_id'] for r in rows]

    async def get_top_users_distinct_games_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com maior diversidade de jogos."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserDistinct AS (
                    SELECT user_id, COUNT(DISTINCT activity_name) as distinct_count
                    FROM user_activities
                    WHERE guild_id = $1 
                      AND activity_type = 'playing'
                      AND started_at >= $2 AND started_at < $3
                      AND duration_seconds > 60 -- Ignora jogos abertos por menos de 1 minuto
                    GROUP BY user_id
                ),
                MaxDistinct AS (
                    SELECT MAX(distinct_count) as max_val FROM UserDistinct
                )
                SELECT ud.user_id 
                FROM UserDistinct ud, MaxDistinct md 
                WHERE ud.distinct_count = md.max_val AND md.max_val > 0
            """, guild_id, start_date, end_date)
            return [r['user_id'] for r in rows]

    async def get_top_users_demo_games_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com maior diversidade de jogos demo."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserDemo AS (
                    SELECT user_id, COUNT(DISTINCT activity_name) as demo_count
                    FROM user_activities
                    WHERE guild_id = $1 
                      AND activity_type = 'playing'
                      AND started_at >= $2 AND started_at < $3
                      AND duration_seconds > 60 -- Ignora jogos abertos por menos de 1 minuto
                      AND activity_name ILIKE '%demo%'
                    GROUP BY user_id
                ),
                MaxDemo AS (
                    SELECT MAX(demo_count) as max_val FROM UserDemo
                )
                SELECT ud.user_id 
                FROM UserDemo ud, MaxDemo md 
                WHERE ud.demo_count = md.max_val AND md.max_val > 0
            """, guild_id, start_date, end_date)
            return [r['user_id'] for r in rows]

    async def get_top_users_longest_session_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários com a maior sessão única de voz."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            ignored = ignored_channels if ignored_channels else []

            channel_filter = ""
            if ignored:
                channel_filter = "AND channel_id != ALL($4::bigint[])"

            query = f"""
                WITH UserMaxSession AS (
                    SELECT user_id, MAX(duration_seconds) as max_session
                    FROM voice_activity
                    WHERE guild_id = $1 
                      AND joined_at >= $2 AND joined_at < $3
                      {channel_filter}
                    GROUP BY user_id
                ),
                GlobalMax AS (
                    SELECT MAX(max_session) as max_val FROM UserMaxSession
                )
                SELECT us.user_id 
                FROM UserMaxSession us, GlobalMax gm 
                WHERE us.max_session = gm.max_val AND gm.max_val > 0
            """
            
            args = [guild_id, start_date, end_date]
            if ignored:
                args.append(ignored)
                
            rows = await conn.fetch(query, *args)
            return [r['user_id'] for r in rows]
    
    async def get_top_users_night_voice_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários com maior tempo de voz na madrugada (00:00-06:00 BRT) no ano."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            ignored = ignored_channels if ignored_channels else []

            channel_filter = ""
            if ignored:
                channel_filter = "AND channel_id != ALL($4::bigint[])"

            query = f"""
                WITH NightVoice AS (
                    SELECT user_id, SUM(duration_seconds) as total_seconds
                    FROM voice_activity
                    WHERE guild_id = $1 
                      AND joined_at >= $2 AND joined_at < $3
                      AND EXTRACT(HOUR FROM (joined_at AT TIME ZONE 'America/Sao_Paulo')) >= 0
                      AND EXTRACT(HOUR FROM (joined_at AT TIME ZONE 'America/Sao_Paulo')) < 6
                      {channel_filter}
                    GROUP BY user_id
                ),
                MaxNight AS (
                    SELECT MAX(total_seconds) as max_val FROM NightVoice
                )
                SELECT nv.user_id 
                FROM NightVoice nv, MaxNight mn 
                WHERE nv.total_seconds = mn.max_val AND mn.max_val > 0
            """
            
            args = [guild_id, start_date, end_date]
            if ignored:
                args.append(ignored)
                
            rows = await conn.fetch(query, *args)
            return [r['user_id'] for r in rows]

    async def get_top_users_attachments_year(self, guild_id: int, year: int) -> List[int]:
        """Retorna usuários com mais arquivos/mídia enviados no ano."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            
            rows = await conn.fetch("""
                WITH UserAttachments AS (
                    SELECT user_id, COUNT(*) as total_attachments
                    FROM messages
                    WHERE guild_id = $1 
                      AND created_at >= $2 AND created_at < $3
                      AND has_attachments = TRUE
                    GROUP BY user_id
                ),
                MaxAttachments AS (
                    SELECT MAX(total_attachments) as max_val FROM UserAttachments
                )
                SELECT ua.user_id 
                FROM UserAttachments ua, MaxAttachments ma 
                WHERE ua.total_attachments = ma.max_val AND ma.max_val > 0
            """, guild_id, start_date, end_date)
            return [r['user_id'] for r in rows]

    async def get_top_users_active_days_year(self, guild_id: int, year: int, ignored_channels: List[int] = None) -> List[int]:
        """Retorna usuários com mais dias ativos (mensagem ou voz) no ano."""
        async with self.pool.acquire() as conn:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            ignored = ignored_channels if ignored_channels else []

            channel_filter_voice = ""
            if ignored:
                channel_filter_voice = "AND channel_id != ALL($4::bigint[])"

            query = f"""
                WITH MessageDays AS (
                    SELECT user_id, (created_at AT TIME ZONE 'America/Sao_Paulo')::DATE as active_date
                    FROM messages
                    WHERE guild_id = $1 
                      AND created_at >= $2 AND created_at < $3
                ),
                VoiceDays AS (
                    SELECT user_id, (joined_at AT TIME ZONE 'America/Sao_Paulo')::DATE as active_date
                    FROM voice_activity
                    WHERE guild_id = $1 
                      AND joined_at >= $2 AND joined_at < $3
                      {channel_filter_voice}
                ),
                AllDays AS (
                    SELECT user_id, active_date FROM MessageDays
                    UNION
                    SELECT user_id, active_date FROM VoiceDays
                ),
                UserActiveDays AS (
                    SELECT user_id, COUNT(DISTINCT active_date) as distinct_days
                    FROM AllDays
                    GROUP BY user_id
                ),
                MaxDays AS (
                    SELECT MAX(distinct_days) as max_val FROM UserActiveDays
                )
                SELECT uad.user_id 
                FROM UserActiveDays uad, MaxDays md 
                WHERE uad.distinct_days = md.max_val AND md.max_val > 0
            """
            
            args = [guild_id, start_date, end_date]
            if ignored:
                args.append(ignored)
                
            rows = await conn.fetch(query, *args)
            return [r['user_id'] for r in rows]

    # ==================== MEMBER JOIN TRACKING ====================
    
    async def upsert_member_join(self, guild_id: int, user_id: int, joined_at: datetime):
        """Registra ou atualiza a data de entrada de um membro."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO member_join_dates (guild_id, user_id, joined_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, user_id)
                DO UPDATE SET joined_at = EXCLUDED.joined_at
            """, guild_id, user_id, joined_at)
    
    async def get_member_join_date(self, guild_id: int, user_id: int) -> Optional[datetime]:
        """Retorna a data de entrada de um membro."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT joined_at FROM member_join_dates
                WHERE guild_id = $1 AND user_id = $2
            """, guild_id, user_id)
    
    async def update_member_last_checked(self, guild_id: int, user_id: int):
        """Atualiza a última vez que verificamos os cargos de um membro."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE member_join_dates
                SET last_checked = NOW()
                WHERE guild_id = $1 AND user_id = $2
            """, guild_id, user_id)
    
    # ==================== AUTO ROLE CONFIG ====================
    
    async def add_auto_role(self, guild_id: int, role_id: int, days_required: int):
        """Adiciona uma configuração de cargo automático."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO auto_role_config (guild_id, role_id, days_required)
                VALUES ($1, $2, $3)
                ON CONFLICT (guild_id, role_id)
                DO UPDATE SET days_required = EXCLUDED.days_required, enabled = TRUE
            """, guild_id, role_id, days_required)
    
    async def remove_auto_role(self, guild_id: int, role_id: int):
        """Remove uma configuração de cargo automático."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM auto_role_config
                WHERE guild_id = $1 AND role_id = $2
            """, guild_id, role_id)
    
    async def get_auto_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Retorna todas as configurações de cargos automáticos de um servidor."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT role_id, days_required, enabled
                FROM auto_role_config
                WHERE guild_id = $1 AND enabled = TRUE
                ORDER BY days_required ASC
            """, guild_id)
            return [dict(row) for row in rows]
    
    async def get_members_needing_roles(self, guild_id: int) -> List[Dict[str, Any]]:
        """Retorna membros que precisam ter cargos verificados."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, joined_at,
                       EXTRACT(EPOCH FROM (NOW() - joined_at))::INTEGER / 86400 as days_in_server
                FROM member_join_dates
                WHERE guild_id = $1
            """, guild_id)
            return [dict(row) for row in rows]
    
    # ==================== GIVEAWAYS ====================
    
    async def create_giveaway(self, guild_id: int, channel_id: int, message_id: int,
                             prize: str, winner_count: int, host_user_id: int,
                             ends_at: datetime, image_url: Optional[str] = None) -> int:
        """Cria um novo sorteio e retorna seu ID."""
        async with self.pool.acquire() as conn:
            giveaway_id = await conn.fetchval("""
                INSERT INTO giveaways (guild_id, channel_id, message_id, prize, 
                                      winner_count, host_user_id, ends_at, image_url)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING giveaway_id
            """, guild_id, channel_id, message_id, prize, winner_count, host_user_id, ends_at, image_url)
            return giveaway_id
    
    async def end_giveaway(self, giveaway_id: int):
        """Marca um sorteio como finalizado."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE giveaways
                SET ended = TRUE
                WHERE giveaway_id = $1
            """, giveaway_id)
    
    async def get_giveaway(self, giveaway_id: int) -> Optional[Dict[str, Any]]:
        """Retorna informações de um sorteio."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM giveaways
                WHERE giveaway_id = $1
            """, giveaway_id)
            return dict(row) if row else None
    
    async def get_giveaway_by_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Retorna um sorteio pelo ID da mensagem."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM giveaways
                WHERE message_id = $1
            """, message_id)
            return dict(row) if row else None
    
    async def get_active_giveaways(self, guild_id: int) -> List[Dict[str, Any]]:
        """Retorna todos os sorteios ativos de um servidor."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM giveaways
                WHERE guild_id = $1 AND ended = FALSE
                ORDER BY ends_at ASC
            """, guild_id)
            return [dict(row) for row in rows]
    
    async def get_expired_giveaways(self) -> List[Dict[str, Any]]:
        """Retorna sorteios que expiraram mas ainda não foram finalizados."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM giveaways
                WHERE ended = FALSE AND ends_at <= NOW()
            """)
            return [dict(row) for row in rows]
    
    async def delete_giveaway(self, giveaway_id: int):
        """Deleta um sorteio (cascade deleta participantes também)."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM giveaways
                WHERE giveaway_id = $1
            """, giveaway_id)
    
    async def add_giveaway_entry(self, giveaway_id: int, user_id: int):
        """Adiciona um participante a um sorteio."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO giveaway_entries (giveaway_id, user_id)
                VALUES ($1, $2)
                ON CONFLICT (giveaway_id, user_id) DO NOTHING
            """, giveaway_id, user_id)
    
    async def remove_giveaway_entry(self, giveaway_id: int, user_id: int):
        """Remove um participante de um sorteio."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM giveaway_entries
                WHERE giveaway_id = $1 AND user_id = $2
            """, giveaway_id, user_id)
    
    async def get_giveaway_entries(self, giveaway_id: int) -> List[int]:
        """Retorna lista de user_ids dos participantes de um sorteio."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id FROM giveaway_entries
                WHERE giveaway_id = $1
            """, giveaway_id)
            return [row['user_id'] for row in rows]
    
    async def get_giveaway_entry_count(self, giveaway_id: int) -> int:
        """Retorna o número de participantes de um sorteio."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT COUNT(*) FROM giveaway_entries
                WHERE giveaway_id = $1
            """, giveaway_id)
    
    # ==================== USER ACTIVITIES ====================
    
    async def start_activity(self, user_id: int, guild_id: int, activity_name: str, 
                            activity_type: str) -> int:
        """Registra início de uma atividade e retorna seu ID."""
        async with self.pool.acquire() as conn:
            activity_id = await conn.fetchval("""
                INSERT INTO user_activities (user_id, guild_id, activity_name, 
                                            activity_type, started_at)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING id
            """, user_id, guild_id, activity_name, activity_type)
            return activity_id
    
    async def end_activity(self, activity_id: int):
        """Finaliza uma atividade."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE user_activities
                SET ended_at = NOW(),
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
                WHERE id = $1 AND ended_at IS NULL
            """, activity_id)
    
    async def get_top_activities(self, guild_id: int, limit: int = 10, 
                                days: int = 30) -> List[Dict[str, Any]]:
        """Retorna as atividades/jogos mais populares."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    activity_name,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as session_count,
                    SUM(duration_seconds) as total_seconds,
                    AVG(duration_seconds) as avg_seconds
                FROM user_activities
                WHERE guild_id = $1 
                  AND started_at >= $2
                  AND duration_seconds IS NOT NULL
                  AND activity_type = 'playing'
                GROUP BY activity_name
                ORDER BY total_seconds DESC
                LIMIT $3
            """, guild_id, cutoff_date, limit)
            
            return [dict(row) for row in rows]
    
    async def get_user_activities(self, user_id: int, guild_id: int, 
                                 days: int = 30) -> List[Dict[str, Any]]:
        """Retorna as atividades de um usuário específico."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    activity_name,
                    COUNT(*) as session_count,
                    SUM(duration_seconds) as total_seconds,
                    AVG(duration_seconds) as avg_seconds
                FROM user_activities
                WHERE user_id = $1 
                  AND guild_id = $2
                  AND started_at >= $3
                  AND duration_seconds IS NOT NULL
                  AND activity_type = 'playing'
                GROUP BY activity_name
                ORDER BY total_seconds DESC
            """, user_id, guild_id, cutoff_date)
            
            return [dict(row) for row in rows]
    
    async def get_yearly_activities(self, guild_id: int, year: int) -> List[Dict[str, Any]]:
        """Retorna retrospectiva anual de atividades."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    activity_name,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as session_count,
                    SUM(duration_seconds) as total_seconds,
                    EXTRACT(MONTH FROM (started_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo'))::INTEGER as month
                FROM user_activities
                WHERE guild_id = $1 
                  AND EXTRACT(YEAR FROM (started_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')) = $2
                  AND duration_seconds IS NOT NULL
                  AND activity_type = 'playing'
                GROUP BY activity_name, month
                ORDER BY total_seconds DESC
            """, guild_id, year)
            
            return [dict(row) for row in rows]

    # ==================== EMBED REQUESTS ====================

    async def get_pending_embeds(self) -> List[Dict[str, Any]]:
        """Retorna solicitações de embed pendentes."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM embed_requests
                WHERE status = 'pending'
                ORDER BY created_at ASC
            """)
            return [dict(row) for row in rows]

    async def update_embed_status(self, request_id: str, status: str, error_message: Optional[str] = None):
        """Atualiza o status de uma solicitação de embed."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE embed_requests
                SET status = $1,
                    error_message = $2
                WHERE id = $3
            """, status, error_message, request_id)

    # ==================== INTERACTION POINTS ====================

    async def get_leaderboard(self, limit: int = 10, days: Optional[int] = None, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retorna o leaderboard de pontos (excluindo bots, SQL direto)."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days if days else 3650) # fallback grande
            
            # Se days for especificado, usamos, senão pegamos tudo (ou ano atual se viesse dos comandos)
            # No Python do stats_commands já tratamos o 'days', aqui ele chega como int ou None (que vira 10 anos)

            rows = await conn.fetch("""
                SELECT 
                    u.username,
                    u.user_id,
                    COALESCE(SUM(p.points), 0) as total_points,
                    RANK() OVER (ORDER BY COALESCE(SUM(p.points), 0) DESC) as rank
                FROM users u
                JOIN interaction_points p ON u.user_id = p.user_id
                WHERE u.is_bot = FALSE
                  AND p.created_at >= $2
                  AND ($3::bigint IS NULL OR p.guild_id = $3 OR p.guild_id IS NULL)
                GROUP BY u.user_id, u.username
                ORDER BY total_points DESC
                LIMIT $1
            """, limit, cutoff_date, guild_id)
            
            return [dict(row) for row in rows]
            
    async def upsert_leaderboard_config(self, guild_id: int, channel_id: int, message_id: int):
        """Salva ou atualiza a configuração do leaderboard persistente."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO leaderboard_config (guild_id, channel_id, message_id, last_updated)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (guild_id) 
                DO UPDATE SET 
                    channel_id = EXCLUDED.channel_id,
                    message_id = EXCLUDED.message_id,
                    last_updated = NOW()
            """, guild_id, channel_id, message_id)
            
    async def get_leaderboard_configs(self) -> List[Dict[str, Any]]:
        """Retorna todas as configurações de leaderboard."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM leaderboard_config")
            return [dict(row) for row in rows]
            
    async def delete_leaderboard_config(self, guild_id: int):
        """Remove a configuração de leaderboard."""
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM leaderboard_config WHERE guild_id = $1", guild_id)

    # ==================== EVENTS ====================

    async def upsert_event(self, event_id: int, guild_id: int, name: str, description: str,
                          start_time, end_time, status: str, creator_id: int,
                          entity_type: str, location: str = None):
        """Insere ou atualiza um evento agendado."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO scheduled_events (
                        event_id, guild_id, name, description, start_time, end_time,
                        status, creator_id, entity_type, location
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (event_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        status = EXCLUDED.status,
                        entity_type = EXCLUDED.entity_type,
                        location = EXCLUDED.location
                """, event_id, guild_id, name, description, start_time, end_time,
                   status, creator_id, entity_type, location)
        except Exception as e:
            logger.error(f"Erro ao salvar evento {event_id}: {e}")

    async def update_event_status(self, event_id: int, status: str):
        """Atualiza o status de um evento."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    UPDATE scheduled_events
                    SET status = $2
                    WHERE event_id = $1
                """, event_id, status)
        except Exception as e:
            logger.error(f"Erro ao atualizar status do evento {event_id}: {e}")

    async def add_event_participant(self, event_id: int, user_id: int, status: str = 'interested'):
        """Adiciona um participante a um evento."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO event_participants (event_id, user_id, status)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (event_id, user_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        joined_at = NOW()
                """, event_id, user_id, status)
        except Exception as e:
            logger.error(f"Erro ao adicionar participante {user_id} ao evento {event_id}: {e}")

    async def remove_event_participant(self, event_id: int, user_id: int):
        """Remove um participante de um evento."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM event_participants
                    WHERE event_id = $1 AND user_id = $2
                """, event_id, user_id)
        except Exception as e:
            logger.error(f"Erro ao remover participante {user_id} do evento {event_id}: {e}")

    async def register_voice_attendance_for_event(self, event_id: int, channel_id: int,
                                                  start_time: Optional[datetime],
                                                  end_time: Optional[datetime]) -> int:
        """Marca presença 'attended' para usuários que estiveram no canal de voz durante o evento."""
        try:
            async with self.pool.acquire() as conn:
                start = start_time or (datetime.now() - timedelta(hours=6))
                end = end_time or datetime.now()
                
                await conn.execute("""
                    INSERT INTO event_participants (event_id, user_id, status, joined_at)
                    SELECT $1, va.user_id, 'attended', NOW()
                    FROM voice_activity va
                    JOIN users u ON va.user_id = u.user_id
                    WHERE va.channel_id = $2
                      AND va.joined_at <= $4
                      AND (va.left_at IS NULL OR va.left_at >= $3)
                      AND u.is_bot = FALSE
                    GROUP BY va.user_id
                    ON CONFLICT (event_id, user_id) DO UPDATE 
                    SET status = 'attended', joined_at = NOW()
                """, event_id, channel_id, start, end)
                return 1
        except Exception as e:
            logger.error(f"Erro ao registrar presença em voz para evento {event_id}: {e}")
            return 0


    # ==================== ADVANCED CONTEXT SYSTEM METHODS ====================

    async def get_server_context(self, guild_id: int) -> Dict[str, Any]:
        """Recupera o contexto global do servidor."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT theme, rules, tone, extras 
                FROM server_contexts 
                WHERE guild_id = $1
            """, guild_id)
            return dict(row) if row else {}

    async def set_server_context(self, guild_id: int, field: str, value: str):
        """Atualiza um campo do contexto do servidor."""
        # Campos permitidos para evitar injeção ou erros
        allowed_fields = ['theme', 'rules', 'tone', 'extras']
        if field not in allowed_fields:
            raise ValueError(f"Campo inválido: {field}")
            
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO server_contexts (guild_id, {field}, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (guild_id) 
                DO UPDATE SET {field} = EXCLUDED.{field}, updated_at = NOW()
            """, guild_id, value)

    async def get_user_bot_profile(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Recupera o perfil comportamental do usuário."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT nickname_preference, tone_preference, interaction_summary, computed_stats
                FROM user_bot_profiles 
                WHERE user_id = $1 AND guild_id = $2
            """, user_id, guild_id)
            return dict(row) if row else {}
            
    async def update_user_bot_profile(self, user_id: int, guild_id: int, updates: Dict[str, Any]):
        """Atualiza campos do perfil do usuário."""
        valid_keys = ['nickname_preference', 'tone_preference', 'interaction_summary', 'computed_stats']
        filtered_updates = {k: v for k, v in updates.items() if k in valid_keys}
        if not filtered_updates:
            return

        set_parts = []
        values = [user_id, guild_id]
        idx = 3
        
        for key, val in filtered_updates.items():
            set_parts.append(f"{key} = ${idx}")
            values.append(val)
            idx += 1

        set_clause = ", ".join(set_parts)
        
        async with self.pool.acquire() as conn:
            # Upsert
            await conn.execute(f"""
                INSERT INTO user_bot_profiles (user_id, guild_id, {', '.join(filtered_updates.keys())}, updated_at)
                VALUES ($1, $2, {', '.join([f'${i}' for i in range(3, idx)])}, NOW())
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET {set_clause}, updated_at = NOW()
            """, *values)

    async def store_memory(self, guild_id: int, content: str, embedding: List[float] = None, user_id: int = None, keywords: List[str] = None):
        """Armazena uma memória de longo prazo."""
        async with self.pool.acquire() as conn:
            if embedding and self.has_vector:
                # Formata embedding para string pgvector '[0.1, 0.2, ...]'
                emb_str = str(embedding)
                await conn.execute("""
                    INSERT INTO bot_memories (guild_id, user_id, content, embedding, keywords)
                    VALUES ($1, $2, $3, $4, $5)
                """, guild_id, user_id, content, emb_str, keywords)
            else:
                await conn.execute("""
                    INSERT INTO bot_memories (guild_id, user_id, content, keywords)
                    VALUES ($1, $2, $3, $4)
                """, guild_id, user_id, content, keywords)

    async def search_memories(self, guild_id: int, embedding: List[float] = None, user_id: int = None, limit: int = 3) -> List[Dict[str, Any]]:
        """Busca memórias relevantes usando similaridade vetorial ou fallback recente."""
        async with self.pool.acquire() as conn:
            if embedding and self.has_vector:
                emb_str = str(embedding)
                # Busca por similaridade de cosseno (<=>)
                # Filtra por guild_id E (user_id específico OU memória global null)
                rows = await conn.fetch("""
                    SELECT content, created_at, 1 - (embedding <=> $1) as similarity
                    FROM bot_memories
                    WHERE guild_id = $2 
                      AND (user_id = $3 OR user_id IS NULL)
                    ORDER BY embedding <=> $1
                    LIMIT $4
                """, emb_str, guild_id, user_id, limit)
                return [dict(row) for row in rows]
            else:
                # Fallback: Apenas as mais recentes
                rows = await conn.fetch("""
                    SELECT content, created_at
                    FROM bot_memories
                    WHERE guild_id = $1 
                      AND (user_id = $2 OR user_id IS NULL)
                    ORDER BY created_at DESC
                    LIMIT $3
                """, guild_id, user_id, limit)
                return [dict(row) for row in rows]

    # ==================== TOURNAMENT SYSTEM ====================

    async def create_tournament(
        self,
        guild_id: int,
        name: str,
        game_name: str,
        format: str = "1v1",
        max_participants: int = 16,
        prize: Optional[str] = None,
        start_time: Optional[datetime] = None,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> int:
        """Cria um novo torneio e retorna o ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO tournaments (
                    guild_id, name, game_name, format, max_participants,
                    prize, start_time, channel_id, message_id, created_by, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'open')
                RETURNING id
            """, guild_id, name, game_name, format, max_participants,
               prize, start_time, channel_id, message_id, created_by)
            return row["id"]

    async def update_tournament_message(self, tournament_id: int, channel_id: int, message_id: int):
        """Atualiza o channel_id e message_id do embed do torneio."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE tournaments
                SET channel_id = $2, message_id = $3
                WHERE id = $1
            """, tournament_id, channel_id, message_id)

    async def get_tournament(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Busca os dados de um torneio pelo ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM tournaments WHERE id = $1
            """, tournament_id)
            return dict(row) if row else None

    async def get_active_tournaments(self, guild_id: int) -> List[Dict[str, Any]]:
        """Retorna todos os torneios abertos ou em andamento de um servidor."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT t.*, COUNT(p.user_id) as participant_count
                FROM tournaments t
                LEFT JOIN tournament_participants p ON t.id = p.tournament_id
                WHERE t.guild_id = $1 AND t.status IN ('open', 'active')
                GROUP BY t.id
                ORDER BY t.created_at DESC
            """, guild_id)
            return [dict(row) for row in rows]

    async def get_recent_tournaments(self, guild_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna os torneios mais recentes com nomes dos vencedores."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    t.*,
                    u1.username as winner_name,
                    u2.username as second_name,
                    u3.username as third_name,
                    COUNT(p.user_id) as participant_count
                FROM tournaments t
                LEFT JOIN users u1 ON t.winner_id = u1.user_id
                LEFT JOIN users u2 ON t.second_place_id = u2.user_id
                LEFT JOIN users u3 ON t.third_place_id = u3.user_id
                LEFT JOIN tournament_participants p ON t.id = p.tournament_id
                WHERE t.guild_id = $1
                GROUP BY t.id, u1.username, u2.username, u3.username
                ORDER BY t.created_at DESC
                LIMIT $2
            """, guild_id, limit)
            return [dict(row) for row in rows]

    async def add_tournament_participant(self, tournament_id: int, user_id: int) -> Dict[str, Any]:
        """Inscreve um participante no torneio se houver vagas."""
        async with self.pool.acquire() as conn:
            tournament = await conn.fetchrow("""
                SELECT status, max_participants FROM tournaments WHERE id = $1
            """, tournament_id)
            if not tournament:
                return {"success": False, "reason": "Torneio não encontrado."}
            if tournament["status"] != "open":
                return {"success": False, "reason": "Inscrições encerradas para este torneio."}

            current_count = await conn.fetchval("""
                SELECT COUNT(*) FROM tournament_participants WHERE tournament_id = $1
            """, tournament_id)

            already_registered = await conn.fetchval("""
                SELECT 1 FROM tournament_participants WHERE tournament_id = $1 AND user_id = $2
            """, tournament_id, user_id)
            if already_registered:
                return {"success": False, "reason": "Você já está inscrito neste torneio!", "count": current_count, "max": tournament["max_participants"]}

            if current_count >= tournament["max_participants"]:
                return {"success": False, "reason": "Torneio lotado! Limite de vagas atingido.", "count": current_count, "max": tournament["max_participants"]}

            await conn.execute("""
                INSERT INTO tournament_participants (tournament_id, user_id, status, registered_at)
                VALUES ($1, $2, 'registered', NOW())
                ON CONFLICT (tournament_id, user_id) DO NOTHING
            """, tournament_id, user_id)

            new_count = current_count + 1
            return {"success": True, "count": new_count, "max": tournament["max_participants"]}

    async def remove_tournament_participant(self, tournament_id: int, user_id: int) -> Dict[str, Any]:
        """Remove a inscrição de um participante."""
        async with self.pool.acquire() as conn:
            tournament = await conn.fetchrow("""
                SELECT status, max_participants FROM tournaments WHERE id = $1
            """, tournament_id)
            if not tournament:
                return {"success": False, "reason": "Torneio não encontrado."}
            if tournament["status"] not in ("open", "active"):
                return {"success": False, "reason": "Não é possível cancelar inscrição em torneio encerrado."}

            res = await conn.execute("""
                DELETE FROM tournament_participants
                WHERE tournament_id = $1 AND user_id = $2
            """, tournament_id, user_id)

            current_count = await conn.fetchval("""
                SELECT COUNT(*) FROM tournament_participants WHERE tournament_id = $1
            """, tournament_id)

            if " 0" in res:
                return {"success": False, "reason": "Você não estava inscrito neste torneio.", "count": current_count, "max": tournament["max_participants"]}

            return {"success": True, "count": current_count, "max": tournament["max_participants"]}

    async def get_tournament_participants(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Retorna os participantes de um torneio (ordenados por seed se sorteado, ou por registro)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT p.user_id, p.status, p.seed_number, p.registered_at, u.username, u.discriminator
                FROM tournament_participants p
                LEFT JOIN users u ON p.user_id = u.user_id
                WHERE p.tournament_id = $1
                ORDER BY 
                    CASE WHEN p.seed_number IS NOT NULL THEN p.seed_number ELSE 99999 END ASC,
                    p.registered_at ASC
            """, tournament_id)
            return [dict(row) for row in rows]

    async def shuffle_tournament_participants(self, tournament_id: int) -> Dict[str, Any]:
        """Embaralha e atribui seeds aleatórios a todos os participantes do torneio."""
        import random
        async with self.pool.acquire() as conn:
            tournament = await conn.fetchrow("SELECT * FROM tournaments WHERE id = $1", tournament_id)
            if not tournament:
                return {"success": False, "reason": "Torneio não encontrado."}

            rows = await conn.fetch("""
                SELECT user_id FROM tournament_participants WHERE tournament_id = $1
            """, tournament_id)

            if len(rows) < 2:
                return {"success": False, "reason": "São necessários pelo menos 2 participantes para realizar o sorteio."}

            user_ids = [r["user_id"] for r in rows]
            random.shuffle(user_ids)

            # Grava o seed de cada um
            for idx, u_id in enumerate(user_ids, 1):
                await conn.execute("""
                    UPDATE tournament_participants
                    SET seed_number = $3
                    WHERE tournament_id = $1 AND user_id = $2
                """, tournament_id, u_id, idx)

            await conn.execute("""
                UPDATE tournaments
                SET is_shuffled = TRUE
                WHERE id = $1
            """, tournament_id)

            # Retorna lista atualizada
            updated = await self.get_tournament_participants(tournament_id)
            fmt_str = tournament.get("format") or "1v1"
            await self.init_tournament_bracket_matches(tournament_id, fmt_str, updated)
            return {"success": True, "participants": updated}

    async def init_tournament_bracket_matches(
        self,
        tournament_id: int,
        format_str: str,
        participants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Gera e inicializa os confrontos do chaveamento no banco de dados."""
        fmt_raw = str(format_str).lower().strip()
        is_2v2 = any(k in fmt_raw for k in ["2v2", "2x2", "dupla", "duplas"])
        is_3v3 = any(k in fmt_raw for k in ["3v3", "3x3", "trio", "trios"])
        team_size = 2 if is_2v2 else (3 if is_3v3 else 1)

        # Agrupa os participantes em equipes ordenadas por seed
        teams = []
        for i in range(0, len(participants), team_size):
            chunk = participants[i:i + team_size]
            teams.append([p["user_id"] for p in chunk])

        num_teams = len(teams)
        if num_teams <= 2:
            bracket_mode = 2
        elif num_teams <= 4:
            bracket_mode = 4
        else:
            bracket_mode = 8

        matches_to_insert = []
        if bracket_mode == 2:
            # Final direta (Jogo 1)
            team_a = teams[0] if len(teams) > 0 else []
            team_b = teams[1] if len(teams) > 1 else []
            matches_to_insert.append({
                "round_name": "final",
                "match_number": 1,
                "team_a_ids": team_a,
                "team_b_ids": team_b,
                "next_match_number": None,
                "next_match_slot": None
            })
        elif bracket_mode == 4:
            # Semifinal 1 (Jogo 1) -> Final (Jogo 3, Slot A)
            matches_to_insert.append({
                "round_name": "semifinal",
                "match_number": 1,
                "team_a_ids": teams[0] if len(teams) > 0 else [],
                "team_b_ids": teams[1] if len(teams) > 1 else [],
                "next_match_number": 3,
                "next_match_slot": "A"
            })
            # Semifinal 2 (Jogo 2) -> Final (Jogo 3, Slot B)
            matches_to_insert.append({
                "round_name": "semifinal",
                "match_number": 2,
                "team_a_ids": teams[2] if len(teams) > 2 else [],
                "team_b_ids": teams[3] if len(teams) > 3 else [],
                "next_match_number": 3,
                "next_match_slot": "B"
            })
            # Final (Jogo 3)
            matches_to_insert.append({
                "round_name": "final",
                "match_number": 3,
                "team_a_ids": [],
                "team_b_ids": [],
                "next_match_number": None,
                "next_match_slot": None
            })
        else:
            # 8 Equipes: Quartas 1..4, Semis 5..6, Final 7
            matches_to_insert.append({
                "round_name": "quartas",
                "match_number": 1,
                "team_a_ids": teams[0] if len(teams) > 0 else [],
                "team_b_ids": teams[1] if len(teams) > 1 else [],
                "next_match_number": 5,
                "next_match_slot": "A"
            })
            matches_to_insert.append({
                "round_name": "quartas",
                "match_number": 2,
                "team_a_ids": teams[2] if len(teams) > 2 else [],
                "team_b_ids": teams[3] if len(teams) > 3 else [],
                "next_match_number": 5,
                "next_match_slot": "B"
            })
            matches_to_insert.append({
                "round_name": "quartas",
                "match_number": 3,
                "team_a_ids": teams[4] if len(teams) > 4 else [],
                "team_b_ids": teams[5] if len(teams) > 5 else [],
                "next_match_number": 6,
                "next_match_slot": "A"
            })
            matches_to_insert.append({
                "round_name": "quartas",
                "match_number": 4,
                "team_a_ids": teams[6] if len(teams) > 6 else [],
                "team_b_ids": teams[7] if len(teams) > 7 else [],
                "next_match_number": 6,
                "next_match_slot": "B"
            })
            matches_to_insert.append({
                "round_name": "semifinal",
                "match_number": 5,
                "team_a_ids": [],
                "team_b_ids": [],
                "next_match_number": 7,
                "next_match_slot": "A"
            })
            matches_to_insert.append({
                "round_name": "semifinal",
                "match_number": 6,
                "team_a_ids": [],
                "team_b_ids": [],
                "next_match_number": 7,
                "next_match_slot": "B"
            })
            matches_to_insert.append({
                "round_name": "final",
                "match_number": 7,
                "team_a_ids": [],
                "team_b_ids": [],
                "next_match_number": None,
                "next_match_slot": None
            })

        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM tournament_matches WHERE tournament_id = $1", tournament_id)
            for m in matches_to_insert:
                await conn.execute("""
                    INSERT INTO tournament_matches (
                        tournament_id, round_name, match_number,
                        team_a_ids, team_b_ids, next_match_number, next_match_slot
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, tournament_id, m["round_name"], m["match_number"], m["team_a_ids"], m["team_b_ids"], m["next_match_number"], m["next_match_slot"])

        return await self.get_tournament_matches(tournament_id)

    async def get_tournament_matches(self, tournament_id: int) -> List[Dict[str, Any]]:
        """Retorna todas as partidas do chaveamento de um torneio."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM tournament_matches
                WHERE tournament_id = $1
                ORDER BY match_number ASC
            """, tournament_id)
            return [dict(r) for r in rows]

    async def record_match_result(
        self,
        tournament_id: int,
        match_number: int,
        score_a: int,
        score_b: int,
        winner_team_ids: List[int]
    ) -> Dict[str, Any]:
        """Registra o placar de uma partida e avança o vencedor para a próxima fase."""
        async with self.pool.acquire() as conn:
            match = await conn.fetchrow("""
                SELECT * FROM tournament_matches
                WHERE tournament_id = $1 AND match_number = $2
            """, tournament_id, match_number)

            if not match:
                return {"success": False, "reason": f"Partida #{match_number} não encontrada para este torneio."}

            await conn.execute("""
                UPDATE tournament_matches
                SET score_a = $3,
                    score_b = $4,
                    winner_team_ids = $5,
                    status = 'completed'
                WHERE tournament_id = $1 AND match_number = $2
            """, tournament_id, match_number, score_a, score_b, winner_team_ids)

            # Avança o vencedor para a próxima partida se houver
            next_num = match["next_match_number"]
            next_slot = match["next_match_slot"]
            if next_num and next_slot:
                if next_slot == "A":
                    await conn.execute("""
                        UPDATE tournament_matches
                        SET team_a_ids = $3
                        WHERE tournament_id = $1 AND match_number = $2
                    """, tournament_id, next_num, winner_team_ids)
                elif next_slot == "B":
                    await conn.execute("""
                        UPDATE tournament_matches
                        SET team_b_ids = $3
                        WHERE tournament_id = $1 AND match_number = $2
                    """, tournament_id, next_num, winner_team_ids)

            # Se for a Grande Final, grava também o placar final no torneio
            if match["round_name"] == "final":
                await conn.execute("""
                    UPDATE tournaments
                    SET final_score = $2
                    WHERE id = $1
                """, tournament_id, f"{score_a} x {score_b}")

            return {
                "success": True,
                "match": dict(match),
                "is_final": (match["round_name"] == "final"),
                "next_match_number": next_num
            }

    async def finish_tournament(
        self,
        tournament_id: int,
        winner_id: int,
        second_place_id: Optional[int] = None,
        third_place_id: Optional[int] = None,
        winner_ids: Optional[List[int]] = None,
        second_place_ids: Optional[List[int]] = None,
        third_place_ids: Optional[List[int]] = None,
        final_score: Optional[str] = None
    ) -> bool:
        """Encerra o torneio e define os vencedores (suporta individuais e equipes/duplas)."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE tournaments
                SET status = 'completed',
                    winner_id = $2,
                    second_place_id = $3,
                    third_place_id = $4,
                    final_score = COALESCE($5, final_score)
                WHERE id = $1
            """, tournament_id, winner_id, second_place_id, third_place_id, final_score)

            w_ids = winner_ids if winner_ids else ([winner_id] if winner_id else [])
            for w_id in w_ids:
                await conn.execute("""
                    UPDATE tournament_participants SET status = 'winner'
                    WHERE tournament_id = $1 AND user_id = $2
                """, tournament_id, w_id)

            s_ids = second_place_ids if second_place_ids else ([second_place_id] if second_place_id else [])
            for s_id in s_ids:
                await conn.execute("""
                    UPDATE tournament_participants SET status = 'runner_up'
                    WHERE tournament_id = $1 AND user_id = $2
                """, tournament_id, s_id)

            t_ids = third_place_ids if third_place_ids else ([third_place_id] if third_place_id else [])
            for t_id in t_ids:
                await conn.execute("""
                    UPDATE tournament_participants SET status = 'third_place'
                    WHERE tournament_id = $1 AND user_id = $2
                """, tournament_id, t_id)

            return True

    async def cancel_tournament(self, tournament_id: int) -> bool:
        """Cancela um torneio aberto."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE tournaments
                SET status = 'cancelled'
                WHERE id = $1
            """, tournament_id)
            return True

    async def get_tournament_hall_of_fame(self, guild_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Retorna o ranking histórico de campeões de torneios com jogos e torneios vencidos."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    tp.user_id,
                    COALESCE(u.username, '') as username,
                    COUNT(DISTINCT tp.tournament_id) as titles_count,
                    ARRAY_AGG(DISTINCT t.game_name) FILTER (WHERE t.game_name IS NOT NULL) as games,
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'id', t.id,
                            'name', t.name,
                            'game_name', t.game_name
                        ) ORDER BY t.id DESC
                    ) as tournaments
                FROM tournament_participants tp
                JOIN tournaments t ON tp.tournament_id = t.id
                LEFT JOIN users u ON tp.user_id = u.user_id
                WHERE t.guild_id = $1 AND t.status = 'completed' AND tp.status = 'winner'
                GROUP BY tp.user_id, u.username
                ORDER BY titles_count DESC
                LIMIT $2
            """, guild_id, limit)
            
            results = []
            for row in rows:
                item = dict(row)
                tourneys = item.get("tournaments")
                if isinstance(tourneys, str):
                    try:
                        item["tournaments"] = json.loads(tourneys)
                    except Exception:
                        item["tournaments"] = []
                elif not isinstance(tourneys, list):
                    item["tournaments"] = []
                results.append(item)
            return results


