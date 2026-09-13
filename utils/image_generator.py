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
    """Gerador visual de chaveamento / brackets dinâmico para torneios de esports do servidor."""

    def __init__(self):
        # Paleta de Cores Cyberpunk / Esports Dark
        self.BG_DARK = (13, 17, 28)           # #0d111c
        self.BG_CARD = (22, 29, 47)           # #161d2f
        self.BG_CARD_BORDER = (45, 59, 90)    # #2d3b5a
        self.NEON_CYAN = (0, 240, 255)        # #00f0ff
        self.NEON_PURPLE = (168, 85, 247)     # #a855f7
        self.GOLD = (255, 215, 0)             # #ffd700
        self.TEXT_WHITE = (255, 255, 255)
        self.TEXT_MUTED = (148, 163, 184)     # #94a3b8
        self.LINE_ACTIVE = (0, 240, 255)

    def _get_font(self, size: int, bold: bool = False):
        font_candidates = [
            "arialbd.ttf" if bold else "arial.ttf",
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            "segoeuib.ttf" if bold else "segoeui.ttf",
            "arial.ttf",
            "DejaVuSans.ttf"
        ]
        for f in font_candidates:
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
        return ImageFont.load_default()

    async def _fetch_avatar(self, member: Optional[discord.Member], user_data: dict, size: int = 44) -> Image.Image:
        """Obtém e redimensiona o avatar do membro de forma circular, com fallback seguro."""
        try:
            if member:
                avatar_asset = member.display_avatar.with_size(128)
                avatar_bytes = await avatar_asset.read()
                av = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                av = av.resize((size, size), Image.Resampling.LANCZOS)
                
                # Máscara circular
                mask = Image.new('L', (size, size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, size, size), fill=255)
                
                output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                output.paste(av, (0, 0), mask)
                return output
        except Exception:
            pass

        # Fallback: Círculo com inicial do usuário
        fallback = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(fallback)
        name = user_data.get("username") or (member.display_name if member else "P")
        initial = name[0].upper() if name else "?"
        draw.ellipse((0, 0, size, size), fill=(40, 60, 100))
        font = self._get_font(int(size * 0.45), bold=True)
        draw.text((size // 3, size // 4), initial, fill=self.TEXT_WHITE, font=font)
        return fallback

    def _create_placeholder_avatar(self, size: int = 44, text: str = "+") -> Image.Image:
        """Cria um avatar placeholder para vaga aberta."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, size, size), fill=(25, 35, 55), outline=self.NEON_CYAN, width=1)
        font = self._get_font(int(size * 0.45), bold=True)
        draw.text((size // 3, size // 5), text, fill=self.NEON_CYAN, font=font)
        return img

    async def generate_bracket(
        self,
        guild: discord.Guild,
        tournament: dict,
        participants: List[dict]
    ) -> BytesIO:
        """
        Gera uma imagem de alta resolução (1920x1080) com o chaveamento dinâmico do torneio.
        Suporta modos de 2 times (Final), 4 times (Semis + Final) e 8 times (Quartas + Semis + Final).
        """
        WIDTH, HEIGHT = 1920, 1080
        img = Image.new("RGB", (WIDTH, HEIGHT), color=self.BG_DARK)
        draw = ImageDraw.Draw(img)

        # 1. Background Grid & Details
        for y in range(0, HEIGHT, 40):
            draw.line([(0, y), (WIDTH, y)], fill=(18, 24, 38), width=1)
        for x in range(0, WIDTH, 40):
            draw.line([(x, 0), (x, HEIGHT)], fill=(18, 24, 38), width=1)

        # Top Bar
        draw.rectangle([0, 0, WIDTH, 8], fill=self.NEON_CYAN)

        # 2. Formato & Cálculo de Times
        fmt_raw = str(tournament.get("format", "1v1")).lower().strip()
        is_2v2 = any(k in fmt_raw for k in ["2v2", "2x2", "dupla", "duplas"])
        is_3v3 = any(k in fmt_raw for k in ["3v3", "3x3", "trio", "trios"])
        team_size = 2 if is_2v2 else (3 if is_3v3 else 1)

        max_participants = int(tournament.get("max_participants") or 16)
        num_teams_target = max(2, max_participants // team_size)

        # Determina o modo de bracket: 2, 4 ou 8 times
        if num_teams_target <= 2:
            bracket_mode = 2
        elif num_teams_target <= 4:
            bracket_mode = 4
        else:
            bracket_mode = 8

        # 3. Header Section
        font_title = self._get_font(38, bold=True)
        font_subtitle = self._get_font(18, bold=False)
        font_badge = self._get_font(15, bold=True)

        title = str(tournament.get("name", "TORNEIO OFICIAL")).upper()
        game = str(tournament.get("game_name", "Geral")).upper()
        prize = str(tournament.get("prize") or "Glória e Pontos")

        # Guild Icon
        if guild.icon:
            try:
                icon_asset = guild.icon.with_size(128)
                icon_bytes = await icon_asset.read()
                icon_img = Image.open(BytesIO(icon_bytes)).convert("RGBA").resize((84, 84), Image.Resampling.LANCZOS)
                mask = Image.new('L', (84, 84), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 84, 84), fill=255)
                img.paste(icon_img, (60, 35), mask)
            except Exception:
                pass

        draw.text((160, 35), title, fill=self.TEXT_WHITE, font=font_title)
        subtitle_text = f"JOGO: {game}   |   FORMATO: {fmt_raw.upper()}   |   PREMIAÇÃO: {prize}   |   INSCRITOS: {len(participants)}/{max_participants}"
        draw.text((160, 86), subtitle_text, fill=self.NEON_CYAN, font=font_subtitle)

        # Status Badge
        is_shuffled = tournament.get("is_shuffled", False)
        winner_id = tournament.get("winner_id")

        if winner_id:
            status_text = "● TORNEIO CONCLUÍDO"
            badge_color = self.GOLD
        elif is_shuffled:
            status_text = "● CHAVEAMENTO OFICIAL"
            badge_color = self.NEON_CYAN
        elif tournament.get("status") == "open":
            status_text = "● PRÉVIA (INSCRIÇÕES ABERTAS)"
            badge_color = (34, 197, 94)
        else:
            status_text = "● CHAVEAMENTO PRELIMINAR"
            badge_color = (168, 85, 247)

        draw.rounded_rectangle([WIDTH - 380, 45, WIDTH - 60, 95], radius=8, fill=(20, 30, 50), outline=badge_color, width=2)
        draw.text((WIDTH - 355, 60), status_text, fill=badge_color, font=font_badge)

        # Separator Line
        draw.line([(60, 135), (WIDTH - 60, 135)], fill=self.BG_CARD_BORDER, width=2)

        # 4. Organizar Participantes em Times
        teams = []
        for i in range(0, len(participants), team_size):
            teams.append(participants[i:i + team_size])

        # Preenche com times vazios até o limite do modo atual
        while len(teams) < bracket_mode:
            teams.append([])

        teams = teams[:bracket_mode]

        # Pré-carregar Avatares
        team_avatars = []
        avatar_size = 40 if is_2v2 else 48
        for t in teams:
            t_avs = []
            for p in t:
                m = guild.get_member(p.get("user_id", 0))
                av = await self._fetch_avatar(m, p, size=avatar_size)
                t_avs.append((m, p, av))
            team_avatars.append(t_avs)

        # 5. Função Utilitária para Desenho de Cards
        font_team_name = self._get_font(17, bold=True)
        font_team_sub = self._get_font(13, bold=False)
        font_vs = self._get_font(15, bold=True)
        font_round_title = self._get_font(21, bold=True)
        font_champ_title = self._get_font(22, bold=True)

        def draw_team_card(x, y, card_w, card_h, team_data, team_idx, placeholder_label=None):
            draw.rounded_rectangle(
                [x, y, x + card_w, y + card_h],
                radius=10,
                fill=self.BG_CARD,
                outline=self.BG_CARD_BORDER,
                width=2
            )
            if not team_data:
                label = placeholder_label or f"Time #{team_idx + 1} (Aguardando)"
                ph_av = self._create_placeholder_avatar(size=avatar_size, text="?")
                img.paste(ph_av, (x + 15, y + (card_h - avatar_size) // 2), ph_av)
                draw.text((x + 15 + avatar_size + 12, y + (card_h // 2) - 10), label, fill=self.TEXT_MUTED, font=font_team_name)
                return

            if is_2v2:
                # Desenha os avatares dos membros da dupla
                offset_x = x + 12
                names = []
                for m, p, av in team_data:
                    img.paste(av, (offset_x, y + (card_h - avatar_size) // 2), av)
                    name = m.display_name if m else (p.get("username") or "Jogador")
                    names.append(name[:11])
                    offset_x += (avatar_size - 6)

                # Se a dupla estiver incompleta (1/2), desenha slot vazio (+)
                if len(team_data) < 2:
                    ph_av = self._create_placeholder_avatar(size=avatar_size, text="+")
                    img.paste(ph_av, (offset_x, y + (card_h - avatar_size) // 2), ph_av)
                    names.append("(Vaga Aberta)")
                    offset_x += (avatar_size - 6)

                team_title = " & ".join(names)
                draw.text((offset_x + 10, y + (card_h // 2) - 10), team_title[:24], fill=self.TEXT_WHITE, font=font_team_name)
            else:
                # 1v1 Individual
                m, p, av = team_data[0]
                img.paste(av, (x + 15, y + (card_h - avatar_size) // 2), av)
                name = m.display_name if m else (p.get("username") or "Jogador")
                draw.text((x + 15 + avatar_size + 12, y + (card_h // 2) - 10), name[:20], fill=self.TEXT_WHITE, font=font_team_name)

        def draw_champion_box(x, y, card_w):
            draw.rounded_rectangle(
                [x, y, x + card_w, y + 95],
                radius=12,
                fill=(26, 36, 22),
                outline=self.GOLD,
                width=2
            )
            draw.text((x + (card_w // 2) - 65, y + 16), "★ CAMPEÃO ★", fill=self.GOLD, font=font_champ_title)
            if winner_id:
                w_member = guild.get_member(winner_id)
                w_name = w_member.display_name if w_member else "Campeão Definido"
                draw.text((x + 30, y + 52), f"Vencedor: {w_name}", fill=self.TEXT_WHITE, font=font_team_name)
            else:
                draw.text((x + (card_w // 2) - 45, y + 52), "A Definir...", fill=self.TEXT_MUTED, font=font_team_name)

        # 6. RENDERIZAÇÃO POR MODO DE BRACKET

        # -------------------------------------------------------------
        # MODO A: 2 TIMES (CONFRONTO DIRETO / SHOWDOWN DE ESPORTS)
        # -------------------------------------------------------------
        if bracket_mode == 2:
            CARD_W, CARD_H = 560, 250
            left_x = 160
            right_x = WIDTH - 160 - CARD_W
            center_x = (WIDTH - 440) // 2
            
            draw.text(((WIDTH // 2) - 180, 175), "★ GRANDE FINAL - CONFRONTO DIRETO ★", fill=self.GOLD, font=font_round_title)

            def draw_showdown_card(x, y, team_data, team_idx, corner_color, corner_title):
                draw.rounded_rectangle(
                    [x, y, x + CARD_W, y + CARD_H],
                    radius=14,
                    fill=self.BG_CARD,
                    outline=corner_color,
                    width=2
                )
                # Header do Card (Corner Title) com bolinha vetorial colorida
                draw.rectangle([x + 2, y + 2, x + CARD_W - 2, y + 36], fill=(26, 34, 52))
                draw.ellipse((x + 18, y + 14, x + 28, y + 24), fill=corner_color)
                draw.text((x + 36, y + 10), corner_title, fill=corner_color, font=self._get_font(15, bold=True))

                if not team_data:
                    ph_av = self._create_placeholder_avatar(size=56, text="?")
                    img.paste(ph_av, (x + 30, y + 70), ph_av)
                    draw.text((x + 105, y + 85), f"Time #{team_idx + 1} (Aguardando Inscrição)", fill=self.TEXT_MUTED, font=self._get_font(20, bold=True))
                    return

                if is_2v2:
                    # Renderiza 2 linhas (1 para cada jogador da dupla)
                    # Jogador 1
                    m1, p1, av1 = team_data[0]
                    img.paste(av1, (x + 30, y + 55), av1)
                    name1 = m1.display_name if m1 else (p1.get("username") or "Jogador 1")
                    draw.text((x + 85, y + 68), name1[:22], fill=self.TEXT_WHITE, font=self._get_font(20, bold=True))

                    # Jogador 2 ou Vaga Aberta
                    if len(team_data) > 1:
                        m2, p2, av2 = team_data[1]
                        img.paste(av2, (x + 30, y + 145), av2)
                        name2 = m2.display_name if m2 else (p2.get("username") or "Jogador 2")
                        draw.text((x + 85, y + 158), name2[:22], fill=self.TEXT_WHITE, font=self._get_font(20, bold=True))
                    else:
                        ph_av = self._create_placeholder_avatar(size=avatar_size, text="+")
                        img.paste(ph_av, (x + 30, y + 145), ph_av)
                        draw.text((x + 85, y + 158), "(Aguardando 2º Jogador)", fill=self.TEXT_MUTED, font=self._get_font(18, bold=False))
                else:
                    # 1v1 (Card com avatar grande em destaque)
                    m, p, av = team_data[0]
                    # Resize avatar maior para 1v1 showdown
                    av_large = av.resize((84, 84), Image.Resampling.LANCZOS)
                    img.paste(av_large, (x + 35, y + 80), av_large)
                    name = m.display_name if m else (p.get("username") or "Jogador")
                    draw.text((x + 140, y + 100), name[:22], fill=self.TEXT_WHITE, font=self._get_font(24, bold=True))

            # Card Esquerdo (Time Azul)
            draw_showdown_card(left_x, 260, team_avatars[0], 0, self.NEON_CYAN, "DUPLA AZUL" if is_2v2 else "LADO AZUL")

            # Card Direito (Time Laranja/Roxo)
            draw_showdown_card(right_x, 260, team_avatars[1], 1, self.NEON_PURPLE, "DUPLA ROXA" if is_2v2 else "LADO ROXO")

            # Emblema VS Central
            vs_w, vs_h = 160, 80
            vs_x = (WIDTH - vs_w) // 2
            vs_y = 345
            draw.rounded_rectangle([vs_x, vs_y, vs_x + vs_w, vs_y + vs_h], radius=12, fill=(24, 18, 42), outline=self.NEON_PURPLE, width=3)
            font_vs_large = self._get_font(32, bold=True)
            draw.text((vs_x + 52, vs_y + 22), "VS", fill=self.NEON_CYAN, font=font_vs_large)


            # Linhas de Conexão Neon (Showdown Faceoff)
            draw.line([(left_x + CARD_W, 385), (vs_x, 385)], fill=self.LINE_ACTIVE, width=4)
            draw.line([(right_x, 385), (vs_x + vs_w, 385)], fill=self.LINE_ACTIVE, width=4)

            # Linha descendo do VS até o Troféu do Campeão
            draw.line([(WIDTH // 2, vs_y + vs_h), (WIDTH // 2, 580)], fill=self.LINE_ACTIVE, width=4)

            # Troféu / Box Campeão
            draw_champion_box(center_x, 580, 440)

        # -------------------------------------------------------------
        # MODO B: 4 TIMES (SEMIFINAIS + GRANDE FINAL)

        # -------------------------------------------------------------
        elif bracket_mode == 4:
            CARD_W, CARD_H = 360, 85
            left_x = 120
            right_x = WIDTH - 120 - CARD_W
            center_x = (WIDTH - CARD_W) // 2

            # Títulos
            draw.text((left_x + 90, 170), "SEMIFINAL 1", fill=self.TEXT_MUTED, font=font_round_title)
            draw.text((center_x + 90, 170), "★ GRANDE FINAL ★", fill=self.GOLD, font=font_round_title)
            draw.text((right_x + 90, 170), "SEMIFINAL 2", fill=self.TEXT_MUTED, font=font_round_title)

            # Semifinal 1 (Esquerda: T0 vs T1)
            y_s1_t0 = 260
            y_s1_t1 = 430
            draw_team_card(left_x, y_s1_t0, CARD_W, CARD_H, team_avatars[0], 0)
            draw_team_card(left_x, y_s1_t1, CARD_W, CARD_H, team_avatars[1], 1)
            draw.text((left_x + (CARD_W // 2) - 10, 365), "VS", fill=self.NEON_PURPLE, font=font_vs)

            # Semifinal 2 (Direita: T2 vs T3)
            y_s2_t2 = 260
            y_s2_t3 = 430
            draw_team_card(right_x, y_s2_t2, CARD_W, CARD_H, team_avatars[2], 2)
            draw_team_card(right_x, y_s2_t3, CARD_W, CARD_H, team_avatars[3], 3)
            draw.text((right_x + (CARD_W // 2) - 10, 365), "VS", fill=self.NEON_PURPLE, font=font_vs)

            # Grande Final (Centro)
            y_f1 = 280
            y_f2 = 450
            draw_team_card(center_x, y_f1, CARD_W, CARD_H, [], 0, "Finalista 1")
            draw_team_card(center_x, y_f2, CARD_W, CARD_H, [], 1, "Finalista 2")
            draw.text((center_x + (CARD_W // 2) - 10, 385), "VS", fill=self.GOLD, font=font_vs)

            # Conectores Semifinal 1 -> Final 1
            draw.line([(left_x + CARD_W, y_s1_t0 + CARD_H // 2), (left_x + CARD_W + 40, y_s1_t0 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_x + CARD_W, y_s1_t1 + CARD_H // 2), (left_x + CARD_W + 40, y_s1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_x + CARD_W + 40, y_s1_t0 + CARD_H // 2), (left_x + CARD_W + 40, y_s1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_x + CARD_W + 40, (y_s1_t0 + y_s1_t1 + CARD_H) // 2), (center_x, y_f1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Semifinal 2 -> Final 2
            draw.line([(right_x, y_s2_t2 + CARD_H // 2), (right_x - 40, y_s2_t2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_x, y_s2_t3 + CARD_H // 2), (right_x - 40, y_s2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_x - 40, y_s2_t2 + CARD_H // 2), (right_x - 40, y_s2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_x - 40, (y_s2_t2 + y_s2_t3 + CARD_H) // 2), (center_x + CARD_W, y_f2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Campeão
            draw_champion_box(center_x, 630, CARD_W)

        # -------------------------------------------------------------
        # MODO C: 8 TIMES (QUARTAS + SEMIFINAIS + GRANDE FINAL)
        # -------------------------------------------------------------
        else:
            CARD_W, CARD_H = 290, 75
            left_q_x = 70
            right_q_x = WIDTH - 70 - CARD_W
            left_semi_x = 420
            right_semi_x = WIDTH - 420 - CARD_W
            final_x = (WIDTH - CARD_W) // 2

            # Títulos das Rodadas
            draw.text((left_q_x + 50, 160), "QUARTAS DE FINAL", fill=self.TEXT_MUTED, font=font_round_title)
            draw.text((left_semi_x + 75, 160), "SEMIFINAL", fill=self.TEXT_MUTED, font=font_round_title)
            draw.text((final_x + 65, 160), "★ GRANDE FINAL ★", fill=self.GOLD, font=font_round_title)
            draw.text((right_semi_x + 75, 160), "SEMIFINAL", fill=self.TEXT_MUTED, font=font_round_title)
            draw.text((right_q_x + 50, 160), "QUARTAS DE FINAL", fill=self.TEXT_MUTED, font=font_round_title)

            # Quartas Left (Match 1 & 2)
            y_m1_t0, y_m1_t1 = 230, 330
            draw_team_card(left_q_x, y_m1_t0, CARD_W, CARD_H, team_avatars[0], 0)
            draw_team_card(left_q_x, y_m1_t1, CARD_W, CARD_H, team_avatars[1], 1)
            draw.text((left_q_x + CARD_W // 2 - 10, y_m1_t0 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

            y_m2_t2, y_m2_t3 = 540, 640
            draw_team_card(left_q_x, y_m2_t2, CARD_W, CARD_H, team_avatars[2], 2)
            draw_team_card(left_q_x, y_m2_t3, CARD_W, CARD_H, team_avatars[3], 3)
            draw.text((left_q_x + CARD_W // 2 - 10, y_m2_t2 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

            # Quartas Right (Match 3 & 4)
            y_m3_t4, y_m3_t5 = 230, 330
            draw_team_card(right_q_x, y_m3_t4, CARD_W, CARD_H, team_avatars[4], 4)
            draw_team_card(right_q_x, y_m3_t5, CARD_W, CARD_H, team_avatars[5], 5)
            draw.text((right_q_x + CARD_W // 2 - 10, y_m3_t4 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

            y_m4_t6, y_m4_t7 = 540, 640
            draw_team_card(right_q_x, y_m4_t6, CARD_W, CARD_H, team_avatars[6], 6)
            draw_team_card(right_q_x, y_m4_t7, CARD_W, CARD_H, team_avatars[7], 7)
            draw.text((right_q_x + CARD_W // 2 - 10, y_m4_t6 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

            # Semifinais
            y_semi_l1, y_semi_l2 = 280, 590
            draw_team_card(left_semi_x, y_semi_l1, CARD_W, CARD_H, [], 0, "Vencedor Q1")
            draw_team_card(left_semi_x, y_semi_l2, CARD_W, CARD_H, [], 1, "Vencedor Q2")
            draw.text((left_semi_x + CARD_W // 2 - 10, 440), "VS", fill=self.NEON_PURPLE, font=font_vs)

            y_semi_r1, y_semi_r2 = 280, 590
            draw_team_card(right_semi_x, y_semi_r1, CARD_W, CARD_H, [], 2, "Vencedor Q3")
            draw_team_card(right_semi_x, y_semi_r2, CARD_W, CARD_H, [], 3, "Vencedor Q4")
            draw.text((right_semi_x + CARD_W // 2 - 10, 440), "VS", fill=self.NEON_PURPLE, font=font_vs)

            # Grande Final
            y_final_1, y_final_2 = 360, 500
            draw_team_card(final_x, y_final_1, CARD_W, CARD_H, [], 0, "Finalista 1")
            draw_team_card(final_x, y_final_2, CARD_W, CARD_H, [], 1, "Finalista 2")
            draw.text((final_x + CARD_W // 2 - 10, 442), "VS", fill=self.GOLD, font=font_vs)

            # Troféu
            draw_champion_box(final_x, 660, CARD_W)

            # Conectores Q1 -> Semi 1
            draw.line([(left_q_x + CARD_W, y_m1_t0 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t0 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W, y_m1_t1 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W + 40, y_m1_t0 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W + 40, (y_m1_t0 + y_m1_t1 + CARD_H) // 2), (left_semi_x, y_semi_l1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Q2 -> Semi 2
            draw.line([(left_q_x + CARD_W, y_m2_t2 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W, y_m2_t3 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W + 40, y_m2_t2 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_q_x + CARD_W + 40, (y_m2_t2 + y_m2_t3 + CARD_H) // 2), (left_semi_x, y_semi_l2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Semis Left -> Final 1
            draw.line([(left_semi_x + CARD_W, y_semi_l1 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_l1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_semi_x + CARD_W, y_semi_l2 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_l2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_semi_x + CARD_W + 30, y_semi_l1 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_l2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(left_semi_x + CARD_W + 30, (y_semi_l1 + y_semi_l2 + CARD_H) // 2), (final_x, y_final_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Q3 -> Semi 1
            draw.line([(right_q_x, y_m3_t4 + CARD_H // 2), (right_q_x - 40, y_m3_t4 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x, y_m3_t5 + CARD_H // 2), (right_q_x - 40, y_m3_t5 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x - 40, y_m3_t4 + CARD_H // 2), (right_q_x - 40, y_m3_t5 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x - 40, (y_m3_t4 + y_m3_t5 + CARD_H) // 2), (right_semi_x + CARD_W, y_semi_r1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Q4 -> Semi 2
            draw.line([(right_q_x, y_m4_t6 + CARD_H // 2), (right_q_x - 40, y_m4_t6 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x, y_m4_t7 + CARD_H // 2), (right_q_x - 40, y_m4_t7 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x - 40, y_m4_t6 + CARD_H // 2), (right_q_x - 40, y_m4_t7 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_q_x - 40, (y_m4_t6 + y_m4_t7 + CARD_H) // 2), (right_semi_x + CARD_W, y_semi_r2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

            # Conectores Semis Right -> Final 2
            draw.line([(right_semi_x, y_semi_r1 + CARD_H // 2), (right_semi_x - 30, y_semi_r1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_semi_x, y_semi_r2 + CARD_H // 2), (right_semi_x - 30, y_semi_r2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_semi_x - 30, y_semi_r1 + CARD_H // 2), (right_semi_x - 30, y_semi_r2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
            draw.line([(right_semi_x - 30, (y_semi_r1 + y_semi_r2 + CARD_H) // 2), (final_x + CARD_W, y_final_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # 7. Footer Section
        draw.line([(60, HEIGHT - 75), (WIDTH - 60, HEIGHT - 75)], fill=self.BG_CARD_BORDER, width=1)
        font_footer = self._get_font(15, bold=False)
        draw.text((60, HEIGHT - 50), "SISTEMA OFICIAL DE TORNEIOS BMIA ESPORTS   |   Use /torneio status para acompanhar", fill=self.TEXT_MUTED, font=font_footer)
        draw.text((WIDTH - 260, HEIGHT - 50), "BDP COMMUNITY • 2026", fill=self.NEON_CYAN, font=font_footer)

        # Retorna buffer PNG
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

