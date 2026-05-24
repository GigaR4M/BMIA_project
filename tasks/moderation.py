# tasks/moderation.py — Moderação por IA (Análise em Lote)
"""
Toda a lógica de moderação com Gemini foi extraída do main.py para cá.
Melhorias em relação à versão original:
 - Prompt solicita JSON estruturado (mais robusto que split(","))
 - Parsing com fallback regex → safe default (assume NÃO)
 - Threshold de confiança (0.8) para evitar falsos positivos
 - Log de auditoria com motivo da decisão
"""

import json
import re
import logging
import traceback

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import discord

from config import (
    GEMINI_API_KEY,
    GEMINI_MODERATION_MODEL,
    MODERATION_CONFIDENCE_THRESHOLD,
    INTERVALO_ANALISE,
    TAMANHO_LOTE_MINIMO,
)

logger = logging.getLogger(__name__)

# Inicializa o modelo de moderação
genai.configure(api_key=GEMINI_API_KEY)
_moderation_model = genai.GenerativeModel(model_name=GEMINI_MODERATION_MODEL)

# ---------------------------------------------------------------------------
# Prompt e Parsing
# ---------------------------------------------------------------------------

_MODERATION_PROMPT_TEMPLATE = """\
Você é um moderador de um chat de jogos em português brasileiro.
Analise as mensagens abaixo e determine se cada uma contém conteúdo proibido.

CRITÉRIOS PARA "SIM" (remover):
- Discurso de ódio (racismo, homofobia, etc.)
- Assédio ou ameaças diretas a usuários
- Conteúdo NSFW explícito (pornografia, violência extrema)

CRITÉRIOS PARA "NÃO" (manter):
- Palavrões leves em contexto casual ou de jogo
- Gírias, sarcasmo, humor, ironia
- Críticas a jogos ou personagens
- Em QUALQUER caso de dúvida, responda NÃO

Responda EXCLUSIVAMENTE com JSON válido no formato abaixo, sem markdown, sem texto extra:
{{"resultados": [{{"id": 1, "veredito": "SIM", "confianca": 0.95, "motivo": "..."}}]}}

Use "SIM" ou "NÃO" como veredito. Confiança entre 0.0 e 1.0.

MENSAGENS:
{messages}
"""


def _build_prompt(messages: list[discord.Message]) -> str:
    lines = "\n".join(
        f'{i}: "{msg.content}"' for i, msg in enumerate(messages, 1)
    )
    return _MODERATION_PROMPT_TEMPLATE.format(messages=lines)


def _parse_json_response(
    response_text: str, expected_count: int
) -> list[dict]:
    """
    Tenta fazer o parse do JSON retornado pelo Gemini.
    Em caso de falha, usa regex como fallback.
    Se tudo falhar, retorna safe defaults (NÃO para todas).
    """
    # Limpa possíveis markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", response_text).strip()

    # Tentativa 1: JSON puro
    try:
        data = json.loads(cleaned)
        return data.get("resultados", [])
    except json.JSONDecodeError:
        logger.debug("Parse JSON falhou, tentando regex fallback.")

    # Tentativa 2: Regex — busca pares id/veredito no texto
    results: list[dict] = []
    pattern = re.compile(
        r'"id"\s*:\s*(\d+).*?"veredito"\s*:\s*"(SIM|NÃO|NAO)"'
        r'.*?"confianca"\s*:\s*([\d.]+)',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(cleaned):
        results.append({
            "id": int(m.group(1)),
            "veredito": m.group(2).upper().replace("NAO", "NÃO"),
            "confianca": float(m.group(3)),
            "motivo": "extraído via regex",
        })

    if results:
        return results

    # Tentativa 3: Safe default
    logger.warning(
        "Não foi possível parsear resposta da IA. Aplicando safe default (NÃO) "
        "para %d mensagens. Resposta bruta: %.200s",
        expected_count,
        response_text,
    )
    return []  # vazio → tratado como "todas NÃO"


def _should_moderate(result: dict) -> bool:
    """
    Retorna True apenas se veredito for SIM e confiança ≥ threshold.
    Safe default: qualquer ambiguidade → não modera.
    """
    if not result:
        return False
    veredito = result.get("veredito", "NÃO").upper()
    confianca = float(result.get("confianca", 0.0))
    return veredito == "SIM" and confianca >= MODERATION_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Função principal de análise
# ---------------------------------------------------------------------------

async def analisar_lote_com_ia(
    lista_de_mensagens: list[discord.Message],
) -> list[str]:
    """
    Analisa um lote de mensagens com Gemini.
    Retorna lista de "SIM" / "NÃO" na mesma ordem das mensagens recebidas.
    """
    if not lista_de_mensagens:
        return []

    logger.info("-> Analisando lote de %d mensagens...", len(lista_de_mensagens))

    try:
        prompt = _build_prompt(lista_de_mensagens)
        response = await _moderation_model.generate_content_async(prompt)
        raw_text = response.text.strip()
        logger.debug("Resposta bruta da IA: %.300s", raw_text)

        parsed = _parse_json_response(raw_text, len(lista_de_mensagens))

        # Monta dicionário id → resultado (id começa em 1)
        result_map: dict[int, dict] = {r["id"]: r for r in parsed}

        vereditos: list[str] = []
        for i in range(1, len(lista_de_mensagens) + 1):
            result = result_map.get(i, {})
            if _should_moderate(result):
                motivo = result.get("motivo", "sem motivo")
                confianca = result.get("confianca", 0.0)
                logger.info(
                    "🚨 Mensagem %d classificada como ofensiva "
                    "(confiança=%.2f, motivo=%s)",
                    i, confianca, motivo,
                )
                vereditos.append("SIM")
            else:
                vereditos.append("NÃO")

        return vereditos

    except ResourceExhausted:
        logger.warning(
            "⚠️ Cota da API Gemini excedida. Ignorando lote de %d mensagens.",
            len(lista_de_mensagens),
        )
        return ["NÃO"] * len(lista_de_mensagens)
    except Exception:
        logger.error("Erro inesperado na análise em lote:")
        traceback.print_exc()
        return ["NÃO"] * len(lista_de_mensagens)


# ---------------------------------------------------------------------------
# Loop do processador em lote
# ---------------------------------------------------------------------------

async def processador_em_lote(
    buffer_mensagens: list[discord.Message],
    db,
    points_manager,
    telegram,
) -> None:
    """
    Corrotina contínua que drena o buffer global de mensagens e aplica moderação.
    Deve ser iniciada como task com client.loop.create_task().
    """
    import asyncio

    while True:
        await asyncio.sleep(INTERVALO_ANALISE)

        if not buffer_mensagens:
            continue

        qtd = min(len(buffer_mensagens), TAMANHO_LOTE_MINIMO)
        chunk = buffer_mensagens[:qtd]
        buffer_mensagens[:] = buffer_mensagens[qtd:]

        # Filtra apenas mensagens de guilds com moderação ativada
        mensagens_filtradas: list[discord.Message] = []
        guild_status_cache: dict[int, bool] = {}

        if db:
            for msg in chunk:
                if not msg.guild:
                    continue
                gid = msg.guild.id
                if gid not in guild_status_cache:
                    guild_status_cache[gid] = await db.is_ai_moderation_enabled(gid)
                if guild_status_cache[gid]:
                    mensagens_filtradas.append(msg)
        else:
            mensagens_filtradas = chunk

        if not mensagens_filtradas:
            continue

        vereditos = await analisar_lote_com_ia(mensagens_filtradas)

        for msg, veredito in zip(mensagens_filtradas, vereditos):
            if veredito == "SIM":
                try:
                    await msg.delete()
                    await msg.channel.send(
                        f"⚠️ Mensagem de {msg.author.mention} removida por "
                        "conter linguagem inadequada.",
                        delete_after=10,
                    )
                    if db:
                        await db.update_message_moderation_status(msg.id, True)

                    # Notifica Telegram
                    if telegram:
                        await telegram.log_message_deleted(
                            guild=msg.guild,
                            channel=msg.channel,
                            author=msg.author,
                            content=msg.content,
                            reason="Moderação por IA",
                        )

                    # Remove pontos do usuário
                    if points_manager:
                        points_to_remove = 1
                        if len(msg.content) >= 10:
                            points_to_remove = 2
                        if msg.reference:
                            points_to_remove += 1
                        if msg.guild:
                            await points_manager.remove_points(
                                msg.author.id,
                                points_to_remove,
                                msg.guild.id,
                                "moderation_deletion",
                            )

                except discord.Forbidden:
                    logger.warning(
                        "Sem permissão para deletar mensagem em %s",
                        msg.channel.name if msg.channel else "canal desconhecido",
                    )
                except Exception as exc:
                    logger.error("Erro ao processar mensagem moderada: %s", exc)
            else:
                if db:
                    await db.update_message_moderation_status(msg.id, False)
