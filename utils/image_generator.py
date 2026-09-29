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
_GUILD_ICON_BYTES_CACHE: Dict[int, bytes] = {}

# Cache de fontes carregadas
_FONT_CACHE: Dict[Tuple[int, bool, bool], ImageFont.ImageFont] = {}

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache", "tournaments")


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
    badge_text = f"★ NÍVEL {level} • {tier_name}"
    b_w = int(draw.textlength(badge_text, font=font_bold14)) + 24
    draw.rounded_rectangle((badge_x, badge_y, badge_x + b_w, badge_y + 26), radius=13, fill=(tier_color[0], tier_color[1], tier_color[2], 40), outline=tier_color, width=1)
    draw.text((badge_x + 12, badge_y + 5), badge_text, fill=tier_color, font=font_bold14)

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
        ("⚡ TOTAL XP", f"{total_xp:,} pts".replace(",", "."), (0, 240, 255, 255)),
        ("💬 MENSAGENS", f"{messages_count:,} msgs".replace(",", "."), (176, 38, 255, 255)),
        ("🎙️ TEMPO EM VOZ", f"{hours_voice}h".replace(".", ","), (255, 215, 0, 255))
    ]

    total_available_w = 1015 - 185
    chip_w = (total_available_w - (len(chips_data) - 1) * gap) // len(chips_data)

    font_chip_title = _get_font(11, bold=True)
    font_chip_val = _get_font(17, bold=True)

    for c_title, c_val, c_accent in chips_data:
        cx1 = chip_x
        cx2 = chip_x + chip_w
        cy1 = chips_y
        cy2 = chips_y + chip_h

        draw.rounded_rectangle((cx1, cy1, cx2, cy2), radius=10, fill=(15, 23, 42, 180), outline=(255, 255, 255, 25), width=1)
        draw.text((cx1 + 14, cy1 + 10), c_title, fill=(148, 163, 184, 255), font=font_chip_title)
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
# 2. PODIUM BUILDER (1300x850 - PIL PURO)
# =============================================================================

def _sync_draw_podium(
    guild_name: str,
    period_text: str,
    top_3_data: List[dict],
    others_data: List[dict]
) -> bytes:
    img = Image.new("RGBA", (1300, 850), (6, 9, 18, 255))
    draw = ImageDraw.Draw(img)

    # Linha neon superior
    _draw_linear_gradient_bar(img, (0, 0, 1300, 5), (0, 240, 255), (255, 215, 0), radius=0)

    # Cabeçalho
    font_header_title = _get_font(28, bold=True)
    font_header_sub = _get_font(15, bold=False)
    draw.text((60, 40), f"🏆 PÓDIO DE ATIVIDADE & RANKING", fill=(255, 255, 255, 255), font=font_header_title)
    draw.text((60, 78), f"Servidor: {guild_name} • Período: {period_text}".upper(), fill=(0, 240, 255, 255), font=font_header_sub)

    # =========================================================================
    # PALCO DO PÓDIO (ESQUERDA - TOP 3)
    # =========================================================================
    p1 = top_3_data[0] if len(top_3_data) > 0 else None
    p2 = top_3_data[1] if len(top_3_data) > 1 else None
    p3 = top_3_data[2] if len(top_3_data) > 2 else None

    # Configurações dos pedestais: (X, Y_top, Width, Height, Cor, Label, Medallion)
    pedestals = [
        (p2, 70, 470, 210, 280, (148, 163, 184, 255), (148, 163, 184, 70), "🥈 2º LUGAR", 90),
        (p1, 305, 380, 230, 370, (255, 215, 0, 255), (255, 215, 0, 90), "👑 1º CAMPEÃO", 110),
        (p3, 560, 530, 210, 220, (205, 127, 50, 255), (205, 127, 50, 70), "🥉 3º LUGAR", 85),
    ]

    font_rank_ped = _get_font(15, bold=True)
    font_ped_name = _get_font(18, bold=True)
    font_ped_pts = _get_font(14, bold=True)

    for p_data, px, py, pw, ph, border_c, glow_c, badge_lbl, av_size in pedestals:
        # Desenha pedestal
        _draw_glow_rect(
            base_img=img,
            xy=(px, py, px + pw, py + ph),
            radius=16,
            glow_color=glow_c,
            glow_radius=10,
            fill_color=(15, 23, 42, 230),
            outline_color=border_c,
            outline_width=2
        )

        if p_data:
            # Avatar
            av_y = py - (av_size // 2)
            av_cx = px + (pw // 2)
            _draw_circle_avatar(
                target_img=img,
                avatar_bytes=p_data.get("avatar_bytes"),
                center_xy=(av_cx, av_y),
                size=av_size,
                border_color=border_c,
                border_width=3,
                fallback_initial=p_data.get("name", "?")[0]
            )

            # Badge do Lugar (ex: 👑 1º CAMPEÃO)
            draw.text((av_cx, py + (av_size // 2) + 12), badge_lbl, fill=border_c, font=font_rank_ped, anchor="mm")

            # Nome
            name_str = p_data.get("name", "Jogador")
            if len(name_str) > 14:
                name_str = name_str[:12] + "..."
            draw.text((av_cx, py + (av_size // 2) + 38), name_str, fill=(255, 255, 255, 255), font=font_ped_name, anchor="mm")

            # Pontos
            pts_str = f"{p_data.get('total_points', 0):,} pts".replace(",", ".")
            draw.rounded_rectangle((av_cx - 65, py + (av_size // 2) + 55, av_cx + 65, py + (av_size // 2) + 82), radius=8, fill=(255, 255, 255, 15), outline=(255, 255, 255, 30), width=1)
            draw.text((av_cx, py + (av_size // 2) + 68), pts_str, fill=border_c, font=font_ped_pts, anchor="mm")

    # =========================================================================
    # TABELA DE MENÇÕES HONROSAS (DIREITA - TOP 4 A 10)
    # =========================================================================
    col_x1, col_y1, col_x2, col_y2 = 810, 130, 1240, 770
    _draw_glow_rect(
        base_img=img,
        xy=(col_x1, col_y1, col_x2, col_y2),
        radius=18,
        glow_color=(0, 240, 255, 60),
        glow_radius=8,
        fill_color=(12, 18, 34, 230),
        outline_color=(0, 240, 255, 120),
        outline_width=2
    )

    # Título da Tabela
    font_col_title = _get_font(15, bold=True)
    draw.text((col_x1 + 24, col_y1 + 20), "⭐ DESTAQUES DA COMUNIDADE (TOP 4 - 10)", fill=(0, 240, 255, 255), font=font_col_title)
    draw.line((col_x1 + 20, col_y1 + 46, col_x2 - 20, col_y1 + 46), fill=(255, 255, 255, 20), width=1)

    row_y = col_y1 + 60
    row_h = 75
    font_row_rank = _get_font(14, bold=True)
    font_row_name = _get_font(16, bold=True)
    font_row_pts = _get_font(14, bold=True)

    for idx, user_item in enumerate(others_data[:7]):
        ry1 = row_y + (idx * row_h)
        ry2 = ry1 + row_h - 10
        rx1 = col_x1 + 16
        rx2 = col_x2 - 16

        # Fundo da linha
        draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=10, fill=(18, 26, 48, 200), outline=(255, 255, 255, 15), width=1)

        # Rank Pill (#04)
        draw.rounded_rectangle((rx1 + 10, ry1 + 12, rx1 + 52, ry2 - 12), radius=6, fill=(0, 240, 255, 30), outline=(0, 240, 255, 100), width=1)
        draw.text((rx1 + 31, (ry1 + ry2) // 2), f"#{user_item.get('rank', idx+4):02d}", fill=(0, 240, 255, 255), font=font_row_rank, anchor="mm")

        # Mini Avatar
        _draw_circle_avatar(
            target_img=img,
            avatar_bytes=user_item.get("avatar_bytes"),
            center_xy=(rx1 + 82, (ry1 + ry2) // 2),
            size=42,
            border_color=(0, 240, 255, 180),
            border_width=2,
            fallback_initial=user_item.get("name", "?")[0]
        )

        # Nome
        r_name = user_item.get("name", "Membro")
        if len(r_name) > 16:
            r_name = r_name[:14] + "..."
        draw.text((rx1 + 115, (ry1 + ry2) // 2), r_name, fill=(255, 255, 255, 255), font=font_row_name, anchor="lm")

        # Pontos
        r_pts = f"{user_item.get('total_points', 0):,} pts".replace(",", ".")
        draw.text((rx2 - 16, (ry1 + ry2) // 2), r_pts, fill=(255, 215, 0, 255), font=font_row_pts, anchor="rm")

    # Rodapé
    font_footer = _get_font(13, bold=False)
    draw.text((60, 815), "⚡ Gerado automaticamente pelo sistema BMIA Esports", fill=(100, 116, 139, 255), font=font_footer)
    draw.text((1240, 815), "BDP COMMUNITY • 2026", fill=(0, 240, 255, 255), font=font_footer, anchor="ra")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class PodiumBuilder:
    """Gerador visual de Pódio e Ranking Periódico (1300x850) em Pillow Puro."""

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

    async def generate_podium(
        self,
        guild: discord.Guild,
        top_users: List[dict],
        period_text: str = "ESTE MÊS",
        use_cache: bool = True
    ) -> BytesIO:
        guild_name = guild.name if guild else "Servidor Esports"
        top_list = top_users[:10]

        # Baixa avatares concorrentemente
        avatar_tasks = []
        for u in top_list:
            uid = u.get("user_id", 0)
            m = guild.get_member(uid) if guild else None
            avatar_tasks.append(self._get_avatar_bytes(m, u))

        results = await asyncio.gather(*avatar_tasks, return_exceptions=True)

        top_3 = []
        others = []
        for i, user_data in enumerate(top_list):
            uid = user_data.get("user_id", 0)
            member = guild.get_member(uid) if guild else None
            av_data = results[i] if (i < len(results) and isinstance(results[i], bytes)) else None
            display_name = member.display_name if member else user_data.get("username", "Membro")

            item = {
                "rank": i + 1,
                "user_id": uid,
                "name": display_name,
                "total_points": user_data.get("total_points", 0),
                "avatar_bytes": av_data
            }
            if i < 3:
                top_3.append(item)
            else:
                others.append(item)

        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            None,
            _sync_draw_podium,
            guild_name,
            period_text,
            top_3,
            others
        )
        buffer = BytesIO(png_bytes)
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
    draw.text((820, 197), "🏆", font=_get_font(38), anchor="mm")
    draw.text((860, 178), "★ CAMPEÃO DO TORNEIO ★", fill=(255, 215, 0, 255), font=font_tr_title)
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
    standings: List[dict]
) -> bytes:
    img = Image.new("RGBA", (1920, 1080), (6, 9, 18, 255))
    draw = ImageDraw.Draw(img)

    _draw_linear_gradient_bar(img, (0, 0, 1920, 6), (0, 240, 255), (255, 215, 0), radius=0)

    title = str(tournament.get("name", "TABELA DA LIGA")).upper()
    game = str(tournament.get("game_name", "Geral")).upper()
    prize = str(tournament.get("prize") or "Glória e Pontos")

    font_title = _get_font(30, bold=True)
    font_sub = _get_font(15, bold=False)
    draw.text((70, 45), f"⚡ TABELA DE CLASSIFICAÇÃO — {title}", fill=(255, 255, 255, 255), font=font_title)
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

    for idx, s in enumerate(standings[:12]):
        ry1 = row_y + (idx * row_h)
        ry2 = ry1 + row_h - 8
        rx1 = t_x1 + 16
        rx2 = t_x2 - 16

        pos = idx + 1
        pos_color = (255, 215, 0, 255) if pos == 1 else ((148, 163, 184, 255) if pos == 2 else ((205, 127, 50, 255) if pos == 3 else (255, 255, 255, 255)))

        draw.rounded_rectangle((rx1, ry1, rx2, ry2), radius=8, fill=(18, 26, 48, 200) if idx % 2 == 0 else (14, 20, 38, 200), outline=(255, 255, 255, 15), width=1)

        # Pos
        draw.text((140, (ry1 + ry2) // 2), f"#{pos:02d}", fill=pos_color, font=font_tr_bold, anchor="mm")

        # Nome
        t_name = s.get("team_name") or (" & ".join([m.get("username", "Jogador") for m in s.get("members", [])]) if s.get("members") else "Time")
        draw.text((320, (ry1 + ry2) // 2), t_name[:24], fill=(255, 255, 255, 255), font=font_tr_bold, anchor="lm")

        # Stats
        draw.text((1000, (ry1 + ry2) // 2), str(s.get("points", 0)), fill=(255, 215, 0, 255), font=font_tr_bold, anchor="mm")
        draw.text((1150, (ry1 + ry2) // 2), str(s.get("wins", 0)), fill=(255, 255, 255, 255), font=font_tr_regular, anchor="mm")
        draw.text((1300, (ry1 + ry2) // 2), str(s.get("draws", 0)), fill=(255, 255, 255, 255), font=font_tr_regular, anchor="mm")
        draw.text((1450, (ry1 + ry2) // 2), str(s.get("losses", 0)), fill=(255, 255, 255, 255), font=font_tr_regular, anchor="mm")
        draw.text((1600, (ry1 + ry2) // 2), str(s.get("score_diff", s.get("goal_diff", 0))), fill=(255, 255, 255, 255), font=font_tr_regular, anchor="mm")

        # Status Pill
        st_lbl = "LÍDER" if pos == 1 else ("G4" if pos <= 4 else "-")
        draw.text((1750, (ry1 + ry2) // 2), st_lbl, fill=pos_color, font=font_tr_bold, anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class LeagueTableBuilder:
    """Gerador visual de Tabela de Liga / Pontos Corridos em Pillow Puro com Cache."""

    async def generate_table(
        self,
        guild: discord.Guild,
        tournament: dict,
        standings: List[dict],
        matches: Optional[List[dict]] = None,
        use_cache: bool = True
    ) -> BytesIO:
        t_id = tournament.get("id", 0)
        state_hash = _get_league_state_hash(tournament, standings, matches)
        prefix = f"table_{t_id}"

        if use_cache:
            cached_buf = _read_cached_image(prefix, state_hash)
            if cached_buf is not None:
                return cached_buf

        loop = asyncio.get_running_loop()
        png_bytes = await loop.run_in_executor(
            None,
            _sync_draw_league_table,
            tournament,
            standings
        )

        _save_cached_image(prefix, state_hash, png_bytes)
        buffer = BytesIO(png_bytes)
        buffer.seek(0)
        return buffer


# =============================================================================
# 5. HIGHLIGHTS BUILDER (1300x850 - PIL PURO)
# =============================================================================

def _sync_draw_highlight_slide(
    title: str,
    subtitle: str,
    category_icon: str,
    theme_color: Tuple[int, int, int, int],
    winners: List[dict],
    year: int
) -> bytes:
    img = Image.new("RGBA", (1300, 850), (6, 9, 18, 255))
    draw = ImageDraw.Draw(img)

    _draw_linear_gradient_bar(img, (0, 0, 1300, 6), (theme_color[0], theme_color[1], theme_color[2]), (255, 215, 0), radius=0)

    # Badge Ano
    font_badge = _get_font(15, bold=True)
    b_text = f"★ RETROSPECTIVA BMIA • {year} ★"
    draw.rounded_rectangle((650 - 150, 40, 650 + 150, 75), radius=18, fill=(theme_color[0], theme_color[1], theme_color[2], 40), outline=theme_color, width=1)
    draw.text((650, 57), b_text, fill=theme_color, font=font_badge, anchor="mm")

    # Título & Subtítulo
    font_title = _get_font(34, bold=True)
    font_sub = _get_font(18, bold=False)
    draw.text((650, 120), f"{category_icon} {title.upper()}", fill=(255, 255, 255, 255), font=font_title, anchor="mm")
    draw.text((650, 160), subtitle, fill=(148, 163, 184, 255), font=font_sub, anchor="mm")

    # Card Principal Central
    card_x1, card_y1, card_x2, card_y2 = 250, 210, 1050, 740
    _draw_glow_rect(img, (card_x1, card_y1, card_x2, card_y2), radius=20, glow_color=(theme_color[0], theme_color[1], theme_color[2], 80), glow_radius=12, fill_color=(15, 23, 42, 240), outline_color=theme_color, width=2)

    if winners:
        top_winner = winners[0]
        w_name = top_winner.get("username") or top_winner.get("name") or top_winner.get("activity_name") or "Destaque"
        w_val = top_winner.get("value") or top_winner.get("value_seconds") or 0

        # Avatar do Campeão da Categoria
        _draw_circle_avatar(img, top_winner.get("avatar_bytes"), (650, 330), size=140, border_color=theme_color, border_width=4, fallback_initial=w_name[0])

        font_w_name = _get_font(32, bold=True)
        font_w_val = _get_font(22, bold=True)

        draw.text((650, 440), "👑 1º LUGAR OFICIAL", fill=(255, 215, 0, 255), font=_get_font(16, bold=True), anchor="mm")
        draw.text((650, 480), w_name, fill=(255, 255, 255, 255), font=font_w_name, anchor="mm")

        # Placar / Score
        val_str = f"Registro: {w_val:,}".replace(",", ".")
        draw.rounded_rectangle((500, 530, 800, 580), radius=10, fill=(255, 255, 255, 15), outline=theme_color, width=1)
        draw.text((650, 555), val_str, fill=theme_color, font=font_w_val, anchor="mm")

    # Rodapé
    font_footer = _get_font(13, bold=False)
    draw.text((60, 815), "⚡ BMIA Community Retrospective Awards", fill=(100, 116, 139, 255), font=font_footer)
    draw.text((1240, 815), f"ANO DE {year}", fill=theme_color, font=font_footer, anchor="ra")

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


class HighlightsBuilder:
    """Construtor e renderizador visual de alta performance para Destaques do Ano em Pillow Puro."""

    @classmethod
    async def generate_all_slides_files(
        cls,
        guild: Optional[discord.Guild],
        year: int,
        highlights_data: Dict[str, Any],
        top_clip: Optional[Dict[str, Any]] = None,
        categories: Optional[List[Dict[str, Any]]] = None
    ) -> List[discord.File]:
        if categories is None:
            from commands.stats_commands import HIGHLIGHTS_CATEGORIES
            categories = HIGHLIGHTS_CATEGORIES

        files = []
        loop = asyncio.get_running_loop()

        for idx, cat in enumerate(categories):
            cat_id = cat["id"]
            title = cat.get("title") or cat.get("label") or "Destaque"
            subtitle = cat.get("subtitle") or cat.get("description") or "Melhores momentos do ano"
            icon = cat.get("icon", "🏆")
            winners = highlights_data.get(cat_id, [])

            png_bytes = await loop.run_in_executor(
                None,
                _sync_draw_highlight_slide,
                title,
                subtitle,
                icon,
                (0, 240, 255, 255),
                winners,
                year
            )
            buf = BytesIO(png_bytes)
            buf.seek(0)
            files.append(discord.File(fp=buf, filename=f"destaques_{idx+1:02d}_{cat_id}.png"))

        return files
