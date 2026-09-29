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


@pytest.mark.asyncio
async def test_config_commands_ignored_voice_isolation(mock_db):
    ctx = BotContext()
    ctx.db = mock_db
    config_cmds = ConfigCommands(mock_db, ctx)

    guild_a = MagicMock()
    guild_a.id = 1327836427915886643
    guild_a.name = "Servidor A"
    member_a = MagicMock()
    member_a.guild_permissions.administrator = True
    guild_a.get_member.return_value = member_a

    # Adiciona canal de voz 2002 no Servidor A
    new_voice = MagicMock(id=2002)
    new_voice.mention = "<#2002>"

    interaction = AsyncMock()
    interaction.guild = guild_a
    interaction.user.id = 999

    await config_cmds.add_ignored_voice.callback(config_cmds, interaction, new_voice)

    ignored_a = await ctx.get_ignored_voice_channels(1327836427915886643)
    ignored_b = await ctx.get_ignored_voice_channels(1444182856489500723)

    assert 2002 in ignored_a
    assert 2002 not in ignored_b


@pytest.mark.asyncio
async def test_bot_context_fallbacks():
    ctx = BotContext()
    # Sem banco de dados configurado, deve retornar defaults sem lançar NameError
    allowed = await ctx.get_allowed_channels(999999)
    ignored = await ctx.get_ignored_voice_channels(999999)
    dyn_roles = await ctx.get_dynamic_roles_config(999999)

    assert isinstance(allowed, list)
    assert isinstance(ignored, list)
    assert isinstance(dyn_roles, dict)


@pytest.mark.asyncio
async def test_annual_highlights_strict_guild_isolation():
    """Garante que a coleta de destaques anuais filtra estritamente por guild_id."""
    from database import Database
    db = Database("postgresql://fake:fake@localhost:5432/fake")
    mock_conn = AsyncMock()

    guild_a = 111111111111111111
    guild_b = 222222222222222222

    # Configura retorno simulado para guild_a
    mock_conn.fetch.side_effect = [
        # 1. MVP
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 5000}],
        # 2. Tagarela
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 120}],
        # 3. Rei da Call
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value_seconds": 3600}],
        # 4. Corujao
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 15}],
        # 5. Rei da Midia
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 8}],
        # 6. Top Gamer
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value_seconds": 7200}],
        # 7. Gamer Ecletico
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 5}],
        # 8. Rei das Demos
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 2}],
        # 9. O Maratonista
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value_seconds": 3600}],
        # 10. Jogo do Ano
        [{"activity_name": "VALORANT", "value_seconds": 15000}],
        # 11. Imã da Galera
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 20}],
        # 12. Onipresente
        [{"user_id": 101, "username": "player_a", "avatar_url": None, "value": 4}],
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    db.pool = mock_pool

    res = await db.get_annual_highlights_data(guild_a, 2026)

    # Verifica se os parâmetros das chamadas SQL incluíram estritamente guild_a
    for call in mock_conn.fetch.call_args_list:
        args = call[0]
        # O primeiro parâmetro posicional após a query é o guild_id
        assert args[1] == guild_a
        assert args[1] != guild_b

    assert res["mvp"][0]["username"] == "player_a"
    assert res["mvp"][0]["value"] == 5000


