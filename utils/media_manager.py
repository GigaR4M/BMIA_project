# utils/media_manager.py - Gerenciador de Mídias e Reações para Retrospectiva Anual

import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import discord
from database import Database

logger = logging.getLogger(__name__)

MEDIA_REGEX = re.compile(
    r'(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp|\.mp4|\.mov|\.webm))|'
    r'(https?://(?:clips\.twitch\.tv|www\.twitch\.tv/[^/]+/clip|medal\.tv/games/[^/]+/clips/|medal\.tv/clips/|streamable\.com/|youtube\.com/shorts/|youtu\.be/|www\.youtube\.com/watch\?v=)[^\s]+)',
    re.IGNORECASE
)

DEDICATED_MEDIA_CHANNELS = [
    "prints-e-clips", "prints-e-clipes", "clips", "prints", "midia", "mídia",
    "galeria", "destaques", "memes"
]


class MediaManager:
    """Gerencia a persistência e pontuação de mídias/prints/clipes em tempo real no PostgreSQL."""

    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def extract_media_url(message: discord.Message) -> Optional[str]:
        """Extrai URL de anexo de imagem/vídeo ou link de mídia no texto."""
        if message.attachments:
            for att in message.attachments:
                ct = att.content_type or ""
                if ct.startswith("image/") or ct.startswith("video/") or any(
                    att.filename.lower().endswith(ext)
                    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".webm"]
                ):
                    return att.url

        if message.content:
            match = MEDIA_REGEX.search(message.content)
            if match:
                return match.group(0)

        return None

    @staticmethod
    def is_media_channel(channel_name: str) -> bool:
        """Verifica se o nome do canal é dedicado a postagem de mídia."""
        norm = re.sub(r'[^a-zA-Z0-9]', '', channel_name).lower()
        return any(re.sub(r'[^a-zA-Z0-9]', '', name).lower() in norm for name in DEDICATED_MEDIA_CHANNELS)

    async def on_message(self, message: discord.Message) -> None:
        """Processa novas mensagens para identificar postagens de mídia ou respostas."""
        if message.author.bot or not message.guild:
            return

        # 1. Se for uma resposta a outra mensagem, verifica se a mensagem pai é uma mídia monitorada
        if message.reference and message.reference.message_id:
            parent_id = message.reference.message_id
            try:
                await self.db.increment_media_highlight_reply(parent_id)
            except Exception as e:
                logger.debug("Erro ao tentar incrementar resposta para mídia %s: %s", parent_id, e)

        # 2. Verifica se a mensagem possui mídia
        media_url = self.extract_media_url(message)
        if not media_url:
            return

        try:
            reactions_dict = {str(r.emoji): r.count for r in message.reactions}
            total_reactions = sum(r.count for r in message.reactions)
            avatar_url = str(message.author.display_avatar.url) if hasattr(message.author, 'display_avatar') else None

            await self.db.upsert_media_highlight(
                message_id=message.id,
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                channel_name=message.channel.name,
                user_id=message.author.id,
                username=message.author.display_name,
                avatar_url=avatar_url,
                media_url=media_url,
                content=message.content[:200] if message.content else "",
                reaction_count=total_reactions,
                reactions_json=reactions_dict,
                reply_count=0,
                jump_url=message.jump_url,
                created_at=message.created_at
            )
            logger.info("📸 Mídia registrada no banco de dados [msg_id: %s, canal: #%s, autor: %s]", message.id, message.channel.name, message.author.display_name)
        except Exception as e:
            logger.error("❌ Erro ao registrar mídia no banco: %s", e, exc_info=True)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent, client: discord.Client) -> None:
        """Sincroniza as reações no banco quando um usuário reage a uma mensagem de mídia."""
        await self._sync_message_reactions(payload.channel_id, payload.message_id, client)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent, client: discord.Client) -> None:
        """Sincroniza as reações no banco quando uma reação é removida."""
        await self._sync_message_reactions(payload.channel_id, payload.message_id, client)

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Remove a mídia do banco caso a mensagem seja deletada."""
        try:
            await self.db.delete_media_highlight(payload.message_id)
        except Exception as e:
            logger.debug("Erro ao deletar mídia %s: %s", payload.message_id, e)

    async def _sync_message_reactions(self, channel_id: int, message_id: int, client: discord.Client) -> None:
        """Atualiza a contagem de reações no banco se a mensagem for uma mídia monitorada."""
        try:
            # Verifica se essa mensagem já é uma mídia cadastrada no banco
            existing = await self.db.get_media_highlight(message_id)
            
            channel = client.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            # Se não está no banco mas o canal é dedicado de mídia, busca a mensagem para cadastrá-la
            if not existing and not self.is_media_channel(channel.name):
                return

            msg = await channel.fetch_message(message_id)
            if not msg or msg.author.bot:
                return

            media_url = self.extract_media_url(msg)
            if not media_url:
                return

            reactions_dict = {str(r.emoji): r.count for r in msg.reactions}
            total_reactions = sum(r.count for r in msg.reactions)
            avatar_url = str(msg.author.display_avatar.url) if hasattr(msg.author, 'display_avatar') else None

            await self.db.upsert_media_highlight(
                message_id=msg.id,
                guild_id=msg.guild.id,
                channel_id=msg.channel.id,
                channel_name=msg.channel.name,
                user_id=msg.author.id,
                username=msg.author.display_name,
                avatar_url=avatar_url,
                media_url=media_url,
                content=msg.content[:200] if msg.content else "",
                reaction_count=total_reactions,
                reactions_json=reactions_dict,
                reply_count=existing.get("reply_count", 0) if existing else 0,
                jump_url=msg.jump_url,
                created_at=msg.created_at
            )
        except discord.NotFound:
            pass
        except Exception as e:
            logger.debug("Erro ao sincronizar reações da mídia %s: %s", message_id, e)

    async def sync_guild_media_history(self, guild: discord.Guild, year: int) -> int:
        """
        Rotina de Backfill: Varre os canais de mídia do servidor para indexar todo o histórico
        do ano no PostgreSQL. Retorna o total de mídias inseridas/atualizadas.
        """
        start_of_year = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        count = 0

        logger.info("🔄 Iniciando sincronização/backfill de mídias de %d para o servidor '%s'...", year, guild.name)

        for ch in guild.text_channels:
            if not ch.permissions_for(guild.me).read_message_history or not self.is_media_channel(ch.name):
                continue

            try:
                messages = []
                reply_counts: Dict[int, int] = {}

                async for message in ch.history(after=start_of_year, limit=None):
                    if message.created_at > end_of_year:
                        continue
                    messages.append(message)
                    if message.reference and message.reference.message_id:
                        ref_id = message.reference.message_id
                        reply_counts[ref_id] = reply_counts.get(ref_id, 0) + 1

                for message in messages:
                    if message.author.bot:
                        continue

                    media_url = self.extract_media_url(message)
                    if not media_url:
                        continue

                    reactions_dict = {str(r.emoji): r.count for r in message.reactions}
                    total_reactions = sum(r.count for r in message.reactions)
                    direct_replies = reply_counts.get(message.id, 0)
                    avatar_url = str(message.author.display_avatar.url) if hasattr(message.author, 'display_avatar') else None

                    await self.db.upsert_media_highlight(
                        message_id=message.id,
                        guild_id=guild.id,
                        channel_id=ch.id,
                        channel_name=ch.name,
                        user_id=message.author.id,
                        username=message.author.display_name,
                        avatar_url=avatar_url,
                        media_url=media_url,
                        content=message.content[:200] if message.content else "",
                        reaction_count=total_reactions,
                        reactions_json=reactions_dict,
                        reply_count=direct_replies,
                        jump_url=message.jump_url,
                        created_at=message.created_at
                    )
                    count += 1
            except Exception as e:
                logger.warning("Falha ao sincronizar histórico do canal #%s: %s", ch.name, e)

        logger.info("✅ Sincronização concluída: %d mídias indexadas para %s (%d)", count, guild.name, year)
        return count
