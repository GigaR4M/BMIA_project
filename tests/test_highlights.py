import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import discord
from commands.stats_commands import HIGHLIGHTS_CATEGORIES
from utils.highlights_scanner import HighlightsScanner
from utils.image_generator import HighlightsBuilder


def test_highlights_categories_count_and_structure():
    assert len(HIGHLIGHTS_CATEGORIES) == 10
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
    assert "outros_destaques" in cat_ids


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

    top_clip = await HighlightsScanner.scan_guild_top_clip(guild, 2026, timeout=5.0)
    assert top_clip is not None
    assert top_clip["user_id"] == 999
    assert top_clip["reaction_count"] == 15
    assert "https://clips.twitch.tv/AwesomeClip" in top_clip["media_url"]


@pytest.mark.asyncio
async def test_highlights_scanner_replies_and_reactions_scoring():
    guild = MagicMock(spec=discord.Guild)
    guild.name = "Test Guild"

    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "prints-e-clipes"
    perm = MagicMock()
    perm.read_message_history = True
    channel.permissions_for.return_value = perm

    # Mensagem 1 (Janeiro): 6 reações, 0 respostas = 6 pts
    msg1 = MagicMock(spec=discord.Message)
    msg1.id = 101
    msg1.author.bot = False
    msg1.author.id = 111
    msg1.author.display_name = "PlayerOne"
    msg1.author.display_avatar.url = "http://example.com/p1.png"
    msg1.attachments = []
    msg1.content = "Print antigo https://cdn.discordapp.com/attachments/1/1/old.png"
    r1 = MagicMock()
    r1.emoji = "👍"
    r1.count = 6
    msg1.reactions = [r1]
    msg1.reference = None
    msg1.created_at = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    msg1.jump_url = "http://discord.com/msg/101"

    # Mensagem 2 (Julho - Gato): 10 reações (5+5), 2 respostas = 10 + (2*2) = 14 pts
    msg2 = MagicMock(spec=discord.Message)
    msg2.id = 202
    msg2.author.bot = False
    msg2.author.id = 222
    msg2.author.display_name = "Gato"
    msg2.author.display_avatar.url = "http://example.com/gato.png"
    att = MagicMock()
    att.content_type = "image/png"
    att.filename = "vitoria_lol.png"
    att.url = "http://cdn.discordapp.com/attachments/1/2/vitoria_lol.png"
    msg2.attachments = [att]
    msg2.content = "SEM O ELDZ NOIS GANHA"
    r2_1 = MagicMock()
    r2_1.emoji = "🏳️‍🌈"
    r2_1.count = 5
    r2_2 = MagicMock()
    r2_2.emoji = "💅"
    r2_2.count = 5
    msg2.reactions = [r2_1, r2_2]
    msg2.reference = None
    msg2.created_at = datetime(2026, 7, 16, 16, 45, tzinfo=timezone.utc)
    msg2.jump_url = "http://discord.com/msg/202"

    # Respostas direcionadas à mensagem 2
    reply1 = MagicMock(spec=discord.Message)
    reply1.id = 301
    reply1.author.bot = False
    reply1.reference = MagicMock()
    reply1.reference.message_id = 202
    reply1.attachments = []
    reply1.content = "Kkkkkkkk mto bom"
    reply1.reactions = []
    reply1.created_at = datetime(2026, 7, 16, 16, 50, tzinfo=timezone.utc)

    reply2 = MagicMock(spec=discord.Message)
    reply2.id = 302
    reply2.author.bot = False
    reply2.reference = MagicMock()
    reply2.reference.message_id = 202
    reply2.attachments = []
    reply2.content = "jogou o fino"
    reply2.reactions = []
    reply2.created_at = datetime(2026, 7, 16, 16, 52, tzinfo=timezone.utc)

    async def mock_history(after=None, limit=None):
        for m in [msg1, msg2, reply1, reply2]:
            yield m

    channel.history = mock_history
    guild.text_channels = [channel]
    guild.me = MagicMock()

    top_clip = await HighlightsScanner.scan_guild_top_clip(guild, 2026, timeout=5.0)
    assert top_clip is not None
    assert top_clip["user_id"] == 222
    assert top_clip["username"] == "Gato"
    assert top_clip["reaction_count"] == 10
    assert top_clip["reply_count"] == 2
    assert top_clip["popularity_score"] == 14
    assert top_clip["media_url"] == "http://cdn.discordapp.com/attachments/1/2/vitoria_lol.png"


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
