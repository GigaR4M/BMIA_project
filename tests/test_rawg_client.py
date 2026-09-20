# tests/test_rawg_client.py — Testes unitários do cliente RAWG e formatadores
"""
Testa as funções auxiliares e a lógica de consulta/cache do RawgClient.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from utils.rawg_client import (
    RawgClient,
    clean_html,
    format_metacritic_badge,
    format_star_rating,
    PARENT_PLATFORMS,
)


class TestRawgFormatters:
    """Testa os formatadores de texto, notas e requisitos do RAWG."""

    def test_clean_html_removes_tags_and_decodes_entities(self):
        raw = "<p>The Witcher 3 &amp; Wild Hunt is an RPG.<br>Enjoy <b>Geralt&#39;s</b> journey.</p>"
        result = clean_html(raw)
        assert "<p>" not in result
        assert "<b>" not in result
        assert "&amp;" not in result
        assert "&" in result
        assert "Geralt's" in result

    def test_clean_html_empty_input(self):
        assert clean_html(None) == "Nenhuma descrição disponível."
        assert clean_html("") == "Nenhuma descrição disponível."

    def test_format_metacritic_badge(self):
        assert "🟢" in format_metacritic_badge(92)
        assert "92" in format_metacritic_badge(92)
        assert "🟡" in format_metacritic_badge(68)
        assert "68" in format_metacritic_badge(68)
        assert "🔴" in format_metacritic_badge(45)
        assert "45" in format_metacritic_badge(45)
        assert format_metacritic_badge(None) == "N/A"

    def test_format_star_rating(self):
        assert "⭐" in format_star_rating(4.7, 1500)
        assert "4.7" in format_star_rating(4.7, 1500)
        assert "1,500" in format_star_rating(4.7, 1500)
        assert format_star_rating(None) == "Sem avaliações"

    def test_parent_platforms_mapping(self):
        assert PARENT_PLATFORMS["pc"] == 1
        assert PARENT_PLATFORMS["playstation"] == 2
        assert PARENT_PLATFORMS["xbox"] == 3
        assert PARENT_PLATFORMS["nintendo"] == 7

    def test_extract_pc_requirements(self):
        game_data = {
            "platforms": [
                {
                    "platform": {"id": 4, "slug": "pc", "name": "PC"},
                    "requirements": {
                        "minimum": "Minimum: OS: Windows 10, CPU: Intel i5, RAM: 8 GB",
                        "recommended": "Recommended: OS: Windows 11, CPU: Intel i7, RAM: 16 GB",
                    },
                },
                {
                    "platform": {"id": 18, "slug": "playstation4", "name": "PlayStation 4"},
                    "requirements": {},
                },
            ]
        }
        reqs = RawgClient.extract_pc_requirements(game_data)
        assert "Windows 10" in reqs["minimum"]
        assert "Windows 11" in reqs["recommended"]
        assert not reqs["minimum"].lower().startswith("minimum:")

    def test_extract_stores(self):
        game_data = {
            "stores": [
                {
                    "store": {"id": 1, "name": "Steam", "domain": "store.steampowered.com"},
                    "url": "https://store.steampowered.com/app/292030",
                },
                {
                    "store": {"id": 11, "name": "Epic Games", "domain": "epicgames.com"},
                    "url": "",
                },
            ]
        }
        stores = RawgClient.extract_stores(game_data)
        assert len(stores) == 2
        assert stores[0]["name"] == "Steam"
        assert "steampowered.com" in stores[0]["url"]
        assert stores[1]["name"] == "Epic Games"
        assert stores[1]["url"] == "https://epicgames.com"


class TestRawgClient:
    """Testes assíncronos do RawgClient com mocks de rede e cache."""

    def test_is_configured(self):
        client_no_key = RawgClient(api_key="")
        assert not client_no_key.is_configured

        client_with_key = RawgClient(api_key="mock_key_123")
        assert client_with_key.is_configured

    @pytest.mark.asyncio
    async def test_search_games_unconfigured_returns_empty(self):
        client = RawgClient(api_key="")
        results = await client.search_games("Witcher")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_games_with_cache(self):
        client = RawgClient(api_key="test_key")

        mock_response_data = {
            "results": [
                {"id": 3328, "name": "The Witcher 3: Wild Hunt", "released": "2015-05-18"},
                {"id": 3329, "name": "The Witcher 2: Assassins of Kings", "released": "2011-05-17"},
            ]
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_data)

        mock_session = MagicMock()
        mock_session.get.return_value.__aenter__.return_value = mock_resp
        mock_session.closed = False

        client._session = mock_session

        # Primeira chamada (busca via HTTP mock)
        results1 = await client.search_games("Witcher", parent_platform="pc", page_size=5)
        assert len(results1) == 2
        assert results1[0]["name"] == "The Witcher 3: Wild Hunt"
        assert mock_session.get.call_count == 1

        # Segunda chamada com os mesmos parâmetros (deve usar cache em memória)
        results2 = await client.search_games("Witcher", parent_platform="pc", page_size=5)
        assert len(results2) == 2
        assert mock_session.get.call_count == 1  # Não deve ter feito nova chamada HTTP

    @pytest.mark.asyncio
    async def test_get_game_details_with_cache(self):
        client = RawgClient(api_key="test_key")

        mock_details = {
            "id": 3328,
            "name": "The Witcher 3: Wild Hunt",
            "slug": "the-witcher-3-wild-hunt",
            "metacritic": 92,
            "rating": 4.65,
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_details)

        mock_session = MagicMock()
        mock_session.get.return_value.__aenter__.return_value = mock_resp
        mock_session.closed = False

        client._session = mock_session

        # Primeira chamada
        data1 = await client.get_game_details("3328")
        assert data1 is not None
        assert data1["name"] == "The Witcher 3: Wild Hunt"
        assert mock_session.get.call_count == 1

        # Segunda chamada (cache)
        data2 = await client.get_game_details("3328")
        assert data2 is not None
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_get_game_details_http_error(self):
        client = RawgClient(api_key="test_key")

        mock_resp = AsyncMock()
        mock_resp.status = 404

        mock_session = MagicMock()
        mock_session.get.return_value.__aenter__.return_value = mock_resp
        mock_session.closed = False

        client._session = mock_session

        data = await client.get_game_details("nonexistent_game")
        assert data is None
