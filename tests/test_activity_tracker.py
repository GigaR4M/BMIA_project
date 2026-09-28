import pytest
from unittest.mock import AsyncMock, MagicMock
import discord
from utils.activity_tracker import ActivityTracker, normalize_game_name


def test_normalize_game_name():
    assert normalize_game_name("roblox") == "Roblox"
    assert normalize_game_name("ROBLOX") == "Roblox"
    assert normalize_game_name("Roblox") == "Roblox"
    assert normalize_game_name("  EA SPORTS FC 24  ") == "EA Sports FC 24"
    assert normalize_game_name("ea sports fc 24") == "EA Sports FC 24"
    assert normalize_game_name("VALORANT") == "VALORANT"
    assert normalize_game_name("valorant") == "VALORANT"
    assert normalize_game_name("cs2") == "Counter-Strike 2"
    assert normalize_game_name("unknown game title") == "unknown game title"
    assert normalize_game_name("") == ""


@pytest.mark.asyncio
async def test_extract_activities_filters_and_normalizes():
    db = MagicMock()
    tracker = ActivityTracker(db)

    # Cria mock member
    member = MagicMock(spec=discord.Member)
    member.bot = False

    # Atividades mistas: ROBLOX, Spotify, Hang Status
    game_act = MagicMock(spec=discord.Game)
    game_act.name = "ROBLOX"
    game_act.type = discord.ActivityType.playing

    spotify_act = MagicMock(spec=discord.Spotify)

    hang_act = MagicMock()
    hang_act.name = "Hang Status"
    hang_act.type = MagicMock()
    hang_act.type.value = 6

    member.activities = [game_act, spotify_act, hang_act]

    extracted = tracker._extract_activities(member)
    assert len(extracted) == 1
    assert "roblox" in extracted
    display_name, act_type = extracted["roblox"]
    assert display_name == "Roblox"
    assert act_type == "playing"


@pytest.mark.asyncio
async def test_case_insensitive_presence_update_no_duplicate_session():
    db = MagicMock()
    db.start_activity = AsyncMock(return_value=123)
    db.end_activity = AsyncMock()

    tracker = ActivityTracker(db)

    # Estado Before com "ROBLOX"
    before = MagicMock(spec=discord.Member)
    before.bot = False
    before.id = 111
    before.guild.id = 222
    act_before = MagicMock(spec=discord.Game)
    act_before.name = "ROBLOX"
    before.activities = [act_before]

    # Inicia com ROBLOX
    await tracker._start_activity(before, "ROBLOX", "playing")
    assert len(tracker.active_activities) == 1
    assert db.start_activity.call_count == 1

    # Estado After com "Roblox" (mesmo jogo, capitalização diferente)
    after = MagicMock(spec=discord.Member)
    after.bot = False
    after.id = 111
    after.guild.id = 222
    act_after = MagicMock(spec=discord.Game)
    act_after.name = "Roblox"
    after.activities = [act_after]

    # Dispara on_presence_update
    await tracker.on_presence_update(before, after)

    # Não deve ter encerrado nem iniciado uma nova atividade
    assert db.start_activity.call_count == 1
    assert db.end_activity.call_count == 0
    assert len(tracker.active_activities) == 1
