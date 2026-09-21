# utils/tenor_client.py - Cliente Assíncrono da API do Tenor v2

import logging
import aiohttp
from typing import Optional, List, Dict, Any
from config import TENOR_API_KEY

logger = logging.getLogger(__name__)


class TenorClient:
    """Cliente para busca de GIFs animados via Tenor API v2."""

    BASE_URL = "https://tenor.googleapis.com/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else TENOR_API_KEY
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def search_gifs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Busca GIFs pelo termo de pesquisa no Tenor.
        Retorna lista de dicionários com 'url' (página Tenor), 'gif_url' (link direto .gif) e 'description'.
        """
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        if q in self._cache:
            return self._cache[q][:limit]

        if not self.is_configured:
            logger.warning("TenorClient: TENOR_API_KEY não configurada.")
            return []

        params = {
            "q": q,
            "key": self.api_key,
            "client_key": "bmia_discord_bot",
            "limit": str(max(1, min(limit, 20))),
            "media_filter": "gif,tinygif",
            "contentfilter": "medium",
            "locale": "pt_BR"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/search", params=params, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                    if resp.status != 200:
                        logger.warning("Tenor API HTTP %s: %s", resp.status, await resp.text())
                        return []

                    data = await resp.json()
                    results = []
                    for item in data.get("results", []):
                        media = item.get("media_formats", {})
                        gif_url = media.get("gif", {}).get("url") or media.get("tinygif", {}).get("url")
                        page_url = item.get("url") or gif_url
                        desc = item.get("content_description", q)
                        if gif_url or page_url:
                            results.append({
                                "url": page_url,
                                "gif_url": gif_url or page_url,
                                "description": desc
                            })

                    if results:
                        self._cache[q] = results
                    return results[:limit]

        except Exception as e:
            logger.error("Erro ao buscar GIF no Tenor (%s): %s", q, e)
            return []

    async def search_gif_url(self, query: str) -> Optional[str]:
        """Busca e retorna a melhor URL de GIF diretamente para envio no chat."""
        results = await self.search_gifs(query, limit=1)
        if results:
            # Prefere o link da página do Tenor que o Discord expande nativamente ou o link direto .gif
            return results[0].get("url") or results[0].get("gif_url")
        return None
