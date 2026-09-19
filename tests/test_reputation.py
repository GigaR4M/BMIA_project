# tests/test_reputation.py — Testes unitários do Sistema de Reputação e Dossiê
import pytest
from unittest.mock import AsyncMock, MagicMock
from utils.reputation_manager import ReputationManager

def test_trust_score_clean_veteran():
    """Usuário veterano sem infrações deve ter Trust Score 100 e classificação EXCELLENT."""
    score_data = ReputationManager.calculate_trust_score(
        account_age_days=1200,          # > 3 anos (+5)
        server_membership_days=200,     # > 6 meses (+5)
        infractions_summary={},
        reports_count=0,
        approved_reports_count=0,
        moderated_messages_count=0,
        is_currently_timed_out=False
    )
    assert score_data["score"] == 100
    assert score_data["tier"] == "EXCELLENT"
    assert len(score_data["penalties"]) == 0
    assert len(score_data["bonuses"]) >= 2

def test_trust_score_new_account_penalty():
    """Conta criada há menos de 7 dias recebe penalidade pesada."""
    score_data = ReputationManager.calculate_trust_score(
        account_age_days=3,             # < 7 dias (-25)
        server_membership_days=1,
        infractions_summary={},
        reports_count=0
    )
    assert score_data["score"] == 75
    assert score_data["tier"] == "GOOD"
    assert any("Conta recém-criada" in p[0] for p in score_data["penalties"])

def test_trust_score_multiple_infractions_high_risk():
    """Múltiplas infrações (timeouts, mutes, kicks) devem derrubar a reputação para HIGH_RISK."""
    infractions = {
        "timeout": {"count": 3, "total_duration": 10800},
        "mute": {"count": 1, "total_duration": 3600},
        "kick": {"count": 1, "total_duration": 0},
        "warn": {"count": 2, "total_duration": 0}
    }
    score_data = ReputationManager.calculate_trust_score(
        account_age_days=100,
        server_membership_days=50,
        infractions_summary=infractions,
        reports_count=3,
        approved_reports_count=2,       # -30
        moderated_messages_count=5,     # -20
        is_currently_timed_out=True     # -15
    )
    assert score_data["score"] < 50
    assert score_data["tier"] == "HIGH_RISK"
    assert len(score_data["penalties"]) >= 5

@pytest.mark.asyncio
async def test_database_infractions_and_reports():
    """Testa métodos de inserção e busca de infrações e denúncias no mock do Database."""
    from database import Database
    db = Database.__new__(Database)
    db.pool = MagicMock()
    
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = 1
    mock_conn.fetch.return_value = [{"id": 1, "action_type": "timeout", "reason": "Spam", "duration_seconds": 600}]
    mock_conn.fetchrow.return_value = {"user_id": 12345, "username": "TestUser"}
    mock_conn.execute.return_value = "UPDATE 1"
    
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_acquire.__aexit__.return_value = None
    db.pool.acquire.return_value = mock_acquire

    # 1. Adicionar infração
    inf_id = await db.add_user_infraction(
        guild_id=123,
        user_id=456,
        moderator_id=789,
        action_type="timeout",
        reason="Flood de mensagens",
        duration_seconds=600
    )
    assert inf_id == 1

    # 2. Criar denúncia
    rep_id = await db.create_user_report(
        guild_id=123,
        target_user_id=456,
        reporter_user_id=789,
        category="spam",
        reason="Divulgando links no chat geral"
    )
    assert rep_id == 1

    # 3. Atualizar status da denúncia
    updated = await db.update_report_status(report_id=1, status="approved", handled_by=789)
    assert updated is True
