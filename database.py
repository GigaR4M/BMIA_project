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
            
            # Índices para melhor performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_user ON voice_activity(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_voice_guild ON voice_activity(guild_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_stats_guild_date ON daily_stats(guild_id, date)")
            
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
                    username = EXCLUDED.username,
                    discriminator = EXCLUDED.discriminator,
                    last_seen = NOW()
            """, user_id, username, discriminator)
    
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
            await conn.execute("""
                INSERT INTO daily_stats (guild_id, date, server_member_count)
                VALUES ($1, CURRENT_DATE, $2)
                ON CONFLICT (guild_id, date)
                DO UPDATE SET server_member_count = $2
            """, guild_id, member_count)
    
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
