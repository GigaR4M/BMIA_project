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
        Gera uma imagem de pódio com os top 3 usuários.
        top_users: lista de dicts com 'user_id', 'username', 'total_points'
        period_text: texto opcional para exibir periodo (ex: "Novembro 2025")
        """
        # 1. Configurar Canvas (800x500)
        img = Image.new('RGB', (800, 500), color=self.BACKGROUND_COLOR)
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
        except:
            font_score = ImageFont.load_default()

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

        # 2. Desenhar cada vencedor
        for i, user_data in enumerate(top_users):
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

        # 3. Retornar buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
