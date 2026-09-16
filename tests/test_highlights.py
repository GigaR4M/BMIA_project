import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import discord
from commands.stats_commands import HIGHLIGHTS_CATEGORIES
from utils.highlights_scanner import HighlightsScanner
from utils.image_generator import HighlightsBuilder


def test_highlights_categories_count_and_structure():
    assert len(HIGHLIGHTS_CATEGORIES) == 13
    cat_ids = [c["id"] for c in HIGHLIGHTS_CATEGORIES]
    assert "cover" in cat_ids
    assert "mvp" in cat_ids
    assert "tagarela" in cat_ids
    assert "rei_da_call" in cat_ids
    assert "corujao" in cat_ids
    assert "streamer" in cat_ids
    assert "top_gamers" in cat_ids
    assert "jogo_do_ano" in cat_ids
    assert "media" in cat_ids
    assert "o_midia" in cat_ids
    assert "o_onipresente" in cat_ids
    assert "ima_da_galera" in cat_ids
    assert "boca_suja" in cat_ids


@pytest.mark.asyncio
async def test_highlights_scanner_channel_scan():
    guild = MagicMock(spec=discord.Guild)
    guild.name = "Test Guild"

    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "prints-e-clips"
    perm = MagicMock()
    perm.read_message_history = True
    channel.permissions_for.return_value = perm

    msg = MagicMock(spec=discord.Message)
    msg.id = 123456
    msg.author.bot = False
    msg.author.id = 999
    msg.author.display_name = "ClipMaster"
    msg.author.display_avatar.url = "http://example.com/avatar.png"
    msg.attachments = []
    msg.content = "Olha esse clipe: https://clips.twitch.tv/AwesomeClip"
    r = MagicMock()
    r.emoji = "🔥"
    r.count = 15
    msg.reactions = [r]
    msg.created_at = datetime(2026, 5, 10, 15, 30, tzinfo=timezone.utc)
    msg.jump_url = "http://discord.com/msg/123456"

    async def mock_history(after=None, limit=200):
        yield msg

    channel.history = mock_history
    guild.text_channels = [channel]
    guild.me = MagicMock()

    top_clip = await HighlightsScanner.scan_guild_top_clip(guild, 2026, timeout=1.0)
    assert top_clip is not None
    assert top_clip["user_id"] == 999
    assert top_clip["reaction_count"] == 15
    assert "https://clips.twitch.tv/AwesomeClip" in top_clip["media_url"]


@pytest.mark.asyncio
async def test_highlights_builder_single_instance_render():
    fake_guild = MagicMock(spec=discord.Guild)
    fake_guild.name = "Servidor Teste"
    fake_guild.icon = None
    fake_guild.get_member.return_value = None

    fake_data = {
        "mvp": [{"user_id": 1, "username": "Giga", "value": 5000}],
        "tagarela": [{"user_id": 1, "username": "Giga", "value": 120}],
        "rei_da_call": [{"user_id": 1, "username": "Giga", "value_seconds": 7200}],
        "corujao": [{"user_id": 1, "username": "Giga", "value_seconds": 3600}],
        "streamer": [{"user_id": 1, "username": "Giga", "value_seconds": 1800}],
        "top_gamers": [{"user_id": 1, "username": "Giga", "value_seconds": 9000}],
        "jogo_do_ano": [{"activity_name": "CS2", "value_seconds": 12000}],
        "o_midia": [{"user_id": 1, "username": "Giga", "value": 30}],
        "o_onipresente": [{"user_id": 1, "username": "Giga", "value": 200}],
        "ima_da_galera": [{"user_id": 1, "username": "Giga", "value": 45}],
        "boca_suja": [{"user_id": 1, "username": "Giga", "value": 12}],
    }

    categories = HIGHLIGHTS_CATEGORIES[:3]  # Testa com 3 categorias
    files = await HighlightsBuilder.generate_all_slides_files(
        guild=fake_guild,
        year=2026,
        highlights_data=fake_data,
        top_clip=None,
        categories=categories
    )

    assert len(files) == 3
    for f in files:
        assert isinstance(f, discord.File)
        assert f.filename.endswith(".png")
        assert f.fp.getbuffer().nbytes > 1000
