# tests/test_moderation.py — Testes unitários do módulo tasks/moderation.py
"""
Testa o parsing de respostas do Gemini e a lógica de decisão de moderação.
Não faz chamadas reais à API.
"""
import pytest
from tasks.moderation import _parse_json_response, _should_moderate


class TestParseJsonResponse:
    """Testa o parsing de respostas da IA."""

    def test_valid_json_single_sim(self):
        """JSON válido com veredito SIM deve ser parseado corretamente."""
        response = '{"resultados": [{"id": 1, "veredito": "SIM", "confianca": 0.95, "motivo": "discurso de odio"}]}'
        result = _parse_json_response(response, expected_count=1)
        assert len(result) == 1
        assert result[0]["veredito"] == "SIM"
        assert result[0]["confianca"] == 0.95

    def test_valid_json_single_nao(self):
        """JSON válido com veredito NÃO deve ser parseado corretamente."""
        response = '{"resultados": [{"id": 1, "veredito": "NÃO", "confianca": 0.1, "motivo": "linguagem casual"}]}'
        result = _parse_json_response(response, expected_count=1)
        assert len(result) == 1
        assert result[0]["veredito"] == "NÃO"

    def test_valid_json_multiple(self):
        """JSON com múltiplos resultados deve retornar todos."""
        response = (
            '{"resultados": ['
            '{"id": 1, "veredito": "SIM", "confianca": 0.90, "motivo": "assedio"},'
            '{"id": 2, "veredito": "NÃO", "confianca": 0.05, "motivo": "normal"},'
            '{"id": 3, "veredito": "NÃO", "confianca": 0.10, "motivo": "giria"}'
            ']}'
        )
        result = _parse_json_response(response, expected_count=3)
        assert len(result) == 3
        assert result[0]["veredito"] == "SIM"
        assert result[1]["veredito"] == "NÃO"
        assert result[2]["veredito"] == "NÃO"

    def test_json_with_markdown_code_fence(self):
        """JSON dentro de markdown code fence deve ser parseado."""
        response = '```json\n{"resultados": [{"id": 1, "veredito": "NÃO", "confianca": 0.1, "motivo": "ok"}]}\n```'
        result = _parse_json_response(response, expected_count=1)
        assert len(result) == 1
        assert result[0]["veredito"] == "NÃO"

    def test_completely_invalid_response_returns_empty(self):
        """Resposta inválida que falha no parse deve retornar lista vazia (safe default)."""
        result = _parse_json_response("Erro na API, tente mais tarde", expected_count=2)
        assert result == []

    def test_empty_string_returns_empty(self):
        """String vazia deve retornar lista vazia."""
        result = _parse_json_response("", expected_count=1)
        assert result == []

    def test_partial_json_fallback_to_empty(self):
        """JSON truncado que não pode ser recuperado retorna lista vazia."""
        result = _parse_json_response('{"resultados": [{"id": 1', expected_count=1)
        assert result == []

    def test_resultado_sem_confianca_defaults(self):
        """Resultado sem campo confiança usa 0.0 como default."""
        response = '{"resultados": [{"id": 1, "veredito": "SIM", "confianca": 0.95}]}'
        result = _parse_json_response(response, expected_count=1)
        assert result[0].get("confianca", 0.0) == 0.95


class TestShouldModerate:
    """Testa a função de decisão de moderação."""

    def test_sim_alta_confianca_deve_moderar(self):
        """SIM com confiança acima do threshold deve moderar."""
        result = {"veredito": "SIM", "confianca": 0.95, "motivo": "hate speech"}
        assert _should_moderate(result) is True

    def test_sim_exatamente_no_threshold(self):
        """SIM com confiança exatamente no threshold (0.80) deve moderar."""
        result = {"veredito": "SIM", "confianca": 0.80, "motivo": "hate speech"}
        assert _should_moderate(result) is True

    def test_sim_abaixo_threshold_nao_modera(self):
        """SIM com confiança abaixo do threshold (0.79) NÃO deve moderar."""
        result = {"veredito": "SIM", "confianca": 0.79, "motivo": "duvidoso"}
        assert _should_moderate(result) is False

    def test_nao_nao_modera(self):
        """Veredito NÃO nunca deve moderar, independente da confiança."""
        result = {"veredito": "NÃO", "confianca": 0.99, "motivo": ""}
        assert _should_moderate(result) is False

    def test_dict_vazio_safe_default(self):
        """Dicionário vazio deve retornar False (safe default)."""
        assert _should_moderate({}) is False

    def test_none_safe_default(self):
        """None deve retornar False (safe default)."""
        assert _should_moderate(None) is False

    def test_confianca_zero_nao_modera(self):
        """Confiança 0 nunca deve moderar."""
        result = {"veredito": "SIM", "confianca": 0.0, "motivo": ""}
        assert _should_moderate(result) is False

    def test_confianca_um_deve_moderar(self):
        """Confiança 1.0 com SIM deve moderar."""
        result = {"veredito": "SIM", "confianca": 1.0, "motivo": "certeza absoluta"}
        assert _should_moderate(result) is True

    def test_veredito_lowercase_sim(self):
        """Veredito 'sim' em lowercase deve ser tratado como SIM."""
        result = {"veredito": "sim", "confianca": 0.95}
        assert _should_moderate(result) is True

    def test_veredito_mixed_case(self):
        """Veredito 'Sim' em mixed case deve ser tratado corretamente."""
        result = {"veredito": "Sim", "confianca": 0.90}
        assert _should_moderate(result) is True
