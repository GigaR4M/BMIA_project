
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database
from utils.image_generator import PodiumBuilder
from unittest.mock import MagicMock
from io import BytesIO
from PIL import Image

# Mock for discord.Member avatar (colored square)
class MockAsset:
    def __init__(self, color=(128, 128, 128)): # default grey
        self.color = color

    def with_size(self, size):
        return self

    async def read(self):
        img = Image.new('RGB', (128, 128), color=self.color)
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()

async def main():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Erro: DATABASE_URL não encontrada no .env")
        return

    db = Database(db_url)
    await db.connect()
    
    # Mock Guild for Image Generation
    guild_mock = MagicMock()
    # We will need to mock 'get_member' to return something for the user IDs found
    members_cache = {}
    def get_member_side_effect(user_id):
        if user_id not in members_cache:
            m = MagicMock()
            m.display_name = f"User_{user_id}"
            m.display_avatar = MockAsset() # Randomize color?
            members_cache[user_id] = m
        return members_cache[user_id]
    
    guild_mock.get_member.side_effect = get_member_side_effect
    
    builder = PodiumBuilder()
    
    # Needs a guild_id to filter points. Assuming user knows it or we fetch the first one found in DB.
    # For this test, I'll fetch the most active guild from daily_stats or interaction_points to grab a valid ID.
    # Or purely rely on user context which isn't available here directly.
    # Try to find a guild_id from the database.
    try:
        # Check various tables for guild_ids
        guilds_interactions = await db.pool.fetch("SELECT DISTINCT guild_id FROM interaction_points")
        guilds_messages = await db.pool.fetch("SELECT DISTINCT guild_id FROM messages")
        guilds_channels = await db.pool.fetch("SELECT DISTINCT guild_id FROM channels")
        
        all_guilds = set()
        for r in guilds_interactions: all_guilds.add(r['guild_id'])
        for r in guilds_messages: all_guilds.add(r['guild_id'])
        for r in guilds_channels: all_guilds.add(r['guild_id'])
        
        print(f"Guild IDs encontrados no DB: {all_guilds}")
        
        if not all_guilds:
             print("Nenhum guild_id encontrado em nenhuma tabela.")
             await db.disconnect()
             return
             
        if not all_guilds:
             print("Nenhum guild_id encontrado em nenhuma tabela.")
             await db.disconnect()
             return
             
        # Iterate over all valid guilds
        valid_guilds = [g for g in all_guilds if g is not None]
        print(f"Guilds válidas para verificação: {valid_guilds}")
        
        for guild_id in valid_guilds:
            print(f"\n==================== Verificando Guild ID: {guild_id} ====================")
            
            # 1. November 2025
            start_nov = datetime(2025, 11, 1)
            end_nov = datetime(2025, 12, 1)
            print(f"--- Buscando dados de Novembro 2025 ({start_nov} - {end_nov}) ---")
            
            try:
                # Custom query to include orphaned points
                rows = await db.pool.fetch("""
                    SELECT 
                        u.user_id,
                        u.username,
                        u.discriminator,
                        COALESCE(SUM(ip.points), 0) as total_points
                    FROM interaction_points ip
                    JOIN users u ON ip.user_id = u.user_id
                    WHERE (ip.guild_id = $1 OR ip.guild_id IS NULL)
                      AND ip.created_at >= $2
                      AND ip.created_at < $3
                    GROUP BY u.user_id, u.username, u.discriminator
                    ORDER BY total_points DESC
                    LIMIT $4
                """, guild_id, start_nov, end_nov, 3)
                top_nov = [dict(r) for r in rows]

                if top_nov:
                    print(f"Top 3 Novembro (Guild {guild_id} + Orphans):")
                    for u in top_nov:
                        print(f" - {u['username']} (ID: {u['user_id']}): {u['total_points']} pts")
                    
                    buffer = await builder.generate_podium(guild_mock, top_nov, period_text="Novembro 2025")
                    filename = f"podium_nov_2025_{guild_id}.png"
                    with open(filename, 'wb') as f:
                        f.write(buffer.getvalue())
                    print(f"Imagem '{filename}' gerada.")
                else:
                    print(f"Sem dados para Novembro 2025 (Guild {guild_id}).")

            except Exception as e:
                print(f"Erro ao processar Novembro (Guild {guild_id}): {e}")

            # 2. Year 2025
            start_year = datetime(2025, 1, 1)
            end_year = datetime(2026, 1, 1)
            print(f"--- Buscando dados do Ano 2025 ({start_year} - {end_year}) ---")
            
            try:
                # Custom query to include orphaned points
                rows = await db.pool.fetch("""
                    SELECT 
                        u.user_id,
                        u.username,
                        u.discriminator,
                        COALESCE(SUM(ip.points), 0) as total_points
                    FROM interaction_points ip
                    JOIN users u ON ip.user_id = u.user_id
                    WHERE (ip.guild_id = $1 OR ip.guild_id IS NULL)
                      AND ip.created_at >= $2
                      AND ip.created_at < $3
                    GROUP BY u.user_id, u.username, u.discriminator
                    ORDER BY total_points DESC
                    LIMIT $4
                """, guild_id, start_year, end_year, 3)
                top_year = [dict(r) for r in rows]

                if top_year:
                    print(f"Top 3 Ano 2025 (Guild {guild_id} + Orphans):")
                    for u in top_year:
                        print(f" - {u['username']} (ID: {u['user_id']}): {u['total_points']} pts")

                    buffer = await builder.generate_podium(guild_mock, top_year, period_text="Ano 2025")
                    filename = f"podium_year_2025_{guild_id}.png"
                    with open(filename, 'wb') as f:
                        f.write(buffer.getvalue())
                    print(f"Imagem '{filename}' gerada.")
                else:
                     print(f"Sem dados para Ano 2025 (Guild {guild_id}).")

            except Exception as e:
                print(f"Erro ao processar Ano 2025 (Guild {guild_id}): {e}")

    except Exception as e:
        print(f"Erro geral: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
