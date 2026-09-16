import discord
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
from typing import Optional, List, Any, Dict
import base64
import asyncio

class PodiumBuilder:
    """
    Gerador visual de Pódio e Ranking Periódico em alta fidelidade (1300x850)
    utilizando HTML5/CSS3 modernos (Glassmorphism, Neon Glows, Gradients e Tipografia Esports)
    renderizados via Playwright.
    """

    async def _get_avatar_data_uri(self, member: Optional[discord.Member], user_data: dict) -> str:
        """Obtém o avatar do membro em base64 data URI ou fallback SVG sofisticado."""
        import base64
        try:
            if member:
                avatar_asset = member.display_avatar.with_size(128)
                avatar_bytes = await avatar_asset.read()
                b64 = base64.b64encode(avatar_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
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
        """Obtém o ícone do servidor em base64 data URI."""
        import base64
        if not guild or not guild.icon:
            return None
        try:
            icon_asset = guild.icon.with_size(128)
            icon_bytes = await icon_asset.read()
            b64 = base64.b64encode(icon_bytes).decode("utf-8")
            return f"data:image/png;base64,{b64}"
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
        
        # Mapeamento para visual: idx 0 = 2º, idx 1 = 1º, idx 2 = 3º
        slot_configs = [
            {"rank": 2, "color": "#00f0ff", "border": "rgba(0, 240, 255, 0.5)", "pedestal_h": "130px", "badge": "2º LUGAR", "crown": "🥈", "avatar_size": "95px"},
            {"rank": 1, "color": "#ffd700", "border": "rgba(255, 215, 0, 0.6)", "pedestal_h": "170px", "badge": "1º LUGAR", "crown": "👑", "avatar_size": "115px"},
            {"rank": 3, "color": "#b026ff", "border": "rgba(176, 38, 255, 0.5)", "pedestal_h": "100px", "badge": "3º LUGAR", "crown": "🥉", "avatar_size": "85px"}
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
        via Playwright 1300x850.
        """
        from playwright.async_api import async_playwright

        guild_name = guild.name if guild else "Servidor BMIA"
        guild_icon_uri = await self._get_guild_icon_data_uri(guild)

        top_3 = []
        others = []

        for i, user_data in enumerate(top_users[:10]):
            uid = user_data.get("user_id", 0)
            member = guild.get_member(uid) if guild else None
            avatar_uri = await self._get_avatar_data_uri(member, user_data)
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
            await page.set_content(html_code, wait_until="networkidle")
            element = await page.query_selector('.card-container')
            if element:
                screenshot_bytes = await element.screenshot(type="png", omit_background=True)
            else:
                screenshot_bytes = await page.screenshot(type="png", omit_background=True)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer



class BracketBuilder:
    """
    Gerador visual de chaveamento e confrontos de esports em alta fidelidade (1920x1080)
    utilizando templates HTML5/CSS3 modernos (Glassmorphism, Neon Glows, Gradients e Tipografia Esports)
    renderizados de forma ultra-rápida via Playwright.
    """

    def __init__(self):
        self._browser = None

    async def _get_avatar_data_uri(self, member: Optional[discord.Member], user_data: dict) -> str:
        """Obtém o avatar do membro em base64 data URI ou gera um fallback SVG sofisticado."""
        import base64
        try:
            if member:
                avatar_asset = member.display_avatar.with_size(128)
                avatar_bytes = await avatar_asset.read()
                b64 = base64.b64encode(avatar_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
        except Exception:
            pass

        # Fallback SVG moderno com gradiente e inicial
        name = user_data.get("username") or (member.display_name if member else "P")
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
        """Obtém o ícone do servidor em base64 data URI."""
        import base64
        if not guild.icon:
            return None
        try:
            icon_asset = guild.icon.with_size(128)
            icon_bytes = await icon_asset.read()
            b64 = base64.b64encode(icon_bytes).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        except Exception:
            return None

    def _build_html_template(
        self,
        tournament: dict,
        participants: List[dict],
        teams_data: List[List[dict]],
        guild_icon_uri: Optional[str],
        bracket_mode: int,
        is_2v2: bool,
        matches: Optional[List[dict]] = None
    ) -> str:
        """Gera o código HTML/CSS completo para renderização."""
        title = str(tournament.get("name", "TORNEIO OFICIAL")).upper()
        game = str(tournament.get("game_name", "Geral")).upper()
        fmt_raw = str(tournament.get("format", "1v1")).upper()
        prize = str(tournament.get("prize") or "Glória e Pontos")
        max_participants = int(tournament.get("max_participants") or 16)
        is_shuffled = tournament.get("is_shuffled", False)
        winner_id = tournament.get("winner_id")
        final_score_str = tournament.get("final_score")

        if winner_id:
            status_text = "TORNEIO CONCLUÍDO"
            status_class = "status-completed"
        elif is_shuffled:
            status_text = "CHAVEAMENTO OFICIAL"
            status_class = "status-official"
        elif tournament.get("status") == "open":
            status_text = "PRÉVIA DE INSCRIÇÕES"
            status_class = "status-open"
        else:
            status_text = "CHAVEAMENTO PRELIMINAR"
            status_class = "status-prelim"

        # Mapa de partidas por número
        matches_by_num = {m["match_number"]: m for m in (matches or [])}

        # Cache de avatar e nome por user_id
        user_info_map = {}
        for team in teams_data:
            for p in team:
                user_info_map[p.get("user_id")] = p

        # Identifica a equipe vencedora se o torneio estiver concluído
        winner_team_idx = None
        winner_team_members = []
        if winner_id:
            for t_idx, team in enumerate(teams_data):
                for p in team:
                    if str(p.get("user_id")) == str(winner_id):
                        winner_team_idx = t_idx
                        winner_team_members = team
                        break
                if winner_team_idx is not None:
                    break

        # Conteúdo do corpo conforme o modo de chaveamento
        content_html = ""

        # ---------------------------------------------------------------------
        # MODO A: 2 TIMES (SHOWDOWN DIRETO / GRANDE FINAL)
        # ---------------------------------------------------------------------
        if bracket_mode == 2:
            team_left = teams_data[0] if len(teams_data) > 0 else []
            team_right = teams_data[1] if len(teams_data) > 1 else []

            # Placar da Grande Final
            m1 = matches_by_num.get(1)
            score_left = None
            score_right = None
            if m1 and m1.get("status") == "completed":
                score_left = m1.get("score_a")
                score_right = m1.get("score_b")
            elif final_score_str:
                import re
                nums = re.findall(r'\d+', str(final_score_str))
                if len(nums) >= 2:
                    score_left = int(nums[0])
                    score_right = int(nums[1])

            def render_showdown_team(team, is_left: bool, t_idx: int):
                is_winner = (winner_team_idx is not None and winner_team_idx == t_idx)
                is_runner = (winner_team_idx is not None and winner_team_idx != t_idx)

                corner_class = "corner-blue" if is_left else "corner-purple"
                if is_winner:
                    corner_class += " is-winner-card"
                elif is_runner:
                    corner_class += " is-runner-card"

                if is_winner:
                    corner_tag = "👑 DUPLA CAMPEÃ" if is_2v2 else "👑 CAMPEÃO"
                elif is_runner:
                    corner_tag = "🥈 VICE-CAMPEÕES" if is_2v2 else "🥈 VICE-CAMPEÃO"
                else:
                    corner_tag = ("⚡ DUPLA AZUL" if is_2v2 else "⚡ LADO AZUL") if is_left else ("🔥 DUPLA ROXA" if is_2v2 else "🔥 LADO ROXO")
                
                rows_html = ""
                if not team:
                    rows_html = """
                    <div class="player-row empty-slot">
                        <div class="avatar-placeholder">?</div>
                        <div class="player-info">
                            <span class="player-name text-muted">Aguardando Inscrição</span>
                            <span class="player-sub">Vaga aberta</span>
                        </div>
                    </div>
                    """
                elif is_2v2:
                    p1 = team[0]
                    sub1 = "👑 Campeão do Torneio" if is_winner else ("🥈 Vice-Campeão" if is_runner else "Capitão / Jogador 1")
                    rows_html += f"""
                    <div class="player-row">
                        <img class="player-avatar" src="{p1['avatar_uri']}" alt="" />
                        <div class="player-info">
                            <span class="player-name">{p1['name']}</span>
                            <span class="player-sub">{sub1}</span>
                        </div>
                    </div>
                    """
                    if len(team) > 1:
                        p2 = team[1]
                        sub2 = "👑 Campeão do Torneio" if is_winner else ("🥈 Vice-Campeão" if is_runner else "Parceiro / Jogador 2")
                        rows_html += f"""
                        <div class="player-row">
                            <img class="player-avatar" src="{p2['avatar_uri']}" alt="" />
                            <div class="player-info">
                                <span class="player-name">{p2['name']}</span>
                                <span class="player-sub">{sub2}</span>
                            </div>
                        </div>
                        """
                    else:
                        rows_html += """
                        <div class="player-row empty-slot">
                            <div class="avatar-placeholder plus">+</div>
                            <div class="player-info">
                                <span class="player-name text-muted">Aguardando 2º Jogador</span>
                                <span class="player-sub">Vaga disponível</span>
                            </div>
                        </div>
                        """
                else:
                    p1 = team[0]
                    sub1 = "👑 Grande Campeão" if is_winner else ("🥈 Vice-Campeão" if is_runner else "Finalista Oficial")
                    rows_html += f"""
                    <div class="player-row solo">
                        <img class="player-avatar solo-avatar" src="{p1['avatar_uri']}" alt="" />
                        <div class="player-info">
                            <span class="player-name solo-name">{p1['name']}</span>
                            <span class="player-sub">{sub1}</span>
                        </div>
                    </div>
                    """

                return f"""
                <div class="showdown-card {corner_class}">
                    <div class="card-tag">{corner_tag}</div>
                    <div class="players-container">
                        {rows_html}
                    </div>
                </div>
                """

            if winner_team_members:
                w_names = " & ".join([m["name"] for m in winner_team_members])
                mini_avatars_html = "".join([
                    f'<img class="trophy-mini-avatar" src="{m["avatar_uri"]}" alt="" />'
                    for m in winner_team_members if m.get("avatar_uri")
                ])
                podium_title = "★ DUPLA CAMPEÃ DO TORNEIO ★" if is_2v2 else "★ CAMPEÃO DO TORNEIO ★"
                score_info = f'<span class="trophy-score-tag">PLACAR FINAL: {score_left} x {score_right}</span>' if (score_left is not None and score_right is not None) else ''
                trophy_content_html = f"""
                <div class="trophy-winner-box">
                    <span class="trophy-winner-name">Vencedores: {w_names}</span>
                    <div class="trophy-mini-avatars">{mini_avatars_html}</div>
                    {score_info}
                </div>
                """
            else:
                podium_title = "★ CAMPEÃO DO TORNEIO ★"
                trophy_content_html = '<span class="trophy-winner-tbd">A DEFINIR NA GRANDE FINAL</span>'

            # Unidade central VS com placares
            score_left_html = f'<div class="score-badge score-left {"score-winner" if winner_team_idx == 0 else ""}">{score_left}</div>' if score_left is not None else ''
            score_right_html = f'<div class="score-badge score-right {"score-winner" if winner_team_idx == 1 else ""}">{score_right}</div>' if score_right is not None else ''

            content_html = f"""
            <div class="showdown-wrapper">
                <div class="round-header">★ GRANDE FINAL — CONFRONTO DIRETO ★</div>
                
                <div class="showdown-arena">
                    {render_showdown_team(team_left, True, 0)}
                    
                    <div class="center-connector">
                        <div class="laser-line laser-left"></div>
                        <div class="vs-unit">
                            {score_left_html}
                            <div class="vs-badge">
                                <span class="vs-text">VS</span>
                            </div>
                            {score_right_html}
                        </div>
                        <div class="laser-line laser-right"></div>
                    </div>
                    
                    {render_showdown_team(team_right, False, 1)}
                </div>

                <div class="trophy-podium">
                    <div class="laser-vertical"></div>
                    <div class="trophy-card">
                        <div class="trophy-icon">🏆</div>
                        <div class="trophy-details">
                            <span class="trophy-title">{podium_title}</span>
                            {trophy_content_html}
                        </div>
                    </div>
                </div>
            </div>
            """

        # ---------------------------------------------------------------------
        # MODO B & C: 4 ou 8 TIMES (SEMIFINAIS / QUARTAS + GRANDE FINAL)
        # ---------------------------------------------------------------------
        else:
            def resolve_team_display(team_ids, fallback_label: str):
                if not team_ids:
                    return {"name": fallback_label, "avatar_uri": "", "is_empty": True}
                names = []
                av_uri = ""
                for uid in team_ids:
                    info = user_info_map.get(uid)
                    if info:
                        names.append(info["name"])
                        if not av_uri and info.get("avatar_uri"):
                            av_uri = info["avatar_uri"]
                    else:
                        names.append(f"Jogador {uid}")
                full_name = " & ".join(names) if names else fallback_label
                return {"name": full_name, "avatar_uri": av_uri, "is_empty": False}

            def render_tree_match(match_num: int, fallback_label_a="Time A", fallback_label_b="Time B"):
                m = matches_by_num.get(match_num)
                team_a_ids = m.get("team_a_ids") if m else None
                team_b_ids = m.get("team_b_ids") if m else None
                is_done = bool(m and m.get("status") == "completed")
                score_a = m.get("score_a", 0) if (m and is_done) else None
                score_b = m.get("score_b", 0) if (m and is_done) else None
                winner_ids = m.get("winner_team_ids") if m else []

                info_a = resolve_team_display(team_a_ids, fallback_label_a)
                info_b = resolve_team_display(team_b_ids, fallback_label_b)

                a_is_winner = is_done and (winner_ids and team_a_ids == winner_ids)
                b_is_winner = is_done and (winner_ids and team_b_ids == winner_ids)

                return f"""
                <div class="match-box {'match-completed' if is_done else ''}">
                    <div class="match-participant {'winner-side' if a_is_winner else ('loser-side' if (is_done and b_is_winner) else '')}">
                        <div class="participant-left">
                            {f'<img class="mini-avatar" src="{info_a["avatar_uri"]}" />' if info_a["avatar_uri"] else '<div class="mini-ph">?</div>'}
                            <span class="p-name">{(info_a['name'][:15] + '...') if len(info_a['name']) > 15 else info_a['name']}</span>
                        </div>
                        {f'<span class="match-score-pill">{score_a}</span>' if score_a is not None else ''}
                    </div>
                    <div class="match-divider"></div>
                    <div class="match-participant {'winner-side' if b_is_winner else ('loser-side' if (is_done and a_is_winner) else '')}">
                        <div class="participant-left">
                            {f'<img class="mini-avatar" src="{info_b["avatar_uri"]}" />' if info_b["avatar_uri"] else '<div class="mini-ph">?</div>'}
                            <span class="p-name">{(info_b['name'][:15] + '...') if len(info_b['name']) > 15 else info_b['name']}</span>
                        </div>
                        {f'<span class="match-score-pill">{score_b}</span>' if score_b is not None else ''}
                    </div>
                </div>
                """

            w_label = " & ".join([m["name"] for m in winner_team_members]) if winner_team_members else "A Definir..."
            if bracket_mode == 4:
                content_html = f"""
                <div class="bracket-tree-wrapper four-teams">
                    <div class="column-round">
                        <div class="column-title">SEMIFINAL 1</div>
                        {render_tree_match(1, "Time 1", "Time 2")}
                    </div>
                    
                    <div class="column-round center-col">
                        <div class="column-title gold-title">★ GRANDE FINAL ★</div>
                        {render_tree_match(3, "Venc. Semi 1", "Venc. Semi 2")}
                        <div class="trophy-card mini">
                            <div class="trophy-icon">🏆</div>
                            <div class="trophy-details">
                                <span class="trophy-title">CAMPEÃO</span>
                                <span class="trophy-winner">{w_label}</span>
                            </div>
                        </div>
                    </div>

                    <div class="column-round">
                        <div class="column-title">SEMIFINAL 2</div>
                        {render_tree_match(2, "Time 3", "Time 4")}
                    </div>
                </div>
                """
            else:
                content_html = f"""
                <div class="bracket-tree-wrapper eight-teams">
                    <div class="column-round">
                        <div class="column-title">QUARTAS</div>
                        {render_tree_match(1, "Time 1", "Time 2")}
                        {render_tree_match(2, "Time 3", "Time 4")}
                    </div>
                    <div class="column-round">
                        <div class="column-title">SEMIFINAIS</div>
                        {render_tree_match(5, "Venc. Q1", "Venc. Q2")}
                    </div>
                    <div class="column-round center-col">
                        <div class="column-title gold-title">★ FINAL ★</div>
                        {render_tree_match(7, "Finalista 1", "Finalista 2")}
                        <div class="trophy-card mini">
                            <div class="trophy-icon">🏆</div>
                            <div class="trophy-details">
                                <span class="trophy-title">CAMPEÃO</span>
                                <span class="trophy-winner">{w_label}</span>
                            </div>
                        </div>
                    </div>
                    <div class="column-round">
                        <div class="column-title">SEMIFINAIS</div>
                        {render_tree_match(6, "Venc. Q3", "Venc. Q4")}
                    </div>
                    <div class="column-round">
                        <div class="column-title">QUARTAS</div>
                        {render_tree_match(3, "Time 5", "Time 6")}
                        {render_tree_match(4, "Time 7", "Time 8")}
                    </div>
                </div>
                """

        # HTML / CSS Completo
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700;800&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            width: 1920px;
            height: 1080px;
            background-color: #060913;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 90% 20%, rgba(176, 38, 255, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 50% 60%, rgba(255, 215, 0, 0.08) 0%, transparent 50%),
                linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
            background-size: 100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px;
            font-family: 'Inter', sans-serif;
            color: #ffffff;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            position: relative;
        }}
        
        /* Neon Top Line */
        .neon-top-bar {{
            height: 6px;
            width: 100%;
            background: linear-gradient(90deg, #00f0ff 0%, #b026ff 50%, #ffd700 100%);
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.8);
        }}

        /* Header */
        .header {{
            padding: 28px 70px 20px 70px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(8, 12, 24, 0.6);
            backdrop-filter: blur(12px);
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 24px;
        }}
        .guild-logo {{
            width: 88px;
            height: 88px;
            border-radius: 50%;
            border: 2px solid #00f0ff;
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.4);
            object-fit: cover;
        }}
        .header-title-box {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .header-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 34px;
            font-weight: 900;
            letter-spacing: 2px;
            color: #ffffff;
            text-shadow: 0 0 25px rgba(0, 240, 255, 0.4), 0 0 50px rgba(0, 240, 255, 0.2);
        }}
        .header-meta {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .meta-pill {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 4px 14px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(0, 240, 255, 0.3);
            border-radius: 8px;
            color: #00f0ff;
        }}
        .meta-pill.prize {{
            border-color: rgba(255, 215, 0, 0.4);
            color: #ffd700;
        }}
        .status-badge {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 10px 22px;
            border-radius: 30px;
            background: rgba(14, 20, 36, 0.9);
            border: 2px solid #22c55e;
            color: #22c55e;
            box-shadow: 0 0 25px rgba(34, 197, 94, 0.3);
        }}
        .status-badge::before {{
            content: '';
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: currentColor;
            box-shadow: 0 0 12px currentColor;
        }}
        .status-badge.status-official {{
            border-color: #00f0ff;
            color: #00f0ff;
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.4);
        }}
        .status-badge.status-completed {{
            border-color: #ffd700;
            color: #ffd700;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.4);
        }}

        /* Main Content Arena */
        .arena-container {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px 60px;
        }}

        /* ----------------------------------------------------------- */
        /* SHOWDOWN 2-TEAM LAYOUT                                      */
        /* ----------------------------------------------------------- */
        .showdown-wrapper {{
            width: 100%;
            max-width: 1760px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 25px;
        }}
        .round-header {{
            font-family: 'Orbitron', sans-serif;
            font-size: 26px;
            font-weight: 800;
            letter-spacing: 3px;
            color: #ffd700;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.6);
        }}
        .showdown-arena {{
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: relative;
        }}
        .showdown-card {{
            width: 600px;
            height: 250px;
            background: linear-gradient(135deg, rgba(13, 20, 38, 0.85) 0%, rgba(18, 28, 55, 0.7) 100%);
            border-radius: 24px;
            padding: 22px 28px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            backdrop-filter: blur(20px);
            position: relative;
            transition: all 0.3s ease;
        }}
        .showdown-card.corner-blue {{
            border: 2px solid #00f0ff;
            box-shadow: 0 10px 40px rgba(0, 240, 255, 0.2), inset 0 0 25px rgba(0, 240, 255, 0.08);
        }}
        .showdown-card.corner-purple {{
            border: 2px solid #b026ff;
            box-shadow: 0 10px 40px rgba(176, 38, 255, 0.2), inset 0 0 25px rgba(176, 38, 255, 0.08);
        }}
        .showdown-card.is-winner-card {{
            border: 2px solid #ffd700 !important;
            box-shadow: 0 10px 50px rgba(255, 215, 0, 0.45), inset 0 0 35px rgba(255, 215, 0, 0.15) !important;
            background: linear-gradient(135deg, rgba(38, 30, 10, 0.95) 0%, rgba(24, 32, 60, 0.85) 100%) !important;
        }}
        .showdown-card.is-winner-card .card-tag {{
            color: #ffd700 !important;
            border-color: rgba(255, 215, 0, 0.7) !important;
            background: rgba(255, 215, 0, 0.18) !important;
            box-shadow: 0 0 18px rgba(255, 215, 0, 0.4) !important;
        }}
        .showdown-card.is-winner-card .player-avatar {{
            border-color: #ffd700 !important;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.8) !important;
        }}
        .showdown-card.is-winner-card .player-sub {{
            color: #ffd700 !important;
            font-weight: 700 !important;
        }}
        .showdown-card.is-runner-card {{
            opacity: 0.82;
            border-color: rgba(148, 163, 184, 0.5) !important;
        }}
        .showdown-card.is-runner-card .card-tag {{
            color: #cbd5e1 !important;
            border-color: rgba(148, 163, 184, 0.5) !important;
        }}
        .card-tag {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 2px;
            padding: 4px 14px;
            border-radius: 6px;
            background: rgba(0, 0, 0, 0.4);
            align-self: flex-start;
        }}
        .corner-blue .card-tag {{
            color: #00f0ff;
            border: 1px solid rgba(0, 240, 255, 0.4);
        }}
        .corner-purple .card-tag {{
            color: #b026ff;
            border: 1px solid rgba(176, 38, 255, 0.4);
        }}
        .players-container {{
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .player-row {{
            display: flex;
            align-items: center;
            gap: 18px;
            background: rgba(255, 255, 255, 0.03);
            padding: 10px 18px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }}
        .player-avatar {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #ffffff;
            box-shadow: 0 0 18px rgba(255, 255, 255, 0.3);
        }}
        .corner-blue .player-avatar {{
            border-color: #00f0ff;
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.5);
        }}
        .corner-purple .player-avatar {{
            border-color: #b026ff;
            box-shadow: 0 0 20px rgba(176, 38, 255, 0.5);
        }}
        .player-info {{
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}
        .player-name {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 26px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.5px;
        }}
        .player-sub {{
            font-size: 13px;
            color: #94a3b8;
            font-weight: 500;
        }}
        .avatar-placeholder {{
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            border: 2px dashed #94a3b8;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            font-weight: 700;
            color: #94a3b8;
        }}
        .avatar-placeholder.plus {{
            border-color: #00f0ff;
            color: #00f0ff;
            background: rgba(0, 240, 255, 0.06);
        }}
        .text-muted {{
            color: #94a3b8 !important;
        }}
        .player-row.solo {{
            padding: 16px 24px;
            gap: 24px;
        }}
        .player-avatar.solo-avatar {{
            width: 80px;
            height: 80px;
        }}
        .player-name.solo-name {{
            font-size: 32px;
        }}

        /* VS Center Unit with Scores */
        .center-connector {{
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 1;
            position: relative;
        }}
        .laser-line {{
            flex: 1;
            height: 4px;
            background: linear-gradient(90deg, #00f0ff, #b026ff);
            box-shadow: 0 0 20px #00f0ff, 0 0 10px #b026ff;
        }}
        .vs-unit {{
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 2;
        }}
        .score-badge {{
            font-family: 'Orbitron', sans-serif;
            font-size: 30px;
            font-weight: 900;
            padding: 8px 18px;
            border-radius: 12px;
            background: rgba(10, 15, 30, 0.95);
            letter-spacing: 1px;
        }}
        .score-badge.score-left {{
            border: 2px solid #00f0ff;
            color: #00f0ff;
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
            text-shadow: 0 0 12px rgba(0, 240, 255, 0.8);
        }}
        .score-badge.score-right {{
            border: 2px solid #b026ff;
            color: #b026ff;
            box-shadow: 0 0 20px rgba(176, 38, 255, 0.4);
            text-shadow: 0 0 12px rgba(176, 38, 255, 0.8);
        }}
        .score-badge.score-winner {{
            border-color: #ffd700 !important;
            color: #ffd700 !important;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.9) !important;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.5) !important;
        }}
        .vs-badge {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: radial-gradient(circle, #1c1033 0%, #0c0818 100%);
            border: 3px solid #b026ff;
            box-shadow: 0 0 40px rgba(176, 38, 255, 0.6), inset 0 0 30px rgba(0, 240, 255, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .vs-text {{
            font-family: 'Orbitron', sans-serif;
            font-size: 44px;
            font-weight: 900;
            font-style: italic;
            background: linear-gradient(180deg, #ffffff 0%, #00f0ff 50%, #b026ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 15px rgba(0, 240, 255, 0.9));
        }}

        /* Trophy Box */
        .trophy-podium {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .laser-vertical {{
            width: 4px;
            height: 25px;
            background: linear-gradient(180deg, #b026ff, #ffd700);
            box-shadow: 0 0 15px #ffd700;
        }}
        .trophy-card {{
            display: flex;
            align-items: center;
            gap: 24px;
            background: linear-gradient(135deg, rgba(35, 28, 10, 0.95) 0%, rgba(45, 36, 15, 0.85) 100%);
            border: 2px solid #ffd700;
            border-radius: 20px;
            padding: 16px 36px;
            box-shadow: 0 0 50px rgba(255, 215, 0, 0.35), inset 0 0 25px rgba(255, 215, 0, 0.12);
            backdrop-filter: blur(16px);
        }}
        .trophy-icon {{
            font-size: 56px;
            filter: drop-shadow(0 0 25px rgba(255, 215, 0, 0.9));
        }}
        .trophy-details {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .trophy-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 17px;
            font-weight: 800;
            letter-spacing: 2.5px;
            color: #ffd700;
            text-shadow: 0 0 15px rgba(255, 215, 0, 0.6);
        }}
        .trophy-winner-box {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .trophy-winner-name {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 28px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 1px;
            text-shadow: 0 0 12px rgba(255, 255, 255, 0.5);
        }}
        .trophy-score-tag {{
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 3px 10px;
            border-radius: 6px;
            background: rgba(255, 215, 0, 0.15);
            border: 1px solid rgba(255, 215, 0, 0.4);
            color: #ffd700;
        }}
        .trophy-winner-tbd {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 22px;
            font-weight: 700;
            color: #94a3b8;
            letter-spacing: 1px;
        }}
        .trophy-mini-avatars {{
            display: flex;
            align-items: center;
            margin-left: 4px;
        }}
        .trophy-mini-avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: 2px solid #ffd700;
            box-shadow: 0 0 12px rgba(255, 215, 0, 0.6);
            margin-left: -10px;
            object-fit: cover;
        }}
        .trophy-mini-avatar:first-child {{
            margin-left: 0;
        }}

        /* ----------------------------------------------------------- */
        /* TREE BRACKETS (4 & 8 TEAMS)                                 */
        /* ----------------------------------------------------------- */
        .bracket-tree-wrapper {{
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
        }}
        .column-round {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 25px;
            flex: 1;
        }}
        .column-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 2px;
            color: #94a3b8;
        }}
        .column-title.gold-title {{
            color: #ffd700;
            text-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
        }}
        .match-box {{
            width: 100%;
            max-width: 290px;
            background: rgba(15, 23, 42, 0.88);
            border: 2px solid rgba(0, 240, 255, 0.25);
            border-radius: 14px;
            padding: 10px 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            backdrop-filter: blur(12px);
        }}
        .match-box.match-completed {{
            border-color: rgba(255, 215, 0, 0.35);
        }}
        .match-participant {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }}
        .participant-left {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex: 1;
            overflow: hidden;
        }}
        .match-score-pill {{
            font-family: 'Orbitron', sans-serif;
            font-size: 15px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        .winner-side .match-score-pill {{
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border-color: rgba(255, 215, 0, 0.6);
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.4);
        }}
        .winner-side .p-name {{
            color: #ffd700 !important;
            font-weight: 800;
        }}
        .loser-side {{
            opacity: 0.55;
        }}
        .mini-avatar {{
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 1px solid #00f0ff;
            object-fit: cover;
        }}
        .mini-ph {{
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.05);
            border: 1px dashed #94a3b8;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            color: #94a3b8;
        }}
        .p-name {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .match-divider {{
            height: 1px;
            background: rgba(255, 255, 255, 0.08);
        }}
        .trophy-card.mini {{
            padding: 10px 20px;
            gap: 14px;
            margin-top: 15px;
        }}
        .trophy-card.mini .trophy-icon {{
            font-size: 32px;
        }}
        .trophy-card.mini .trophy-title {{
            font-size: 14px;
        }}
        .trophy-card.mini .trophy-winner {{
            font-size: 18px;
        }}

        /* Footer */
        .footer {{
            padding: 16px 70px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            background: rgba(6, 9, 18, 0.8);
            font-size: 14px;
            color: #64748b;
        }}
        .footer-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .footer-tag {{
            color: #00f0ff;
            font-weight: 600;
            font-family: 'Rajdhani', sans-serif;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>
    <div class="neon-top-bar"></div>
    
    <header class="header">
        <div class="header-left">
            {f'<img class="guild-logo" src="{guild_icon_uri}" alt="" />' if guild_icon_uri else ''}
            <div class="header-title-box">
                <h1 class="header-title">{title}</h1>
                <div class="header-meta">
                    <span class="meta-pill">🎮 JOGO: {game}</span>
                    <span class="meta-pill">⚔️ FORMATO: {fmt_raw}</span>
                    <span class="meta-pill prize">🎁 PRÊMIO: {prize}</span>
                    <span class="meta-pill">👥 INSCRITOS: {len(participants)}/{max_participants}</span>
                </div>
            </div>
        </div>
        <div class="status-badge {status_class}">{status_text}</div>
    </header>

    <main class="arena-container">
        {content_html}
    </main>

    <footer class="footer">
        <div class="footer-left">
            <span>⚡ Gerado automaticamente pelo sistema BMIA Esports</span>
            <span>•</span>
            <span>Use <strong style="color: #94a3b8;">/torneio status</strong> para detalhes</span>
        </div>
        <div class="footer-tag">BDP COMMUNITY • 2026</div>
    </footer>
</body>
</html>"""

    async def generate_bracket(
        self,
        guild: discord.Guild,
        tournament: dict,
        participants: List[dict],
        matches: Optional[List[dict]] = None
    ) -> BytesIO:
        """
        Renderiza o chaveamento do torneio em 1920x1080 com HTML/CSS de altíssima fidelidade.
        """
        from playwright.async_api import async_playwright

        fmt_raw = str(tournament.get("format", "1v1")).lower().strip()
        is_2v2 = any(k in fmt_raw for k in ["2v2", "2x2", "dupla", "duplas"])
        is_3v3 = any(k in fmt_raw for k in ["3v3", "3x3", "trio", "trios"])
        team_size = 2 if is_2v2 else (3 if is_3v3 else 1)

        if matches and len(matches) > 0:
            if len(matches) == 1:
                bracket_mode = 2
            elif len(matches) <= 3:
                bracket_mode = 4
            else:
                bracket_mode = 8
        else:
            max_participants = int(tournament.get("max_participants") or 16)
            num_teams_target = max(2, max_participants // team_size)
            if num_teams_target <= 2:
                bracket_mode = 2
            elif num_teams_target <= 4:
                bracket_mode = 4
            else:
                bracket_mode = 8

        # Agrupa e carrega avatares em base64 data URI
        teams_data = []
        for i in range(0, len(participants), team_size):
            chunk = participants[i:i + team_size]
            team_members = []
            for p in chunk:
                m = guild.get_member(p.get("user_id", 0))
                raw_name = m.display_name if (m and hasattr(m, "display_name") and not str(type(m.display_name)).endswith("MagicMock'>")) else (p.get("username") or "Jogador")
                name = str(raw_name)
                av_uri = await self._get_avatar_data_uri(m, p)
                team_members.append({"name": name, "avatar_uri": av_uri, "user_id": p.get("user_id")})

            teams_data.append(team_members)

        # Preenche com slots vazios
        while len(teams_data) < bracket_mode:
            teams_data.append([])

        guild_icon_uri = await self._get_guild_icon_data_uri(guild)

        # Gera o HTML
        html_code = self._build_html_template(
            tournament=tournament,
            participants=participants,
            teams_data=teams_data,
            guild_icon_uri=guild_icon_uri,
            bracket_mode=bracket_mode,
            is_2v2=is_2v2,
            matches=matches
        )

        # Renderiza via Playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html_code, wait_until="networkidle")
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer


class LeagueTableBuilder:
    """
    Gerador visual de Tabela de Classificação de Liga / Pontos Corridos em alta fidelidade (1920x1080)
    utilizando HTML5/CSS3 modernos (Glassmorphism, Cyberpunk Neons, Gradients e Tipografia Esports)
    renderizados via Playwright.
    """

    async def _get_avatar_data_uri(self, member: Optional[discord.Member], user_data: dict) -> str:
        """Obtém o avatar do membro em base64 data URI ou fallback SVG."""
        import base64
        try:
            if member:
                avatar_asset = member.display_avatar.with_size(128)
                avatar_bytes = await avatar_asset.read()
                b64 = base64.b64encode(avatar_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
        except Exception:
            pass

        name = user_data.get("username") or (member.display_name if member else "P")
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
        import base64
        if not guild.icon:
            return None
        try:
            icon_asset = guild.icon.with_size(128)
            icon_bytes = await icon_asset.read()
            b64 = base64.b64encode(icon_bytes).decode("utf-8")
            return f"data:image/png;base64,{b64}"
        except Exception:
            return None

    def _build_html_template(
        self,
        tournament: dict,
        standings: List[dict],
        guild_icon_uri: Optional[str],
        matches: Optional[List[dict]] = None
    ) -> str:
        title = str(tournament.get("name", "LIGA OFICIAL")).upper()
        game = str(tournament.get("game_name", "Geral")).upper()
        fmt_raw = str(tournament.get("format", "1v1")).upper()
        prize = str(tournament.get("prize") or "Glória e Pontos")
        status = tournament.get("status", "open")

        if status == "completed":
            status_text = "LIGA CONCLUÍDA"
            status_class = "status-completed"
        elif tournament.get("is_shuffled"):
            status_text = "RODADAS EM ANDAMENTO"
            status_class = "status-official"
        else:
            status_text = "INSCRIÇÕES ABERTAS"
            status_class = "status-open"

        # Constrói linhas da tabela
        rows_html = []
        for s in standings:
            rank = s.get("rank", 1)
            rank_class = "rank-gold" if rank == 1 else ("rank-silver" if rank == 2 else ("rank-bronze" if rank == 3 else "rank-normal"))
            medal_badge = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"{rank:02d}"))

            # Avatares dos membros da equipe
            avatars_html = []
            for m in s.get("members", []):
                av = m.get("avatar_uri")
                if av:
                    avatars_html.append(f'<img class="row-avatar" src="{av}" alt="" />')
                else:
                    avatars_html.append('<div class="avatar-ph">?</div>')
            avatars_str = f'<div class="avatars-group">{"".join(avatars_html)}</div>'

            name_str = s.get("team_name", "Equipe")
            if len(name_str) > 22:
                name_str = name_str[:20] + "..."

            pts = s.get("points", 0)
            j = s.get("played", 0)
            v = s.get("won", 0)
            e = s.get("drawn", 0)
            d = s.get("lost", 0)
            gp = s.get("goals_for", 0)
            gc = s.get("goals_against", 0)
            sg = s.get("goal_diff", 0)
            sg_str = f"+{sg}" if sg > 0 else str(sg)
            sg_class = "diff-pos" if sg > 0 else ("diff-neg" if sg < 0 else "diff-zero")
            win_rate = s.get("win_rate", 0.0)

            row = f"""
            <tr class="table-row {rank_class}">
                <td class="col-rank">
                    <span class="rank-badge">{medal_badge}</span>
                </td>
                <td class="col-team">
                    <div class="team-cell">
                        {avatars_str}
                        <span class="team-name">{name_str}</span>
                    </div>
                </td>
                <td class="col-pts"><span class="pts-pill">{pts}</span></td>
                <td class="col-num">{j}</td>
                <td class="col-num win-text">{v}</td>
                <td class="col-num draw-text">{e}</td>
                <td class="col-num loss-text">{d}</td>
                <td class="col-num">{gp}</td>
                <td class="col-num">{gc}</td>
                <td class="col-num {sg_class}">{sg_str}</td>
                <td class="col-rate">{win_rate:.0f}%</td>
            </tr>
            """
            rows_html.append(row)

        table_rows_str = "\n".join(rows_html) if rows_html else """
        <tr><td colspan="11" style="text-align:center; padding: 40px; color:#94a3b8; font-size:22px;">Nenhum participante registrado ainda</td></tr>
        """

        # Resumo de partidas concluídas vs totais
        total_matches = len(matches) if matches else 0
        done_matches = sum(1 for m in (matches or []) if m.get("status") == "completed")
        progress_pct = round((done_matches / total_matches * 100)) if total_matches > 0 else 0

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            user-select: none;
        }}
        body {{
            width: 1920px;
            height: 1080px;
            background: #07090e;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(176, 38, 255, 0.12) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.9) 0%, #06080d 100%);
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            flex-direction: column;
            padding: 40px 60px;
            overflow: hidden;
            position: relative;
        }}

        /* Glow Elements */
        body::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #00f0ff, #b026ff, #ffd700, #00f0ff);
            box-shadow: 0 0 20px rgba(0, 240, 255, 0.8);
        }}

        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 28px;
        }}
        .header-left {{
            display: flex;
            align-items: center;
            gap: 24px;
        }}
        .guild-logo {{
            width: 80px;
            height: 80px;
            border-radius: 16px;
            border: 2px solid rgba(0, 240, 255, 0.6);
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.3);
            object-fit: cover;
        }}
        .header-title-box {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .header-title {{
            font-family: 'Orbitron', sans-serif;
            font-size: 34px;
            font-weight: 900;
            letter-spacing: 2px;
            color: #ffffff;
            text-shadow: 0 0 25px rgba(0, 240, 255, 0.4);
        }}
        .header-meta {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .meta-pill {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 4px 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(0, 240, 255, 0.3);
            border-radius: 8px;
            color: #00f0ff;
        }}
        .meta-pill.prize {{
            border-color: rgba(255, 215, 0, 0.4);
            color: #ffd700;
        }}
        .status-badge {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 1.5px;
            padding: 10px 22px;
            border-radius: 30px;
            background: rgba(14, 20, 36, 0.9);
            border: 2px solid #22c55e;
            color: #22c55e;
            box-shadow: 0 0 25px rgba(34, 197, 94, 0.3);
        }}
        .status-badge.status-official {{
            border-color: #00f0ff;
            color: #00f0ff;
            box-shadow: 0 0 25px rgba(0, 240, 255, 0.4);
        }}
        .status-badge.status-completed {{
            border-color: #ffd700;
            color: #ffd700;
            box-shadow: 0 0 25px rgba(255, 215, 0, 0.4);
        }}

        /* Main Container */
        .content-container {{
            flex: 1;
            display: flex;
            gap: 30px;
            align-items: flex-start;
        }}

        /* Table Card */
        .table-card {{
            flex: 3;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(0, 240, 255, 0.25);
            border-radius: 20px;
            padding: 24px;
            backdrop-filter: blur(20px);
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
            max-height: 750px;
            overflow: hidden;
        }}
        .standings-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 10px;
        }}
        .standings-table th {{
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: #94a3b8;
            padding: 10px 14px;
            text-align: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.08);
        }}
        .standings-table th.col-team-head {{
            text-align: left;
            padding-left: 20px;
        }}
        .table-row {{
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.2s ease;
        }}
        .table-row td {{
            padding: 12px 14px;
            text-align: center;
            font-size: 20px;
            font-weight: 700;
        }}
        .table-row td:first-child {{
            border-top-left-radius: 12px;
            border-bottom-left-radius: 12px;
        }}
        .table-row td:last-child {{
            border-top-right-radius: 12px;
            border-bottom-right-radius: 12px;
        }}

        /* Rank Highlights */
        .table-row.rank-gold {{
            background: linear-gradient(90deg, rgba(255, 215, 0, 0.15), rgba(30, 41, 59, 0.8));
            border-left: 4px solid #ffd700;
        }}
        .table-row.rank-silver {{
            background: linear-gradient(90deg, rgba(192, 192, 192, 0.12), rgba(30, 41, 59, 0.8));
            border-left: 4px solid #c0c0c0;
        }}
        .table-row.rank-bronze {{
            background: linear-gradient(90deg, rgba(205, 127, 50, 0.12), rgba(30, 41, 59, 0.8));
            border-left: 4px solid #cd7f32;
        }}

        .rank-badge {{
            font-family: 'Orbitron', sans-serif;
            font-size: 20px;
            font-weight: 900;
        }}
        .team-cell {{
            display: flex;
            align-items: center;
            gap: 16px;
            text-align: left;
            padding-left: 10px;
        }}
        .avatars-group {{
            display: flex;
            align-items: center;
        }}
        .row-avatar {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: 2px solid #00f0ff;
            object-fit: cover;
            margin-left: -10px;
        }}
        .row-avatar:first-child {{
            margin-left: 0;
        }}
        .team-name {{
            font-family: 'Rajdhani', sans-serif;
            font-size: 22px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 0.5px;
        }}
        .pts-pill {{
            font-family: 'Orbitron', sans-serif;
            font-size: 20px;
            font-weight: 900;
            color: #00f0ff;
            padding: 4px 14px;
            background: rgba(0, 240, 255, 0.12);
            border-radius: 8px;
            border: 1px solid rgba(0, 240, 255, 0.3);
        }}
        .table-row.rank-gold .pts-pill {{
            color: #ffd700;
            background: rgba(255, 215, 0, 0.15);
            border-color: rgba(255, 215, 0, 0.4);
        }}
        .win-text {{ color: #22c55e; }}
        .draw-text {{ color: #f59e0b; }}
        .loss-text {{ color: #ef4444; }}
        .diff-pos {{ color: #22c55e; }}
        .diff-neg {{ color: #ef4444; }}
        .diff-zero {{ color: #94a3b8; }}
        .col-rate {{
            font-family: 'Orbitron', sans-serif;
            font-size: 16px;
            color: #94a3b8;
        }}

        /* Sidebar Stats */
        .sidebar-card {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .stat-box {{
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 18px;
            padding: 22px;
            backdrop-filter: blur(16px);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .stat-label {{
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: #94a3b8;
        }}
        .stat-value {{
            font-family: 'Orbitron', sans-serif;
            font-size: 32px;
            font-weight: 900;
            color: #00f0ff;
        }}
        .progress-bar-bg {{
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 6px;
        }}
        .progress-bar-fill {{
            height: 100%;
            width: {progress_pct}%;
            background: linear-gradient(90deg, #00f0ff, #b026ff);
            border-radius: 5px;
        }}

        /* Footer */
        .footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            font-size: 16px;
            color: #64748b;
            font-weight: 600;
        }}
        .footer-tag {{
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
            letter-spacing: 2px;
            color: #00f0ff;
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-left">
            {f'<img class="guild-logo" src="{guild_icon_uri}" alt="" />' if guild_icon_uri else ''}
            <div class="header-title-box">
                <h1 class="header-title">{title}</h1>
                <div class="header-meta">
                    <span class="meta-pill">🎮 JOGO: {game}</span>
                    <span class="meta-pill">⚡ FORMATO: PONTOS CORRIDOS ({fmt_raw})</span>
                    <span class="meta-pill prize">🎁 PRÊMIO: {prize}</span>
                </div>
            </div>
        </div>
        <div class="status-badge {status_class}">{status_text}</div>
    </header>

    <main class="content-container">
        <div class="table-card">
            <table class="standings-table">
                <thead>
                    <tr>
                        <th style="width: 70px;">#</th>
                        <th class="col-team-head">EQUIPE / PARTICIPANTE</th>
                        <th style="width: 90px;">PTS</th>
                        <th style="width: 60px;">J</th>
                        <th style="width: 60px;">V</th>
                        <th style="width: 60px;">E</th>
                        <th style="width: 60px;">D</th>
                        <th style="width: 65px;">GP</th>
                        <th style="width: 65px;">GC</th>
                        <th style="width: 75px;">SG</th>
                        <th style="width: 85px;">APROV</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_str}
                </tbody>
            </table>
        </div>

        <div class="sidebar-card">
            <div class="stat-box">
                <span class="stat-label">PROGRESSO DO TORNEIO</span>
                <span class="stat-value">{done_matches} / {total_matches} <span style="font-size:16px; color:#94a3b8;">JOGOS</span></span>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill"></div>
                </div>
            </div>
            <div class="stat-box">
                <span class="stat-label">LÍDER ATUAL</span>
                <span class="stat-value" style="font-size:24px; color:#ffd700;">
                    {standings[0].get("team_name") if standings else "A definir"}
                </span>
            </div>
            <div class="stat-box">
                <span class="stat-label">TOTAL DE PARTICIPANTES</span>
                <span class="stat-value">{len(standings)} <span style="font-size:16px; color:#94a3b8;">TIMES</span></span>
            </div>
        </div>
    </main>

    <footer class="footer">
        <div>⚡ Sistema BMIA Esports • Liga de Pontos Corridos • Use <strong>/torneio rodadas</strong> para ver os jogos</div>
        <div class="footer-tag">BDP COMMUNITY • 2026</div>
    </footer>
</body>
</html>"""

    async def generate_table(
        self,
        guild: discord.Guild,
        tournament: dict,
        standings: List[dict],
        matches: Optional[List[dict]] = None
    ) -> BytesIO:
        """Renderiza a tabela de classificação em imagem 1920x1080 com Playwright."""
        from playwright.async_api import async_playwright

        # Enriquece os dados de avatares para cada participante na classificação
        for s in standings:
            for m_data in s.get("members", []):
                uid = m_data.get("user_id", 0)
                m = guild.get_member(uid)
                m_data["avatar_uri"] = await self._get_avatar_data_uri(m, m_data)

        guild_icon_uri = await self._get_guild_icon_data_uri(guild)

        html_code = self._build_html_template(
            tournament=tournament,
            standings=standings,
            guild_icon_uri=guild_icon_uri,
            matches=matches
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})
            await page.set_content(html_code, wait_until="networkidle")
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            await browser.close()

        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer


class RankCardBuilder:
    """
    Gerador visual de Rank Card / Perfil de Nível e XP em alta fidelidade (1100x340)
    utilizando HTML5/CSS3 modernos (Glassmorphism, Neon Glows, Gradients e Tipografia Esports)
    renderizado via Playwright.
    """

    async def _get_avatar_data_uri(self, member: Optional[discord.Member], username: str = "User") -> str:
        """Obtém o avatar do membro em base64 data URI ou fallback SVG."""
        import base64
        try:
            if member:
                avatar_asset = member.display_avatar.with_size(256)
                avatar_bytes = await avatar_asset.read()
                b64 = base64.b64encode(avatar_bytes).decode("utf-8")
                return f"data:image/png;base64,{b64}"
        except Exception:
            pass

        initial = username[0].upper() if username else "?"
        svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'>
            <defs>
                <linearGradient id='grad' x1='0%' y1='0%' x2='100%' y2='100%'>
                    <stop offset='0%' stop-color='#00f0ff'/>
                    <stop offset='100%' stop-color='#b026ff'/>
                </linearGradient>
            </defs>
            <circle cx='80' cy='80' r='76' fill='#151c2e' stroke='url(#grad)' stroke-width='6'/>
            <text x='80' y='98' font-family='sans-serif' font-size='56' font-weight='bold' fill='#ffffff' text-anchor='middle'>{initial}</text>
        </svg>"""
        b64_svg = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64_svg}"

    def _build_html_template(
        self,
        username: str,
        display_name: str,
        avatar_uri: str,
        level_data: dict,
        server_rank: int,
        messages_count: int,
        voice_minutes: int,
        guild_name: str
    ) -> str:
        level = level_data.get("level", 1)
        total_xp = level_data.get("total_xp", 0)
        xp_in_level = level_data.get("xp_in_level", 0)
        xp_needed = level_data.get("xp_needed_in_level", 100)
        progress_pct = level_data.get("progress_pct", 0.0)

        hours_voice = round(voice_minutes / 60, 1)

        # Cor do Nível baseada na faixa
        if level >= 50:
            level_color = "#ffd700" # Ouro / Master
            level_border = "rgba(255, 215, 0, 0.6)"
            badge_title = "MESTRE"
        elif level >= 25:
            level_color = "#00f0ff" # Ciano / Diamond
            level_border = "rgba(0, 240, 255, 0.6)"
            badge_title = "DIAMANTE"
        elif level >= 10:
            level_color = "#b026ff" # Roxo / Platina
            level_border = "rgba(176, 38, 255, 0.6)"
            badge_title = "PLATINA"
        else:
            level_color = "#38bdf8" # Azul / Veterano
            level_border = "rgba(56, 189, 248, 0.5)"
            badge_title = "EXPLORADOR"

        rank_display = f"#{server_rank}" if server_rank > 0 else "#-"

        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Rank Card</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;800;900&family=Rajdhani:wght@500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            user-select: none;
        }}
        body {{
            width: 1060px;
            height: 300px;
            background: transparent;
            font-family: 'Rajdhani', sans-serif;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }}
        .card-container {{
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #0b1120 0%, #070a14 100%);
            border: 1.5px solid rgba(0, 240, 255, 0.35);
            border-radius: 20px;
            padding: 24px 32px;
            display: flex;
            align-items: center;
            gap: 28px;
            position: relative;
            box-shadow: inset 0 0 40px rgba(0, 240, 255, 0.04);
        }}
        .card-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 10%;
            right: 10%;
            height: 2px;
            background: linear-gradient(90deg, transparent, #00f0ff, #b026ff, transparent);
            box-shadow: 0 0 15px #00f0ff;
        }}

        /* Avatar Section */
        .avatar-box {{
            position: relative;
            flex-shrink: 0;
        }}
        .avatar-img {{
            width: 130px;
            height: 130px;
            border-radius: 50%;
            object-fit: cover;
            background: #0f172a;
            border: 3px solid {level_color};
            box-shadow: 0 0 25px {level_border};
        }}
        .rank-pill {{
            position: absolute;
            bottom: -6px;
            left: 50%;
            transform: translateX(-50%);
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 1px;
            padding: 3px 12px;
            background: #070a14;
            border: 1.5px solid {level_color};
            border-radius: 12px;
            color: {level_color};
            box-shadow: 0 0 15px rgba(0,0,0,0.9);
            white-space: nowrap;
        }}


        /* Main Details */
        .details-box {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        /* Top Row: Names and Rank/Level */
        .top-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .user-info {{
            display: flex;
            flex-direction: column;
        }}
        .user-display {{
            font-size: 32px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 0.5px;
            line-height: 1.1;
        }}
        .user-handle {{
            font-size: 16px;
            color: #94a3b8;
            font-weight: 600;
        }}

        .rank-level-group {{
            display: flex;
            align-items: baseline;
            gap: 20px;
        }}
        .rank-stat {{
            font-family: 'Orbitron', sans-serif;
            font-size: 20px;
            font-weight: 800;
            color: #94a3b8;
        }}
        .rank-stat span {{
            color: #00f0ff;
            font-size: 28px;
            font-weight: 900;
        }}
        .level-stat {{
            font-family: 'Orbitron', sans-serif;
            font-size: 20px;
            font-weight: 800;
            color: #94a3b8;
        }}
        .level-stat span {{
            color: {level_color};
            font-size: 38px;
            font-weight: 900;
            text-shadow: 0 0 20px {level_border};
        }}

        /* Progress Bar */
        .progress-section {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .progress-meta {{
            display: flex;
            justify-content: space-between;
            font-family: 'Rajdhani', sans-serif;
            font-size: 16px;
            font-weight: 700;
            color: #94a3b8;
        }}
        .xp-text span {{
            color: #ffffff;
            font-weight: 800;
        }}
        .bar-bg {{
            width: 100%;
            height: 14px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            overflow: hidden;
            position: relative;
        }}
        .bar-fill {{
            height: 100%;
            width: {progress_pct}%;
            background: linear-gradient(90deg, #00f0ff, {level_color});
            border-radius: 8px;
            box-shadow: 0 0 20px #00f0ff;
        }}

        /* Bottom Stats Chips */
        .bottom-chips {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-top: 4px;
        }}
        .chip {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 5px 14px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            font-size: 15px;
            font-weight: 700;
            color: #cbd5e1;
        }}
        .chip-icon {{
            font-size: 14px;
        }}
        .chip strong {{
            color: #00f0ff;
            font-family: 'Orbitron', sans-serif;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="avatar-box">
            <img class="avatar-img" src="{avatar_uri}" alt="" />
            <div class="rank-pill">{badge_title}</div>
        </div>

        <div class="details-box">
            <div class="top-row">
                <div class="user-info">
                    <span class="user-display">{display_name}</span>
                    <span class="user-handle">@{username} • {guild_name}</span>
                </div>
                <div class="rank-level-group">
                    <div class="rank-stat">RANK <span>{rank_display}</span></div>
                    <div class="level-stat">NÍVEL <span>{level}</span></div>
                </div>
            </div>

            <div class="progress-section">
                <div class="progress-meta">
                    <span class="xp-text"><span>{xp_in_level:,}</span> / {xp_needed:,} XP</span>
                    <span class="pct-text">{progress_pct:.1f}%</span>
                </div>
                <div class="bar-bg">
                    <div class="bar-fill"></div>
                </div>
            </div>

            <div class="bottom-chips">
                <div class="chip">
                    <span class="chip-icon">✨</span>
                    <span>Total: <strong>{total_xp:,} XP</strong></span>
                </div>
                <div class="chip">
                    <span class="chip-icon">💬</span>
                    <span>Mensagens: <strong>{messages_count:,}</strong></span>
                </div>
                <div class="chip">
                    <span class="chip-icon">🎙️</span>
                    <span>Voz: <strong>{hours_voice}h</strong></span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

    async def generate_rank_card(
        self,
        member: discord.Member,
        level_data: dict,
        server_rank: int,
        messages_count: int,
        voice_minutes: int,
        guild_name: str
    ) -> BytesIO:
        """Renderiza o Rank Card do membro em imagem 1100x340 com Playwright."""
        from playwright.async_api import async_playwright

        username = member.name
        display_name = member.display_name
        avatar_uri = await self._get_avatar_data_uri(member, username)

        html_code = self._build_html_template(
            username=username,
            display_name=display_name,
            avatar_uri=avatar_uri,
            level_data=level_data,
            server_rank=server_rank,
            messages_count=messages_count,
            voice_minutes=voice_minutes,
            guild_name=guild_name
        )

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(viewport={"width": 1060, "height": 300})
            await page.set_content(html_code, wait_until="networkidle")
            element = await page.query_selector('.card-container')
            if element:
                screenshot_bytes = await element.screenshot(type="png", omit_background=True)
            else:
                screenshot_bytes = await page.screenshot(type="png", omit_background=True)
        buffer = BytesIO(screenshot_bytes)
        buffer.seek(0)
        return buffer


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

        # 1. Constrói todo o HTML assincronamente em paralelo (downloads de avatar / formatações)
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


