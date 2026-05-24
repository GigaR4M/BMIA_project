# tests/test_database.py — Testes unitários do módulo Database
"""
Testa os métodos do Database usando mocks de asyncpg para evitar
dependência de banco de dados real.
Cobre: guild_settings, get_guild_config, set_allowed_channels, is_ai_moderation_enabled.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_pool():
    """Cria um mock de asyncpg.Pool."""
    pool = MagicMock()

    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    pool.acquire = MagicMock(
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        )
    )
    return pool, conn


@pytest_asyncio.fixture
async def db_with_mock(mock_pool):
    """Instancia Database injetando o mock de pool."""
    from database import Database
    pool, conn = mock_pool
    db = Database.__new__(Database)
    db.pool = pool
    db.database_url = "postgresql://mock"
    return db, conn


# ── Testes de is_ai_moderation_enabled ────────────────────────────────────────

class TestIsAiModerationEnabled:

    @pytest.mark.asyncio
    async def test_returns_true_when_enabled(self, db_with_mock):
        """Deve retornar True quando banco diz True."""
        db, conn = db_with_mock
        conn.fetchval = AsyncMock(return_value=True)
        result = await db.is_ai_moderation_enabled(12345)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self, db_with_mock):
        """Deve retornar False quando banco diz False."""
        db, conn = db_with_mock
        conn.fetchval = AsyncMock(return_value=False)
        result = await db.is_ai_moderation_enabled(12345)
        assert result is False

    @pytest.mark.asyncio
    async def test_default_true_when_not_configured(self, db_with_mock):
        """Deve retornar True por padrão quando guild não está configurada."""
        db, conn = db_with_mock
        conn.fetchval = AsyncMock(return_value=None)
        result = await db.is_ai_moderation_enabled(99999)
        assert result is True


# ── Testes de set_ai_moderation ────────────────────────────────────────────────

class TestSetAiModeration:

    @pytest.mark.asyncio
    async def test_calls_execute_with_correct_args(self, db_with_mock):
        """set_ai_moderation deve chamar execute com os parâmetros corretos."""
        db, conn = db_with_mock
        await db.set_ai_moderation(guild_id=42, enabled=False)
        conn.execute.assert_called_once()
        args = conn.execute.call_args[0]
        assert 42 in args
        assert False in args


# ── Testes de get_guild_config ─────────────────────────────────────────────────

class TestGetGuildConfig:

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_row(self, db_with_mock):
        """Deve retornar dicionário vazio se guild não existe."""
        db, conn = db_with_mock
        conn.fetchrow = AsyncMock(return_value=None)
        result = await db.get_guild_config(guild_id=1)
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_correct_structure(self, db_with_mock):
        """Deve retornar dicionário com todas as chaves esperadas."""
        db, conn = db_with_mock
        mock_row = {
            "ai_moderation_enabled": True,
            "allowed_channels": [111, 222],
            "ignored_voice_channels": [333],
            "announcement_channel_id": 444,
            "dynamic_roles_config": {"top_1": 555},
        }
        conn.fetchrow = AsyncMock(return_value=mock_row)
        result = await db.get_guild_config(guild_id=100)

        assert result["ai_moderation_enabled"] is True
        assert result["allowed_channels"] == [111, 222]
        assert result["ignored_voice_channels"] == [333]
        assert result["announcement_channel_id"] == 444
        assert result["dynamic_roles_config"] == {"top_1": 555}

    @pytest.mark.asyncio
    async def test_handles_null_arrays(self, db_with_mock):
        """Deve tratar arrays NULL do banco como listas vazias."""
        db, conn = db_with_mock
        mock_row = {
            "ai_moderation_enabled": True,
            "allowed_channels": None,
            "ignored_voice_channels": None,
            "announcement_channel_id": None,
            "dynamic_roles_config": None,
        }
        conn.fetchrow = AsyncMock(return_value=mock_row)
        result = await db.get_guild_config(guild_id=200)

        assert result["allowed_channels"] == []
        assert result["ignored_voice_channels"] == []
        assert result["dynamic_roles_config"] == {}


# ── Testes de set_allowed_channels ────────────────────────────────────────────

class TestSetAllowedChannels:

    @pytest.mark.asyncio
    async def test_calls_execute_with_channels(self, db_with_mock):
        """Deve chamar execute com o guild_id e lista de canais."""
        db, conn = db_with_mock
        channels = [111, 222, 333]
        await db.set_allowed_channels(guild_id=10, channel_ids=channels)
        conn.execute.assert_called_once()
        args = conn.execute.call_args[0]
        assert 10 in args
        assert channels in args

    @pytest.mark.asyncio
    async def test_accepts_empty_list(self, db_with_mock):
        """Deve aceitar lista vazia (desabilita todos os canais)."""
        db, conn = db_with_mock
        await db.set_allowed_channels(guild_id=10, channel_ids=[])
        conn.execute.assert_called_once()


# ── Testes de set_dynamic_roles ───────────────────────────────────────────────

class TestSetDynamicRoles:

    @pytest.mark.asyncio
    async def test_calls_execute_with_roles(self, db_with_mock):
        """Deve chamar execute com guild_id e JSON dos cargos."""
        db, conn = db_with_mock
        roles = {"top_1": 123456, "gamer": 789}
        await db.set_dynamic_roles(guild_id=50, roles_config=roles)
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_accepts_empty_dict(self, db_with_mock):
        """Deve aceitar dicionário vazio (sem cargos dinâmicos)."""
        db, conn = db_with_mock
        await db.set_dynamic_roles(guild_id=50, roles_config={})
        conn.execute.assert_called_once()
