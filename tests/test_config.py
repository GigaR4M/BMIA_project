# tests/test_config.py — Testes unitários do módulo config
"""
Testa as funções utilitárias de config.py sem depender de variáveis de ambiente reais.
"""
import os
import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class TestTimezoneHelpers:
    """Testes para now_brt() e utcnow()."""

    def test_now_brt_returns_aware_datetime(self):
        """now_brt() deve retornar datetime com timezone info."""
        from config import now_brt
        dt = now_brt()
        assert dt.tzinfo is not None

    def test_now_brt_is_brt_timezone(self):
        """now_brt() deve estar no fuso de São Paulo."""
        from config import now_brt, BRT
        dt = now_brt()
        # UTC offset de São Paulo é -3 (sem DST) ou -2 (com DST no verão)
        offset_hours = dt.utcoffset().total_seconds() / 3600
        assert offset_hours in (-3.0, -2.0)

    def test_utcnow_returns_aware_datetime(self):
        """utcnow() deve retornar datetime com timezone UTC."""
        from config import utcnow
        dt = utcnow()
        assert dt.tzinfo is not None
        assert dt.utcoffset().total_seconds() == 0

    def test_now_brt_and_utcnow_consistent(self):
        """now_brt() e utcnow() devem representar o mesmo instante."""
        from config import now_brt, utcnow
        brt = now_brt()
        utc = utcnow()
        # Diferença deve ser menos de 1 segundo (chamadas consecutivas)
        diff = abs((brt.astimezone(timezone.utc) - utc).total_seconds())
        assert diff < 1.0

    def test_now_brt_year_consistency(self):
        """O ano retornado por now_brt() deve ser o ano atual."""
        from config import now_brt
        dt = now_brt()
        from datetime import datetime
        assert dt.year >= 2025  # Sanity check

    def test_brt_constant_is_sao_paulo(self):
        """BRT deve ser o ZoneInfo de America/Sao_Paulo."""
        from config import BRT
        assert str(BRT) == "America/Sao_Paulo"


class TestEnvDefaults:
    """Testa que defaults sensatos são usados quando env vars não estão definidas."""

    def test_gemini_chat_model_has_default(self):
        """GEMINI_CHAT_MODEL deve ter valor padrão."""
        from config import GEMINI_CHAT_MODEL
        assert GEMINI_CHAT_MODEL  # não vazio
        assert isinstance(GEMINI_CHAT_MODEL, str)

    def test_moderation_threshold_in_range(self):
        """Threshold de moderação deve estar entre 0 e 1."""
        from config import MODERATION_CONFIDENCE_THRESHOLD
        assert 0.0 < MODERATION_CONFIDENCE_THRESHOLD <= 1.0

    def test_intervalo_analise_positive(self):
        """INTERVALO_ANALISE deve ser positivo."""
        from config import INTERVALO_ANALISE
        assert INTERVALO_ANALISE > 0

    def test_tamanho_lote_minimo_positive(self):
        """TAMANHO_LOTE_MINIMO deve ser positivo."""
        from config import TAMANHO_LOTE_MINIMO
        assert TAMANHO_LOTE_MINIMO > 0

    def test_default_allowed_channels_is_list(self):
        """DEFAULT_ALLOWED_CHANNELS deve ser lista."""
        from config import DEFAULT_ALLOWED_CHANNELS
        assert isinstance(DEFAULT_ALLOWED_CHANNELS, list)

    def test_default_ignored_voice_channels_is_list(self):
        """DEFAULT_IGNORED_VOICE_CHANNELS deve ser lista."""
        from config import DEFAULT_IGNORED_VOICE_CHANNELS
        assert isinstance(DEFAULT_IGNORED_VOICE_CHANNELS, list)

    def test_default_dynamic_roles_config_is_dict(self):
        """DEFAULT_DYNAMIC_ROLES_CONFIG deve ser dicionário."""
        from config import DEFAULT_DYNAMIC_ROLES_CONFIG
        assert isinstance(DEFAULT_DYNAMIC_ROLES_CONFIG, dict)


class TestSetupLogging:
    """Testa que setup_logging() não lança exceções."""

    def test_setup_logging_no_exception(self):
        """setup_logging() deve executar sem erros."""
        from config import setup_logging
        import logging
        setup_logging(level=logging.WARNING)  # não levanta exceção


class TestCreateIntents:
    """Testa que create_intents() retorna intents configurados corretamente."""

    def test_create_intents_returns_intents(self):
        """create_intents() deve retornar objeto Intents."""
        import discord
        from config import create_intents
        intents = create_intents()
        assert isinstance(intents, discord.Intents)

    def test_create_intents_has_required_permissions(self):
        """create_intents() deve ter os intents necessários para o bot."""
        from config import create_intents
        intents = create_intents()
        assert intents.guilds is True
        assert intents.messages is True
        assert intents.message_content is True
        assert intents.voice_states is True
        assert intents.members is True
        assert intents.presences is True
