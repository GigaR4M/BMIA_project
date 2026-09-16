"""
Scanner de histórico do Discord para Clipes e Prints Mais Reagidos do Ano.
Possui timeout rígido (3.0s) e tratamento de erros resiliente para não travar o bot.
"""

import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import discord

logger = logging.getLogger(__name__)

MEDIA_REGEX = re.compile(
    r'(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp|\.mp4|\.mov|\.webm))|'
    r'(https?://(?:clips\.twitch\.tv|www\.twitch\.tv/[^/]+/clip|medal\.tv/games/[^/]+/clips/|medal\.tv/clips/|streamable\.com/|youtube\.com/shorts/|youtu\.be/|www\.youtube\.com/watch\?v=)[^\s]+)',
    re.IGNORECASE
)


class HighlightsScanner:
    """Escaneia canais específicos do servidor para encontrar a mídia mais votada do ano."""

    @classmethod
    async def scan_guild_top_clip(
        cls,
        guild: discord.Guild,
        year: int,
        target_channel_names: Optional[List[str]] = None,
        timeout: float = 3.0
    ) -> Optional[Dict[str, Any]]:
        """
        Busca o clipe/print com mais reações no ano corrente com timeout estrito.
        """
        if target_channel_names is None:
            target_channel_names = ["prints-e-clips", "prints-e-clipes", "clips", "prints", "geral", "mídia"]

        try:
            return await asyncio.wait_for(
                cls._scan_guild_clips(guild, year, target_channel_names),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("⏱️ Timeout (%ss) atingido ao escanear canais de clipes em %s.", timeout, guild.name)
            return None
        except Exception as e:
            logger.error("❌ Erro ao escanear clipes em %s: %s", guild.name, e)
            return None

    @classmethod
    async def _scan_guild_clips(
        cls,
        guild: discord.Guild,
        year: int,
        target_channel_names: List[str]
    ) -> Optional[Dict[str, Any]]:
        start_of_year = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        channels_to_scan = []

        for name in target_channel_names:
            normalized_target = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
            for ch in guild.text_channels:
                norm_ch = re.sub(r'[^a-zA-Z0-9]', '', ch.name).lower()
                if normalized_target in norm_ch and ch.permissions_for(guild.me).read_message_history:
                    if ch not in channels_to_scan:
                        channels_to_scan.append(ch)

        if not channels_to_scan:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).read_message_history:
                    channels_to_scan.append(ch)
                    break

        if not channels_to_scan:
            return None

        logger.info("🔍 Escaneando %d canal(is) para Clipes/Prints de %d em %s...", len(channels_to_scan), year, guild.name)
        top_item = None
        max_score = -1

        for ch in channels_to_scan:
            try:
                messages = []
                reply_counts: Dict[int, int] = {}

                async for message in ch.history(after=start_of_year, limit=300):
                    messages.append(message)
                    if message.reference and message.reference.message_id:
                        ref_id = message.reference.message_id
                        reply_counts[ref_id] = reply_counts.get(ref_id, 0) + 1

                for message in messages:
                    if message.author.bot:
                        continue

                    # Verifica se tem anexo de mídia ou link de mídia no texto
                    media_url = None
                    if message.attachments:
                        for att in message.attachments:
                            ct = att.content_type or ""
                            if ct.startswith("image/") or ct.startswith("video/") or any(att.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov"]):
                                media_url = att.url
                                break
                    
                    if not media_url and message.content:
                        match = MEDIA_REGEX.search(message.content)
                        if match:
                            media_url = match.group(0)

                    if not media_url:
                        continue

                    total_reactions = sum(r.count for r in message.reactions)
                    direct_replies = reply_counts.get(message.id, 0)
                    
                    # Fórmula de engajamento: 1 reação = 1 pt, 1 resposta = 2 pts
                    popularity_score = total_reactions + (direct_replies * 2)

                    if popularity_score > max_score or (popularity_score == max_score and total_reactions > (top_item.get("reaction_count", 0) if top_item else -1)):
                        max_score = popularity_score
                        top_item = {
                            "message_id": message.id,
                            "channel_name": ch.name,
                            "user_id": message.author.id,
                            "username": message.author.display_name,
                            "avatar_url": str(message.author.display_avatar.url),
                            "media_url": media_url,
                            "reaction_count": total_reactions,
                            "reply_count": direct_replies,
                            "popularity_score": popularity_score,
                            "reaction_summary": " ".join(f"{r.emoji} {r.count}" for r in message.reactions[:5]),
                            "created_at": message.created_at.strftime("%d/%m/%Y"),
                            "jump_url": message.jump_url,
                            "content": message.content[:150]
                        }
            except Exception as e:
                logger.warning("Falha ao escanear histórico de #%s: %s", ch.name, e)

        return top_item
