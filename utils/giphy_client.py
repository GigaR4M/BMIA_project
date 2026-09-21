# utils/giphy_client.py - Cliente Assíncrono da API do GIPHY

import logging
import aiohttp
from typing import Optional, List, Dict, Any
from config import GIPHY_API_KEY

logger = logging.getLogger(__name__)


def to_direct_gif_url(url: str) -> str:
    """Converte URL de página do GIPHY/Tenor para URL direta de imagem/GIF se necessário."""
    if not url:
        return url
    if "media.giphy.com" in url or url.endswith(".gif"):
        return url
    import re
    match = re.search(r'giphy\.com/gifs/(?:[a-zA-Z0-9_-]+-)?([a-zA-Z0-9]+)', url)
    if match:
        gif_id = match.group(1)
        return f"https://media.giphy.com/media/{gif_id}/giphy.gif"
    return url


class GiphyClient:
    """Cliente para busca de GIFs animados via GIPHY API v1."""

    BASE_URL = "https://api.giphy.com/v1/gifs"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else GIPHY_API_KEY
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def search_gifs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Busca GIFs pelo termo de pesquisa no GIPHY.
        Retorna lista de dicionários com 'url' (página GIPHY), 'gif_url' (link direto .gif) e 'description'.
        """
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        if q in self._cache:
            return self._cache[q][:limit]

        if not self.is_configured:
            logger.warning("GiphyClient: GIPHY_API_KEY não configurada.")
            return []

        params = {
            "api_key": self.api_key,
            "q": q,
            "limit": str(max(1, min(limit, 25))),
            "offset": "0",
            "rating": "pg-13",
            "lang": "pt"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/search", params=params, timeout=aiohttp.ClientTimeout(total=8.0)) as resp:
                    if resp.status != 200:
                        logger.warning("GIPHY API HTTP %s: %s", resp.status, await resp.text())
                        return []

                    data = await resp.json()
                    results = []
                    for item in data.get("data", []):
                        images = item.get("images", {})
                        gif_url = images.get("original", {}).get("url") or images.get("downsized_medium", {}).get("url")
                        page_url = item.get("url") or gif_url
                        desc = item.get("title") or q
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
            logger.error("Erro ao buscar GIF no GIPHY (%s): %s", q, e)
            return []

    async def search_gif_url(self, query: str) -> Optional[str]:
        """Busca e retorna a melhor URL direta de GIF para envio no chat."""
        results = await self.search_gifs(query, limit=1)
        if results:
            return results[0].get("gif_url") or results[0].get("url")
        return None
