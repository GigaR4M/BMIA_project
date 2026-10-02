import base64
import os
import hashlib
import json
import discord
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import aiohttp
from typing import Optional, List, Any, Dict, Tuple
import asyncio
from datetime import datetime

# Cache em memória para bytes brutos de avatares e ícones
_AVATAR_BYTES_CACHE: Dict[str, bytes] = {}
_AVATAR_CACHE: Dict[str, str] = {}
_GUILD_ICON_CACHE: Dict[int, str] = {}
_GUILD_ICON_BYTES_CACHE: Dict[int, bytes] = {}

# Cache de fontes carregadas
_FONT_CACHE: Dict[Tuple[int, bool, bool], ImageFont.ImageFont] = {}

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "tournaments")


async def fetch_image_from_dashboard(payload_type: str, payload_data: dict, timeout_seconds: float = 20.0) -> Optional[BytesIO]:
    """
    Dispara a renderização pesada (HTML5/CSS3) para o microsserviço serverless na Vercel (bmia-dashboard).
    Economiza 100% de memória RAM na VPS. Retorna BytesIO da imagem PNG pronta.
    Retorna None caso a URL não esteja configurada ou ocorra falha de rede (permitindo fallback seguro).
    """
    try:
        from config import DASHBOARD_RENDER_URL, INTERNAL_RENDER_SECRET
    except ImportError:
        DASHBOARD_RENDER_URL = os.getenv("DASHBOARD_RENDER_URL", os.getenv("DASHBOARD_URL", "")).rstrip("/")
        if DASHBOARD_RENDER_URL and not DASHBOARD_RENDER_URL.endswith("/api/render"):
            DASHBOARD_RENDER_URL = f"{DASHBOARD_RENDER_URL}/api/render"
        INTERNAL_RENDER_SECRET = os.getenv("INTERNAL_RENDER_SECRET", os.getenv("NEXTAUTH_SECRET", ""))

    if not DASHBOARD_RENDER_URL:
        return None

    headers = {
        "Content-Type": "application/json",
    }
    if INTERNAL_RENDER_SECRET:
        headers["Authorization"] = f"Bearer {INTERNAL_RENDER_SECRET}"

    json_payload = {
        "type": payload_type,
        "data": payload_data
    }

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(DASHBOARD_RENDER_URL, json=json_payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if data and data.startswith(b"\x89PNG"):
                        buf = BytesIO(data)
                        buf.seek(0)
                        return buf
    except Exception:
        pass

    return None


def _get_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.ImageFont:
    """Carrega fontes de alta qualidade com fallback seguro e cache em memória."""
    key = (size, bold, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidate_fonts = []
    if mono:
        candidate_fonts = [
            "consola.ttf", "consolab.ttf" if bold else "consola.ttf",
            "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf",
            "Courier New.ttf", "cour.ttf"
        ]
    elif bold:
        candidate_fonts = [
            "arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf",
            "LiberationSans-Bold.ttf", "FreeSansBold.ttf", "arial.ttf"
        ]
    else:
        candidate_fonts = [
            "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf", "FreeSans.ttf"
        ]

    font_obj = None
    for fname in candidate_fonts:
        try:
            font_obj = ImageFont.truetype(fname, size)
            break
        except Exception:
            continue

    if font_obj is None:
        try:
            font_obj = ImageFont.load_default()
        except Exception:
            pass

    _FONT_CACHE[key] = font_obj
    return font_obj


def _get_tournament_state_hash(tourney: dict, participants: list, matches: Optional[list] = None) -> str:
    """Gera uma assinatura hash determinística do estado atual do torneio."""
    state_payload = {
        "id": tourney.get("id"),
        "status": tourney.get("status"),
        "format": tourney.get("format"),
        "participants": [(p.get("user_id"), p.get("username")) for p in sorted(participants, key=lambda x: str(x.get("user_id", 0)))],
        "matches": [
            (
                m.get("id"),
                m.get("round_number"),
                m.get("match_number"),
                m.get("winner_id"),
                m.get("score_a"),
                m.get("score_b"),
                m.get("scores_json"),
                m.get("status")
            )
            for m in sorted((matches or []), key=lambda x: str(x.get("id", 0)))
        ]
    }
    encoded = json.dumps(state_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.md5(encoded).hexdigest()


def _get_league_state_hash(tourney: dict, standings: list, matches: Optional[list] = None) -> str:
    """Gera uma assinatura hash determinística do estado atual da liga de pontos corridos."""
    state_payload = {
        "id": tourney.get("id"),
        "status": tourney.get("status"),
        "standings": standings,
        "matches": [
            (
                m.get("id"),
                m.get("round_number"),
                m.get("match_number"),
                m.get("winner_id"),
                m.get("score_a"),
                m.get("score_b"),
                m.get("status")
            )
            for m in sorted((matches or []), key=lambda x: str(x.get("id", 0)))
        ]
    }
    encoded = json.dumps(state_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.md5(encoded).hexdigest()


def _read_cached_image(prefix: str, state_hash: str) -> Optional[BytesIO]:
    """Lê a imagem em cache do disco se o hash de estado coincidir."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        filename = f"{prefix}_{state_hash}.png"
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                data = f.read()
            if data and data.startswith(b"\x89PNG"):
                buf = BytesIO(data)
                buf.seek(0)
                return buf
    except Exception:
        pass
    return None


def _save_cached_image(prefix: str, state_hash: str, image_bytes: bytes):
    """Salva a nova imagem gerada no disco e remove versões obsoletas para economizar espaço."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        for fname in os.listdir(CACHE_DIR):
            if fname.startswith(f"{prefix}_") and fname.endswith(".png"):
                try:
                    os.remove(os.path.join(CACHE_DIR, fname))
                except Exception:
                    pass
        target_path = os.path.join(CACHE_DIR, f"{prefix}_{state_hash}.png")
        with open(target_path, "wb") as f:
            f.write(image_bytes)
    except Exception:
        pass


# =============================================================================
# HELPER DE DESENHO VETORIAL COM PILLOW
# =============================================================================

def _draw_glow_rect(
    base_img: Image.Image,
    xy: Tuple[int, int, int, int],
    radius: int = 16,
    glow_color: Tuple[int, int, int, int] = (0, 240, 255, 120),
    glow_radius: int = 14,
    fill_color: Optional[Tuple[int, int, int, int]] = (15, 23, 42, 235),
    outline_color: Optional[Tuple[int, int, int, int]] = (0, 240, 255, 180),
    outline_width: int = 2,
    width: Optional[int] = None
):
    """Desenha um retângulo com cantos arredondados e efeito de brilho neon (Glow)."""
    if width is not None:
        outline_width = width
    x1, y1, x2, y2 = xy
    w = x2 - x1
    h = y2 - y1
    if w <= 0 or h <= 0:
        return

    # Camada de Glow com Blur
    padding = glow_radius * 2
    glow_canvas = Image.new("RGBA", (w + padding * 2, h + padding * 2), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_canvas)
    glow_draw.rounded_rectangle(
        (padding, padding, padding + w, padding + h),
        radius=radius,
        fill=None,
        outline=glow_color,
        width=outline_width + 3
    )
    glow_blurred = glow_canvas.filter(ImageFilter.GaussianBlur(glow_radius))
    base_img.alpha_composite(glow_blurred, (x1 - padding, y1 - padding))

    # Desenha o corpo principal e borda nítida
    top_draw = ImageDraw.Draw(base_img)
    top_draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=fill_color,
        outline=outline_color,
        width=outline_width
    )


def _draw_circle_avatar(
    target_img: Image.Image,
    avatar_bytes: Optional[bytes],
    center_xy: Tuple[int, int],
    size: int,
    border_color: Optional[Tuple[int, int, int, int]] = (0, 240, 255, 255),
    border_width: int = 3,
    fallback_initial: str = "?"
):
    """
    Desenha um avatar circular perfeito com super-sampling (2x anti-aliasing)
    e borda de destaque da patente/cor do membro.
    """
    cx, cy = center_xy
    half = size // 2
    x1 = cx - half
    y1 = cy - half

    # Super-sampling 2x
    scale = 2
    big_size = size * scale

    if avatar_bytes:
        try:
            raw_av = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            av_resized = raw_av.resize((big_size, big_size), Image.Resampling.LANCZOS)
        except Exception:
            av_resized = None
    else:
        av_resized = None

    if av_resized is None:
        # Fallback Avatar Esportivo
        av_resized = Image.new("RGBA", (big_size, big_size), (21, 28, 46, 255))
        d_fb = ImageDraw.Draw(av_resized)
        f_init = _get_font(int(big_size * 0.45), bold=True)
        d_fb.text((big_size // 2, big_size // 2), fallback_initial.upper()[:1], fill=(255, 255, 255, 255), font=f_init, anchor="mm")

    # Máscara circular 2x
    mask = Image.new("L", (big_size, big_size), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.ellipse((0, 0, big_size, big_size), fill=255)

    # Aplica máscara e reduz para o tamanho final (LANCZOS = Anti-Serrilhado suave)
    final_av = Image.new("RGBA", (big_size, big_size), (0, 0, 0, 0))
    final_av.paste(av_resized, (0, 0), mask=mask)
    final_av = final_av.resize((size, size), Image.Resampling.LANCZOS)

    # Cola o avatar no canvas
    target_img.alpha_composite(final_av, (x1, y1))

    # Borda externa circular
    if border_color and border_width > 0:
        d_main = ImageDraw.Draw(target_img)
        d_main.ellipse((x1, y1, x1 + size, y1 + size), outline=border_color, width=border_width)


def _draw_linear_gradient_bar(
    target_img: Image.Image,
    xy: Tuple[int, int, int, int],
    start_color: Tuple[int, int, int],
    end_color: Tuple[int, int, int],
    radius: int = 8
):
    """Desenha uma barra com gradiente linear horizontal e cantos arredondados."""
    x1, y1, x2, y2 = xy
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)

    grad_img = Image.new("RGBA", (w, h))
    for x in range(w):
        factor = x / max(1, w - 1)
        r = int(start_color[0] + factor * (end_color[0] - start_color[0]))
        g = int(start_color[1] + factor * (end_color[1] - start_color[1]))
        b = int(start_color[2] + factor * (end_color[2] - start_color[2]))
        for y in range(h):
            grad_img.putpixel((x, y), (r, g, b, 255))

    mask = Image.new("L", (w, h), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=255)

    target_img.paste(grad_img, (x1, y1), mask=mask)


# =============================================================================

def _draw_vector_icon(
    draw: ImageDraw.ImageDraw,
    icon_type: str,
    x: int,
    y: int,
    color: Tuple[int, int, int, int] = (0, 240, 255, 255),
    scale: float = 1.0
):
    """Desenha ícones vetoriais nítidos em alta definição sem depender de emojis ou fontes externas."""
    if icon_type == "lightning":
        # Raio futurista
        points = [
            (x + int(5 * scale), y),
            (x + int(1 * scale), y + int(6 * scale)),
            (x + int(5 * scale), y + int(6 * scale)),
            (x + int(3 * scale), y + int(13 * scale)),
            (x + int(9 * scale), y + int(5 * scale)),
            (x + int(5 * scale), y + int(5 * scale))
        ]
        draw.polygon(points, fill=color)
    elif icon_type == "chat":
        # Balão de conversa
        w, h = int(12 * scale), int(8 * scale)
        draw.rounded_rectangle((x, y + int(1 * scale), x + w, y + h + int(1 * scale)), radius=max(1, int(2 * scale)), fill=color)
        draw.polygon([(x + int(2 * scale), y + h + int(1 * scale)), (x + int(2 * scale), y + h + int(4 * scale)), (x + int(6 * scale), y + h + int(1 * scale))], fill=color)
    elif icon_type == "mic":
        # Microfone / Áudio
        draw.rounded_rectangle((x + int(3 * scale), y, x + int(8 * scale), y + int(7 * scale)), radius=max(1, int(2 * scale)), fill=color)
        draw.arc((x + int(1 * scale), y + int(2 * scale), x + int(10 * scale), y + int(9 * scale)), start=0, end=180, fill=color, width=max(1, int(1 * scale)))
        draw.line([(x + int(5 * scale), y + int(9 * scale)), (x + int(5 * scale), y + int(12 * scale))], fill=color, width=max(1, int(1 * scale)))
        draw.line([(x + int(2 * scale), y + int(12 * scale)), (x + int(8 * scale), y + int(12 * scale))], fill=color, width=max(1, int(1 * scale)))
    elif icon_type == "star":
        # Estrela de 5 pontas
        points = [
            (x + int(5 * scale), y),
            (x + int(6 * scale), y + int(3 * scale)),
            (x + int(10 * scale), y + int(3 * scale)),
            (x + int(7 * scale), y + int(6 * scale)),
            (x + int(8 * scale), y + int(10 * scale)),
            (x + int(5 * scale), y + int(7 * scale)),
            (x + int(2 * scale), y + int(10 * scale)),
            (x + int(3 * scale), y + int(6 * scale)),
            (x, y + int(3 * scale)),
            (x + int(4 * scale), y + int(3 * scale))
        ]
        draw.polygon(points, fill=color)
    elif icon_type == "trophy":
        # Troféu Esportivo
        w = int(14 * scale)
        draw.polygon([(x + int(2 * scale), y), (x + w - int(2 * scale), y), (x + w - int(4 * scale), y + int(8 * scale)), (x + int(4 * scale), y + int(8 * scale))], fill=color)
        draw.rectangle((x + int(6 * scale), y + int(8 * scale), x + int(8 * scale), y + int(12 * scale)), fill=color)
        draw.rounded_rectangle((x + int(2 * scale), y + int(12 * scale), x + w - int(2 * scale), y + int(14 * scale)), radius=1, fill=color)
    elif icon_type == "crown":
        # Coroa de Campeão
        w = int(14 * scale)
        points = [
            (x, y + int(10 * scale)),
            (x + int(2 * scale), y + int(2 * scale)),
            (x + int(5 * scale), y + int(6 * scale)),
            (x + int(7 * scale), y + int(1 * scale)),
            (x + int(9 * scale), y + int(6 * scale)),
            (x + int(12 * scale), y + int(2 * scale)),
            (x + w, y + int(10 * scale))
        ]
        draw.polygon(points, fill=color)
        draw.rounded_rectangle((x, y + int(10 * scale), x + w, y + int(12 * scale)), radius=1, fill=color)


# 1. RANK CARD BUILDER (1060x300 - PIL PURO)
# =============================================================================

def _sync_draw_rank_card(
    username: str,
    display_name: str,
    avatar_bytes: Optional[bytes],
    level_data: dict,
    server_rank: int,
    messages_count: int,
    voice_minutes: int,
    guild_name: str
) -> bytes:
    level = level_data.get("level", 1)
    total_xp = level_data.get("total_xp", 0)
    xp_in_level = level_data.get("xp_in_level", 0)
    xp_needed = level_data.get("xp_needed_in_level", 100)
    progress_pct = max(0.0, min(1.0, level_data.get("progress_pct", 0.0) / 100.0))
    hours_voice = round(voice_minutes / 60, 1)

    # Identifica a patente e cores
    if level >= 50:
        tier_name = "MESTRE"
        tier_color = (255, 215, 0, 255) # Ouro
        glow_c = (255, 215, 0, 100)
        grad_start = (255, 215, 0)
        grad_end = (245, 158, 11)
    elif level >= 25:
        tier_name = "DIAMANTE"
        tier_color = (0, 240, 255, 255) # Ciano
        glow_c = (0, 240, 255, 120)
        grad_start = (0, 240, 255)
        grad_end = (59, 130, 246)
    elif level >= 10:
        tier_name = "PLATINA"
        tier_color = (176, 38, 255, 255) # Roxo
        glow_c = (176, 38, 255, 110)
        grad_start = (176, 38, 255)
        grad_end = (236, 72, 153)
    else:
        tier_name = "BRONZE"
        tier_color = (56, 189, 248, 255) # Azul
        glow_c = (56, 189, 248, 90)
        grad_start = (56, 189, 248)
        grad_end = (99, 102, 241)

    # Canvas 1060x300 transparente
    img = Image.new("RGBA", (1060, 300), (0, 0, 0, 0))

    # Fundo do Card com Glow
    _draw_glow_rect(
        base_img=img,
        xy=(15, 15, 1045, 285),
        radius=20,
        glow_color=glow_c,
        glow_radius=12,
        fill_color=(10, 15, 28, 245),
        outline_color=tier_color,
        outline_width=2
    )

    draw = ImageDraw.Draw(img)

    # Linha neon superior
    _draw_linear_gradient_bar(img, (25, 16, 1035, 20), grad_start, grad_end, radius=2)

    # Avatar do Usuário (120px) com Super-Sampling
    _draw_circle_avatar(
        target_img=img,
        avatar_bytes=avatar_bytes,
        center_xy=(100, 150),
        size=120,
        border_color=tier_color,
        border_width=3,
        fallback_initial=display_name[0] if display_name else username[0]
    )

    # Textos do Topo: Nome, Tag e Servidor
    font_name = _get_font(28, bold=True)
    font_sub = _get_font(16, bold=False)
    font_bold14 = _get_font(14, bold=True)
    font_rank_num = _get_font(38, bold=True)
    font_rank_label = _get_font(14, bold=True)

    # Nome e Tag
    d_name = display_name[:18] + ("..." if len(display_name) > 18 else "")
    draw.text((185, 42), d_name, fill=(255, 255, 255, 255), font=font_name)
    name_w = draw.textlength(d_name, font=font_name)

    tag_str = f"@{username[:14]}"
    draw.text((185 + name_w + 12, 52), tag_str, fill=(148, 163, 184, 255), font=font_sub)

    # Badge do Nível / Patente
    badge_x = 185
    badge_y = 86
    badge_text = f"NÍVEL {level} • {tier_name}"
    b_w = int(draw.textlength(badge_text, font=font_bold14)) + 38
    draw.rounded_rectangle((badge_x, badge_y, badge_x + b_w, badge_y + 26), radius=13, fill=(tier_color[0], tier_color[1], tier_color[2], 40), outline=tier_color, width=1)
    _draw_vector_icon(draw, "star", badge_x + 10, badge_y + 7, tier_color, scale=1.1)
    draw.text((badge_x + 26, badge_y + 5), badge_text, fill=tier_color, font=font_bold14)

    # Servidor Rank (Canto Superior Direito)
    rank_str = f"#{server_rank}"
    draw.text((1015, 40), rank_str, fill=tier_color, font=font_rank_num, anchor="ra")
    draw.text((1015, 84), "RANK NO SERVIDOR", fill=(148, 163, 184, 255), font=font_rank_label, anchor="ra")

    # Barra de Progresso XP
    bar_x1, bar_y1, bar_x2, bar_y2 = 185, 130, 1015, 162
    bar_w = bar_x2 - bar_x1
    # Fundo da barra
    draw.rounded_rectangle((bar_x1, bar_y1, bar_x2, bar_y2), radius=8, fill=(20, 30, 50, 255), outline=(255, 255, 255, 30), width=1)

    # Preenchimento Gradiente da barra
    fill_w = max(6, int(bar_w * progress_pct))
    _draw_linear_gradient_bar(img, (bar_x1 + 1, bar_y1 + 1, bar_x1 + fill_w, bar_y2 - 1), grad_start, grad_end, radius=7)

    # Texto dentro/acima da barra de XP
    font_xp = _get_font(13, bold=True)
    xp_text = f"{xp_in_level:,} / {xp_needed:,} XP ({int(progress_pct * 100)}%)".replace(",", ".")
    draw.text((bar_x2 - 10, bar_y1 + 8), xp_text, fill=(255, 255, 255, 255), font=font_xp, anchor="ra")

    # Chips Inferiores (Flexbox simulado)
    chips_y = 190
    chip_h = 56
    chip_x = 185
    gap = 14

    chips_data = [
        ("lightning", "TOTAL XP", f"{total_xp:,} pts".replace(",", "."), (0, 240, 255, 255)),
        ("chat", "MENSAGENS", f"{messages_count:,} msgs".replace(",", "."), (176, 38, 255, 255)),
        ("mic", "TEMPO EM VOZ", f"{hours_voice}h".replace(".", ","), (255, 215, 0, 255))
    ]

    total_available_w = 1015 - 185
    chip_w = (total_available_w - (len(chips_data) - 1) * gap) // len(chips_data)

    font_chip_title = _get_font(11, bold=True)
    font_chip_val = _get_font(17, bold=True)

    for icon_t, c_title, c_val, c_accent in chips_data:
        cx1 = chip_x
        cx2 = chip_x + chip_w
        cy1 = chips_y
        cy2 = chips_y + chip_h

        draw.rounded_rectangle((cx1, cy1, cx2, cy2), radius=10, fill=(15, 23, 42, 180), outline=(255, 255, 255, 25), width=1)
        _draw_vector_icon(draw, icon_t, cx1 + 14, cy1 + 10, c_accent, scale=1.0)
        draw.text((cx1 + 30, cy1 + 10), c_title, fill=(148, 163, 184, 255), font=font_chip_title)
        draw.text((cx1 + 14, cy1 + 28), c_val, fill=c_accent, font=font_chip_val)

        chip_x += chip_w + gap

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class RankCardBuilder:
    """Gerador visual de Rank Card / Perfil de Nível e XP com Pillow Puro e Zero Chromium."""

    async def _get_avatar_bytes(self, member: Optional[discord.Member]) -> Optional[bytes]:
        if not member:
            return None
        uid = str(member.id)
        if uid in _AVATAR_BYTES_CACHE:
            return _AVATAR_BYTES_CACHE[uid]
        try:
            asset = member.display_avatar.with_size(128)
            data = await asset.read()
            if len(_AVATAR_BYTES_CACHE) > 300:
                _AVATAR_BYTES_CACHE.clear()
            _AVATAR_BYTES_CACHE[uid] = data
            return data
        except Exception:
            return None

    async def generate_rank_card(
        self,
        member: discord.Member,
        level_data: dict,
        server_rank: int,
        messages_count: int,
        voice_minutes: int,
        guild_name: str
    ) -> BytesIO:
        avatar_bytes = await self._get_avatar_bytes(member)
        username = member.name
        display_name = member.display_name

        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            None,
            _sync_draw_rank_card,
            username,
            display_name,
            avatar_bytes,
            level_data,
            server_rank,
            messages_count,
            voice_minutes,
            guild_name
        )
        buffer = BytesIO(png_bytes)
        buffer.seek(0)
        return buffer


# =============================================================================
# =============================================================================
# 2. PODIUM BUILDER (HTML5 / PLAYWRIGHT)
# =============================================================================

class PodiumBuilder:
    """
    Gerador visual de Pódio e Ranking Periódico em alta fidelidade (1300x850)
    utilizando HTML5/CSS3 modernos (Glassmorphism, Neon Glows, Gradients e Tipografia Esports)
    renderizados via Playwright.
    """

    async def _get_avatar_data_uri(self, member: Optional[discord.Member], user_data: dict) -> str:
        """Obtém o avatar do membro em base64 data URI ou fallback SVG sofisticado com cache em memória."""
        uid = getattr(member, "id", None) or user_data.get("user_id") or user_data.get("id")
        cache_key = str(uid) if uid else None
        if cache_key and cache_key in _AVATAR_CACHE:
            return _AVATAR_CACHE[cache_key]

        try:
            if member:
                avatar_asset = member.display_avatar.with_size(128)
                avatar_bytes = await avatar_asset.read()
                b64 = base64.b64encode(avatar_bytes).decode("utf-8")
                res = f"data:image/png;base64,{b64}"
                if cache_key:
                    if len(_AVATAR_CACHE) > 500:
                        _AVATAR_CACHE.clear()
                    _AVATAR_CACHE[cache_key] = res
                return res
        except Exception:
            pass

        name = user_data.get("username") or (member.display_name if member else "M")
        initial = name[0].upper() if name else "?"
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'>
            <defs>
                <linearGradient id='grad' x1='0%' y1='0%' x2='100%' y2='100%'>
                    <stop offset='0%' stop-color='#00f0ff'/>
                    <stop offset='100%' stop-color='#b026ff'/>
                </linearGradient>
            </defs>
            <circle cx='40' cy='40' r='38' fill='#151c2e' stroke='url(#grad)' stroke-width='3'/>
            <text x='40' y='48' font-family='sans-serif' font-size='28' font-weight='bold' fill='#ffffff' text-anchor='middle'>{initial}</text>
        </svg>"""
        b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64_svg}"

    async def _get_guild_icon_data_uri(self, guild: discord.Guild) -> Optional[str]:
        """Obtém o ícone do servidor em base64 data URI com cache."""
        if not guild or not guild.icon:
            return None
        gid = getattr(guild, "id", None)
        if gid and gid in _GUILD_ICON_CACHE:
            return _GUILD_ICON_CACHE[gid]
        try:
            icon_asset = guild.icon.with_size(128)
            icon_bytes = await icon_asset.read()
            b64 = base64.b64encode(icon_bytes).decode("utf-8")
            res = f"data:image/png;base64,{b64}"
            if gid:
                _GUILD_ICON_CACHE[gid] = res
            return res
        except Exception:
            return None

    def _build_html_template(
        self,
        guild_name: str,
        guild_icon_uri: Optional[str],
        top_3_data: list,
        others_data: list,
        period_text: Optional[str] = None
    ) -> str:
        from utils.level_manager import get_level_from_xp

        period_label = period_text if period_text else "PÓDIO OFICIAL DE INTERAÇÃO"

        # Formata Top 3
        # Ordem visual do pódio: [2º Lugar, 1º Lugar, 3º Lugar]
        podium_slots = []
        
        # Mapeamento para visual: idx 0 = 2º, idx 1 = 1º, idx 2 = 3º (alturas aumentadas proporcionalmente)
        slot_configs = [
            {"rank": 2, "color": "#00f0ff", "border": "rgba(0, 240, 255, 0.5)", "pedestal_h": "235px", "badge": "2º LUGAR", "crown": "🥈", "avatar_size": "95px"},
            {"rank": 1, "color": "#ffd700", "border": "rgba(255, 215, 0, 0.6)", "pedestal_h": "300px", "badge": "1º LUGAR", "crown": "👑", "avatar_size": "115px"},
            {"rank": 3, "color": "#b026ff", "border": "rgba(176, 38, 255, 0.5)", "pedestal_h": "175px", "badge": "3º LUGAR", "crown": "🥉", "avatar_size": "85px"}
        ]

        # Monta dados do pódio
        for cfg in slot_configs:
            rank_num = cfg["rank"]
            # Encontra o usuário do ranking
            user = None
            for u in top_3_data:
                if u.get("rank") == rank_num:
                    user = u
                    break
            
            if user:
                total_xp = user.get("total_points", 0)
                lvl = get_level_from_xp(total_xp)
                podium_slots.append(f"""
                <div class="podium-column" style="order: {1 if rank_num == 2 else (2 if rank_num == 1 else 3)};">
                    <div class="avatar-wrapper">
                        <div class="crown-badge">{cfg['crown']}</div>
                        <img class="podium-avatar" src="{user['avatar_uri']}" style="width: {cfg['avatar_size']}; height: {cfg['avatar_size']}; border-color: {cfg['color']}; box-shadow: 0 0 25px {cfg['border']};" alt="{user['name']}" />
                    </div>
                    <div class="podium-user-card" style="border-top: 2px solid {cfg['color']};">
                        <div class="podium-username">{user['name']}</div>
                        <div class="podium-meta">
                            <span class="level-tag" style="border-color: {cfg['color']}; color: {cfg['color']};">Nv. {lvl}</span>
                            <span class="xp-val">{total_xp:,} XP</span>
                        </div>
                    </div>
                    <div class="pedestal" style="height: {cfg['pedestal_h']}; border-color: {cfg['border']}; background: linear-gradient(180deg, {cfg['color']}22 0%, rgba(10, 16, 30, 0.8) 100%);">
                        <div class="pedestal-rank" style="color: {cfg['color']}; text-shadow: 0 0 15px {cfg['color']};">#{rank_num}</div>
                    </div>
                </div>
                """)
            else:
                podium_slots.append(f"""
                <div class="podium-column empty" style="order: {1 if rank_num == 2 else (2 if rank_num == 1 else 3)};">
                    <div class="pedestal" style="height: {cfg['pedestal_h']}; border-color: rgba(255,255,255,0.1);">
                        <div class="pedestal-rank" style="color: rgba(255,255,255,0.2);">#{rank_num}</div>
                    </div>
                </div>
                """)

        # Formata Top 4-10
        others_html = ""
        for u in others_data:
            rank_num = u.get("rank", 4)
            total_xp = u.get("total_points", 0)
            lvl = get_level_from_xp(total_xp)
            others_html += f"""
            <div class="list-item">
                <div class="list-rank">#{rank_num}</div>
                <img class="list-avatar" src="{u['avatar_uri']}" alt="{u['name']}" />
                <div class="list-name">{u['name']}</div>
                <div class="list-level">Nv. {lvl}</div>
                <div class="list-xp">{total_xp:,} <span style="font-size: 11px; color: #94a3b8;">XP</span></div>
            </div>
            """

        guild_icon_html = f'<img src="{guild_icon_uri}" class="guild-icon" alt="Guild Icon" />' if guild_icon_uri else '<div class="guild-icon placeholder">⚔️</div>'

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Pódio Oficial</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            user-select: none;
        }}
        body {{
            width: 1300px;
            height: 850px;
            background: transparent;
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}
        .card-container {{
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #070a14 0%, #0d1527 50%, #080c18 100%);
            border: 1.5px solid rgba(0, 240, 255, 0.35);
            border-radius: 24px;
            padding: 28px 36px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            position: relative;
            box-shadow: inset 0 0 50px rgba(0, 240, 255, 0.05);
        }}
        .card-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 15%;
            right: 15%;
            height: 2px;
            background: linear-gradient(90deg, transparent, #00f0ff, #ffd700, #b026ff, transparent);
            box-shadow: 0 0 20px #00f0ff;
        }}

        /* Header */
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 14px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .guild-info {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .guild-icon {{
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: 2px solid #00f0ff;
            object-fit: cover;
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.4);
        }}
        .guild-icon.placeholder {{
            display: flex;
            align-items: center;
            justify-content: center;
            background: #1e293b;
            font-size: 24px;
        }}
        .header-titles h1 {{
            font-family: 'Orbitron', sans-serif;
            font-size: 22px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .header-titles p {{
            font-size: 15px;
            color: #94a3b8;
            font-weight: 600;
        }}
        .period-badge {{
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 1px;
            padding: 6px 16px;
            background: rgba(0, 240, 255, 0.08);
            border: 1.5px solid rgba(0, 240, 255, 0.4);
            border-radius: 12px;
            color: #00f0ff;
            box-shadow: 0 0 15px rgba(0, 240, 255, 0.15);
        }}

        /* Main Content Grid */
        .content-area {{
            flex: 1;
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 28px;
            align-items: center;
        }}

        /* Podium Stage */
        .podium-stage {{
            height: 100%;
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 16px;
            padding-bottom: 10px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 18px;
            padding: 20px 16px;
        }}
        .podium-column {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }}
        .avatar-wrapper {{
            position: relative;
            display: flex;
            justify-content: center;
        }}
        .crown-badge {{
            position: absolute;
            top: -16px;
            font-size: 24px;
            z-index: 2;
            filter: drop-shadow(0 0 8px rgba(255, 215, 0, 0.6));
        }}
        .podium-avatar {{
            border-radius: 50%;
            object-fit: cover;
            background: #0f172a;
            border-width: 3px;
            border-style: solid;
        }}
        .podium-user-card {{
            width: 100%;
            text-align: center;
            background: rgba(15, 23, 42, 0.9);
            border-radius: 10px;
            padding: 6px 4px;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        .podium-username {{
            font-size: 16px;
            font-weight: 800;
            color: #ffffff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .podium-meta {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }}
        .level-tag {{
            font-family: 'Orbitron', sans-serif;
            font-size: 11px;
            font-weight: 800;
            padding: 1px 6px;
            background: rgba(0,0,0,0.4);
            border: 1px solid;
            border-radius: 6px;
        }}
        .xp-val {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 14px;
            font-weight: 700;
            color: #cbd5e1;
        }}
        .pedestal {{
            width: 100%;
            border-radius: 12px 12px 0 0;
            border-width: 2px 2px 0 2px;
            border-style: solid;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .pedestal-rank {{
            font-family: 'Orbitron', sans-serif;
            font-size: 32px;
            font-weight: 900;
        }}

        /* List Top 4-10 */
        .list-section {{
            height: 100%;
            display: flex;
            flex-direction: column;
            gap: 8px;
            justify-content: center;
        }}
        .list-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 800;
            color: #94a3b8;
            letter-spacing: 1px;
            margin-bottom: 2px;
        }}
        .list-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.07);
            border-radius: 10px;
            padding: 7px 14px;
            transition: all 0.2s;
        }}
        .list-rank {{
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 800;
            color: #00f0ff;
            min-width: 26px;
        }}
        .list-avatar {{
            width: 34px;
            height: 34px;
            border-radius: 50%;
            object-fit: cover;
            background: #0f172a;
            border: 1.5px solid rgba(255, 255, 255, 0.2);
        }}
        .list-name {{
            flex: 1;
            font-size: 16px;
            font-weight: 700;
            color: #f1f5f9;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .list-level {{
            font-family: 'Orbitron', sans-serif;
            font-size: 11px;
            font-weight: 800;
            color: #b026ff;
            background: rgba(176, 38, 255, 0.1);
            border: 1px solid rgba(176, 38, 255, 0.3);
            border-radius: 6px;
            padding: 2px 6px;
        }}
        .list-xp {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 15px;
            font-weight: 800;
            color: #ffd700;
            min-width: 75px;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="header">
            <div class="guild-info">
                {guild_icon_html}
                <div class="header-titles">
                    <h1>{guild_name}</h1>
                    <p>Membros com maior destaque e atividade</p>
                </div>
            </div>
            <div class="period-badge">{period_label}</div>
        </div>

        <div class="content-area">
            <div class="podium-stage">
                {''.join(podium_slots)}
            </div>
            <div class="list-section">
                <div class="list-title">HONORABLE MENTIONS (TOP 4 - 10)</div>
                {others_html if others_html else '<div style="color: #64748b; font-size: 14px; padding: 10px;">Sem mais participantes no período.</div>'}
            </div>
        </div>
    </div>
</body>
</html>"""

    async def generate_podium(self, guild: discord.Guild, top_users: list, period_text: str = None) -> BytesIO:
        """
        Gera uma imagem moderna de pódio com os top 10 usuários (3 no pódio + 7 em lista)
        via Playwright 1300x850 com carregamento paralelo e domcontentloaded.
        """
        from playwright.async_api import async_playwright

        guild_name = guild.name if guild else "Servidor BMIA"
        
        # Carrega guild icon e avatares concorrentemente
        top_list = top_users[:10]
        avatar_tasks = []
        for u in top_list:
            uid = u.get("user_id", 0)
            m = guild.get_member(uid) if guild else None
            avatar_tasks.append(self._get_avatar_data_uri(m, u))

        icon_task = self._get_guild_icon_data_uri(guild)
        results = await asyncio.gather(icon_task, *avatar_tasks, return_exceptions=True)
        
        guild_icon_uri = results[0] if isinstance(results[0], (str, type(None))) else None
        avatar_uris = results[1:]

        top_3 = []
        others = []

        for i, user_data in enumerate(top_list):
            uid = user_data.get("user_id", 0)
            member = guild.get_member(uid) if guild else None
            raw_uri = avatar_uris[i] if i < len(avatar_uris) else None
            avatar_uri = raw_uri if isinstance(raw_uri, str) else await self._get_avatar_data_uri(None, user_data)
            display_name = member.display_name if member else user_data.get("username", "Membro")

            item = {
                "rank": i + 1,
                "user_id": uid,
                "name": display_name,
                "total_points": user_data.get("total_points", 0),
                "avatar_uri": avatar_uri
            }

            if i < 3:
                top_3.append(item)
            else:
                others.append(item)

        # 1. Tenta delegar a renderização para a Vercel Serverless (0 MB de RAM na VPS)
        remote_payload = {
            "guild_name": guild_name,
            "period_text": period_text,
            "guild_icon_uri": guild_icon_uri,
            "top_3_data": top_3,
            "others_data": others
        }
        remote_buf = await fetch_image_from_dashboard("podium", remote_payload)
        if remote_buf is not None:
            return remote_buf

        # 2. Fallback Local via Playwright se a Vercel estiver offline/não configurada
        html_code = self._build_html_template(
            guild_name=guild_name,
            guild_icon_uri=guild_icon_uri,
            top_3_data=top_3,
            others_data=others,
            period_text=period_text
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})
            await page.set_content(html_code, wait_until="domcontentloaded")
            element = await page.query_selector('.card-container')
            if element:
                screenshot_bytes = await element.screenshot(type="png", omit_background=True)
            else:
                screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer


# =============================================================================
# 3. BRACKET BUILDER (1920x1080 - PIL PURO)
# =============================================================================

def _sync_draw_bracket(
    tournament: dict,
    participants: List[dict],
    teams_data: List[List[dict]],
    bracket_mode: int,
    is_2v2: bool,
    matches: Optional[List[dict]] = None
) -> bytes:
    img = Image.new("RGBA", (1920, 1080), (6, 9, 18, 255))
    draw = ImageDraw.Draw(img)

    # Topo Neon Bar
    _draw_linear_gradient_bar(img, (0, 0, 1920, 6), (0, 240, 255), (255, 215, 0), radius=0)

    # Cabeçalho
    title = str(tournament.get("name", "TORNEIO OFICIAL")).upper()
    game = str(tournament.get("game_name", "Geral")).upper()
    fmt_raw = str(tournament.get("format", "1v1")).upper()
    prize = str(tournament.get("prize") or "Glória e Pontos")
    max_participants = int(tournament.get("max_participants") or 16)
    winner_id = tournament.get("winner_id")

    font_title = _get_font(30, bold=True)
    font_meta = _get_font(15, bold=True)
    font_badge = _get_font(16, bold=True)

    draw.text((70, 45), title, fill=(255, 255, 255, 255), font=font_title)

    # Meta Pills
    meta_pills = [
        f"🎮 JOGO: {game}",
        f"⚔️ FORMATO: {fmt_raw}",
        f"🎁 PRÊMIO: {prize}",
        f"👥 INSCRITOS: {len(participants)}/{max_participants}"
    ]
    mx = 70
    my = 88
    for mp in meta_pills:
        mw = int(draw.textlength(mp, font=font_meta)) + 24
        draw.rounded_rectangle((mx, my, mx + mw, my + 28), radius=6, fill=(255, 255, 255, 12), outline=(0, 240, 255, 80), width=1)
        draw.text((mx + 12, my + 5), mp, fill=(0, 240, 255, 255), font=font_meta)
        mx += mw + 14

    # Status Badge
    status_text = "● TORNEIO CONCLUÍDO" if winner_id else "● CHAVEAMENTO OFICIAL"
    badge_c = (255, 215, 0, 255) if winner_id else (0, 240, 255, 255)
    bw = int(draw.textlength(status_text, font=font_badge)) + 30
    draw.rounded_rectangle((1850 - bw, 52, 1850, 88), radius=18, fill=(14, 20, 36, 240), outline=badge_c, width=2)
    draw.text((1850 - (bw // 2), 70), status_text, fill=badge_c, font=font_badge, anchor="mm")

    # Linha divisória do cabeçalho
    draw.line((70, 130, 1850, 130), fill=(255, 255, 255, 20), width=1)

    # Mapa de Partidas
    matches_by_num = {m["match_number"]: m for m in (matches or [])}

    # =========================================================================
    # FUNÇÃO INTERNA PARA DESENHAR UMA MATCH BOX (CONFRONTO)
    # =========================================================================
    def draw_match_box(
        center_x: int,
        center_y: int,
        width: int,
        height: int,
        match_num: int,
        fallback_a: str = "Time A",
        fallback_b: str = "Time B",
        is_final: bool = False
    ):
        m = matches_by_num.get(match_num)
        team_a_ids = m.get("team_a_ids") if m else None
        team_b_ids = m.get("team_b_ids") if m else None
        is_done = bool(m and m.get("status") == "completed")
        score_a = m.get("score_a") if (m and is_done) else None
        score_b = m.get("score_b") if (m and is_done) else None
        winner_ids = m.get("winner_team_ids") if m else []

        # Resolve nomes e avatares
        p_map = {p.get("user_id"): p for team in teams_data for p in team}

        def get_team_info(t_ids, fallback):
            if not t_ids:
                return fallback, None
            names = [p_map[uid]["name"] for uid in t_ids if uid in p_map]
            avs = [p_map[uid].get("avatar_bytes") for uid in t_ids if uid in p_map and p_map[uid].get("avatar_bytes")]
            return (" & ".join(names) if names else fallback), (avs[0] if avs else None)

        name_a, av_a = get_team_info(team_a_ids, fallback_a)
        name_b, av_b = get_team_info(team_b_ids, fallback_b)

        a_win = is_done and bool(winner_ids and team_a_ids == winner_ids)
        b_win = is_done and bool(winner_ids and team_b_ids == winner_ids)

        x1 = center_x - (width // 2)
        y1 = center_y - (height // 2)
        x2 = center_x + (width // 2)
        y2 = center_y + (height // 2)

        # Borda com Glow para a final ou completada
        box_border = (255, 215, 0, 220) if (is_final or is_done) else (0, 240, 255, 90)
        box_glow = (255, 215, 0, 80) if is_final else (0, 240, 255, 40)
        _draw_glow_rect(img, (x1, y1, x2, y2), radius=12, glow_color=box_glow, glow_radius=6, fill_color=(15, 23, 42, 235), outline_color=box_border, outline_width=2)

        # Divisor interno
        mid_y = (y1 + y2) // 2
        draw.line((x1 + 6, mid_y, x2 - 6, mid_y), fill=(255, 255, 255, 25), width=1)

        # Participante A
        av_sz = 30 if is_final else 24
        f_name = _get_font(16 if is_final else 14, bold=True)
        f_score = _get_font(15 if is_final else 13, bold=True)

        row_a_y = y1 + (height // 4)
        _draw_circle_avatar(img, av_a, (x1 + 18, row_a_y), size=av_sz, border_color=(255, 215, 0, 255) if a_win else (0, 240, 255, 180), border_width=2, fallback_initial=name_a[0])
        draw.text((x1 + 38 + (av_sz // 2), row_a_y), name_a[:16], fill=(255, 215, 0, 255) if a_win else (255, 255, 255, 255), font=f_name, anchor="lm")
        if score_a is not None:
            draw.rounded_rectangle((x2 - 38, row_a_y - 12, x2 - 10, row_a_y + 12), radius=4, fill=(255, 215, 0, 60) if a_win else (255, 255, 255, 20), outline=(255, 215, 0, 180) if a_win else (255, 255, 255, 40), width=1)
            draw.text((x2 - 24, row_a_y), str(score_a), fill=(255, 215, 0, 255) if a_win else (255, 255, 255, 255), font=f_score, anchor="mm")

        # Participante B
        row_b_y = mid_y + (height // 4)
        _draw_circle_avatar(img, av_b, (x1 + 18, row_b_y), size=av_sz, border_color=(255, 215, 0, 255) if b_win else (0, 240, 255, 180), border_width=2, fallback_initial=name_b[0])
        draw.text((x1 + 38 + (av_sz // 2), row_b_y), name_b[:16], fill=(255, 215, 0, 255) if b_win else (255, 255, 255, 255), font=f_name, anchor="lm")
        if score_b is not None:
            draw.rounded_rectangle((x2 - 38, row_b_y - 12, x2 - 10, row_b_y + 12), radius=4, fill=(255, 215, 0, 60) if b_win else (255, 255, 255, 20), outline=(255, 215, 0, 180) if b_win else (255, 255, 255, 40), width=1)
            draw.text((x2 - 24, row_b_y), str(score_b), fill=(255, 215, 0, 255) if b_win else (255, 255, 255, 255), font=f_score, anchor="mm")

    # =========================================================================
    # TROPHY CARD NO TOPO CENTRAL
    # =========================================================================
    w_label = "A DEFINIR..."
    if winner_id:
        p_map_all = {p.get("user_id"): p for team in teams_data for p in team}
        if str(winner_id) in p_map_all or winner_id in p_map_all:
            w_label = p_map_all.get(str(winner_id), p_map_all.get(winner_id, {})).get("name", "Campeão")
        elif tournament.get("winner_name"):
            w_label = tournament["winner_name"]

    _draw_glow_rect(img, (780, 155, 1140, 240), radius=16, glow_color=(255, 215, 0, 110), glow_radius=12, fill_color=(35, 28, 10, 245), outline_color=(255, 215, 0, 255), outline_width=2)
    font_tr_title = _get_font(13, bold=True)
    font_tr_win = _get_font(24, bold=True)
    _draw_vector_icon(draw, "trophy", 805, 178, (255, 215, 0, 255), scale=2.6)
    draw.text((860, 178), "CAMPEÃO DO TORNEIO", fill=(255, 215, 0, 255), font=font_tr_title)
    draw.text((860, 208), w_label[:20], fill=(255, 255, 255, 255), font=font_tr_win)

    # =========================================================================
    # RENDERIZAÇÃO DA ÁRVORE 16 TIMES (OU MODOS ADAPTADOS)
    # =========================================================================
    font_col_h = _get_font(14, bold=True)

    if bracket_mode == 16:
        # Colunas X:
        x_oit_l, x_qua_l, x_sem_l, x_fin, x_sem_r, x_qua_r, x_oit_r = 180, 420, 660, 960, 1260, 1500, 1740
        w_box, h_box = 210, 68

        # Títulos das Colunas
        for cx, lbl in [(x_oit_l, "OITAVAS"), (x_qua_l, "QUARTAS"), (x_sem_l, "SEMIFINAIS"), (x_fin, "★ GRANDE FINAL ★"), (x_sem_r, "SEMIFINAIS"), (x_qua_r, "QUARTAS"), (x_oit_r, "OITAVAS")]:
            draw.text((cx, 280), lbl, fill=(255, 215, 0, 255) if "FINAL" in lbl else (148, 163, 184, 255), font=font_col_h, anchor="mm")

        # Y positions Oitavas (8 jogos)
        y_oit = [350, 435, 535, 620, 720, 805, 905, 990]
        # Y positions Quartas (4 jogos)
        y_qua = [(y_oit[0] + y_oit[1]) // 2, (y_oit[2] + y_oit[3]) // 2, (y_oit[4] + y_oit[5]) // 2, (y_oit[6] + y_oit[7]) // 2]
        # Y positions Semis (2 jogos)
        y_sem = [(y_qua[0] + y_qua[1]) // 2, (y_qua[2] + y_qua[3]) // 2]
        # Y position Final (1 jogo)
        y_fin = (y_sem[0] + y_sem[1]) // 2

        line_c = (0, 240, 255, 100)

        # Conexões Linhas: Oitavas -> Quartas (Esquerda)
        for i in range(2):
            yo1, yo2 = y_oit[i*2], y_oit[i*2+1]
            yq = y_qua[i]
            draw.line((x_oit_l + (w_box//2), yo1, x_oit_l + (w_box//2) + 15, yo1), fill=line_c, width=2)
            draw.line((x_oit_l + (w_box//2), yo2, x_oit_l + (w_box//2) + 15, yo2), fill=line_c, width=2)
            draw.line((x_oit_l + (w_box//2) + 15, yo1, x_oit_l + (w_box//2) + 15, yo2), fill=line_c, width=2)
            draw.line((x_oit_l + (w_box//2) + 15, yq, x_qua_l - (w_box//2), yq), fill=line_c, width=2)

        # Conexões Linhas: Quartas -> Semis (Esquerda)
        yq1, yq2 = y_qua[0], y_qua[1]
        draw.line((x_qua_l + (w_box//2), yq1, x_qua_l + (w_box//2) + 15, yq1), fill=line_c, width=2)
        draw.line((x_qua_l + (w_box//2), yq2, x_qua_l + (w_box//2) + 15, yq2), fill=line_c, width=2)
        draw.line((x_qua_l + (w_box//2) + 15, yq1, x_qua_l + (w_box//2) + 15, yq2), fill=line_c, width=2)
        draw.line((x_qua_l + (w_box//2) + 15, y_sem[0], x_sem_l - (w_box//2), y_sem[0]), fill=line_c, width=2)

        # Conexões Linhas: Semis -> Final (Esquerda)
        draw.line((x_sem_l + (w_box//2), y_sem[0], x_fin - 150, y_fin), fill=line_c, width=2)

        # Conexões Linhas: Final <- Semis (Direita)
        draw.line((x_fin + 150, y_fin, x_sem_r - (w_box//2), y_sem[1]), fill=line_c, width=2)

        # Conexões Linhas: Semis <- Quartas (Direita)
        yq3, yq4 = y_qua[2], y_qua[3]
        draw.line((x_qua_r - (w_box//2), yq3, x_qua_r - (w_box//2) - 15, yq3), fill=line_c, width=2)
        draw.line((x_qua_r - (w_box//2), yq4, x_qua_r - (w_box//2) - 15, yq4), fill=line_c, width=2)
        draw.line((x_qua_r - (w_box//2) - 15, yq3, x_qua_r - (w_box//2) - 15, yq4), fill=line_c, width=2)
        draw.line((x_qua_r - (w_box//2) - 15, y_sem[1], x_sem_r + (w_box//2), y_sem[1]), fill=line_c, width=2)

        # Conexões Linhas: Quartas <- Oitavas (Direita)
        for i in range(2):
            yo1, yo2 = y_oit[4 + i*2], y_oit[4 + i*2+1]
            yq = y_qua[2 + i]
            draw.line((x_oit_r - (w_box//2), yo1, x_oit_r - (w_box//2) - 15, yo1), fill=line_c, width=2)
            draw.line((x_oit_r - (w_box//2), yo2, x_oit_r - (w_box//2) - 15, yo2), fill=line_c, width=2)
            draw.line((x_oit_r - (w_box//2) - 15, yo1, x_oit_r - (w_box//2) - 15, yo2), fill=line_c, width=2)
            draw.line((x_oit_r - (w_box//2) - 15, yq, x_qua_r + (w_box//2), yq), fill=line_c, width=2)

        # Desenha Caixas de Partidas:
        # Oitavas Esquerda (1..4)
        for idx, m_num in enumerate([1, 2, 3, 4]):
            draw_match_box(x_oit_l, y_oit[idx], w_box, h_box, m_num, f"Time {idx*2+1}", f"Time {idx*2+2}")
        # Quartas Esquerda (9, 10)
        draw_match_box(x_qua_l, y_qua[0], w_box, h_box, 9, "Venc. O1", "Venc. O2")
        draw_match_box(x_qua_l, y_qua[1], w_box, h_box, 10, "Venc. O3", "Venc. O4")
        # Semis Esquerda (13)
        draw_match_box(x_sem_l, y_sem[0], w_box, h_box, 13, "Venc. Q1", "Venc. Q2")

        # GRANDE FINAL (15)
        draw_match_box(x_fin, y_fin, 300, 84, 15, "Finalista 1", "Finalista 2", is_final=True)

        # Semis Direita (14)
        draw_match_box(x_sem_r, y_sem[1], w_box, h_box, 14, "Venc. Q3", "Venc. Q4")
        # Quartas Direita (11, 12)
        draw_match_box(x_qua_r, y_qua[2], w_box, h_box, 11, "Venc. O5", "Venc. O6")
        draw_match_box(x_qua_r, y_qua[3], w_box, h_box, 12, "Venc. O7", "Venc. O8")
        # Oitavas Direita (5..8)
        for idx, m_num in enumerate([5, 6, 7, 8]):
            draw_match_box(x_oit_r, y_oit[4 + idx], w_box, h_box, m_num, f"Time {8 + idx*2+1}", f"Time {8 + idx*2+2}")

    else:
        # Modo Showdown / 2, 4 ou 8 Times Genérico
        x_left, x_center, x_right = 400, 960, 1520
        y_mid = 580
        draw_match_box(x_left, y_mid, 260, 80, 1, "Time 1", "Time 2")
        draw_match_box(x_center, y_mid, 320, 90, 3 if bracket_mode == 4 else (7 if bracket_mode == 8 else 1), "Finalista 1", "Finalista 2", is_final=True)
        draw_match_box(x_right, y_mid, 260, 80, 2, "Time 3", "Time 4")

        draw.line((x_left + 130, y_mid, x_center - 160, y_mid), fill=(0, 240, 255, 120), width=2)
        draw.line((x_center + 160, y_mid, x_right - 130, y_mid), fill=(0, 240, 255, 120), width=2)

    # Rodapé
    font_footer = _get_font(13, bold=False)
    draw.text((70, 1045), "⚡ Gerado automaticamente pelo sistema BMIA Esports • Use /torneio status", fill=(100, 116, 139, 255), font=font_footer)
    draw.text((1850, 1045), "BDP COMMUNITY • 2026", fill=(0, 240, 255, 255), font=font_footer, anchor="ra")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class BracketBuilder:
    """Gerador visual de Chaveamento de Torneios (1920x1080) em Pillow Puro com Cache."""

    async def _get_avatar_bytes(self, member: Optional[discord.Member], user_data: dict) -> Optional[bytes]:
        uid = str(getattr(member, "id", None) or user_data.get("user_id") or user_data.get("id"))
        if uid in _AVATAR_BYTES_CACHE:
            return _AVATAR_BYTES_CACHE[uid]
        if member:
            try:
                data = await member.display_avatar.with_size(128).read()
                _AVATAR_BYTES_CACHE[uid] = data
                return data
            except Exception:
                pass
        return None

    async def generate_bracket(
        self,
        guild: discord.Guild,
        tournament: dict,
        participants: List[dict],
        matches: Optional[List[dict]] = None,
        use_cache: bool = True
    ) -> BytesIO:
        t_id = tournament.get("id", 0)
        state_hash = _get_tournament_state_hash(tournament, participants, matches)
        prefix = f"bracket_{t_id}"

        if use_cache:
            cached_buf = _read_cached_image(prefix, state_hash)
            if cached_buf is not None:
                return cached_buf

        fmt_raw = str(tournament.get("format", "1v1")).lower().strip()
        is_2v2 = any(k in fmt_raw for k in ["2v2", "2x2", "dupla", "duplas"])
        is_3v3 = any(k in fmt_raw for k in ["3v3", "3x3", "trio", "trios"])
        team_size = 2 if is_2v2 else (3 if is_3v3 else 1)

        if matches and len(matches) > 0:
            if len(matches) == 1:
                bracket_mode = 2
            elif len(matches) <= 3:
                bracket_mode = 4
            elif len(matches) <= 7:
                bracket_mode = 8
            elif len(matches) <= 15:
                bracket_mode = 16
            else:
                bracket_mode = 32
        else:
            max_participants = int(tournament.get("max_participants") or 16)
            num_teams_target = max(2, max_participants // team_size)
            if num_teams_target <= 2:
                bracket_mode = 2
            elif num_teams_target <= 4:
                bracket_mode = 4
            elif num_teams_target <= 8:
                bracket_mode = 8
            elif num_teams_target <= 16:
                bracket_mode = 16
            else:
                bracket_mode = 32

        avatar_tasks = []
        for p in participants:
            m = guild.get_member(p.get("user_id", 0)) if guild else None
            avatar_tasks.append(self._get_avatar_bytes(m, p))

        avatar_bytes_list = await asyncio.gather(*avatar_tasks, return_exceptions=True)

        participant_map = {}
        for idx, p in enumerate(participants):
            uid = p.get("user_id", 0)
            m = guild.get_member(uid) if guild else None
            raw_name = m.display_name if (m and hasattr(m, "display_name") and not str(type(m.display_name)).endswith("MagicMock'>")) else (p.get("username") or "Jogador")
            av_data = avatar_bytes_list[idx] if (idx < len(avatar_bytes_list) and isinstance(avatar_bytes_list[idx], bytes)) else None
            participant_map[uid] = {"name": str(raw_name), "avatar_bytes": av_data, "user_id": uid}

        teams_data = []
        for i in range(0, len(participants), team_size):
            chunk = participants[i:i + team_size]
            team_members = [participant_map[p.get("user_id", 0)] for p in chunk if p.get("user_id", 0) in participant_map]
            teams_data.append(team_members)

        while len(teams_data) < bracket_mode:
            teams_data.append([])

        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            None,
            _sync_draw_bracket,
            tournament,
            participants,
            teams_data,
            bracket_mode,
            is_2v2,
            matches
        )

        _save_cached_image(prefix, state_hash, png_bytes)
        buffer = BytesIO(png_bytes)
        buffer.seek(0)
        return buffer


# =============================================================================
# 4. LEAGUE TABLE BUILDER (1920x1080 - PIL PURO)
# =============================================================================

def _sync_draw_league_table(
    tournament: dict,
    standings: List[dict],
    avatar_data_map: Optional[Dict[str, bytes]] = None,
    winner_ids: Optional[List[int]] = None,
) -> bytes:
    """
    Renderiza a tabela de classificação (Pontos Corridos) em Pillow puro.

    Args:
        tournament: dicionário do torneio.
        standings: lista ordenada de classificação — chaves esperadas:
                   points, wins, draws, losses, goal_diff / score_diff.
        avatar_data_map: dict {user_id_str: bytes} com dados PNG/JPG do avatar.
        winner_ids: lista de user_ids do vencedor (para highlight de campeão).
    """
    img = Image.new("RGBA", (1920, 1080), (6, 9, 18, 255))
    draw = ImageDraw.Draw(img)

    _draw_linear_gradient_bar(img, (0, 0, 1920, 6), (0, 240, 255), (255, 215, 0), radius=0)

    title = str(tournament.get("name", "TABELA DA LIGA")).upper()
    game = str(tournament.get("game_name", "Geral")).upper()
    prize = str(tournament.get("prize") or "Glória e Pontos")
    is_final = bool(winner_ids)  # Torneio encerrado?

    font_title = _get_font(30, bold=True)
    font_sub = _get_font(15, bold=False)
    title_suffix = " — 🏆 ENCERRADO" if is_final else ""
    draw.text((70, 45), f"⚡ TABELA DE CLASSIFICAÇÃO — {title}{title_suffix}", fill=(255, 255, 255, 255), font=font_title)
    draw.text((70, 85), f"JOGO: {game} • PREMIAÇÃO: {prize} • PONTOS CORRIDOS".upper(), fill=(0, 240, 255, 255), font=font_sub)

    # Container da Tabela
    t_x1, t_y1, t_x2, t_y2 = 70, 130, 1850, 1010
    _draw_glow_rect(img, (t_x1, t_y1, t_x2, t_y2), radius=16, glow_color=(0, 240, 255, 60), glow_radius=8, fill_color=(12, 18, 34, 230), outline_color=(0, 240, 255, 120), width=2)

    # Cabeçalho da Tabela
    headers = [("POS", 140), ("PARTICIPANTE / EQUIPE", 520), ("PTS", 1000), ("V", 1150), ("E", 1300), ("D", 1450), ("SG", 1600), ("STATUS", 1750)]
    font_th = _get_font(14, bold=True)
    for h_name, h_x in headers:
        draw.text((h_x, 160), h_name, fill=(0, 240, 255, 255), font=font_th, anchor="mm")

    draw.line((t_x1 + 20, 185, t_x2 - 20, 185), fill=(255, 255, 255, 25), width=1)

    # Linhas da Classificação
    row_y = 200
    row_h = 58
    font_tr_bold = _get_font(16, bold=True)
    font_tr_regular = _get_font(15, bold=False)
    avatar_size = row_h - 14  # ~44px

    winner_id_set: set = set(int(x) for x in (winner_ids or []))

    # Fallback: se o torneio está encerrado mas winner_ids não bate com nenhuma
    # entrada das standings (ex: admin especificou membro real, mas o torneio
    # tinha bots fictícios), destaca o 1º colocado como campeão por posição.
    if is_final and winner_id_set and standings:
        any_match = any(
            bool(set(int(x) for x in (s.get("team_ids") or [])) & winner_id_set)
            for s in standings
        )
        if not any_match:
            # Nenhum match de ID — usa team_ids do líder como vencedor
            leader_ids = standings[0].get("team_ids") or []
            winner_id_set = set(int(x) for x in leader_ids)

    # Também destaca por posição quando is_final=True e winner_ids não foi fornecido
    highlight_rank_one = is_final and not winner_id_set

    for idx, s in enumerate(standings[:12]):
        ry1 = row_y + (idx * row_h)
        ry2 = ry1 + row_h - 8
        rx1 = t_x1 + 16
        rx2 = t_x2 - 16

        pos = idx + 1
        pos_color = (255, 215, 0, 255) if pos == 1 else ((148, 163, 184, 255) if pos == 2 else ((205, 127, 50, 255) if pos == 3 else (255, 255, 255, 255)))

        # Verifica se esta equipe é a vencedora
        team_ids_raw = s.get("team_ids", [])
        is_champion = is_final and (
            # Critério primário: IDs do vencedor batem com team_ids
            (bool(winner_id_set) and bool(set(int(x) for x in team_ids_raw) & winner_id_set))
            # Fallback: torna o 1º colocado campeão quando não há match de IDs
            or (highlight_rank_one and idx == 0)
        )

        # Fundo da linha — dourado para campeão
        if is_champion:
            draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=8, fill=(40, 32, 8, 230), outline=(255, 215, 0, 200), width=2)
        else:
            draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=8, fill=(18, 26, 48, 200) if idx % 2 == 0 else (14, 20, 38, 200), outline=(255, 255, 255, 15), width=1)

        row_mid_y = (ry1 + ry2) // 2

        # Pos + troféu para campeão
        if is_champion:
            draw.text((140, row_mid_y), "🏆", fill=(255, 215, 0, 255), font=font_tr_bold, anchor="mm")
        else:
            draw.text((140, row_mid_y), f"#{pos:02d}", fill=pos_color, font=font_tr_bold, anchor="mm")

        # Avatar circular
        av_x_left = 195
        avatar_drawn = False
        if avatar_data_map:
            # Tenta primeiro membro da equipe
            for uid in (s.get("team_ids") or []):
                av_bytes = avatar_data_map.get(str(uid))
                if av_bytes:
                    try:
                        av_img = Image.open(BytesIO(av_bytes)).convert("RGBA").resize((avatar_size, avatar_size), Image.LANCZOS)
                        # Máscara circular
                        mask = Image.new("L", (avatar_size, avatar_size), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
                        av_pos = (av_x_left, row_mid_y - avatar_size // 2)
                        img.paste(av_img, av_pos, mask)
                        # Borda circular dourada p/ campeão, branca suave para os demais
                        border_color = (255, 215, 0, 255) if is_champion else (255, 255, 255, 60)
                        draw.ellipse(
                            (av_pos[0] - 2, av_pos[1] - 2, av_pos[0] + avatar_size + 1, av_pos[1] + avatar_size + 1),
                            outline=border_color, width=2
                        )
                        avatar_drawn = True
                    except Exception:
                        pass
                    break

        # Nome — desloca para direita se avatar foi desenhado
        name_x = av_x_left + avatar_size + 10 if avatar_drawn else 320
        t_name = s.get("team_name") or (" & ".join([m.get("username", "Jogador") for m in s.get("members", [])]) if s.get("members") else "Time")
        name_color = (255, 215, 0, 255) if is_champion else (255, 255, 255, 255)
        draw.text((name_x, row_mid_y), t_name[:24], fill=name_color, font=font_tr_bold, anchor="lm")

        # Stats — chaves corretas retornadas pelo get_tournament_standings
        # DB salva: won, drawn, lost → standings retorna: wins, draws, losses
        wins_val   = s.get("wins",   s.get("won",   0))
        draws_val  = s.get("draws",  s.get("drawn", 0))
        losses_val = s.get("losses", s.get("lost",  0))
        sg_val     = s.get("score_diff", s.get("goal_diff", 0))

        draw.text((1000, row_mid_y), str(s.get("points", 0)), fill=(255, 215, 0, 255), font=font_tr_bold, anchor="mm")
        draw.text((1150, row_mid_y), str(wins_val),   fill=(100, 255, 130, 255) if wins_val   else (255, 255, 255, 200), font=font_tr_regular, anchor="mm")
        draw.text((1300, row_mid_y), str(draws_val),  fill=(255, 200, 60,  255) if draws_val  else (255, 255, 255, 200), font=font_tr_regular, anchor="mm")
        draw.text((1450, row_mid_y), str(losses_val), fill=(255, 90,  90,  255) if losses_val else (255, 255, 255, 200), font=font_tr_regular, anchor="mm")
        sg_color = (100, 255, 130, 255) if sg_val > 0 else ((255, 90, 90, 255) if sg_val < 0 else (255, 255, 255, 200))
        draw.text((1600, row_mid_y), (f"+{sg_val}" if sg_val > 0 else str(sg_val)), fill=sg_color, font=font_tr_regular, anchor="mm")

        # Status Pill
        if is_champion:
            st_lbl = "CAMPEÃO"
            st_color = (255, 215, 0, 255)
        elif pos == 1:
            st_lbl, st_color = "LÍDER", (255, 215, 0, 255)
        elif pos <= 4:
            st_lbl, st_color = "G4", pos_color
        else:
            st_lbl, st_color = "-", (148, 163, 184, 255)
        draw.text((1750, row_mid_y), st_lbl, fill=st_color, font=font_tr_bold, anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class LeagueTableBuilder:
    """Gerador visual de Tabela de Liga / Pontos Corridos em Pillow Puro com Cache."""

    async def _get_avatar_bytes(self, member: Optional[discord.Member], user_data: dict) -> Optional[bytes]:
        """Busca os bytes do avatar do membro, com cache em memória."""
        uid = str(getattr(member, "id", None) or user_data.get("user_id") or user_data.get("id"))
        if uid in _AVATAR_BYTES_CACHE:
            return _AVATAR_BYTES_CACHE[uid]
        if member:
            try:
                data = await member.display_avatar.with_size(128).read()
                if len(_AVATAR_BYTES_CACHE) > 300:
                    _AVATAR_BYTES_CACHE.clear()
                _AVATAR_BYTES_CACHE[uid] = data
                return data
            except Exception:
                pass
        return None

    async def generate_table(
        self,
        guild: discord.Guild,
        tournament: dict,
        standings: List[dict],
        matches: Optional[List[dict]] = None,
        winner_ids: Optional[List[int]] = None,
        use_cache: bool = True
    ) -> BytesIO:
        """
        Gera a imagem da tabela de classificação.

        Args:
            winner_ids: lista de user_ids do(s) vencedor(es) para highlight de campeão.
                        Deve ser passado apenas ao encerrar o torneio.
        """
        t_id = tournament.get("id", 0)
        state_hash = _get_league_state_hash(tournament, standings, matches)
        prefix = f"table_{t_id}"

        # Cache hit apenas se não for encerramento (winner_ids muda o visual)
        if use_cache and not winner_ids:
            cached_buf = _read_cached_image(prefix, state_hash)
            if cached_buf is not None:
                return cached_buf

        # Busca avatares de forma assíncrona (todos em paralelo)
        avatar_data_map: Dict[str, bytes] = {}
        all_members: List[dict] = []
        for s in standings:
            for uid in (s.get("team_ids") or []):
                # Monta um user_data mínimo compatível com _get_avatar_bytes
                all_members.append({"user_id": uid})

        if guild and all_members:
            tasks = []
            for ud in all_members:
                member = guild.get_member(ud["user_id"]) if guild else None
                tasks.append(self._get_avatar_bytes(member, ud))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for ud, result in zip(all_members, results):
                if isinstance(result, bytes):
                    avatar_data_map[str(ud["user_id"])] = result

        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            None,
            _sync_draw_league_table,
            tournament,
            standings,
            avatar_data_map or None,
            winner_ids or None,
        )

        if not winner_ids:
            _save_cached_image(prefix, state_hash, png_bytes)
        buffer = BytesIO(png_bytes)
        buffer.seek(0)
        return buffer


# =============================================================================
class HighlightsBuilder:
    """
    Construtor e renderizador de alta performance para os slides visuais da Retrospectiva Anual / Destaques do Ano.
    Utiliza reaproveitamento de processo do Playwright Chromium para renderizar 13 slides em ~2 segundos com apenas ~80MB de RAM.
    """

    @classmethod
    async def _fetch_avatar_data_uri(cls, avatar_url: Optional[str], fallback_name: str = "User") -> str:
        initials = (fallback_name[:2] if len(fallback_name) >= 2 else (fallback_name + "U")).upper()
        default_svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'>
            <defs>
                <linearGradient id='grad' x1='0%' y1='0%' x2='100%' y2='100%'>
                    <stop offset='0%' style='stop-color:#38bdf8;stop-opacity:1' />
                    <stop offset='100%' style='stop-color:#6366f1;stop-opacity:1' />
                </linearGradient>
            </defs>
            <rect width='100%' height='100%' rx='60' fill='url(#grad)'/>
            <text x='50%' y='54%' font-family='sans-serif' font-size='44' font-weight='bold' fill='#ffffff' dominant-baseline='middle' text-anchor='middle'>{initials}</text>
        </svg>"""
        default_data_uri = f"data:image/svg+xml;base64,{base64.b64encode(default_svg.encode('utf-8')).decode('utf-8')}"

        if not avatar_url:
            return default_data_uri

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url, timeout=aiohttp.ClientTimeout(total=2.0)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "image/png").split(";")[0]
                        data = await resp.read()
                        b64 = base64.b64encode(data).decode("utf-8")
                        return f"data:{content_type};base64,{b64}"
        except Exception:
            pass

        return default_data_uri

    @classmethod
    async def _build_cover_html(cls, guild: Optional[discord.Guild], year: int, total_categories: int = 12) -> str:
        guild_name = guild.name if guild else "BMIA Community"
        guild_icon_url = str(guild.icon.url) if guild and guild.icon else None
        guild_icon_uri = await cls._fetch_avatar_data_uri(guild_icon_url, guild_name)

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 1300px;
            height: 850px;
            background: #06080d;
            background-image: 
                radial-gradient(circle at 50% 15%, rgba(0, 240, 255, 0.18) 0%, transparent 55%),
                radial-gradient(circle at 10% 85%, rgba(176, 38, 255, 0.18) 0%, transparent 55%),
                radial-gradient(circle at 90% 85%, rgba(255, 215, 0, 0.15) 0%, transparent 55%),
                radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.95) 0%, #06080d 100%);
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px;
            overflow: hidden;
            position: relative;
        }}
        .top-glow {{
            position: absolute; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #00f0ff, #b026ff, #ffd700, #00f0ff);
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.9);
        }}
        .badge-year {{
            background: linear-gradient(135deg, rgba(255,215,0,0.2), rgba(176,38,255,0.2));
            border: 1px solid rgba(255,215,0,0.6);
            border-radius: 999px;
            padding: 8px 24px;
            font-family: 'Orbitron', sans-serif;
            font-size: 16px;
            font-weight: 800;
            color: #ffd700;
            letter-spacing: 4px;
            margin-bottom: 25px;
            box-shadow: 0 0 20px rgba(255,215,0,0.3);
            text-transform: uppercase;
        }}
        .server-avatar {{
            width: 140px; height: 140px;
            border-radius: 50%;
            border: 4px solid #00f0ff;
            box-shadow: 0 0 35px rgba(0,240,255,0.6);
            object-fit: cover;
            margin-bottom: 25px;
        }}
        .title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 56px;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 3px;
            background: linear-gradient(180deg, #ffffff 0%, #a5b4fc 60%, #818cf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 10px 30px rgba(0,0,0,0.8);
            text-align: center;
            margin-bottom: 12px;
        }}
        .subtitle {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 26px;
            font-weight: 600;
            color: #94a3b8;
            letter-spacing: 2px;
            text-align: center;
            margin-bottom: 45px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            width: 100%;
            max-width: 960px;
        }}
        .stat-card {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }}
        .stat-card:hover {{
            border-color: rgba(0, 240, 255, 0.4);
        }}
        .stat-icon {{ font-size: 32px; margin-bottom: 8px; display: block; }}
        .stat-title {{ font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px; }}
        .stat-desc {{ font-size: 16px; font-weight: 600; color: #cbd5e1; margin-top: 4px; }}
        .footer {{
            position: absolute; bottom: 30px;
            font-size: 15px; color: #64748b; font-weight: 600; letter-spacing: 2px;
            text-transform: uppercase;
        }}
    </style>
</head>
<body>
    <div class="top-glow"></div>
    <div class="badge-year">✨ RETROSPECTIVA OFICIAL {year} ✨</div>
    <img class="server-avatar" src="{guild_icon_uri}" alt="{guild_name}">
    <h1 class="title">DESTAQUES DO ANO</h1>
    <p class="subtitle">{guild_name} • Celebrando as Maiores Lendas da Comunidade</p>
    
    <div class="stats-grid">
        <div class="stat-card">
            <span class="stat-icon">⚡</span>
            <div class="stat-title">Engajamento</div>
            <div class="stat-desc">XP, Mensagens & Atividade</div>
        </div>
        <div class="stat-card">
            <span class="stat-icon">🎙️</span>
            <div class="stat-title">Voz & Madrugada</div>
            <div class="stat-desc">Horas em Call & Corujão</div>
        </div>
        <div class="stat-card">
            <span class="stat-icon">🎮</span>
            <div class="stat-title">Games & Clipes</div>
            <div class="stat-desc">Jogos do Ano & Momentos Épicos</div>
        </div>
    </div>
    <div class="footer">Navegue pelas fotos da galeria acima • BMIA Esports</div>
</body>
</html>"""

    @classmethod
    async def generate_cover_slide(cls, guild: Optional[discord.Guild], year: int, total_categories: int = 12) -> BytesIO:
        """Gera o slide de capa oficial da Retrospectiva Anual."""
        from playwright.async_api import async_playwright
        html = await cls._build_cover_html(guild, year, total_categories)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})
            await page.set_content(html, wait_until="load")
            screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer

    @classmethod
    async def _build_category_html(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        category_title: str,
        category_subtitle: str,
        category_icon: str,
        theme_color: str,
        winners: List[Dict[str, Any]],
        unit_label: str = "",
        is_time: bool = False
    ) -> str:
        def format_val(item: Dict[str, Any]) -> str:
            if is_time:
                sec = float(item.get("value_seconds", 0) or item.get("value", 0) or 0)
                hours = int(sec // 3600)
                mins = int((sec % 3600) // 60)
                return f"{hours}h {mins}m"
            val = item.get("value", 0)
            try:
                num = int(val)
                return f"{num:,}".replace(",", ".")
            except (ValueError, TypeError):
                return str(val)

        top_data = []
        for i in range(3):
            if i < len(winners):
                w = winners[i]
                uid = w.get("user_id")
                uname = w.get("username") or w.get("activity_name") or f"Membro #{i+1}"
                avatar_url = None
                if guild and uid:
                    member = guild.get_member(uid)
                    if member:
                        avatar_url = str(member.display_avatar.url)
                avatar_uri = await cls._fetch_avatar_data_uri(avatar_url, uname)
                top_data.append({
                    "name": uname,
                    "val_str": format_val(w),
                    "avatar_uri": avatar_uri,
                    "exists": True
                })
            else:
                top_data.append({
                    "name": "—",
                    "val_str": "Sem registros",
                    "avatar_uri": await cls._fetch_avatar_data_uri(None, "BM"),
                    "exists": False
                })

        p1, p2, p3 = top_data[0], top_data[1], top_data[2]

        honorable_cards_html = ""
        if len(winners) > 3:
            for idx, w in enumerate(winners[3:5], start=4):
                uname = w.get("username") or w.get("activity_name") or f"Membro #{idx}"
                val_str = format_val(w)
                honorable_cards_html += f"""
                <div class="honorable-card">
                    <span class="honorable-pos">#{idx}</span>
                    <span class="honorable-name">{uname}</span>
                    <span class="honorable-val">{val_str} {unit_label}</span>
                </div>
                """

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 1300px;
            height: 850px;
            background: #06080d;
            background-image: 
                radial-gradient(circle at 50% 10%, {theme_color}25 0%, transparent 60%),
                radial-gradient(circle at 90% 80%, rgba(176, 38, 255, 0.12) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.95) 0%, #06080d 100%);
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            flex-direction: column;
            padding: 40px 60px;
            overflow: hidden;
            position: relative;
        }}
        .top-glow {{
            position: absolute; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, {theme_color}, #ffd700, {theme_color});
            box-shadow: 0 0 25px {theme_color};
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 20px;
            margin-bottom: 25px;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .header-icon {{
            font-size: 44px;
            background: rgba(255,255,255,0.05);
            border: 2px solid {theme_color};
            border-radius: 20px;
            width: 80px; height: 80px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 25px {theme_color}60;
        }}
        .title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 36px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}
        .subtitle {{
            font-size: 18px;
            color: #94a3b8;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        .badge-year {{
            background: rgba(255,215,0,0.1);
            border: 1px solid #ffd700;
            color: #ffd700;
            padding: 6px 18px;
            border-radius: 999px;
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 2px;
        }}
        .podium-container {{
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 30px;
            margin-top: 10px;
            height: 470px;
        }}
        .podium-slot {{
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }}
        .avatar-box {{
            position: relative;
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .avatar {{
            border-radius: 50%;
            object-fit: cover;
            background: #1e293b;
        }}
        .rank-crown {{
            position: absolute;
            top: -24px;
            font-size: 32px;
            filter: drop-shadow(0 0 10px rgba(255,215,0,0.8));
        }}
        .user-name {{
            font-family: 'Orbitron', sans-serif;
            font-weight: 800;
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 250px;
            margin-top: 6px;
        }}
        .user-score {{
            font-size: 18px;
            font-weight: 700;
            color: #cbd5e1;
            margin-top: 2px;
        }}
        .pillar {{
            width: 240px;
            border-radius: 20px 20px 8px 8px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            padding-top: 20px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
            box-shadow: 0 15px 35px rgba(0,0,0,0.6);
            border-top: 3px solid rgba(255,255,255,0.4);
            position: relative;
        }}
        .pillar-1 {{
            height: 270px;
            background: linear-gradient(180deg, rgba(255, 215, 0, 0.35) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 2px solid #ffd700;
            box-shadow: 0 0 40px rgba(255, 215, 0, 0.4);
        }}
        .pillar-2 {{
            height: 210px;
            background: linear-gradient(180deg, rgba(192, 192, 192, 0.3) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 2px solid #c0c0c0;
            box-shadow: 0 0 30px rgba(192, 192, 192, 0.25);
        }}
        .pillar-3 {{
            height: 160px;
            background: linear-gradient(180deg, rgba(205, 127, 50, 0.3) 0%, rgba(15, 23, 42, 0.95) 100%);
            border: 2px solid #cd7f32;
            box-shadow: 0 0 30px rgba(205, 127, 50, 0.25);
        }}
        .pillar-rank {{
            font-size: 54px;
            font-weight: 900;
            line-height: 1;
            letter-spacing: -2px;
        }}
        .pillar-1 .pillar-rank {{ color: #ffd700; text-shadow: 0 0 20px rgba(255,215,0,0.8); }}
        .pillar-2 .pillar-rank {{ color: #e2e8f0; text-shadow: 0 0 15px rgba(255,255,255,0.6); }}
        .pillar-3 .pillar-rank {{ color: #fdba74; text-shadow: 0 0 15px rgba(253,186,116,0.6); }}
        .pillar-label {{
            font-size: 14px;
            font-weight: 700;
            color: #94a3b8;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .honorable-mention-grid {{
            position: absolute;
            bottom: 25px;
            left: 60px;
            right: 60px;
            display: flex;
            justify-content: center;
            gap: 20px;
        }}
        .honorable-card {{
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 10px 24px;
            display: flex;
            align-items: center;
            gap: 15px;
            backdrop-filter: blur(8px);
        }}
        .honorable-pos {{
            font-family: 'Orbitron', sans-serif;
            font-weight: 800;
            color: {theme_color};
            font-size: 16px;
        }}
        .honorable-name {{
            font-weight: 700;
            font-size: 16px;
            color: #ffffff;
            max-width: 180px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .honorable-val {{
            font-weight: 600;
            font-size: 15px;
            color: #94a3b8;
        }}
    </style>
</head>
<body>
    <div class="top-glow"></div>
    <div class="header">
        <div class="header-left">
            <div class="header-icon">{category_icon}</div>
            <div>
                <h1 class="title">{category_title}</h1>
                <p class="subtitle">{category_subtitle}</p>
            </div>
        </div>
        <div class="badge-year">BMIA WRAPPED {year}</div>
    </div>

    <div class="podium-container">
        <!-- 2º Lugar -->
        <div class="podium-slot">
            <div class="avatar-box">
                <img class="avatar" src="{p2['avatar_uri']}" alt="{p2['name']}" style="width: 100px; height: 100px; border: 3px solid #c0c0c0; box-shadow: 0 0 20px rgba(192,192,192,0.4);">
                <div class="user-name" style="font-size: 18px; color: #e2e8f0;">{p2['name']}</div>
                <div class="user-score">{p2['val_str']} {unit_label}</div>
            </div>
            <div class="pillar pillar-2">
                <div class="pillar-rank">#2</div>
                <div class="pillar-label">Prata</div>
            </div>
        </div>

        <!-- 1º Lugar -->
        <div class="podium-slot">
            <div class="avatar-box">
                <div class="rank-crown">👑</div>
                <img class="avatar" src="{p1['avatar_uri']}" alt="{p1['name']}" style="width: 125px; height: 125px; border: 4px solid #ffd700; box-shadow: 0 0 30px rgba(255,215,0,0.6);">
                <div class="user-name" style="font-size: 22px; color: #ffd700;">{p1['name']}</div>
                <div class="user-score" style="font-size: 20px; color: #fff; font-weight: 800;">{p1['val_str']} {unit_label}</div>
            </div>
            <div class="pillar pillar-1">
                <div class="pillar-rank">#1</div>
                <div class="pillar-label">Campeão</div>
            </div>
        </div>

        <!-- 3º Lugar -->
        <div class="podium-slot">
            <div class="avatar-box">
                <img class="avatar" src="{p3['avatar_uri']}" alt="{p3['name']}" style="width: 90px; height: 90px; border: 3px solid #cd7f32; box-shadow: 0 0 20px rgba(205,127,50,0.4);">
                <div class="user-name" style="font-size: 17px; color: #fdba74;">{p3['name']}</div>
                <div class="user-score">{p3['val_str']} {unit_label}</div>
            </div>
            <div class="pillar pillar-3">
                <div class="pillar-rank">#3</div>
                <div class="pillar-label">Bronze</div>
            </div>
        </div>
    </div>

    <div class="honorable-mention-grid">
        {honorable_cards_html}
    </div>
</body>
</html>"""

    @classmethod
    async def generate_category_slide(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        category_title: str,
        category_subtitle: str,
        category_icon: str,
        theme_color: str,
        winners: List[Dict[str, Any]],
        unit_label: str = "",
        is_time: bool = False
    ) -> BytesIO:
        """Renderiza um slide temático de pódio para uma categoria dos Destaques do Ano."""
        from playwright.async_api import async_playwright
        html = await cls._build_category_html(
            guild, year, category_title, category_subtitle, category_icon,
            theme_color, winners, unit_label, is_time
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})
            await page.set_content(html, wait_until="load")
            screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer

    @classmethod
    async def _build_media_html(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        clip_data: Optional[Dict[str, Any]] = None
    ) -> str:
        if not clip_data:
            clip_data = {
                "username": "Nenhum registro",
                "avatar_url": None,
                "reaction_count": 0,
                "reaction_summary": "—",
                "channel_name": "prints-e-clips",
                "created_at": f"01/01/{year}",
                "content": "Nenhum clipe ou print registrado este ano.",
                "media_url": None
            }

        author_name = clip_data.get("username", "Autor")
        avatar_uri = await cls._fetch_avatar_data_uri(clip_data.get("avatar_url"), author_name)
        channel_name = clip_data.get("channel_name", "prints-e-clips")
        reactions_cnt = clip_data.get("reaction_count", 0)
        reply_cnt = clip_data.get("reply_count", 0)
        date_str = clip_data.get("created_at", "")
        media_url = clip_data.get("media_url")
        engagement_str = f"🔥 {reactions_cnt} reações"
        if reply_cnt > 0:
            engagement_str += f" • 💬 {reply_cnt} respostas"

        preview_html = f"""<img class="media-preview" src="{media_url}" alt="Clipe do Ano">""" if media_url else """
        <div class="no-preview">
            <span style="font-size: 64px;">🎬</span>
            <span style="font-size: 20px; color: #94a3b8; margin-top: 10px;">Link de Mídia Registrado</span>
        </div>
        """

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 1300px;
            height: 850px;
            background: #06080d;
            background-image: 
                radial-gradient(circle at 50% 10%, rgba(236, 72, 153, 0.2) 0%, transparent 60%),
                radial-gradient(circle at 90% 80%, rgba(0, 240, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.95) 0%, #06080d 100%);
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            flex-direction: column;
            padding: 40px 60px;
            overflow: hidden;
            position: relative;
        }}
        .top-glow {{
            position: absolute; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #ec4899, #00f0ff, #ffd700, #ec4899);
            box-shadow: 0 0 25px rgba(236, 72, 153, 0.9);
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header-left {{ display: flex; align-items: center; gap: 20px; }}
        .header-icon {{
            font-size: 44px;
            background: rgba(255,255,255,0.05);
            border: 2px solid #ec4899;
            border-radius: 20px;
            width: 80px; height: 80px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 25px rgba(236, 72, 153, 0.5);
        }}
        .title {{ font-family: 'Orbitron', sans-serif; font-size: 36px; font-weight: 900; color: #fff; letter-spacing: 2px; text-transform: uppercase; }}
        .subtitle {{ font-size: 18px; color: #94a3b8; font-weight: 600; }}
        .badge-year {{ background: rgba(255,215,0,0.1); border: 1px solid #ffd700; color: #ffd700; padding: 6px 18px; border-radius: 999px; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 800; letter-spacing: 2px; }}

        .media-layout {{
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 40px;
            height: 580px;
            align-items: center;
        }}
        .preview-box {{
            background: rgba(15, 23, 42, 0.8);
            border: 2px solid rgba(236, 72, 153, 0.4);
            border-radius: 24px;
            height: 520px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 35px rgba(0,0,0,0.7);
            position: relative;
        }}
        .media-preview {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .no-preview {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .meta-box {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .author-card {{
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 24px;
            display: flex;
            align-items: center;
            gap: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        }}
        .author-avatar {{
            width: 80px; height: 80px;
            border-radius: 50%;
            border: 3px solid #ec4899;
            box-shadow: 0 0 20px rgba(236, 72, 153, 0.6);
            object-fit: cover;
        }}
        .author-name {{
            font-family: 'Orbitron', sans-serif;
            font-size: 24px;
            font-weight: 800;
            color: #ffffff;
        }}
        .author-role {{
            font-size: 16px;
            color: #38bdf8;
            font-weight: 600;
        }}
        .reactions-card {{
            background: linear-gradient(135deg, rgba(236, 72, 153, 0.15) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(236, 72, 153, 0.5);
            border-radius: 20px;
            padding: 24px;
            box-shadow: 0 10px 25px rgba(236, 72, 153, 0.2);
        }}
        .reactions-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 700;
            color: #ec4899;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 8px;
        }}
        .reactions-val {{
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
        }}
        .info-pill {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 12px 18px;
            font-size: 16px;
            color: #cbd5e1;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="top-glow"></div>
    <div class="header">
        <div class="header-left">
            <div class="header-icon">📸</div>
            <div>
                <h1 class="title">CLIPE / PRINT DO ANO</h1>
                <p class="subtitle">O momento mais votado e reagido pela comunidade</p>
            </div>
        </div>
        <div class="badge-year">BMIA WRAPPED {year}</div>
    </div>

    <div class="media-layout">
        <div class="preview-box">
            {preview_html}
        </div>
        <div class="meta-box">
            <div class="author-card">
                <img class="author-avatar" src="{avatar_uri}" alt="{author_name}">
                <div>
                    <div class="author-name">{author_name}</div>
                    <div class="author-role">Postado em #{channel_name}</div>
                </div>
            </div>

            <div class="reactions-card">
                <div class="reactions-title">🔥 Engajamento da Comunidade</div>
                <div class="reactions-val">{engagement_str}</div>
            </div>

            <div class="info-pill">
                📅 Publicado em: <strong>{date_str}</strong>
            </div>
        </div>
    </div>
</body>
</html>"""

    @classmethod
    async def _build_other_highlights_html(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        highlights_data: Dict[str, Any]
    ) -> str:
        """Renderiza o slide especial #10 de 'Outros Destaques' com grid 3x2 reunindo os 6 rankings secundários."""
        subcats = [
            {"key": "o_midia", "title": "O MÍDIA", "subtitle": "Mais Anexos & Prints", "icon": "🖼️", "color": "#06b6d4", "unit": "anexos", "is_time": False},
            {"key": "o_onipresente", "title": "O ONIPRESENTE", "subtitle": "Mais Dias Ativos", "icon": "📅", "color": "#10b981", "unit": "dias", "is_time": False},
            {"key": "ima_da_galera", "title": "ÍMÃ DA GALERA", "subtitle": "Reações & Menções", "icon": "🧲", "color": "#f97316", "unit": "reações", "is_time": False},
            {"key": "boca_suja", "title": "BOCA SUJA", "subtitle": "Mensagens Ofensivas", "icon": "🤬", "color": "#ef4444", "unit": "msgs", "is_time": False},
            {"key": "rei_das_demos", "title": "REI DAS DEMOS", "subtitle": "Jogos Demo Registrados", "icon": "🎮", "color": "#8b5cf6", "unit": "demos", "is_time": False},
            {"key": "maratonista", "title": "O MARATONISTA", "subtitle": "Maior Sessão de Voz", "icon": "⏱️", "color": "#3b82f6", "unit": "", "is_time": True}
        ]

        def format_val_str(val_any: Any, is_time: bool) -> str:
            if is_time:
                sec = float(val_any or 0)
                hours = int(sec // 3600)
                mins = int((sec % 3600) // 60)
                return f"{hours}h {mins}m"
            try:
                num = int(val_any or 0)
                return f"{num:,}".replace(",", ".")
            except (ValueError, TypeError):
                return str(val_any or 0)

        rendered_panels = []
        for scat in subcats:
            raw_winners = highlights_data.get(scat["key"], [])
            panel_rows = []
            
            medals = ["🥇", "🥈", "🥉"]
            border_colors = ["#ffd700", "#e2e8f0", "#cd7f32"]

            for rank_idx in range(3):
                if rank_idx < len(raw_winners):
                    w = raw_winners[rank_idx]
                    uid = w.get("user_id")
                    uname = w.get("username") or f"Membro #{rank_idx+1}"
                    avatar_url = w.get("avatar_url")
                    if guild and uid:
                        member = guild.get_member(uid)
                        if member:
                            avatar_url = str(member.display_avatar.url)
                    
                    val_raw = w.get("value_seconds") if scat["is_time"] else (w.get("value") or w.get("count") or 0)
                    formatted_val = format_val_str(val_raw, scat["is_time"])
                    if scat["unit"] and not scat["is_time"]:
                        formatted_val = f"{formatted_val} {scat['unit']}"

                    avatar_uri = await cls._fetch_avatar_data_uri(avatar_url, uname)

                    panel_rows.append(f"""
                    <div class="user-row">
                        <div class="user-left">
                            <span class="rank-badge" style="color: {border_colors[rank_idx]};">{medals[rank_idx]}</span>
                            <img class="user-avatar" src="{avatar_uri}" alt="{uname}">
                            <span class="user-name">{uname}</span>
                        </div>
                        <span class="user-val" style="color: {scat['color']};">{formatted_val}</span>
                    </div>
                    """)
                else:
                    panel_rows.append(f"""
                    <div class="user-row empty">
                        <div class="user-left">
                            <span class="rank-badge">—</span>
                            <span class="user-name empty-text">Sem registro</span>
                        </div>
                        <span class="user-val">—</span>
                    </div>
                    """)

            rows_html = "".join(panel_rows)
            rendered_panels.append(f"""
            <div class="mini-card" style="border-top: 3px solid {scat['color']};">
                <div class="mini-card-header">
                    <span class="mini-icon">{scat['icon']}</span>
                    <div>
                        <div class="mini-title">{scat['title']}</div>
                        <div class="mini-subtitle">{scat['subtitle']}</div>
                    </div>
                </div>
                <div class="mini-card-body">
                    {rows_html}
                </div>
            </div>
            """)

        all_panels_html = "".join(rendered_panels)

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            width: 1300px;
            height: 850px;
            background: #06080d;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(0, 240, 255, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 85% 15%, rgba(139, 92, 246, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 50% 85%, rgba(249, 115, 22, 0.12) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.95) 0%, #06080d 100%);
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            flex-direction: column;
            padding: 35px 50px;
            overflow: hidden;
            position: relative;
        }}
        .top-glow {{
            position: absolute; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #06b6d4, #10b981, #f97316, #ef4444, #8b5cf6, #3b82f6);
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.8);
        }}
        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .header-left {{ display: flex; align-items: center; gap: 18px; }}
        .header-icon {{
            font-size: 38px;
            background: rgba(255,255,255,0.05);
            border: 2px solid #8b5cf6;
            border-radius: 16px;
            width: 68px; height: 68px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
        }}
        .title {{ font-family: 'Orbitron', sans-serif; font-size: 32px; font-weight: 900; color: #fff; letter-spacing: 2px; text-transform: uppercase; }}
        .subtitle {{ font-size: 16px; color: #94a3b8; font-weight: 600; }}
        .badge-year {{ background: rgba(255,215,0,0.1); border: 1px solid #ffd700; color: #ffd700; padding: 6px 18px; border-radius: 999px; font-family: 'Orbitron', sans-serif; font-size: 14px; font-weight: 800; letter-spacing: 2px; }}

        .grid-layout {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: repeat(2, 1fr);
            gap: 22px;
            height: 660px;
        }}
        .mini-card {{
            background: rgba(15, 23, 42, 0.75);
            border-radius: 18px;
            border-left: 1px solid rgba(255,255,255,0.08);
            border-right: 1px solid rgba(255,255,255,0.08);
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            backdrop-filter: blur(10px);
            box-shadow: 0 10px 28px rgba(0,0,0,0.5);
        }}
        .mini-card-header {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 8px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.06);
        }}
        .mini-icon {{ font-size: 26px; }}
        .mini-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 16px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 1px;
        }}
        .mini-subtitle {{
            font-size: 13px;
            color: #94a3b8;
            font-weight: 600;
        }}
        .mini-card-body {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .user-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(255,255,255,0.035);
            border: 1px solid rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 9px 12px;
        }}
        .user-row.empty {{
            opacity: 0.4;
        }}
        .user-left {{
            display: flex;
            align-items: center;
            gap: 12px;
            overflow: hidden;
        }}
        .rank-badge {{
            font-size: 18px;
            font-weight: 700;
            width: 24px;
            text-align: center;
        }}
        .user-avatar {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            object-fit: cover;
            border: 1.5px solid rgba(255,255,255,0.25);
        }}
        .user-name {{
            font-size: 16px;
            font-weight: 700;
            color: #f1f5f9;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 140px;
        }}
        .empty-text {{
            color: #64748b;
            font-style: italic;
        }}
        .user-val {{
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    <div class="top-glow"></div>
    <div class="header">
        <div class="header-left">
            <div class="header-icon">🌟</div>
            <div>
                <h1 class="title">OUTROS DESTAQUES DO ANO</h1>
                <p class="subtitle">Recordes e menções honrosas da comunidade</p>
            </div>
        </div>
        <div class="badge-year">BMIA WRAPPED {year}</div>
    </div>

    <div class="grid-layout">
        {all_panels_html}
    </div>
</body>
</html>"""

    @classmethod
    async def generate_media_slide(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        clip_data: Optional[Dict[str, Any]] = None
    ) -> BytesIO:
        """Renderiza o slide especial de '📸 Clipe / Print do Ano' com preview e estatísticas."""
        from playwright.async_api import async_playwright
        html = await cls._build_media_html(guild, year, clip_data)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})
            await page.set_content(html, wait_until="load")
            screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer

    @classmethod
    async def generate_other_highlights_slide(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        highlights_data: Dict[str, Any]
    ) -> BytesIO:
        """Renderiza o slide composto de '🌟 Outros Destaques do Ano'."""
        from playwright.async_api import async_playwright
        html = await cls._build_other_highlights_html(guild, year, highlights_data)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})
            await page.set_content(html, wait_until="load")
            screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer

    @classmethod
    async def generate_all_slides_files(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        highlights_data: Dict[str, Any],
        top_clip: Optional[Dict[str, Any]] = None,
        categories: Optional[List[Dict[str, Any]]] = None
    ) -> List[discord.File]:
        """
        Gera todos os slides dos Destaques do Ano de forma ultra-otimizada reutilizando
        uma única instância e aba do Chromium, economizando memória (~80MB de RAM) e gerando em ~2 segundos.
        """
        from playwright.async_api import async_playwright

        if categories is None:
            from commands.stats_commands import HIGHLIGHTS_CATEGORIES
            categories = HIGHLIGHTS_CATEGORIES

        # 1. Tenta delegar a renderização dos slides para a Vercel Serverless (0 MB de RAM na VPS)
        try:
            async def fetch_slide_remote(cat: Dict[str, Any], idx: int) -> Optional[discord.File]:
                cat_id = cat["id"]
                title = cat.get("title", cat.get("label", ""))
                subtitle = cat.get("subtitle", cat.get("description", ""))
                icon = cat.get("icon", "🏆")
                color = cat.get("color", "#00f0ff")
                winners_raw = highlights_data.get(cat_id, [])

                winners_fmt = []
                for w in winners_raw:
                    val = w.get("value") or w.get("value_seconds") or 0
                    unit = cat.get("unit", "")
                    score_str = f"{val:,} {unit}".strip() if val else ""
                    winners_fmt.append({
                        "name": w.get("username") or w.get("name") or "Destaque",
                        "value": val,
                        "score_formatted": score_str
                    })

                payload = {
                    "year": year,
                    "category_id": cat_id,
                    "category_title": title,
                    "category_subtitle": subtitle,
                    "category_icon": icon,
                    "theme_color": color,
                    "winners": winners_fmt,
                    "guild_name": guild.name if guild else "BMIA Community"
                }
                buf = await fetch_image_from_dashboard("wrapped", payload)
                if buf:
                    return discord.File(fp=buf, filename=f"destaques_{idx+1:02d}_{cat_id}.png")
                return None

            remote_tasks = [fetch_slide_remote(cat, i) for i, cat in enumerate(categories)]
            remote_files = await asyncio.gather(*remote_tasks)
            if all(f is not None for f in remote_files):
                return [f for f in remote_files if f is not None]
        except Exception:
            pass

        # 2. Fallback Local via Playwright se a Vercel estiver offline/não configurada
        async def build_html_task(cat: Dict[str, Any]):
            cat_id = cat["id"]
            if cat_id == "cover":
                html = await cls._build_cover_html(guild, year, len(categories))
            elif cat_id == "media":
                html = await cls._build_media_html(guild, year, top_clip)
            elif cat_id == "outros_destaques":
                html = await cls._build_other_highlights_html(guild, year, highlights_data)
            else:
                winners = highlights_data.get(cat_id, [])
                html = await cls._build_category_html(
                    guild=guild,
                    year=year,
                    category_title=cat.get("title", cat.get("label", "")),
                    category_subtitle=cat.get("subtitle", cat.get("description", "")),
                    category_icon=cat.get("icon", "🏆"),
                    theme_color=cat.get("color", "#00f0ff"),
                    winners=winners,
                    unit_label=cat.get("unit", ""),
                    is_time=cat.get("is_time", False)
                )
            return cat_id, html

        html_tasks = [build_html_task(cat) for cat in categories]
        html_results = await asyncio.gather(*html_tasks)

        # 2. Renderiza sequencialmente em um único navegador Chromium (evita múltiplos processos simultâneos)
        files = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote"
                ]
            )
            page = await browser.new_page(viewport={"width": 1300, "height": 850})

            for idx, (cat_id, html) in enumerate(html_results):
                await page.set_content(html, wait_until="load")
                screenshot_bytes = await page.screenshot(type="png", omit_background=True)
                buf = BytesIO(screenshot_bytes)
                buf.seek(0)
                files.append(discord.File(fp=buf, filename=f"destaques_{idx+1:02d}_{cat_id}.png"))

            await browser.close()

        return files


