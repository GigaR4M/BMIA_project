
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from database import Database

async def main():
    load_dotenv()
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("Erro: DATABASE_URL não encontrada no .env")
        return

    db = Database(db_url)
    await db.connect()
    
    # Target User: doctorpraga
    user_id = 312389956045897731
    guild_id = 1327836427915886643 # Found in previous step
    
    print(f"--- Diagnosticando Pontos para User ID: {user_id} ---")
    
    # 1. Total Absoluto (Sem filtro de data)
    total_all = await db.pool.fetchval("""
        SELECT SUM(points) FROM interaction_points 
        WHERE user_id = $1 AND guild_id = $2
    """, user_id, guild_id)
    print(f"Total Absoluto (DB): {total_all}")
    
    # 2. Total 2025
    start_2025 = datetime(2025, 1, 1)
    end_2025 = datetime(2026, 1, 1)
    
    total_2025 = await db.pool.fetchval("""
        SELECT SUM(points) FROM interaction_points 
        WHERE user_id = $1 AND guild_id = $2
        AND created_at >= $3 AND created_at < $4
    """, user_id, guild_id, start_2025, end_2025)
    print(f"Total 2025 ({start_2025.date()} - {end_2025.date()}): {total_2025}")
    
    # 3. Breakdown por Tipo (2025)
    breakdown = await db.pool.fetch("""
        SELECT interaction_type, SUM(points) as p, COUNT(*) as c
        FROM interaction_points
        WHERE user_id = $1 AND guild_id = $2
        AND created_at >= $3 AND created_at < $4
        GROUP BY interaction_type
    """, user_id, guild_id, start_2025, end_2025)
    
    print("\nDetalhamento por Tipo (2025):")
    for r in breakdown:
        print(f" - {r['interaction_type']}: {r['p']} pts ({r['c']} registros)")
        
    # 4. Breakdown Mensal (2025)
    monthly = await db.pool.fetch("""
        SELECT DATE_TRUNC('month', created_at) as m, SUM(points) as p
        FROM interaction_points
        WHERE user_id = $1 AND guild_id = $2
        AND created_at >= $3 AND created_at < $4
        GROUP BY m
        ORDER BY m
    """, user_id, guild_id, start_2025, end_2025)
    
    print("\nDetalhamento Mensal (2025):")
    # 5. Breakdown por Guild ID
    guild_breakdown = await db.pool.fetch("""
        SELECT guild_id, SUM(points) as p
        FROM interaction_points
        WHERE user_id = $1
        GROUP BY guild_id
    """, user_id)
    
    print("\nDetalhamento por Guild ID (Total Absoluto):")
    total_check = 0
    for r in guild_breakdown:
        gid = r['guild_id'] if r['guild_id'] is not None else "None"
        print(f" - Guild {gid}: {r['p']} pts")
        total_check += r['p']
    print(f"Total Geral Verificado: {total_check}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
