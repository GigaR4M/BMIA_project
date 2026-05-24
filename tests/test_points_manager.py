# tests/test_points_manager.py — Testes unitários do PointsManager
"""
Testa a lógica de cálculo e validação de pontos sem banco de dados real.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db():
    """Mock do Database para injeção no PointsManager."""
    db = MagicMock()
    # Métodos realmente usados em PointsManager.add_points()
    db.upsert_user = AsyncMock(return_value=None)
    db.add_interaction_point = AsyncMock(return_value=None)
    db.get_user_current_total_points = AsyncMock(return_value=105)
    db.update_daily_user_stats = AsyncMock(return_value=None)
    # Método de remoção
    db.remove_user_points = AsyncMock(return_value=None)
    return db


class TestPointsManagerInit:

    def test_instantiation_with_db(self, mock_db):
        """PointsManager deve ser instanciado com db e ignored_channels."""
        from utils.points_manager import PointsManager
        pm = PointsManager(mock_db, ignored_channels=[111, 222])
        assert pm.db is mock_db

    def test_instantiation_without_ignored_channels(self, mock_db):
        """PointsManager deve aceitar lista vazia de canais ignorados."""
        from utils.points_manager import PointsManager
        pm = PointsManager(mock_db, ignored_channels=[])
        assert pm is not None


class TestAddPoints:

    @pytest.mark.asyncio
    async def test_add_points_calls_db(self, mock_db):
        """add_points deve chamar o método correto do banco."""
        from utils.points_manager import PointsManager
        pm = PointsManager(mock_db, ignored_channels=[])
        await pm.add_points(
            user_id=1,
            points=5,
            interaction_type="message",
            guild_id=100,
            username="TestUser",
            discriminator="0001",
        )
        mock_db.add_interaction_point.assert_called_once()


    @pytest.mark.asyncio
    async def test_add_zero_points_skips_db(self, mock_db):
        """add_points com 0 pontos não deve chamar o banco."""
        from utils.points_manager import PointsManager
        pm = PointsManager(mock_db, ignored_channels=[])
        await pm.add_points(
            user_id=1,
            points=0,
            interaction_type="message",
            guild_id=100,
            username="TestUser",
            discriminator="0001",
        )
        mock_db.add_user_points.assert_not_called()


class TestGiveawayManagerParseDuration:
    """Testa o parser de duração do GiveawayManager (sem DB)."""

    def setup_method(self):
        from utils.giveaway_manager import GiveawayManager
        db = MagicMock()
        self.gm = GiveawayManager(db)

    def test_parse_minutes(self):
        """30m deve retornar timedelta de 30 minutos."""
        from datetime import timedelta
        td = self.gm.parse_duration("30m")
        assert td == timedelta(minutes=30)

    def test_parse_hours(self):
        """2h deve retornar timedelta de 2 horas."""
        from datetime import timedelta
        td = self.gm.parse_duration("2h")
        assert td == timedelta(hours=2)

    def test_parse_days(self):
        """3d deve retornar timedelta de 3 dias."""
        from datetime import timedelta
        td = self.gm.parse_duration("3d")
        assert td == timedelta(days=3)

    def test_parse_weeks(self):
        """1w deve retornar timedelta de 7 dias."""
        from datetime import timedelta
        td = self.gm.parse_duration("1w")
        assert td == timedelta(weeks=1)

    def test_invalid_format_returns_none(self):
        """Formato inválido deve retornar None."""
        assert self.gm.parse_duration("abc") is None

    def test_empty_string_returns_none(self):
        """String vazia deve retornar None."""
        assert self.gm.parse_duration("") is None

    def test_numeric_only_returns_none(self):
        """Número sem unidade deve retornar None."""
        assert self.gm.parse_duration("60") is None

    def test_case_insensitive(self):
        """Parser deve ser case-insensitive."""
        from datetime import timedelta
        td = self.gm.parse_duration("2H")
        assert td == timedelta(hours=2)
