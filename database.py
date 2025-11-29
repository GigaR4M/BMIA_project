# database.py - Módulo de Gerenciamento do Banco de Dados PostgreSQL

import asyncpg
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
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
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_seen TIMESTAMP DEFAULT NOW()
                )
            """)
            
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
            
            # Índices para melhor performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_activity(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_guild ON voice_activity(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_guild_date ON daily_stats(guild_id, date)")
            
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

            
            logger.info("✅ Schema do banco de dados inicializado")
    
    # ==================== INSERÇÃO DE DADOS ====================
    
    async def upsert_user(self, user_id: int, username: str, discriminator: str = None):
        """Insere ou atualiza um usuário."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, discriminator, last_seen)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    username = CASE WHEN EXCLUDED.username != 'Unknown' THEN EXCLUDED.username ELSE users.username END,
                    discriminator = CASE WHEN EXCLUDED.discriminator != '0000' THEN EXCLUDED.discriminator ELSE users.discriminator END,
                    last_seen = NOW()
            """, user_id, username, discriminator)
            
    async def add_interaction_point(self, user_id: int, points: int, interaction_type: str):
        """Adiciona pontos de interação para um usuário."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO interaction_points (user_id, points, interaction_type)
                VALUES ($1, $2, $3)
            """, user_id, points, interaction_type)
    
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
        """Retorna os usuários mais ativos por mensagens."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    u.user_id,
                    u.username,
                    COUNT(m.message_id) as message_count
                FROM users u
                JOIN messages m ON u.user_id = m.user_id
                WHERE m.guild_id = $1 AND m.created_at >= $2
                GROUP BY u.user_id, u.username
                ORDER BY message_count DESC
                LIMIT $3
            """, guild_id, cutoff_date, limit)
            
            return [dict(row) for row in rows]
    
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
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Total de mensagens
            total_messages = await conn.fetchval("""
                SELECT COUNT(*) FROM messages 
                WHERE user_id = $1 AND guild_id = $2 AND created_at >= $3
            """, user_id, guild_id, cutoff_date)
            
            # Canais mais usados
            top_channels = await conn.fetch("""
                SELECT c.channel_name, COUNT(*) as count
                FROM messages m
                JOIN channels c ON m.channel_id = c.channel_id
                WHERE m.user_id = $1 AND m.guild_id = $2 AND m.created_at >= $3
                GROUP BY c.channel_name
                ORDER BY count DESC
                LIMIT 3
            """, user_id, guild_id, cutoff_date)
            
            return {
                'total_messages': total_messages,
                'top_channels': [dict(row) for row in top_channels],
                'period_days': days
            }
    
    async def get_messages_per_day(self, guild_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Retorna contagem de mensagens por dia."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as message_count
                FROM messages
                WHERE guild_id = $1 AND created_at >= $2
                GROUP BY DATE(created_at)
                ORDER BY date
            """, guild_id, cutoff_date)
            
            return [dict(row) for row in rows]
    
    async def get_hourly_activity(self, guild_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Retorna atividade por hora do dia (para heatmap)."""
        async with self.pool.acquire() as conn:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            rows = await conn.fetch("""
                SELECT 
                    EXTRACT(HOUR FROM created_at)::INTEGER as hour,
                    COUNT(*) as message_count
                FROM messages
                WHERE guild_id = $1 AND created_at >= $2
                GROUP BY hour
                ORDER BY hour
            """, guild_id, cutoff_date)
            
            return [dict(row) for row in rows]
    
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
                    EXTRACT(MONTH FROM started_at)::INTEGER as month
                FROM user_activities
                WHERE guild_id = $1 
                  AND EXTRACT(YEAR FROM started_at) = $2
                  AND duration_seconds IS NOT NULL
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

    async def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna o leaderboard de pontos."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM get_leaderboard($1)
            """, limit)
            return [dict(row) for row in rows]

