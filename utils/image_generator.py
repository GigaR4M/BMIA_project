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
    """Gerador visual de chaveamento / brackets para torneios de esports do servidor."""

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
        self.LINE_COLOR = (45, 75, 120)       # #2d4b78
        self.LINE_ACTIVE = (0, 240, 255)

    def _get_font(self, size: int, bold: bool = False):
        import os
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

    async def _fetch_avatar(self, member: Optional[discord.Member], user_data: dict, size: int = 48) -> Image.Image:
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
        font = self._get_font(int(size * 0.5), bold=True)
        draw.text((size // 3, size // 4), initial, fill=self.TEXT_WHITE, font=font)
        return fallback

    async def generate_bracket(
        self,
        guild: discord.Guild,
        tournament: dict,
        participants: List[dict]
    ) -> BytesIO:
        """
        Gera uma imagem de alta resolução (1920x1080) com o chaveamento do torneio.
        """
        WIDTH, HEIGHT = 1920, 1080
        img = Image.new("RGB", (WIDTH, HEIGHT), color=self.BG_DARK)
        draw = ImageDraw.Draw(img)

        # 1. Background Grid & Gradient Accents
        for y in range(0, HEIGHT, 40):
            draw.line([(0, y), (WIDTH, y)], fill=(18, 24, 38), width=1)
        for x in range(0, WIDTH, 40):
            draw.line([(x, 0), (x, HEIGHT)], fill=(18, 24, 38), width=1)

        # Neon Header Top Bar
        draw.rectangle([0, 0, WIDTH, 8], fill=self.NEON_CYAN)

        # 2. Header Section
        font_title = self._get_font(42, bold=True)
        font_subtitle = self._get_font(20, bold=False)
        font_badge = self._get_font(16, bold=True)

        title = tournament.get("name", "TORNEIO OFICIAL").upper()
        game = tournament.get("game_name", "Geral")
        fmt = tournament.get("format", "1v1")
        prize = tournament.get("prize", "Glória e Pontos")

        # Guild Icon / Logo
        if guild.icon:
            try:
                icon_asset = guild.icon.with_size(128)
                icon_bytes = await icon_asset.read()
                icon_img = Image.open(BytesIO(icon_bytes)).convert("RGBA").resize((90, 90), Image.Resampling.LANCZOS)
                mask = Image.new('L', (90, 90), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, 90, 90), fill=255)
                img.paste(icon_img, (60, 35), mask)
            except Exception:
                pass

        draw.text((170, 35), title, fill=self.TEXT_WHITE, font=font_title)
        subtitle_text = f"🎮 {game.upper()}  •  ⚔️ FORMATO: {fmt.upper()}  •  🎁 PREMIAÇÃO: {prize}  •  👥 {len(participants)} INSCRITOS"
        draw.text((170, 88), subtitle_text, fill=self.NEON_CYAN, font=font_subtitle)

        # Badge Status Top Right
        status_text = "● INSCRIÇÕES ABERTAS" if tournament.get("status") == "open" else "● FASE ELIMINATÓRIA"
        badge_color = (34, 197, 94) if tournament.get("status") == "open" else self.GOLD
        draw.rounded_rectangle([WIDTH - 320, 45, WIDTH - 60, 95], radius=8, fill=(20, 30, 50), outline=badge_color, width=2)
        draw.text((WIDTH - 295, 60), status_text, fill=badge_color, font=font_badge)

        # Separator Line
        draw.line([(60, 140), (WIDTH - 60, 140)], fill=self.BG_CARD_BORDER, width=2)

        # 3. Organizar Participantes em Times
        is_2v2 = "2v2" in fmt.lower() or "dupla" in fmt.lower()
        team_size = 2 if is_2v2 else 1

        teams = []
        for i in range(0, len(participants), team_size):
            chunk = participants[i:i + team_size]
            teams.append(chunk)

        # Se tiver menos de 8 times, preenche com placeholders "Aguardando"
        total_slots = 8
        while len(teams) < total_slots:
            teams.append([])

        teams = teams[:8]  # Limita a 8 times nas quartas para caber perfeitamente no layout

        # Pré-carregar Avatares
        team_avatars = []
        for t in teams:
            t_avs = []
            for p in t:
                m = guild.get_member(p.get("user_id", 0))
                av = await self._fetch_avatar(m, p, size=38)
                t_avs.append((m, p, av))
            team_avatars.append(t_avs)

        # 4. Desenhar Bracket / Árvore de Eliminação (Esquerda -> Centro <- Direita ou 3 Rodadas)
        # Layout: Quartas (Left & Right), Semis (Mid-Left & Mid-Right), Grande Final (Centro)
        font_team_name = self._get_font(18, bold=True)
        font_round_title = self._get_font(20, bold=True)
        font_vs = self._get_font(14, bold=True)

        CARD_W = 280
        CARD_H = 75
        
        # Coordenadas das Quartas (4 confrontos = 8 times)
        # Lado Esquerdo: Times 0 vs 1 (Match 1), Times 2 vs 3 (Match 2)
        # Lado Direito: Times 4 vs 5 (Match 3), Times 6 vs 7 (Match 4)
        
        left_q_x = 80
        right_q_x = WIDTH - 80 - CARD_W
        
        left_semi_x = 440
        right_semi_x = WIDTH - 440 - CARD_W
        
        final_x = (WIDTH - CARD_W) // 2
        
        # Títulos das Rodadas
        draw.text((left_q_x + 60, 160), "QUARTAS DE FINAL", fill=self.TEXT_MUTED, font=font_round_title)
        draw.text((left_semi_x + 75, 160), "SEMIFINAL", fill=self.TEXT_MUTED, font=font_round_title)
        draw.text((final_x + 75, 160), "GRANDE FINAL", fill=self.GOLD, font=font_round_title)
        draw.text((right_semi_x + 75, 160), "SEMIFINAL", fill=self.TEXT_MUTED, font=font_round_title)
        draw.text((right_q_x + 60, 160), "QUARTAS DE FINAL", fill=self.TEXT_MUTED, font=font_round_title)

        def draw_team_card(x, y, team_data, team_idx, placeholder_label=None):
            draw.rounded_rectangle(
                [x, y, x + CARD_W, y + CARD_H],
                radius=10,
                fill=self.BG_CARD,
                outline=self.BG_CARD_BORDER,
                width=2
            )
            if not team_data:
                label = placeholder_label or f"Time #{team_idx + 1} (Aguardando)"
                draw.text((x + 20, y + 26), label, fill=self.TEXT_MUTED, font=font_team_name)
                return

            # Renderiza membros do time
            offset_x = x + 12
            names = []
            for m, p, av in team_data:
                img.paste(av, (offset_x, y + 18), av)
                name = m.display_name if m else (p.get("username") or "Jogador")
                names.append(name[:12])
                offset_x += 44

            team_label = " & ".join(names)
            draw.text((offset_x + 8, y + 26), team_label[:18], fill=self.TEXT_WHITE, font=font_team_name)

        # --- QUARTAS DE FINAL (LEFT) ---
        # Match 1: T0 vs T1
        y_m1_t0 = 230
        y_m1_t1 = 330
        draw_team_card(left_q_x, y_m1_t0, team_avatars[0], 0)
        draw_team_card(left_q_x, y_m1_t1, team_avatars[1], 1)
        draw.text((left_q_x + CARD_W // 2 - 10, y_m1_t0 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

        # Match 2: T2 vs T3
        y_m2_t2 = 540
        y_m2_t3 = 640
        draw_team_card(left_q_x, y_m2_t2, team_avatars[2], 2)
        draw_team_card(left_q_x, y_m2_t3, team_avatars[3], 3)
        draw.text((left_q_x + CARD_W // 2 - 10, y_m2_t2 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

        # --- QUARTAS DE FINAL (RIGHT) ---
        # Match 3: T4 vs T5
        y_m3_t4 = 230
        y_m3_t5 = 330
        draw_team_card(right_q_x, y_m3_t4, team_avatars[4], 4)
        draw_team_card(right_q_x, y_m3_t5, team_avatars[5], 5)
        draw.text((right_q_x + CARD_W // 2 - 10, y_m3_t4 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

        # Match 4: T6 vs T7
        y_m4_t6 = 540
        y_m4_t7 = 640
        draw_team_card(right_q_x, y_m4_t6, team_avatars[6], 6)
        draw_team_card(right_q_x, y_m4_t7, team_avatars[7], 7)
        draw.text((right_q_x + CARD_W // 2 - 10, y_m4_t6 + 78), "VS", fill=self.NEON_PURPLE, font=font_vs)

        # --- SEMIFINAIS ---
        y_semi_left_1 = 280
        y_semi_left_2 = 590
        draw_team_card(left_semi_x, y_semi_left_1, [], 0, "Vencedor Q1")
        draw_team_card(left_semi_x, y_semi_left_2, [], 1, "Vencedor Q2")
        draw.text((left_semi_x + CARD_W // 2 - 10, 440), "VS", fill=self.NEON_PURPLE, font=font_vs)

        y_semi_right_1 = 280
        y_semi_right_2 = 590
        draw_team_card(right_semi_x, y_semi_right_1, [], 2, "Vencedor Q3")
        draw_team_card(right_semi_x, y_semi_right_2, [], 3, "Vencedor Q4")
        draw.text((right_semi_x + CARD_W // 2 - 10, 440), "VS", fill=self.NEON_PURPLE, font=font_vs)

        # --- GRANDE FINAL & TROFÉU ---
        y_final_1 = 360
        y_final_2 = 500
        draw_team_card(final_x, y_final_1, [], 0, "Finalista 1")
        draw_team_card(final_x, y_final_2, [], 1, "Finalista 2")
        draw.text((final_x + CARD_W // 2 - 10, 442), "VS", fill=self.GOLD, font=font_vs)

        # Troféu / Campeão Box
        trophy_box_y = 660
        draw.rounded_rectangle(
            [final_x, trophy_box_y, final_x + CARD_W, trophy_box_y + 90],
            radius=12,
            fill=(30, 40, 20),
            outline=self.GOLD,
            width=2
        )
        font_champ_title = self._get_font(22, bold=True)
        draw.text((final_x + 55, trophy_box_y + 16), "🏆 CAMPEÃO", fill=self.GOLD, font=font_champ_title)

        winner_id = tournament.get("winner_id")
        if winner_id:
            w_member = guild.get_member(winner_id)
            w_name = w_member.display_name if w_member else "Campeão Definido"
            draw.text((final_x + 35, trophy_box_y + 50), f"👑 {w_name}", fill=self.TEXT_WHITE, font=font_team_name)
        else:
            draw.text((final_x + 70, trophy_box_y + 50), "A Definir...", fill=self.TEXT_MUTED, font=font_team_name)

        # --- CONEXÕES / LINHAS DO BRACKET (NEON CONNECTORS) ---
        # Conexão Q1 (Left) -> Semi 1
        q1_mid_y = (y_m1_t0 + CARD_H // 2 + y_m1_t1 + CARD_H // 2) // 2
        draw.line([(left_q_x + CARD_W, y_m1_t0 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t0 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W, y_m1_t1 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W + 40, y_m1_t0 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m1_t1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W + 40, q1_mid_y), (left_semi_x, y_semi_left_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # Conexão Q2 (Left) -> Semi 2
        q2_mid_y = (y_m2_t2 + CARD_H // 2 + y_m2_t3 + CARD_H // 2) // 2
        draw.line([(left_q_x + CARD_W, y_m2_t2 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W, y_m2_t3 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W + 40, y_m2_t2 + CARD_H // 2), (left_q_x + CARD_W + 40, y_m2_t3 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_q_x + CARD_W + 40, q2_mid_y), (left_semi_x, y_semi_left_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # Conexão Semis (Left) -> Final 1
        draw.line([(left_semi_x + CARD_W, y_semi_left_1 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_left_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_semi_x + CARD_W, y_semi_left_2 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_left_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_semi_x + CARD_W + 30, y_semi_left_1 + CARD_H // 2), (left_semi_x + CARD_W + 30, y_semi_left_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(left_semi_x + CARD_W + 30, (y_semi_left_1 + y_semi_left_2 + CARD_H) // 2), (final_x, y_final_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # Conexão Q3 (Right) -> Semi 1
        q3_mid_y = (y_m3_t4 + CARD_H // 2 + y_m3_t5 + CARD_H // 2) // 2
        draw.line([(right_q_x, y_m3_t4 + CARD_H // 2), (right_q_x - 40, y_m3_t4 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x, y_m3_t5 + CARD_H // 2), (right_q_x - 40, y_m3_t5 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x - 40, y_m3_t4 + CARD_H // 2), (right_q_x - 40, y_m3_t5 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x - 40, q3_mid_y), (right_semi_x + CARD_W, y_semi_right_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # Conexão Q4 (Right) -> Semi 2
        q4_mid_y = (y_m4_t6 + CARD_H // 2 + y_m4_t7 + CARD_H // 2) // 2
        draw.line([(right_q_x, y_m4_t6 + CARD_H // 2), (right_q_x - 40, y_m4_t6 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x, y_m4_t7 + CARD_H // 2), (right_q_x - 40, y_m4_t7 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x - 40, y_m4_t6 + CARD_H // 2), (right_q_x - 40, y_m4_t7 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_q_x - 40, q4_mid_y), (right_semi_x + CARD_W, y_semi_right_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # Conexão Semis (Right) -> Final 2
        draw.line([(right_semi_x, y_semi_right_1 + CARD_H // 2), (right_semi_x - 30, y_semi_right_1 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_semi_x, y_semi_right_2 + CARD_H // 2), (right_semi_x - 30, y_semi_right_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_semi_x - 30, y_semi_right_1 + CARD_H // 2), (right_semi_x - 30, y_semi_right_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)
        draw.line([(right_semi_x - 30, (y_semi_right_1 + y_semi_right_2 + CARD_H) // 2), (final_x + CARD_W, y_final_2 + CARD_H // 2)], fill=self.LINE_ACTIVE, width=3)

        # 5. Footer Section
        draw.line([(60, HEIGHT - 80), (WIDTH - 60, HEIGHT - 80)], fill=self.BG_CARD_BORDER, width=1)
        font_footer = self._get_font(16, bold=False)
        draw.text((60, HEIGHT - 55), "⚡ Gerado automaticamente pelo sistema BMIA Esports • Use /torneio status para acompanhar", fill=self.TEXT_MUTED, font=font_footer)
        draw.text((WIDTH - 300, HEIGHT - 55), "BDP COMMUNITY • 2026", fill=self.NEON_CYAN, font=font_footer)

        # Retorna buffer PNG
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
