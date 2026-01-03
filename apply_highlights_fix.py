import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# SQL commands to fix the functions
SQL_COMMANDS = [
    """
    -- Fix: Change 'STREAMING' to 'streaming' to match lower case storage
    CREATE OR REPLACE FUNCTION public.get_highlight_longest_streaming(p_guild_id bigint, p_limit integer DEFAULT 5)
     RETURNS TABLE(user_id bigint, username text, discriminator text, value_seconds bigint)
     LANGUAGE sql
     SET search_path TO 'public'
    AS $function$
      SELECT 
        u.user_id,
        u.username,
        u.discriminator,
        COALESCE(SUM(a.duration_seconds), 0)::BIGINT as value_seconds
      FROM users u
      INNER JOIN user_activities a ON u.user_id = a.user_id
      WHERE a.guild_id = p_guild_id
        AND u.is_bot = FALSE
        AND a.started_at >= get_start_of_year()
        AND a.duration_seconds > 0
        AND (a.activity_type = 'streaming' OR a.activity_name = 'Streaming') 
      GROUP BY u.user_id, u.username, u.discriminator
      ORDER BY value_seconds DESC
      LIMIT p_limit;
    $function$;
    """,
    """
    -- Fix: Add channel exclusion filter to match get_highlight_most_voice_time
    CREATE OR REPLACE FUNCTION public.get_top_users_by_voice(p_guild_id bigint, p_days integer DEFAULT 30, p_limit integer DEFAULT 10, p_start_date timestamp without time zone DEFAULT NULL::timestamp without time zone)
     RETURNS TABLE(user_id text, username text, discriminator text, total_minutes bigint, last_seen timestamp without time zone)
     LANGUAGE sql
     SET search_path TO 'public'
    AS $function$
      SELECT 
        u.user_id::TEXT,
        u.username,
        u.discriminator,
        COALESCE(SUM(v.duration_seconds) / 60, 0) as total_minutes,
        MAX(v.left_at) as last_seen
      FROM users u
      INNER JOIN voice_activity v ON u.user_id = v.user_id
      WHERE v.guild_id = p_guild_id
        AND (
          (p_start_date IS NOT NULL AND v.joined_at >= p_start_date AT TIME ZONE 'America/Sao_Paulo')
          OR 
          (p_start_date IS NULL AND v.joined_at >= NOW() - (p_days || ' days')::INTERVAL)
        )
        -- Added Filter to match Highlights Page
        AND (v.channel_id NOT IN (
            1356045946743689236, -- Três mosqueteiros
            1335352978986635468  -- AFK
        ) OR v.channel_id IS NULL)
      GROUP BY u.user_id, u.username, u.discriminator
      ORDER BY total_minutes DESC
      LIMIT p_limit;
    $function$;
    """
]

async def apply_fix():
    if not DATABASE_URL:
        print("DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("Applying SQL fixes...")
        for i, sql in enumerate(SQL_COMMANDS):
            print(f"Executing command {i+1}...")
            await conn.execute(sql)
            
        print("✅ Fixes applied successfully!")
        await conn.close()

    except Exception as e:
        print(f"❌ Error applying fixes: {e}")

if __name__ == "__main__":
    asyncio.run(apply_fix())
