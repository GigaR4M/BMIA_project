# tests/test_steam_deals.py - Testes para o sistema de promoções e eventos sazonais da Steam

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from utils.gg_deals_client import extract_steam_appid, GGDealsClient
from commands.deals_commands import format_countdown


class TestSteamAppIdExtraction:
    """Testes de extração de Steam AppID a partir de vários formatos de link."""

    def test_extract_full_url(self):
        url = "https://store.steampowered.com/app/2680010/The_First_Berserker_Khazan/"
        assert extract_steam_appid(url) == 2680010

    def test_extract_url_with_query_params(self):
        url = "https://store.steampowered.com/app/2322010/God_of_War_Ragnarok/?snr=1_4_4__118"
        assert extract_steam_appid(url) == 2322010

    def test_extract_short_url(self):
        url = "https://store.steampowered.com/app/892970"
        assert extract_steam_appid(url) == 892970

    def test_extract_integer_or_numeric_string(self):
        assert extract_steam_appid(2358720) == 2358720
        assert extract_steam_appid("814380") == 814380

    def test_extract_invalid_url(self):
        assert extract_steam_appid("https://example.com/games/123") is None
        assert extract_steam_appid("") is None
        assert extract_steam_appid(None) is None


class TestCountdownFormatting:
    """Testes para a formatação de contagem regressiva em português."""

    def test_countdown_days_and_hours(self):
        now = datetime(2026, 9, 27, 14, 0, 0, tzinfo=timezone.utc)
        target = now + timedelta(days=3, hours=5, minutes=30)
        formatted = format_countdown(target, now)
        assert formatted == "3d 5h"

    def test_countdown_hours_and_minutes(self):
        now = datetime(2026, 9, 27, 14, 0, 0, tzinfo=timezone.utc)
        target = now + timedelta(hours=2, minutes=45)
        formatted = format_countdown(target, now)
        assert formatted == "2h 45min"

    def test_countdown_minutes_only(self):
        now = datetime(2026, 9, 27, 14, 0, 0, tzinfo=timezone.utc)
        target = now + timedelta(minutes=45)
        formatted = format_countdown(target, now)
        assert formatted == "45min"

    def test_countdown_already_reached(self):
        now = datetime(2026, 9, 27, 14, 0, 0, tzinfo=timezone.utc)
        target = now - timedelta(minutes=5)
        formatted = format_countdown(target, now)
        assert formatted == "agora"


@pytest.mark.asyncio
class TestGGDealsClient:
    """Testes do cliente GGDealsClient com fallback para Steam Storefront API."""

    async def test_steam_fallback_mock(self):
        client = GGDealsClient(api_key=None)
        mock_response = {
            "2680010": {
                "success": True,
                "data": {
                    "name": "The First Berserker: Khazan",
                    "is_free": False,
                    "header_image": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2680010/header.jpg",
                    "price_overview": {
                        "initial": 29990,
                        "final": 23992,
                        "discount_percent": 20
                    }
                }
            }
        }

        with patch.object(client, "_fetch_from_steam", new_callable=AsyncMock) as mock_steam:
            mock_steam.return_value = {
                "steam_appid": 2680010,
                "game_name": "The First Berserker: Khazan",
                "base_price": 299.90,
                "current_price": 239.92,
                "discount_percent": 20,
                "historical_low_price": 239.92,
                "best_store_name": "Steam",
                "best_store_url": "https://store.steampowered.com/app/2680010/",
                "header_image_url": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2680010/header.jpg",
                "gg_deals_url": "https://gg.deals/game/2680010/",
                "is_free": False
            }

            info = await client.get_game_info("https://store.steampowered.com/app/2680010/")
            assert info is not None
            assert info["steam_appid"] == 2680010
            assert info["game_name"] == "The First Berserker: Khazan"
            assert info["current_price"] == 239.92
            assert info["discount_percent"] == 20

    async def test_gg_deals_official_keyshop_data(self):
        client = GGDealsClient(api_key="mock_key")
        with patch.object(client, "_fetch_from_gg_deals", new_callable=AsyncMock) as mock_gg:
            mock_gg.return_value = {
                "steam_appid": 2322010,
                "game_name": "God of War Ragnarök",
                "base_price": 249.90,
                "current_price": 187.42,
                "discount_percent": 25,
                "historical_low_price": 187.42,
                "best_store_name": "Nuuvem",
                "best_store_url": "https://www.nuuvem.com/item/god-of-war-ragnarok",
                "header_image_url": "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2322010/header.jpg",
                "gg_deals_url": "https://gg.deals/game/2322010/",
                "is_free": False
            }

            info = await client.get_game_info(2322010)
            assert info is not None
            assert info["best_store_name"] == "Nuuvem"
            assert info["discount_percent"] == 25


@pytest.mark.asyncio
class TestSteamDatabaseIntegration:
    """Testes estruturais de métodos de banco de dados para jogos e eventos."""

    async def test_database_tracked_games_methods_interface(self):
        from database import Database
        # Verificando se os métodos existem na classe Database
        assert hasattr(Database, "add_tracked_game")
        assert hasattr(Database, "get_tracked_games")
        assert hasattr(Database, "get_all_tracked_games")
        assert hasattr(Database, "get_tracked_game")
        assert hasattr(Database, "update_tracked_game_price")
        assert hasattr(Database, "mark_tracked_game_notified")
        assert hasattr(Database, "remove_tracked_game")
        assert hasattr(Database, "upsert_steam_event")
        assert hasattr(Database, "get_upcoming_steam_events")
        assert hasattr(Database, "get_due_steam_events_for_notification")
        assert hasattr(Database, "mark_steam_event_notified")
        assert hasattr(Database, "seed_initial_steam_deals_data")
        assert hasattr(Database, "set_deals_channel")


class TestGamingChannelPriority:
    """Testes para a lógica de seleção do canal de anúncios de jogos e eventos."""

    def test_prefers_configured_deals_channel(self):
        from tasks.background_tasks import find_gaming_announcement_channel
        
        guild = MagicMock()
        guild.me = MagicMock()
        
        deals_ch = MagicMock()
        deals_ch.id = 1327836428524191766
        deals_ch.name = "sugestão-de-jogos"
        deals_ch.permissions_for.return_value.send_messages = True

        other_ch = MagicMock()
        other_ch.id = 1111111111111111111
        other_ch.name = "chat-principal"
        other_ch.permissions_for.return_value.send_messages = True

        guild.get_channel.side_effect = lambda cid: deals_ch if cid == deals_ch.id else None
        guild.text_channels = [other_ch, deals_ch]

        config = {
            "deals_channel_id": 1327836428524191766,
            "allowed_channels": [1111111111111111111]
        }

        selected = find_gaming_announcement_channel(guild, config)
        assert selected == deals_ch

    def test_falls_back_to_gaming_keyword_when_not_configured(self):
        from tasks.background_tasks import find_gaming_announcement_channel

        guild = MagicMock()
        guild.me = MagicMock()

        deals_ch = MagicMock()
        deals_ch.name = "🎮sugestão-de-jogos"
        deals_ch.permissions_for.return_value.send_messages = True

        main_ch = MagicMock()
        main_ch.name = "🎯chat-principal"
        main_ch.permissions_for.return_value.send_messages = True

        guild.text_channels = [main_ch, deals_ch]
        config = {"deals_channel_id": None, "allowed_channels": []}

        selected = find_gaming_announcement_channel(guild, config)
        assert selected == deals_ch

    def test_never_selects_staff_channel(self):
        from tasks.background_tasks import find_gaming_announcement_channel

        guild = MagicMock()
        guild.me = MagicMock()

        staff_ch = MagicMock()
        staff_ch.name = "⚠-administração-⚠"
        staff_ch.permissions_for.return_value.send_messages = True

        main_ch = MagicMock()
        main_ch.name = "🎯chat-principal"
        main_ch.permissions_for.return_value.send_messages = True

        guild.text_channels = [staff_ch, main_ch]
        guild.system_channel = None
        guild.get_channel.side_effect = lambda cid: main_ch if cid == 999 else None

        config = {"deals_channel_id": None, "allowed_channels": [999]}

        selected = find_gaming_announcement_channel(guild, config)
        assert selected == main_ch
        assert selected != staff_ch

