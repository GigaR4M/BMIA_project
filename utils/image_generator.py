import discord
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
from typing import Optional, List, Any

class PodiumBuilder:
    def __init__(self):
        # Cores
        self.BACKGROUND_COLOR = (43, 45, 49) # Discord Dark Mode
        self.TEXT_COLOR = (255, 255, 255)
        self.GOLD = (255, 215, 0)
        self.SILVER = (192, 192, 192)
        self.BRONZE = (205, 127, 50)
        
    async def generate_podium(self, guild: discord.Guild, top_users: list, period_text: str = None) -> BytesIO:
        """
        Gera uma imagem de pódio com os top 10 usuários (3 no pódio + 7 em lista).
        top_users: lista de dicts com 'user_id', 'username', 'total_points'
        period_text: texto opcional para exibir periodo (ex: "Novembro 2025")
        """
        # Separa Top 3 e Restante
        top_3 = top_users[:3]
        others = top_users[3:]

        # Dimensões e Configurações
        PODIUM_HEIGHT = 500
        LIST_ITEM_HEIGHT = 70
        LIST_PADDING = 10
        
        # Calcula altura total
        list_height = len(others) * (LIST_ITEM_HEIGHT + LIST_PADDING) + 20 # +20 margem inferior
        total_height = PODIUM_HEIGHT + list_height

        # 1. Configurar Canvas (800xAlturaTotal)
        img = Image.new('RGB', (800, total_height), color=self.BACKGROUND_COLOR)
        draw = ImageDraw.Draw(img)
        
        # Posições dos pódios (Centro, Esquerda, Direita)
        # Formato: (x, y_chão, largura, altura_pilar, cor, ranking)
        positions = [
            (400, 450, 180, 200, self.GOLD, 0),   # 1º Lugar (Meio)
            (200, 450, 180, 140, self.SILVER, 1), # 2º Lugar (Esq)
            (600, 450, 180, 80, self.BRONZE, 2)   # 3º Lugar (Dir)
        ]
        
        # Fonte (Tenta carregar Arial ou padrão)
        try:
            # Tenta usar Arial no Windows ou DejaVuSans no Linux
            import os
            font_path = "arial.ttf" if os.name == 'nt' else "DejaVuSans.ttf"
            font_name = ImageFont.truetype(font_path, 30)
            font_score = ImageFont.truetype(font_path, 24)
            # Novas fontes para a lista
            font_list_rank = ImageFont.truetype(font_path, 36)
            font_list_name = ImageFont.truetype(font_path, 28)
            font_list_score = ImageFont.truetype(font_path, 28)
        except:
            font_score = ImageFont.load_default()
            font_list_rank = ImageFont.load_default()
            font_list_name = ImageFont.load_default()
            font_list_score = ImageFont.load_default()

        # Desenhar o texto do período se fornecido
        if period_text:
            try:
                # Tenta uma fonte maior para o título
                font_title = ImageFont.truetype(font_path, 40)
            except:
                font_title = font_name
            
            # Centralizar texto "Ranking: {period_text}" ou apenas o texto
            title = f"Ranking: {period_text}"
            # Posição aproximada centralizada no topo (800 largura / 2 = 400)
            # Ajuste fino: subtrair metado do tamanho estimado do texto (aprox 15px por char com fonte 40)
            text_width = len(title) * 20 
            draw.text((400 - (text_width // 2), 50), title, fill=self.GOLD, font=font_title)

        # 2. Desenhar cada vencedor (Top 3)
        for i, user_data in enumerate(top_3):
            if i >= 3: break
            
            # Ajusta índice para ordem visual (1º no meio, 2º na esq, 3º na dir)
            # A lista top_users vem ordenada [1º, 2º, 3º]
            
            x_center, y_floor, width, height, color, rank_idx = positions[i]
            
            # Desenha o pilar
            left = x_center - (width // 2)
            top = y_floor - height
            right = x_center + (width // 2)
            bottom = y_floor
            
            draw.rectangle([left, top, right, bottom], fill=color)
            draw.text((x_center - 10, bottom - 40), f"#{i+1}", fill=(0,0,0), font=font_name)
            
            # Pegar Avatar e Nome
            # user pode ser Mock ou Real
            user = guild.get_member(user_data['user_id'])
            
            # --- Desenhar Avatar ---
            if user:
                # Trata avatar mockado no teste vs real no discord.py
                # No script de teste, vamos mockar display_avatar.with_size().read()
                try:
                    avatar_asset = user.display_avatar.with_size(128)
                    avatar_bytes = await avatar_asset.read()
                    
                    avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                    avatar_img = avatar_img.resize((100, 100))
                    
                    # Criar máscara circular
                    mask = Image.new('L', (100, 100), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, 100, 100), fill=255)
                    
                    # Colar avatar em cima do pilar
                    avatar_x = x_center - 50
                    avatar_y = top - 110 # 10px de margem + 100px altura
                    img.paste(avatar_img, (avatar_x, avatar_y), mask)
                except Exception as e:
                    print(f"Erro ao desenhar avatar de {user_data.get('username')}: {e}")
                
                # Nome e Pontos
                name = user.display_name[:12] # Limitar caracteres
                points = f"{user_data['total_points']} pts"
                
                # Centralizar texto (cálculo básico)
                # Para centralizar direito, idealmente usamos draw.textbbox, mas hardcoded serve por agora
                draw.text((x_center - 40, avatar_y - 40), name, fill=self.TEXT_COLOR, font=font_name)
                draw.text((x_center - 30, avatar_y - 70), points, fill=self.GOLD, font=font_score)
            else:
                # Caso usuário tenha saído do servidor, desenha apenas os dados do DB se possivel
                name = user_data.get('username', 'Desconhecido')[:12]
                draw.text((x_center - 40, top - 50), f"{name}\n(Saiu)", fill=self.TEXT_COLOR, font=font_name)

        # 3. Desenhar a Lista (Top 4-10)
        start_y = 520 # Logo abaixo do pódio
        
        for i, user_data in enumerate(others):
            rank = i + 4
            row_y = start_y + (i * (LIST_ITEM_HEIGHT + LIST_PADDING))
            
            # Fundo da linha (alternado para melhor leitura)
            if i % 2 == 0:
                draw.rectangle([50, row_y, 750, row_y + LIST_ITEM_HEIGHT], fill=(50, 53, 59))
            else:
                 draw.rectangle([50, row_y, 750, row_y + LIST_ITEM_HEIGHT], fill=(43, 45, 49)) # Mesma cor fundo principal

            # Rank
            draw.text((70, row_y + 15), f"#{rank}", fill=(150, 150, 150), font=font_list_rank)
            
            # Avatar Pequeno
            avatar_size = 50
            avatar_x = 160
            avatar_y_pos = row_y + 10
            
            user = guild.get_member(user_data['user_id'])
            if user:
                try:
                    avatar_asset = user.display_avatar.with_size(64)
                    avatar_bytes = await avatar_asset.read()
                    
                    avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                    avatar_img = avatar_img.resize((avatar_size, avatar_size))
                    
                    # Máscara circular
                    mask = Image.new('L', (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    
                    img.paste(avatar_img, (avatar_x, int(avatar_y_pos)), mask)
                except Exception as e:
                    # Fallback (círculo cinza)
                    draw.ellipse((avatar_x, avatar_y_pos, avatar_x + avatar_size, avatar_y_pos + avatar_size), fill=(100,100,100))
            else:
                 # Fallback usuário saiu
                 draw.ellipse((avatar_x, avatar_y_pos, avatar_x + avatar_size, avatar_y_pos + avatar_size), fill=(100,100,100))

            # Nome
            if user:
                name = user.display_name[:20]
            else:
                name = user_data.get('username', 'Desconhecido')[:20]

            draw.text((230, row_y + 18), name, fill=self.TEXT_COLOR, font=font_list_name)
            
            # Pontos (Alinhado a direita)
            points_text = f"{user_data['total_points']} pts"
            # Usar textbbox para alinhar à direita (se disponível) ou estimativa
            try:
                bbox = draw.textbbox((0, 0), points_text, font=font_list_score)
                p_width = bbox[2] - bbox[0]
                draw.text((730 - p_width, row_y + 18), points_text, fill=self.GOLD, font=font_list_score)
            except:
                # Fallback para versões antigas do PIL
                draw.text((650, row_y + 18), points_text, fill=self.GOLD, font=font_list_score)

        # 3. Retornar buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
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

