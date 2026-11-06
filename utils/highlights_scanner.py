"""
Scanner de histórico do Discord para Clipes e Prints Mais Reagidos do Ano.
Possui timeout ajustável (padrão 30.0s) e tratamento de erros resiliente para não travar o bot.
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

# Canais prioritários focados em mídia
DEDICATED_MEDIA_CHANNELS = [
    "prints-e-clips", "prints-e-clipes", "clips", "prints", "midia", "mídia",
    "galeria", "destaques", "memes"
]

# Canais secundários (gerais) para busca complementar caso necessário
SECONDARY_CHANNELS = ["geral", "chat", "resenha"]

# Palavras-chave de canais/categorias restritas (administração, moderação, staff, logs)
RESTRICTED_CHANNEL_KEYWORDS = [
    "admin", "adm", "modera", "staff", "log", "restrito", "privado", "diretoria", "gerencia", "gerência"
]


def is_public_channel(channel: Any) -> bool:
    """Verifica se o canal é público para os membros do servidor (não restrito à administração/staff)."""
    guild = getattr(channel, "guild", None)
    default_role = getattr(guild, "default_role", None) if guild else None
    if default_role is not None:
        try:
            perms = channel.permissions_for(default_role)
            if getattr(perms, "view_channel", True) is False:
                return False
        except Exception:
            pass

    ch_name = getattr(channel, "name", "")
    if not isinstance(ch_name, str):
        ch_name = ""
    cat_obj = getattr(channel, "category", None)
    cat_name = getattr(cat_obj, "name", "") if cat_obj else ""
    if not isinstance(cat_name, str):
        cat_name = ""
    combined = f"{ch_name} {cat_name}".lower()
    if any(kw in combined for kw in RESTRICTED_CHANNEL_KEYWORDS):
        return False

    return True


class HighlightsScanner:
    """Escaneia canais específicos do servidor para encontrar a mídia mais votada do ano."""

    @classmethod
    async def scan_guild_top_clip(
        cls,
        guild: discord.Guild,
        year: int,
        target_channel_names: Optional[List[str]] = None,
        timeout: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """
        Busca o clipe/print com mais engajamento (reações + respostas) no ano fornecido.
        """
        if target_channel_names is None:
            target_channel_names = DEDICATED_MEDIA_CHANNELS + SECONDARY_CHANNELS

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
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        
        dedicated_channels = []
        secondary_channels = []

        for ch in guild.text_channels:
            if not ch.permissions_for(guild.me).read_message_history or not is_public_channel(ch):
                continue

            norm_ch = re.sub(r'[^a-zA-Z0-9]', '', ch.name).lower()

            # Identifica se é canal dedicado de mídia
            is_dedicated = any(re.sub(r'[^a-zA-Z0-9]', '', name).lower() in norm_ch for name in DEDICATED_MEDIA_CHANNELS)
            if is_dedicated and ch not in dedicated_channels:
                dedicated_channels.append(ch)
                continue

            # Identifica se é canal secundário
            is_secondary = any(re.sub(r'[^a-zA-Z0-9]', '', name).lower() in norm_ch for name in SECONDARY_CHANNELS)
            if is_secondary and ch not in secondary_channels:
                secondary_channels.append(ch)

        # Se não encontrou nenhum dos configurados, seleciona o primeiro canal público legível
        if not dedicated_channels and not secondary_channels:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).read_message_history and is_public_channel(ch):
                    secondary_channels.append(ch)
                    break

        logger.info(
            "🔍 Escaneando mídia de %d em %s: %d canal(is) dedicado(s), %d secundário(s)...",
            year, guild.name, len(dedicated_channels), len(secondary_channels)
        )

        top_item = None
        max_score = -1

        # 1. Escaneia primeiro canais dedicados de mídia com varredura completa do ano (sem corte prematuro)
        for ch in dedicated_channels:
            try:
                ch_top = await cls._scan_single_channel(ch, start_of_year, end_of_year, limit=None)
                if ch_top:
                    score = ch_top.get("popularity_score", 0)
                    total_reactions = ch_top.get("reaction_count", 0)
                    if score > max_score or (score == max_score and total_reactions > (top_item.get("reaction_count", 0) if top_item else -1)):
                        max_score = score
                        top_item = ch_top
            except Exception as e:
                logger.warning("Falha ao escanear canal dedicado #%s: %s", ch.name, e)

        # 2. Se nenhum item foi encontrado ou se os canais dedicados estavam vazios, varre secundários com limite razoável
        if not top_item:
            for ch in secondary_channels:
                try:
                    ch_top = await cls._scan_single_channel(ch, start_of_year, end_of_year, limit=1000)
                    if ch_top:
                        score = ch_top.get("popularity_score", 0)
                        total_reactions = ch_top.get("reaction_count", 0)
                        if score > max_score or (score == max_score and total_reactions > (top_item.get("reaction_count", 0) if top_item else -1)):
                            max_score = score
                            top_item = ch_top
                except Exception as e:
                    logger.warning("Falha ao escanear canal secundário #%s: %s", ch.name, e)

        return top_item

    @classmethod
    async def _scan_single_channel(
        cls,
        channel: discord.TextChannel,
        start_of_year: datetime,
        end_of_year: datetime,
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Varre as mensagens de um canal, calcula reações + respostas e retorna o destaque máximo."""
        messages = []
        reply_counts: Dict[int, int] = {}

        # Busca todas as mensagens do ano
        async for message in channel.history(after=start_of_year, limit=limit):
            if message.created_at > end_of_year:
                continue
            messages.append(message)
            if message.reference and message.reference.message_id:
                ref_id = message.reference.message_id
                reply_counts[ref_id] = reply_counts.get(ref_id, 0) + 1

        top_item = None
        max_score = -1

        for message in messages:
            if message.author.bot:
                continue

            # Verifica se tem anexo de mídia ou link de mídia no texto
            media_url = None
            if message.attachments:
                for att in message.attachments:
                    ct = att.content_type or ""
                    if ct.startswith("image/") or ct.startswith("video/") or any(
                        att.filename.lower().endswith(ext)
                        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".webm"]
                    ):
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

            # Fórmula de engajamento da comunidade: 1 reação = 1 pt, 1 resposta direta = 2 pts
            popularity_score = total_reactions + (direct_replies * 2)

            # Só considera se tiver ao menos 1 reação ou 1 resposta
            if popularity_score <= 0:
                continue

            if popularity_score > max_score or (
                popularity_score == max_score and total_reactions > (top_item.get("reaction_count", 0) if top_item else -1)
            ):
                max_score = popularity_score
                top_item = {
                    "message_id": message.id,
                    "channel_name": channel.name,
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
                    "content": message.content[:150] if message.content else ""
                }

        return top_item

    @classmethod
    async def find_first_gif_message_url(
        cls,
        guild: discord.Guild,
        gif_url: str,
        year: int,
        timeout: float = 15.0
    ) -> Optional[str]:
        """
        Busca no histórico dos canais de texto a primeira mensagem que enviou o GIF no ano.
        Usado como fallback quando first_message_url ainda não está salvo no banco.
        """
        if not gif_url or not guild:
            return None

        try:
            return await asyncio.wait_for(
                cls._scan_guild_first_gif(guild, gif_url, year),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("⏱️ Timeout (%ss) ao buscar primeira mensagem do GIF em %s.", timeout, guild.name)
            return None
        except Exception as e:
            logger.warning("Erro ao buscar primeira mensagem do GIF em %s: %s", guild.name, e)
            return None

    @classmethod
    async def _scan_guild_first_gif(
        cls,
        guild: discord.Guild,
        gif_url: str,
        year: int
    ) -> Optional[str]:
        start_of_year = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_of_year = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        base_gif_url = gif_url.split("?")[0].lower()

        priority_names = SECONDARY_CHANNELS + DEDICATED_MEDIA_CHANNELS
        priority_channels = []
        other_channels = []

        for ch in guild.text_channels:
            if not ch.permissions_for(guild.me).read_message_history or not is_public_channel(ch):
                continue
            norm_ch = re.sub(r'[^a-zA-Z0-9]', '', ch.name).lower()
            if any(re.sub(r'[^a-zA-Z0-9]', '', name).lower() in norm_ch for name in priority_names):
                priority_channels.append(ch)
            else:
                other_channels.append(ch)

        earliest_msg = None

        for ch in priority_channels + other_channels:
            try:
                async for message in ch.history(after=start_of_year, before=end_of_year, limit=1500, oldest_first=True):
                    if message.author.bot:
                        continue
                    matched = False
                    if message.content and (gif_url.lower() in message.content.lower() or base_gif_url in message.content.lower()):
                        matched = True
                    elif message.attachments:
                        for att in message.attachments:
                            if att.url.lower() == gif_url.lower() or base_gif_url in att.url.lower():
                                matched = True
                                break
                    if matched:
                        if earliest_msg is None or message.created_at < earliest_msg.created_at:
                            earliest_msg = message
                        break
            except Exception as e:
                logger.debug("Falha ao buscar GIF no canal #%s: %s", ch.name, e)

        return earliest_msg.jump_url if earliest_msg else None
