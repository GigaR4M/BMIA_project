import discord
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp

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
