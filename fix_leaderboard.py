import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def fix_bots_in_leaderboard():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL, statement_cache_size=0)
        
        # 1. Update known bots to be is_bot=TRUE just in case
        print("Ensuring known bots are marked as bots...")
        bots = ['Carl-bot', 'FlaviBot', 'BMIA', 'Loritta', 'MEE6'] 
        # Add other common bots if needed or rely on 'Bot' in username
        
        for bot_name in bots:
            await conn.execute("""
                UPDATE users 
                SET is_bot = TRUE 
                WHERE username ILIKE $1 AND is_bot = FALSE
            """, f'%{bot_name}%')
        
        print("Bot status updated.")

        # 2. Update the stored function get_leaderboard
        print("dropping old functions...")
        await conn.execute("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN SELECT oid::regprocedure::text as sig FROM pg_proc WHERE proname = 'get_leaderboard' LOOP
                    EXECUTE 'DROP FUNCTION ' || r.sig;
                END LOOP;
            END$$;
        """)
        print("Old functions dropped.")

        print("Updating stored function get_leaderboard...")
        
        # We redefine the function to include filtering and match Dashboard signature
        # We redefine the function to include filtering and match Dashboard signature
        create_function_sql = """
        CREATE OR REPLACE FUNCTION get_leaderboard(p_limit INT, p_days INT DEFAULT NULL, p_start_date TIMESTAMP WITH TIME ZONE DEFAULT NULL, p_guild_id BIGINT DEFAULT NULL)
        RETURNS TABLE (
            username TEXT,
            user_id BIGINT,
            total_points BIGINT,
            rank BIGINT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                u.username::TEXT,
                u.user_id,
                COALESCE(SUM(p.points), 0)::BIGINT as total_points,
                RANK() OVER (ORDER BY COALESCE(SUM(p.points), 0) DESC)::BIGINT as rank
            FROM users u
            JOIN interaction_points p ON u.user_id = p.user_id
            WHERE u.is_bot = FALSE
              AND (
                  (p_days IS NOT NULL AND p.created_at >= (NOW() - (p_days || ' days')::INTERVAL))
                  OR
                  (p_start_date IS NOT NULL AND p.created_at >= p_start_date)
                  OR
                  (p_days IS NULL AND p_start_date IS NULL)
              )
              AND (p_guild_id IS NULL OR p.guild_id = p_guild_id OR p.guild_id IS NULL)
            GROUP BY u.user_id, u.username
            ORDER BY total_points DESC
            LIMIT p_limit;
        END;
        $$ LANGUAGE plpgsql;
        
        GRANT EXECUTE ON FUNCTION get_leaderboard(INT, INT, TIMESTAMP WITH TIME ZONE, BIGINT) TO anon, authenticated, service_role;
        """
        
        await conn.execute(create_function_sql)
        print("Stored function updated successfully.")
        
        await conn.close()
        print("Connection closed.")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_bots_in_leaderboard())
