# tests/test_spam_detector.py — Testes unitários do SpamDetector
import time
import pytest
from utils.spam_detector import SpamDetector


class TestSpamDetector:
    """Testes para SpamDetector."""

    def test_single_message_not_spam(self):
        """Uma única mensagem nunca é spam."""
        detector = SpamDetector(max_messages=5, time_window=5)
        assert detector.is_spam(user_id=1) is False

    def test_messages_below_limit_not_spam(self):
        """Mensagens abaixo do limite não são spam."""
        detector = SpamDetector(max_messages=5, time_window=5)
        for _ in range(5):
            result = detector.is_spam(user_id=1)
        assert result is False

    def test_burst_messages_detected_as_spam(self):
        """Mensagens em excesso dentro da janela são detectadas como spam."""
        detector = SpamDetector(max_messages=3, time_window=5)
        for _ in range(3):
            detector.is_spam(user_id=42)
        # A 4ª mensagem deve ser spam
        assert detector.is_spam(user_id=42) is True

    def test_different_users_independent(self):
        """Usuários diferentes têm contadores independentes."""
        detector = SpamDetector(max_messages=3, time_window=5)
        for _ in range(3):
            detector.is_spam(user_id=1)
        # Usuário 1 teria atingido o limite; usuário 2 não
        detector.is_spam(user_id=1)  # spam para user 1
        assert detector.is_spam(user_id=2) is False

    def test_spam_resets_after_time_window(self):
        """Após a janela de tempo, o usuário pode enviar mensagens novamente."""
        detector = SpamDetector(max_messages=3, time_window=1)  # janela de 1 segundo
        for _ in range(4):
            detector.is_spam(user_id=99)  # dispara spam

        # Aguarda a janela expirar
        time.sleep(1.1)

        # Agora deve poder enviar novamente
        assert detector.is_spam(user_id=99) is False

    def test_cleanup_triggers_on_large_user_set(self):
        """A limpeza é ativada quando há mais de 100 usuários rastreados."""
        detector = SpamDetector(max_messages=5, time_window=0.01)  # janela muito curta
        # Simula 110 usuários inativos
        for uid in range(110):
            detector.is_spam(user_id=uid)

        time.sleep(0.05)  # Deixa todos expirarem

        # Dispara um novo usuário (ativa cleanup interno)
        detector.is_spam(user_id=200)

        # Usuários inativos devem ter sido limpos (não precisamos checar o tamanho exato,
        # mas o dict não deve crescer indefinidamente)
        assert len(detector.user_messages) <= 110  # Pode ter 200 + alguns residuais

    def test_max_messages_one(self):
        """Com max_messages=1, toda segunda mensagem é spam."""
        detector = SpamDetector(max_messages=1, time_window=60)
        assert detector.is_spam(user_id=7) is False
        assert detector.is_spam(user_id=7) is True

    def test_zero_time_window_always_clears(self):
        """Com janela 0, timestamps antigos são sempre removidos."""
        detector = SpamDetector(max_messages=2, time_window=0)
        # Mensagens com janela 0 se limpam imediatamente
        for _ in range(10):
            result = detector.is_spam(user_id=5)
        # Com janela 0, cada mensagem remove as anteriores -> nunca spam
        assert result is False
