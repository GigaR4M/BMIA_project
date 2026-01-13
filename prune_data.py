import asyncio
import os
import logging
from datetime import datetime, timedelta
import asyncpg
from dotenv import load_dotenv

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def prune_data():
    """
    Remove dados antigos para manter o banco de dados leve (Plano Gratuito Supabase).
    Mantém 90 dias de histórico detalhado.
    """
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("❌ DATABASE_URL não encontrada no .env")
        return

    try:
        logger.info("🔌 Conectando ao banco de dados...")
        conn = await asyncpg.connect(database_url)
        
        # Define limite de retenção (90 dias)
        retention_days = 90
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        logger.info(f"📅 Data de corte: {cutoff_date.strftime('%Y-%m-%d')}")

        # 1. Limpar tabela messages
        logger.info("🗑️  Limpando mensagens antigas...")
        result_msgs = await conn.execute("""
            DELETE FROM messages 
            WHERE created_at < $1
        """, cutoff_date)
        logger.info(f"✅ {result_msgs}")

        # 2. Limpar tabela voice_activity
        logger.info("🗑️  Limpando atividade de voz antiga...")
        result_voice = await conn.execute("""
            DELETE FROM voice_activity 
            WHERE joined_at < $1
        """, cutoff_date)
        logger.info(f"✅ {result_voice}")

        # 3. VACUUM (Opcional, mas bom para recuperar espaço físico)
        # Nota: VACUUM não pode ser rodado dentro de transação, porem asyncpg.connect 
        # não abre transação por padrão a menos que explicitado.
        # Mas VACUUM simples é seguro.
        # logger.info("🧹 Executando VACUUM para recuperar espaço...")
        # await conn.execute("VACUUM") 
        # logger.info("✅ VACUUM concluído")

    except Exception as e:
        logger.error(f"❌ Erro ao limpar dados: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()
            logger.info("🔌 Conexão fechada.")

if __name__ == "__main__":
    asyncio.run(prune_data())
