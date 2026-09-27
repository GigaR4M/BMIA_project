# utils/gg_deals_client.py - Cliente de Consulta para GG.deals e Steam Store

import aiohttp
import os
import re
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def extract_steam_appid(url_or_id: Any) -> Optional[int]:
    """Extrai o Steam AppID numérico a partir de uma URL da Steam ou de um ID/string."""
    if not url_or_id:
        return None
    if isinstance(url_or_id, int):
        return url_or_id
    url_str = str(url_or_id).strip()
    match = re.search(r'store\.steampowered\.com/app/(\d+)', url_str)
    if match:
        return int(match.group(1))
    # Se for apenas o número puro
    if url_str.isdigit():
        return int(url_str)
    return None


class GGDealsClient:
    """Cliente para integração com GG.deals API com fallback resiliente para Steam Storefront API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GG_DEALS_API_KEY")
        self.base_url = "https://api.gg.deals/v1"

    async def get_game_info(self, steam_appid_or_url: Any) -> Optional[Dict[str, Any]]:
        """Busca informações completas de preço, desconto, menor histórico e lojas pelo AppID."""
        appid = extract_steam_appid(steam_appid_or_url)
        if not appid:
            logger.warning(f"Não foi possível extrair Steam AppID de: {steam_appid_or_url}")
            return None

        # 1. Tenta buscar via GG.deals API se houver chave configurada
        if self.api_key:
            try:
                gg_data = await self._fetch_from_gg_deals(appid)
                if gg_data:
                    return gg_data
            except Exception as e:
                logger.debug(f"Erro ao consultar GG.deals API para AppID {appid}: {e}")

        # 2. Fallback oficial: Steam Storefront API (gratuita, em BRL)
        return await self._fetch_from_steam(appid)

    async def _fetch_from_gg_deals(self, appid: int) -> Optional[Dict[str, Any]]:
        """Consulta o endpoint da API do GG.deals para obter preços, histórico e lojas parceiras."""
        headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json"
        }
        url = f"{self.base_url}/game/by-steam-app-id/{appid}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Mapeia resposta do GG.deals
                    title = data.get("title") or f"Steam App {appid}"
                    header_img = data.get("image") or f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
                    gg_url = data.get("url") or f"https://gg.deals/game/{appid}/"

                    # Preços oficiais
                    deals = data.get("deals", {})
                    official = deals.get("official", {})
                    best_price = official.get("price") or 0.0
                    retail_price = official.get("retailPrice") or best_price
                    discount = official.get("discountPercent") or 0
                    store_name = official.get("storeName") or "Steam"
                    store_url = official.get("url") or f"https://store.steampowered.com/app/{appid}/"
                    historical_low = data.get("historicalLow", {}).get("price") or best_price

                    return {
                        "steam_appid": appid,
                        "game_name": title,
                        "base_price": float(retail_price),
                        "current_price": float(best_price),
                        "discount_percent": int(discount),
                        "historical_low_price": float(historical_low),
                        "best_store_name": store_name,
                        "best_store_url": store_url,
                        "header_image_url": header_img,
                        "gg_deals_url": gg_url,
                        "is_free": (float(best_price) == 0.0 and float(retail_price) == 0.0)
                    }
        return None

    async def _fetch_from_steam(self, appid: int) -> Optional[Dict[str, Any]]:
        """Consulta a Steam Storefront API pública em BRL para metadados e preços."""
        url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=br&l=brazilian"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        cookies = {
            "birthtime": "283993201",
            "mature_content": "1",
            "lastagecheckage": "1-0-1990",
            "wants_mature_content": "1"
        }
        try:
            jar = aiohttp.CookieJar(unsafe=True)
            async with aiohttp.ClientSession(cookies=cookies, cookie_jar=jar) as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json(content_type=None)
                    app_data = data.get(str(appid), {})
                    if not app_data.get("success"):
                        return None

                    d = app_data.get("data", {})
                    name = d.get("name", f"App {appid}")
                    is_free = d.get("is_free", False)
                    header_img = d.get("header_image") or f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
                    steam_url = f"https://store.steampowered.com/app/{appid}/"

                    price_overview = d.get("price_overview")
                    if price_overview:
                        initial = price_overview.get("initial", 0) / 100.0
                        final = price_overview.get("final", 0) / 100.0
                        discount = price_overview.get("discount_percent", 0)
                    else:
                        initial = 0.0
                        final = 0.0
                        discount = 0

                    return {
                        "steam_appid": appid,
                        "game_name": name,
                        "base_price": float(initial if initial > 0 else final),
                        "current_price": float(final),
                        "discount_percent": int(discount),
                        "historical_low_price": float(final),
                        "best_store_name": "Steam",
                        "best_store_url": steam_url,
                        "header_image_url": header_img,
                        "gg_deals_url": f"https://gg.deals/game/{appid}/",
                        "is_free": is_free
                    }
        except Exception as e:
            logger.error(f"Erro ao consultar Steam API para AppID {appid}: {e}")
            return None
