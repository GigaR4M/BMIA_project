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

    # Timeout padrao para requisicoes HTTP
    _TIMEOUT = aiohttp.ClientTimeout(total=10, connect=5)

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GG_DEALS_API_KEY")
        self.base_url = "https://api.gg.deals/v1"
        # Sessao persistente: reutiliza conexoes TCP (evita overhead de handshake por request)
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_session(self) -> aiohttp.ClientSession:
        """Retorna (ou cria) a sessao HTTP persistente."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=self._TIMEOUT,
                headers={"User-Agent": "BMIA-DiscordBot/1.0"},
            )
        return self._session

    async def close(self) -> None:
        """Fecha a sessao HTTP. Chamar no shutdown do bot."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

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
        session = self._get_session()
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
            # Reutiliza a sessao persistente mas com cookie jar proprio para Steam
            jar = aiohttp.CookieJar(unsafe=True)
            session = self._get_session()
            steam_url = f"https://store.steampowered.com/app/{appid}/"
            header_img = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"

            # 1. Tenta via Steam Storefront API JSON
            name = None
            is_free = False
            initial = 0.0
            final = 0.0
            discount = 0

            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        app_data = data.get(str(appid), {})
                        if app_data.get("success"):
                            d = app_data.get("data", {})
                            name = d.get("name")
                            is_free = d.get("is_free", False)
                            header_img = d.get("header_image") or header_img
                            price_overview = d.get("price_overview")
                            if price_overview:
                                initial = price_overview.get("initial", 0) / 100.0
                                final = price_overview.get("final", 0) / 100.0
                                discount = price_overview.get("discount_percent", 0)
            except Exception as api_err:
                logger.debug(f"Erro ao consultar appdetails JSON para AppID {appid}: {api_err}")

            # 2. Se a API falhar ou nao trouxer preco (pacotes/pre-venda), busca no HTML da loja Steam
            if not name or (final == 0.0 and not is_free):
                try:
                    async with session.get(steam_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as page_resp:
                        if page_resp.status == 200:
                            html = await page_resp.text()
                            if not name:
                                title_m = re.search(r'class="apphub_AppName">([^<]+)</div>', html)
                                if title_m:
                                    name = title_m.group(1).strip()

                            prices = re.findall(r'data-price-final="(\d+)"', html)
                            if prices:
                                final = int(prices[0]) / 100.0
                                initial = final
                                is_free = False
                            elif "free to play" in html.lower() or "gratuito p/ jogar" in html.lower():
                                is_free = True
                except Exception as html_err:
                    logger.debug(f"Erro ao consultar HTML da pagina Steam para AppID {appid}: {html_err}")

            if not name:
                return None

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
            logger.error(f"Erro ao consultar Steam para AppID {appid}: {e}")
            return None
