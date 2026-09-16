# utils/highlights_scanner.py - Scanner de Clipes e Prints Mais Votados do Ano

import discord
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MEDIA_DOMAINS = [
    "medal.tv",
    "twitch.tv",
    "clips.twitch.tv",
    "youtube.com",
    "youtu.be",
    "streamable.com",
    "tiktok.com",
    "cdn.discordapp.com",
    "media.discordapp.net",
    "tenor.com",
    "imgur.com",
    "twitter.com",
    "x.com",
]


class HighlightsScanner:
    """Responsável por escanear canais de mídia para identificar os destaques mais reagidos."""

    @staticmethod
    def _is_media_message(message: discord.Message) -> bool:
        """Verifica se a mensagem contém anexo visual ou link de mídia."""
        if message.attachments:
            for att in message.attachments:
                content_type = att.content_type or ""
                if content_type.startswith("image/") or content_type.startswith("video/") or att.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".webm")
                ):
                    return True

        content_lower = message.content.lower()
        for domain in MEDIA_DOMAINS:
            if domain in content_lower:
                return True

        return False

    @staticmethod
    def _extract_media_preview(message: discord.Message) -> Optional[str]:
        """Extrai a URL da mídia ou thumbnail do anexo."""
        if message.attachments:
            for att in message.attachments:
                content_type = att.content_type or ""
                if content_type.startswith("image/") or att.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                ):
                    return att.url
                elif content_type.startswith("video/") or att.filename.lower().endswith((".mp4", ".mov", ".webm")):
                    return att.proxy_url or att.url
            return message.attachments[0].url

        # Extrai link do texto se houver embeds
        if message.embeds:
            for emb in message.embeds:
                if emb.thumbnail and emb.thumbnail.url:
                    return emb.thumbnail.url
                if emb.image and emb.image.url:
                    return emb.image.url

        return None

    @classmethod
    async def find_top_clips_and_prints(
        cls, guild: discord.Guild, year: int, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Escaneia os canais de prints e clipes do servidor buscando as mensagens com mais reações do ano.
        """
        start_date = datetime(year, 1, 1)

        # Prioriza canais específicos de prints e clipes
        target_channels = []
        for ch in guild.text_channels:
            name = ch.name.lower()
            if any(k in name for k in ["print", "clip", "mídia", "midia", "destaque", "galeria"]):
                target_channels.append(ch)

        # Se nenhum canal específico de prints for encontrado, adiciona canais de texto visíveis
        if not target_channels:
            target_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).read_message_history][:3]

        logger.info(
            f"🔍 Escaneando {len(target_channels)} canais para Clipes/Prints do Ano {year} em {guild.name}..."
        )

        candidates = []

        for channel in target_channels:
            perms = channel.permissions_for(guild.me)
            if not perms.read_messages or not perms.read_message_history:
                continue

            try:
                # Limita para as últimas 500 mensagens do ano por canal para rapidez
                async for msg in channel.history(limit=500, after=start_date):
                    if msg.author.bot:
                        continue

                    if not cls._is_media_message(msg):
                        continue

                    total_reactions = sum(r.count for r in msg.reactions)
                    if total_reactions == 0:
                        continue

                    # Extrai os emojis mais usados
                    top_reactions = sorted(msg.reactions, key=lambda r: r.count, reverse=True)[:3]
                    reaction_summary = " ".join([f"{str(r.emoji)} {r.count}" for r in top_reactions])

                    candidates.append({
                        "message_id": msg.id,
                        "channel_id": channel.id,
                        "channel_name": channel.name,
                        "user_id": msg.author.id,
                        "username": msg.author.display_name,
                        "avatar_url": str(msg.author.display_avatar.url) if hasattr(msg.author, "display_avatar") else None,
                        "content": msg.content[:200] if msg.content else "",
                        "media_url": cls._extract_media_preview(msg),
                        "reaction_count": total_reactions,
                        "reaction_summary": reaction_summary,
                        "jump_url": msg.jump_url,
                        "created_at": msg.created_at.strftime("%d/%m/%Y"),
                    })
            except Exception as e:
                logger.warning(f"⚠️ Erro ao escanear histórico do canal #{channel.name}: {e}")

        # Ordena candidatos por total de reações
        candidates.sort(key=lambda x: x["reaction_count"], reverse=True)
        return candidates[:limit]
