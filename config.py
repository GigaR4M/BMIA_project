# config.py — Configuração Centralizada do Bot BMIA
"""
Módulo único de configuração. Todos os outros módulos importam daqui.
Carrega variáveis de ambiente, define constantes, configura logging
e expõe um helper de timezone consistente.
"""

import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from dotenv import load_dotenv

# ── 1. Carrega variáveis de ambiente ──────────────────────────────────────────
load_dotenv()

# Discord
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")

# Google Gemini
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHAT_API_KEY: str = os.getenv("GEMINI_CHAT_API_KEY", "") or GEMINI_API_KEY
GEMINI_CHAT_MODEL: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
GEMINI_MODERATION_MODEL: str = os.getenv("GEMINI_MODERATION_MODEL", "gemini-2.5-flash")

# Banco de dados
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Canais e cargos padrão (fallback enquanto guild_settings não estiver populado no banco)
# Formato: IDs separados por vírgula
_raw_allowed = os.getenv("DEFAULT_ALLOWED_CHANNELS", "")
_raw_ignored = os.getenv("DEFAULT_IGNORED_VOICE_CHANNELS", "")

DEFAULT_ALLOWED_CHANNELS: list[int] = (
    [int(x.strip()) for x in _raw_allowed.split(",") if x.strip()]
    if _raw_allowed
    else []
)

DEFAULT_IGNORED_VOICE_CHANNELS: list[int] = (
    [int(x.strip()) for x in _raw_ignored.split(",") if x.strip()]
    if _raw_ignored
    else []
)

# Cargos dinâmicos padrão (sobrescritos pelo banco em runtime)
DEFAULT_DYNAMIC_ROLES_CONFIG: dict[str, int] = {}


# ── 2. Constantes de moderação ─────────────────────────────────────────────────
INTERVALO_ANALISE: int = 60          # segundos entre processamentos de lote
TAMANHO_LOTE_MINIMO: int = 10        # mínimo de mensagens por lote
MODERATION_CONFIDENCE_THRESHOLD: float = 0.80  # confiança mínima para deletar

# ── 3. Timezone ────────────────────────────────────────────────────────────────
BRT = ZoneInfo("America/Sao_Paulo")


def now_brt() -> datetime:
    """Retorna datetime *aware* no fuso horário de São Paulo (BRT / UTC-3)."""
    return datetime.now(BRT)


def utcnow() -> datetime:
    """Retorna datetime *aware* em UTC. Substitui datetime.utcnow() (deprecated)."""
    from datetime import timezone
    return datetime.now(timezone.utc)


# ── 4. Logging ─────────────────────────────────────────────────────────────────
def setup_logging(level: int = logging.INFO) -> None:
    """Configura o sistema de logging do bot."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# ── 5. Discord Intents ─────────────────────────────────────────────────────────
def create_intents() -> discord.Intents:
    """Cria e retorna os intents necessários para o bot."""
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    intents.voice_states = True   # estatísticas de voz
    intents.members = True        # informações de membros
    intents.presences = True      # rastrear jogos/atividades
    return intents
