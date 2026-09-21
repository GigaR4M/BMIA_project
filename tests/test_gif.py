# tests/test_gif.py - Testes unitários para TenorClient, Slash Command /gif e AIToolkit.buscar_gif

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from utils.tenor_client import TenorClient
from utils.ai_tools import AIToolkit
from commands.gif_commands import setup_gif_slash_command
import discord


@pytest.fixture
def tenor_client():
    return TenorClient(api_key="test_tenor_key")


@pytest.fixture
def mock_db():
    return MagicMock()


class TestTenorClient:
    def test_is_configured(self):
        client_with_key = TenorClient(api_key="valid_key")
        assert client_with_key.is_configured is True

        client_empty = TenorClient(api_key="")
        assert client_empty.is_configured is False

    @pytest.mark.asyncio
    async def test_search_gifs_empty_query(self, tenor_client):
        res = await tenor_client.search_gifs("")
        assert res == []
        res_spaces = await tenor_client.search_gifs("   ")
        assert res_spaces == []

    @pytest.mark.asyncio
    async def test_search_gifs_not_configured(self):
        client = TenorClient(api_key="")
        res = await client.search_gifs("dance")
        assert res == []

    @pytest.mark.asyncio
    async def test_search_gifs_success_and_caching(self, tenor_client):
        mock_payload = {
            "results": [
                {
                    "url": "https://tenor.com/view/dance-cat-gif-123",
                    "content_description": "Cat dancing meme",
                    "media_formats": {
                        "gif": {"url": "https://media.tenor.com/cat.gif"},
                        "tinygif": {"url": "https://media.tenor.com/tinycat.gif"},
                    },
                }
            ]
        }

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_payload)

        mock_session = MagicMock()
        mock_session.get.return_value.__aenter__.return_value = mock_resp

        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__.return_value = mock_session

        with patch("aiohttp.ClientSession", return_value=mock_session_ctx):
            results = await tenor_client.search_gifs("dance cat", limit=1)

            assert len(results) == 1
            assert results[0]["url"] == "https://tenor.com/view/dance-cat-gif-123"
            assert results[0]["gif_url"] == "https://media.tenor.com/cat.gif"
            assert results[0]["description"] == "Cat dancing meme"

            # Test cache hit (should not call aiohttp again)
            cached_results = await tenor_client.search_gifs("dance cat", limit=1)
            assert cached_results == results
            assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_search_gif_url(self, tenor_client):
        with patch.object(
            tenor_client,
            "search_gifs",
            new=AsyncMock(
                return_value=[
                    {
                        "url": "https://tenor.com/view/win-gif-456",
                        "gif_url": "https://media.tenor.com/win.gif",
                    }
                ]
            ),
        ):
            url = await tenor_client.search_gif_url("vitoria")
            assert url == "https://tenor.com/view/win-gif-456"

    @pytest.mark.asyncio
    async def test_search_gif_url_not_found(self, tenor_client):
        with patch.object(tenor_client, "search_gifs", new=AsyncMock(return_value=[])):
            url = await tenor_client.search_gif_url("inexistente_xyz_123")
            assert url is None


class TestAIToolkitGif:
    @pytest.mark.asyncio
    async def test_buscar_gif_success(self, mock_db, tenor_client):
        with patch.object(
            tenor_client,
            "search_gif_url",
            new=AsyncMock(return_value="https://tenor.com/view/cheering-gif-789"),
        ):
            toolkit = AIToolkit(db=mock_db, guild_id=123, tenor_client=tenor_client)
            res = await toolkit.buscar_gif("comemorando")

            assert res["gif_url"] == "https://tenor.com/view/cheering-gif-789"
            assert res["tema"] == "comemorando"
            assert "instrucao" in res

    @pytest.mark.asyncio
    async def test_buscar_gif_not_found(self, mock_db, tenor_client):
        with patch.object(tenor_client, "search_gif_url", new=AsyncMock(return_value=None)):
            toolkit = AIToolkit(db=mock_db, guild_id=123, tenor_client=tenor_client)
            res = await toolkit.buscar_gif("termo_estranho")

            assert "Nenhum GIF encontrado" in res["mensagem"]

    def test_get_tool_callables_includes_buscar_gif(self, mock_db):
        toolkit = AIToolkit(db=mock_db, guild_id=123)
        callables = toolkit.get_tool_callables()
        assert toolkit.buscar_gif in callables


class TestGifSlashCommand:
    @pytest.mark.asyncio
    async def test_setup_and_execute_slash_command(self, tenor_client):
        tree = MagicMock()
        registered_command = None

        def mock_command(**kwargs):
            def decorator(func):
                nonlocal registered_command
                registered_command = func
                return func
            return decorator

        tree.command = mock_command

        setup_gif_slash_command(tree, tenor_client)
        assert registered_command is not None

        # Test valid search
        interaction = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(
            tenor_client,
            "search_gif_url",
            new=AsyncMock(return_value="https://tenor.com/view/dance-123"),
        ):
            await registered_command(interaction, busca="dance")
            interaction.response.defer.assert_awaited_once_with(thinking=False)
            interaction.followup.send.assert_awaited_once_with(
                content="https://tenor.com/view/dance-123"
            )

        # Test empty search
        interaction_empty = AsyncMock()
        interaction_empty.response.send_message = AsyncMock()
        await registered_command(interaction_empty, busca="   ")
        interaction_empty.response.send_message.assert_awaited_once()
        assert "❌ Digite um termo" in interaction_empty.response.send_message.call_args[0][0]
