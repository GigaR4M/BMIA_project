import asyncio
import aiohttp
from utils.image_generator import PodiumBuilder

# Mocks
class MockAsset:
    def __init__(self, url):
        self.url = url
    
    def with_size(self, size):
        return self

    async def read(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as resp:
                return await resp.read()

class MockMember:
    def __init__(self, user_id, name, avatar_url):
        self.id = user_id
        self.display_name = name
        self.display_avatar = MockAsset(avatar_url)

class MockGuild:
    def __init__(self):
        self.members = {}
    
    def add_member(self, member):
        self.members[member.id] = member
    
    def get_member(self, user_id):
        return self.members.get(user_id)

async def test_generation():
    print("Gerando imagem de teste com PodiumBuilder...")
    
    # Dados fictícios do DB
    top_users = [
        {'user_id': 1, 'username': 'GamerPro', 'total_points': 1500},
        {'user_id': 2, 'username': 'StreamerX', 'total_points': 1200},
        {'user_id': 3, 'username': 'ChatterBox', 'total_points': 900}
    ]
    
    # Mock do Guild e Membros
    guild = MockGuild()
    guild.add_member(MockMember(1, 'GamerPro', 'https://cdn.discordapp.com/embed/avatars/0.png'))
    guild.add_member(MockMember(2, 'StreamerX', 'https://cdn.discordapp.com/embed/avatars/1.png'))
    guild.add_member(MockMember(3, 'ChatterBox', 'https://cdn.discordapp.com/embed/avatars/2.png'))
    
    builder = PodiumBuilder()
    image_bio = await builder.generate_podium(guild, top_users)
    
    with open("test_podium.png", "wb") as f:
        f.write(image_bio.getvalue())
        
    print("Imagem salva como test_podium.png")

if __name__ == "__main__":
    asyncio.run(test_generation())
