# tests/test_guild_isolation.py — Testes de isolamento de configurações por servidor
"""
Garante que configurações de um servidor (canais permitidos, voz ignorada, etc.)
nunca vazem ou afetem outro servidor no bot BMIA.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import discord
from events.discord_events import BotContext
from commands.config_commands import ConfigCommands


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Armazenamento em memória simulando Postgres
    store = {
        1327836427915886643: {
            "allowed_channels": [1001, 1002],
            "ignored_voice_channels": [2001],
            "ai_moderation_enabled": True,
            "announcement_channel_id": None,
            "dynamic_roles_config": {}
        },
        1444182856489500723: {
            "allowed_channels": [3001],
            "ignored_voice_channels": [],
            "ai_moderation_enabled": False,
            "announcement_channel_id": 3002,
            "dynamic_roles_config": {}
        }
    }

    async def get_guild_config(guild_id: int):
        return dict(store.get(guild_id, {}))

    async def set_allowed_channels(guild_id: int, channel_ids: list):
        if guild_id not in store:
            store[guild_id] = {}
        store[guild_id]["allowed_channels"] = list(channel_ids)

    async def set_ignored_voice_channels(guild_id: int, channel_ids: list):
        if guild_id not in store:
            store[guild_id] = {}
        store[guild_id]["ignored_voice_channels"] = list(channel_ids)

    db.get_guild_config = AsyncMock(side_effect=get_guild_config)
    db.set_allowed_channels = AsyncMock(side_effect=set_allowed_channels)
    db.set_ignored_voice_channels = AsyncMock(side_effect=set_ignored_voice_channels)
    return db


@pytest.mark.asyncio
async def test_bot_context_guild_isolation(mock_db):
    ctx = BotContext()
    ctx.db = mock_db

    guild_a = 1327836427915886643
    guild_b = 1444182856489500723

    allowed_a = await ctx.get_allowed_channels(guild_a)
    allowed_b = await ctx.get_allowed_channels(guild_b)

    assert allowed_a == [1001, 1002]
    assert allowed_b == [3001]
    assert allowed_a != allowed_b


@pytest.mark.asyncio
async def test_config_commands_list_allowed_channels_isolation(mock_db):
    ctx = BotContext()
    ctx.db = mock_db

    config_cmds = ConfigCommands(mock_db, ctx)

    # Simula interação no Servidor A
    guild_a = MagicMock()
    guild_a.id = 1327836427915886643
    guild_a.name = "Servidor A"
    ch1 = MagicMock(id=1001)
    ch2 = MagicMock(id=1002)
    guild_a.channels = [ch1, ch2]
    guild_a.get_channel = lambda cid: ch1 if cid == 1001 else (ch2 if cid == 1002 else None)

    interaction_a = AsyncMock()
    interaction_a.guild = guild_a
    interaction_a.user.id = 999
    member_a = MagicMock()
    member_a.guild_permissions.administrator = True
    guild_a.get_member.return_value = member_a

    await config_cmds.list_allowed_channels.callback(config_cmds, interaction_a)

    interaction_a.response.send_message.assert_awaited_once()
    call_args = interaction_a.response.send_message.call_args[1]
    embed = call_args["embed"]
    assert "<#1001>" in embed.description
    assert "<#1002>" in embed.description
    assert "<#3001>" not in embed.description  # Canal do Servidor B não pode aparecer!


@pytest.mark.asyncio
async def test_config_commands_add_and_remove_allowed_channel_isolation(mock_db):
    ctx = BotContext()
    ctx.db = mock_db
    config_cmds = ConfigCommands(mock_db, ctx)

    guild_a = MagicMock()
    guild_a.id = 1327836427915886643
    guild_a.name = "Servidor A"
    member_a = MagicMock()
    member_a.guild_permissions.administrator = True
    guild_a.get_member.return_value = member_a

    # Adiciona canal 1003 no Servidor A
    new_channel = MagicMock(id=1003)
    new_channel.mention = "<#1003>"
    new_channel.name = "novo-chat"

    interaction = AsyncMock()
    interaction.guild = guild_a
    interaction.user.id = 999

    await config_cmds.add_allowed_channel.callback(config_cmds, interaction, new_channel)

    # Verifica se servidor A tem o canal 1003 e servidor B continua com apenas [3001]
    allowed_a = await ctx.get_allowed_channels(1327836427915886643)
    allowed_b = await ctx.get_allowed_channels(1444182856489500723)

    assert 1003 in allowed_a
    assert allowed_b == [3001]

