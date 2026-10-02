import os
import aiohttp
import urllib.parse
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class GameCoverFetcher:
    _igdb_token: Optional[str] = None
    _token_expires_at: float = 0.0

    @classmethod
    async def get_igdb_token(cls, client_id: str, client_secret: str) -> Optional[str]:
        if cls._igdb_token and time.time() < cls._token_expires_at:
            return cls._igdb_token

        try:
            auth_url = f"https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials"
            async with aiohttp.ClientSession() as session:
                async with session.post(auth_url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        cls._igdb_token = data.get("access_token")
                        expires_in = data.get("expires_in", 3600)
                        # Margem de segurança de 5 minutos
                        cls._token_expires_at = time.time() + expires_in - 300
                        return cls._igdb_token
        except Exception as e:
            logger.warning("Erro ao autenticar na IGDB/Twitch: %s", e)
        return None

    @classmethod
    async def fetch_cover_url(cls, game_name: str) -> Optional[str]:
        """
        Busca a arte do jogo. Tenta IGDB primeiro (se chaves estiverem no .env).
        Faz fallback para a API de busca da Steam se IGDB falhar ou não estiver configurado.
        """
        avatar_url = None
        
        # 1. Tenta IGDB
        igdb_client_id = os.getenv("IGDB_CLIENT_ID")
        igdb_client_secret = os.getenv("IGDB_CLIENT_SECRET")

        if igdb_client_id and igdb_client_secret:
            token = await cls.get_igdb_token(igdb_client_id, igdb_client_secret)
            if token:
                try:
                    headers = {
                        "Client-ID": igdb_client_id,
                        "Authorization": f"Bearer {token}"
                    }
                    # O IGDB usa query POST na sintaxe deles
                    body = f'search "{game_name}"; fields name, cover.image_id; limit 1;'
                    async with aiohttp.ClientSession() as session:
                        async with session.post("https://api.igdb.com/v4/games", headers=headers, data=body, timeout=5) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                if data and len(data) > 0 and "cover" in data[0]:
                                    img_id = data[0]["cover"]["image_id"]
                                    # Formato 1080p
                                    avatar_url = f"https://images.igdb.com/igdb/image/upload/t_1080p/{img_id}.jpg"
                except Exception as e:
                    logger.debug("Erro na busca do IGDB para '%s': %s", game_name, e)

        # 2. Fallback Steam API
        if not avatar_url:
            try:
                safe_name = urllib.parse.quote(game_name)
                search_url = f"https://store.steampowered.com/api/storesearch/?term={safe_name}&l=portuguese&cc=BR"
                async with aiohttp.ClientSession() as session:
                    async with session.get(search_url, timeout=4) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("total", 0) > 0:
                                appid = data["items"][0]["id"]
                                avatar_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"
            except Exception as e:
                logger.debug("Erro no fallback da Steam para '%s': %s", game_name, e)

        return avatar_url
