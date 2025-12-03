
import asyncio
import os
import logging
from dotenv import load_dotenv
from database import Database
from utils.points_manager import PointsManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def restore_points():
    load_dotenv()
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        logger.error("DATABASE_URL não encontrada.")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    points_manager = PointsManager(db)

    try:
        logger.info("🔍 Buscando sessões de voz sem pontos atribuídos...")
        
        # Query para encontrar sessões sem pontos correspondentes
        query = """
            SELECT
                va.user_id,
                u.username,
                va.joined_at,
                va.left_at,
                va.duration_seconds,
                (va.duration_seconds / 60) as expected_points
            FROM
                voice_activity va
            JOIN
                users u ON va.user_id = u.user_id
            WHERE
                va.duration_seconds > 60
                AND va.left_at IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM interaction_points ip
                    WHERE ip.user_id = va.user_id
                      AND ip.interaction_type = 'voice'
                      AND ip.created_at BETWEEN va.left_at - INTERVAL '10 seconds' AND va.left_at + INTERVAL '10 seconds'
                )
            ORDER BY
                va.left_at DESC;
        """
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(query)
            
        logger.info(f"📋 Encontradas {len(rows)} sessões elegíveis para restauração.")
        
        total_points_restored = 0
        
        for row in rows:
            user_id = row['user_id']
            username = row['username']
            points = int(row['expected_points'])
            
            if points > 0:
                logger.info(f"➕ Restaurando {points} pontos para {username} (ID: {user_id})...")
                await points_manager.add_points(user_id, points, 'voice', username)
                total_points_restored += points
                
        logger.info(f"✅ Restauração concluída! Total de pontos restaurados: {total_points_restored}")

    except Exception as e:
        logger.error(f"❌ Erro durante a restauração: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(restore_points())
