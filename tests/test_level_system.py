# tests/test_level_system.py — Testes Unitários do Sistema de Níveis e XP

import pytest
from unittest.mock import AsyncMock, MagicMock
from utils.level_manager import (
    get_xp_needed_for_level_up,
    get_total_xp_for_level,
    get_level_from_xp,
    get_level_progress
)
from utils.points_manager import PointsManager


class TestLevelFormulas:
    def test_xp_needed_formula(self):
        # Level 1 -> 2: 5(1)^2 + 50(1) + 100 = 155
        # Note: 5*1 + 50 + 100 = 155
        assert get_xp_needed_for_level_up(1) == 155
        # Level 2 -> 3: 5(4) + 50(2) + 100 = 20 + 100 + 100 = 220
        assert get_xp_needed_for_level_up(2) == 220
        # Level 10 -> 11: 5(100) + 50(10) + 100 = 500 + 500 + 100 = 1100
        assert get_xp_needed_for_level_up(10) == 1100

    def test_total_xp_for_level(self):
        assert get_total_xp_for_level(1) == 0
        assert get_total_xp_for_level(2) == 155
        assert get_total_xp_for_level(3) == 155 + 220

    def test_get_level_from_xp(self):
        assert get_level_from_xp(0) == 1
        assert get_level_from_xp(100) == 1
        assert get_level_from_xp(154) == 1
        assert get_level_from_xp(155) == 2
        assert get_level_from_xp(374) == 2
        assert get_level_from_xp(375) == 3

    def test_get_level_progress(self):
        prog = get_level_progress(0)
        assert prog["level"] == 1
        assert prog["progress_pct"] == 0.0
        assert prog["xp_in_level"] == 0
        assert prog["xp_needed_in_level"] == 155

        # Progress mid level 1
        prog_mid = get_level_progress(77)
        assert prog_mid["level"] == 1
        assert prog_mid["progress_pct"] == round(77 / 155 * 100, 1)

        # Progress exactly at level 2
        prog_lvl2 = get_level_progress(155)
        assert prog_lvl2["level"] == 2
        assert prog_lvl2["xp_in_level"] == 0


class TestLevelUpDetection:
    @pytest.mark.asyncio
    async def test_level_up_announcement(self):
        mock_db = MagicMock()
        mock_db.upsert_user = AsyncMock()
        mock_db.add_interaction_point = AsyncMock()
        # Current total is 160 XP (Level 2), added 20 XP (old total was 140 XP - Level 1)
        mock_db.get_user_current_total_points = AsyncMock(return_value=160)
        mock_db.update_daily_user_stats = AsyncMock()

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        pm = PointsManager(mock_db)
        await pm.add_xp(
            user_id=12345,
            points=20,
            interaction_type="message",
            guild_id=999,
            username="ProGamer",
            channel=mock_channel
        )

        # Channel should receive level up announcement
        mock_channel.send.assert_called_once()
        call_kwargs = mock_channel.send.call_args[1]
        embed = call_kwargs["embed"]
        assert "LEVEL UP" in embed.title
        assert "Nível 2" in embed.description


class TestPodiumBuilder:
    @pytest.mark.asyncio
    async def test_generate_podium(self):
        from utils.image_generator import PodiumBuilder
        
        guild = MagicMock()
        guild.name = "Servidor BMIA Esports"
        guild.icon = None
        guild.get_member.return_value = None

        top_users = [
            {"user_id": 1, "username": "GigaR4M", "total_points": 9238},
            {"user_id": 2, "username": "PlayerTwo", "total_points": 7450},
            {"user_id": 3, "username": "PlayerThree", "total_points": 5120},
            {"user_id": 4, "username": "PlayerFour", "total_points": 3800},
            {"user_id": 5, "username": "PlayerFive", "total_points": 2900},
        ]

        builder = PodiumBuilder()
        buf = await builder.generate_podium(guild, top_users, "MARÇO 2026")
        assert buf is not None
        assert buf.getbuffer().nbytes > 1000

