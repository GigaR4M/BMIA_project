
import asyncio
from io import BytesIO
from unittest.mock import MagicMock, AsyncMock
from PIL import Image
from utils.image_generator import PodiumBuilder

# Mock for discord.Member's display_avatar
class MockAsset:
    def __init__(self, color):
        self.color = color

    def with_size(self, size):
        return self

    async def read(self):
        # Generate a solid color image in memory
        img = Image.new('RGB', (128, 128), color=self.color)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()

async def main():
    print("Iniciando teste de geração de pódio...")
    
    builder = PodiumBuilder()
    
    # Mock Guild (not actually used deeply in the method, mostly for get_member)
    guild = MagicMock()
    
    # Mock Members
    member1 = MagicMock()
    member1.display_name = "Campeão"
    member1.display_avatar = MockAsset((255, 0, 0)) # Red
    
    member2 = MagicMock()
    member2.display_name = "Vice"
    member2.display_avatar = MockAsset((0, 255, 0)) # Green
    
    member3 = MagicMock()
    member3.display_name = "Terceiro"
    member3.display_avatar = MockAsset((0, 0, 255)) # Blue
    
    # Setup guild.get_member to return our mocks
    # user_ids will be 1, 2, 3
    def get_member_side_effect(user_id):
        if user_id == 1: return member1
        if user_id == 2: return member2
        if user_id == 3: return member3
        return None
    
    guild.get_member.side_effect = get_member_side_effect
    
    top_users = [
        {'user_id': 1, 'username': 'Campeão', 'total_points': 5000},
        {'user_id': 2, 'username': 'Vice', 'total_points': 3500},
        {'user_id': 3, 'username': 'Terceiro', 'total_points': 2000}
    ]
    
    # Generate
    print("Gerando imagem para 'Novembro 2025'...")
    buffer = await builder.generate_podium(guild, top_users, period_text="Novembro 2025")
    
    # Save to disk
    with open('test_podium.png', 'wb') as f:
        f.write(buffer.getvalue())
        
    print("Imagem salva com sucesso: test_podium.png")

if __name__ == "__main__":
    asyncio.run(main())
