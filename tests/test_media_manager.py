import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import discord
from utils.media_manager import MediaManager, DEDICATED_MEDIA_CHANNELS
from database import Database


def test_media_extraction():
    # Anexo de imagem
    msg = MagicMock(spec=discord.Message)
    att = MagicMock()
    att.content_type = "image/png"
    att.filename = "print.png"
    att.url = "http://example.com/print.png"
    msg.attachments = [att]
    msg.content = "Sem o Eldz nois ganha"
    assert MediaManager.extract_media_url(msg) == "http://example.com/print.png"

    # Link de clipe no texto
    msg2 = MagicMock(spec=discord.Message)
    msg2.attachments = []
    msg2.content = "Olha esse clipe https://clips.twitch.tv/SuperPlay"
    assert MediaManager.extract_media_url(msg2) == "https://clips.twitch.tv/SuperPlay"

    # Mensagem sem mídia
    msg3 = MagicMock(spec=discord.Message)
    msg3.attachments = []
    msg3.content = "Apenas uma mensagem de texto comum"
    assert MediaManager.extract_media_url(msg3) is None


def test_is_media_channel():
    assert MediaManager.is_media_channel("prints-e-clips") is True
    assert MediaManager.is_media_channel("prints-e-clipes") is True
    assert MediaManager.is_media_channel("clips") is True
    assert MediaManager.is_media_channel("geral") is False


@pytest.mark.asyncio
async def test_media_manager_on_message_and_replies():
    mock_db = MagicMock(spec=Database)
    mock_db.upsert_media_highlight = AsyncMock()
    mock_db.increment_media_highlight_reply = AsyncMock()

    manager = MediaManager(mock_db)

    # Mensagem com print
    msg = MagicMock(spec=discord.Message)
    msg.id = 12345
    msg.author.bot = False
    msg.author.id = 999
    msg.author.display_name = "Gato"
    msg.author.display_avatar.url = "http://example.com/avatar.png"
    att = MagicMock()
    att.content_type = "image/png"
    att.filename = "vitoria.png"
    att.url = "http://example.com/vitoria.png"
    msg.attachments = [att]
    msg.content = "SEM O ELDZ NOIS GANHA"
    msg.reactions = []
    msg.reference = None
    msg.guild.id = 555
    msg.channel.id = 777
    msg.channel.name = "prints-e-clipes"
    msg.created_at = datetime(2026, 7, 16, 16, 45, tzinfo=timezone.utc)
    msg.jump_url = "http://discord.com/msg/12345"

    await manager.on_message(msg)

    mock_db.upsert_media_highlight.assert_called_once()
    kwargs = mock_db.upsert_media_highlight.call_args.kwargs
    assert kwargs["message_id"] == 12345
    assert kwargs["username"] == "Gato"
    assert kwargs["media_url"] == "http://example.com/vitoria.png"

    # Resposta à mensagem
    reply = MagicMock(spec=discord.Message)
    reply.id = 67890
    reply.author.bot = False
    reply.attachments = []
    reply.content = "Boa!"
    reply.reference = MagicMock()
    reply.reference.message_id = 12345
    reply.guild.id = 555

    await manager.on_message(reply)
    mock_db.increment_media_highlight_reply.assert_called_once_with(12345)


@pytest.mark.asyncio
async def test_media_manager_reaction_sync():
    mock_db = MagicMock(spec=Database)
    mock_db.get_media_highlight = AsyncMock(return_value={"reply_count": 2})
    mock_db.upsert_media_highlight = AsyncMock()

    manager = MediaManager(mock_db)

    client = MagicMock(spec=discord.Client)
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "prints-e-clipes"
    client.get_channel.return_value = channel

    msg = MagicMock(spec=discord.Message)
    msg.id = 12345
    msg.author.bot = False
    msg.author.id = 999
    msg.author.display_name = "Gato"
    msg.author.display_avatar.url = "http://example.com/avatar.png"
    att = MagicMock()
    att.content_type = "image/png"
    att.filename = "vitoria.png"
    att.url = "http://example.com/vitoria.png"
    msg.attachments = [att]
    msg.content = "SEM O ELDZ NOIS GANHA"
    
    r1 = MagicMock()
    r1.emoji = "🏳️‍🌈"
    r1.count = 5
    r2 = MagicMock()
    r2.emoji = "💅"
    r2.count = 5
    msg.reactions = [r1, r2]
    msg.guild.id = 555
    msg.channel = channel
    msg.created_at = datetime(2026, 7, 16, 16, 45, tzinfo=timezone.utc)
    msg.jump_url = "http://discord.com/msg/12345"

    channel.fetch_message = AsyncMock(return_value=msg)

    payload = MagicMock(spec=discord.RawReactionActionEvent)
    payload.channel_id = 777
    payload.message_id = 12345

    await manager.on_raw_reaction_add(payload, client)

    mock_db.upsert_media_highlight.assert_called_once()
    kwargs = mock_db.upsert_media_highlight.call_args.kwargs
    assert kwargs["reaction_count"] == 10
    assert kwargs["reply_count"] == 2
    assert kwargs["reactions_json"] == {"🏳️‍🌈": 5, "💅": 5}
