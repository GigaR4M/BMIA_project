# utils/rawg_client.py — Cliente da API RAWG Video Games Database
"""
Módulo cliente assíncrono para integração com a RAWG Video Games Database API.
Inclui cache em memória com TTL para autocomplete instantâneo e métodos utilitários
para formatação de embeds, notas, requisitos de sistema e links de lojas.
"""

import asyncio
import html
import logging
import re
import time
from typing import Any, Optional
import aiohttp

logger = logging.getLogger(__name__)

RAWG_BASE_URL = "https://api.rawg.io/api"

# Mapeamento de plataformas mãe (parent_platforms) no RAWG
PARENT_PLATFORMS = {
    "pc": 1,
    "playstation": 2,
    "xbox": 3,
    "ios": 4,
    "mac": 5,
    "linux": 6,
    "nintendo": 7,
    "android": 8,
}

# Ícones / emojis por plataforma mãe
PLATFORM_EMOJIS = {
    1: "🖥️ PC",
    2: "🎮 PlayStation",
    3: "🟩 Xbox",
    4: "📱 iOS",
    5: "🍏 Mac",
    6: "🐧 Linux",
    7: "🔴 Nintendo",
    8: "🤖 Android",
}


def clean_html(raw_text: Optional[str], max_len: int = 800) -> str:
    """Remove tags HTML, converte quebras de linha e decodifica entidades HTML."""
    if not raw_text:
        return "Nenhuma descrição disponível."

    # Substitui quebras HTML por newlines
    text = re.sub(r"<(?:br\s*/?|/p|/li)>", "\n", raw_text, flags=re.IGNORECASE)
    # Remove demais tags HTML
    text = re.sub(r"<[^>]+>", "", text)
    # Decodifica entidades como &amp;, &#39;, &quot;
    text = html.unescape(text)
    # Remove múltiplas quebras de linha consecutivas
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def format_metacritic_badge(score: Optional[int]) -> str:
    """Formata o score do Metacritic com indicador visual."""
    if score is None:
        return "N/A"
    if score >= 75:
        return f"🟢 **{score}**/100"
    if score >= 50:
        return f"🟡 **{score}**/100"
    return f"🔴 **{score}**/100"


def format_star_rating(rating: Optional[float], count: int = 0) -> str:
    """Formata avaliação de 0 a 5 estrelas."""
    if not rating:
        return "Sem avaliações"
    stars = "⭐" * max(1, min(5, round(rating)))
    count_str = f" ({count:,} votos)" if count else ""
    return f"{stars} **{rating:.1f}**/5.0{count_str}"


class RawgClient:
    """Cliente assíncrono para consulta e busca de jogos no RAWG com cache TTL."""

    def __init__(
        self,
        api_key: str,
        session: Optional[aiohttp.ClientSession] = None,
        search_ttl: int = 300,
        details_ttl: int = 1800,
    ):
        self.api_key = api_key.strip() if api_key else ""
        self._session = session
        self._owns_session = False
        self.search_ttl = search_ttl  # 5 minutos
        self.details_ttl = details_ttl  # 30 minutos

        # Caches em memória: {key: (timestamp, data)}
        self._search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._details_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    @property
    def is_configured(self) -> bool:
        """Indica se uma chave de API válida foi fornecida."""
        return bool(self.api_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Retorna uma sessão aiohttp ativa."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5.0)
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Fecha a sessão HTTP se criada internamente."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def search_games(
        self,
        query: str,
        parent_platform: Optional[int | str] = None,
        page_size: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Busca jogos por nome/iniciais para autocomplete e comandos.
        Retorna lista de dicionários resumidos dos jogos.
        """
        query_clean = query.strip()
        if not query_clean or not self.is_configured:
            return []

        # Converte plataforma se for string
        platform_id: Optional[int] = None
        if isinstance(parent_platform, str):
            platform_id = PARENT_PLATFORMS.get(parent_platform.lower())
        elif isinstance(parent_platform, int):
            platform_id = parent_platform

        cache_key = f"{query_clean.lower()}|{platform_id}|{page_size}"
        now = time.time()

        # Checa cache
        if cache_key in self._search_cache:
            ts, cached_data = self._search_cache[cache_key]
            if now - ts < self.search_ttl:
                return cached_data

        session = await self._get_session()
        params: dict[str, Any] = {
            "key": self.api_key,
            "search": query_clean,
            "page_size": page_size,
            "search_precise": "true",
        }
        if platform_id:
            params["parent_platforms"] = str(platform_id)

        try:
            async with session.get(
                f"{RAWG_BASE_URL}/games",
                params=params,
                headers={"User-Agent": "BMIA-DiscordBot/1.0"},
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "RAWG search failed for query '%s': HTTP %d",
                        query_clean,
                        resp.status,
                    )
                    return []
                data = await resp.json()
                results = data.get("results", [])

                # Salva em cache
                self._search_cache[cache_key] = (now, results)
                return results

        except asyncio.TimeoutError:
            logger.warning("Timeout ao buscar jogo no RAWG: %s", query_clean)
            return []
        except Exception as e:
            logger.error("Erro ao consultar API RAWG search: %s", e)
            return []

    async def get_game_details(
        self,
        game_id_or_slug: str | int,
    ) -> Optional[dict[str, Any]]:
        """
        Obtém os detalhes completos de um jogo pelo ID ou slug.
        """
        key_str = str(game_id_or_slug).strip()
        if not key_str or not self.is_configured:
            return None

        cache_key = key_str.lower()
        now = time.time()

        if cache_key in self._details_cache:
            ts, cached_data = self._details_cache[cache_key]
            if now - ts < self.details_ttl:
                return cached_data

        session = await self._get_session()
        params = {"key": self.api_key}

        try:
            async with session.get(
                f"{RAWG_BASE_URL}/games/{key_str}",
                params=params,
                headers={"User-Agent": "BMIA-DiscordBot/1.0"},
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "RAWG details failed for '%s': HTTP %d", key_str, resp.status
                    )
                    return None
                data = await resp.json()
                self._details_cache[cache_key] = (now, data)
                return data

        except asyncio.TimeoutError:
            logger.warning("Timeout ao buscar detalhes do jogo no RAWG: %s", key_str)
            return None
        except Exception as e:
            logger.error("Erro ao consultar API RAWG details: %s", e)
            return None

    @staticmethod
    def extract_pc_requirements(game_data: dict[str, Any]) -> dict[str, str]:
        """Extrai requisitos mínimos e recomendados para PC, se disponíveis."""
        reqs = {"minimum": "", "recommended": ""}
        platforms = game_data.get("platforms", []) or []

        for p_entry in platforms:
            platform_info = p_entry.get("platform", {})
            if platform_info.get("slug") == "pc" or platform_info.get("id") == 4:
                req_obj = p_entry.get("requirements", {}) or {}
                reqs["minimum"] = req_obj.get("minimum", "") or ""
                reqs["recommended"] = req_obj.get("recommended", "") or ""
                break

        # Limpa texto de requisitos
        for k in ("minimum", "recommended"):
            if reqs[k]:
                clean_req = re.sub(r"^(?:Minimum|Recommended):\s*", "", reqs[k], flags=re.IGNORECASE)
                clean_req = clean_html(clean_req, max_len=600)
                reqs[k] = clean_req

        return reqs

    @staticmethod
    def extract_stores(game_data: dict[str, Any]) -> list[dict[str, str]]:
        """Extrai lista de lojas com nome e URL para compra."""
        stores_list = []
        raw_stores = game_data.get("stores", []) or []

        for s in raw_stores:
            store_info = s.get("store", {}) or {}
            name = store_info.get("name", "Loja")
            url = s.get("url", "")
            if not url and store_info.get("domain"):
                url = f"https://{store_info.get('domain')}"

            if url:
                stores_list.append({"name": name, "url": url})

        return stores_list
