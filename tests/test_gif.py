# tests/test_gif.py - Testes unitários para GiphyClient, Slash Command /gif e AIToolkit.buscar_gif

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp
from utils.giphy_client import GiphyClient
from utils.ai_tools import AIToolkit
from commands.gif_commands import setup_gif_slash_command
import discord


@pytest.fixture
def gif_client():
    return GiphyClient(api_key="test_giphy_key")


@pytest.fixture
def mock_db():
    return MagicMock()


class TestGiphyClient:
    def test_is_configured(self):
        client_with_key = GiphyClient(api_key="valid_key")
        assert client_with_key.is_configured is True

        client_empty = GiphyClient(api_key="")
        assert client_empty.is_configured is False

    @pytest.mark.asyncio
    async def test_search_gifs_empty_query(self, gif_client):
        res = await gif_client.search_gifs("")
        assert res == []
        res_spaces = await gif_client.search_gifs("   ")
        assert res_spaces == []

    @pytest.mark.asyncio
    async def test_search_gifs_not_configured(self):
        client = GiphyClient(api_key="")
        res = await client.search_gifs("dance")
        assert res == []

    @pytest.mark.asyncio
    async def test_search_gifs_success_and_caching(self, gif_client):
        mock_payload = {
            "data": [
                {
                    "url": "https://giphy.com/gifs/cat-dance-123",
                    "title": "Cat Dancing Meme",
                    "images": {
                        "original": {"url": "https://media.giphy.com/media/cat.gif"},
                        "downsized_medium": {"url": "https://media.giphy.com/media/cat_med.gif"},
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
            results = await gif_client.search_gifs("dance cat", limit=1)

            assert len(results) == 1
            assert results[0]["url"] == "https://giphy.com/gifs/cat-dance-123"
            assert results[0]["gif_url"] == "https://media.giphy.com/media/cat.gif"
            assert results[0]["description"] == "Cat Dancing Meme"

            # Test cache hit (should not call aiohttp again)
            cached_results = await gif_client.search_gifs("dance cat", limit=1)
            assert cached_results == results
            assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_search_gif_url(self, gif_client):
        with patch.object(
            gif_client,
            "search_gifs",
            new=AsyncMock(
                return_value=[
                    {
                        "url": "https://giphy.com/gifs/win-456",
                        "gif_url": "https://media.giphy.com/media/win.gif",
                    }
                ]
            ),
        ):
            url = await gif_client.search_gif_url("vitoria")
            assert url == "https://media.giphy.com/media/win.gif"

    @pytest.mark.asyncio
    async def test_search_gif_url_not_found(self, gif_client):
        with patch.object(gif_client, "search_gifs", new=AsyncMock(return_value=[])):
            url = await gif_client.search_gif_url("inexistente_xyz_123")
            assert url is None


class TestAIToolkitGif:
    @pytest.mark.asyncio
    async def test_buscar_gif_success(self, mock_db, gif_client):
        with patch.object(
            gif_client,
            "search_gif_url",
            new=AsyncMock(return_value="https://giphy.com/gifs/cheering-789"),
        ):
            toolkit = AIToolkit(db=mock_db, guild_id=123, gif_client=gif_client)
            res = await toolkit.buscar_gif("comemorando")

            assert res["gif_url"] == "https://giphy.com/gifs/cheering-789"
            assert res["tema"] == "comemorando"
            assert "instrucao" in res

    @pytest.mark.asyncio
    async def test_buscar_gif_not_found(self, mock_db, gif_client):
        with patch.object(gif_client, "search_gif_url", new=AsyncMock(return_value=None)):
            toolkit = AIToolkit(db=mock_db, guild_id=123, gif_client=gif_client)
            res = await toolkit.buscar_gif("termo_estranho")

            assert "Nenhum GIF encontrado" in res["mensagem"]

    def test_get_tool_callables_includes_buscar_gif(self, mock_db):
        toolkit = AIToolkit(db=mock_db, guild_id=123)
        callables = toolkit.get_tool_callables()
        assert toolkit.buscar_gif in callables


class TestGifSlashCommand:
    @pytest.mark.asyncio
    async def test_setup_and_execute_slash_command(self, gif_client):
        tree = MagicMock()
        registered_command = None

        def mock_command(**kwargs):
            def decorator(func):
                nonlocal registered_command
                registered_command = func
                return func
            return decorator

        tree.command = mock_command

        setup_gif_slash_command(tree, gif_client)
        assert registered_command is not None

        # Test valid search
        interaction = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        with patch.object(
            gif_client,
            "search_gif_url",
            new=AsyncMock(return_value="https://giphy.com/gifs/dance-123"),
        ):
            await registered_command(interaction, busca="dance")
            interaction.response.defer.assert_awaited_once_with(thinking=False)
            interaction.followup.send.assert_awaited_once()
            embed_sent = interaction.followup.send.call_args[1].get("embed")
            assert embed_sent is not None
            assert "media.giphy.com" in embed_sent.image.url or "123" in embed_sent.image.url

        # Test empty search
        interaction_empty = AsyncMock()
        interaction_empty.response.send_message = AsyncMock()
        await registered_command(interaction_empty, busca="   ")
        interaction_empty.response.send_message.assert_awaited_once()
        assert "❌ Digite um termo" in interaction_empty.response.send_message.call_args[0][0]


class TestExtractAndCleanGif:
    def test_extract_from_empty_brackets(self):
        from events.discord_events import extract_and_clean_gif

        raw = "Poxa, chefe, valeu demais!\n\n[](https://giphy.com/gifs/friends-joey-tribbiani-matt-leblanc-TxsMQV4p1sE8G4QZ2r)"
        gif_url, clean_text = extract_and_clean_gif(raw)
        assert gif_url == "https://media.giphy.com/media/TxsMQV4p1sE8G4QZ2r/giphy.gif"
        assert "https://" not in clean_text
        assert "[]" not in clean_text
        assert clean_text == "Poxa, chefe, valeu demais!"

    def test_extract_from_raw_url(self):
        from events.discord_events import extract_and_clean_gif

        raw = "Aqui está:\nhttps://media0.giphy.com/media/xyz123/giphy.gif\nEspero que goste!"
        gif_url, clean_text = extract_and_clean_gif(raw)
        assert gif_url == "https://media0.giphy.com/media/xyz123/giphy.gif"
        assert "https://" not in clean_text
        assert "Aqui está:\n\nEspero que goste!" in clean_text or "Aqui está:" in clean_text

    def test_fallback_gif_url(self):
        from events.discord_events import extract_and_clean_gif

        raw = "Aqui está seu GIF sem links na mensagem!"
        gif_url, clean_text = extract_and_clean_gif(raw, fallback_gif_url="https://giphy.com/gifs/funny-abc999")
        assert gif_url == "https://media.giphy.com/media/abc999/giphy.gif"
        assert clean_text == raw
