import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

SQL_UPDATE = """
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
    AND (
      a.activity_type = 'streaming' 
      OR a.activity_name = 'Streaming'
      OR a.activity_type = 'screen_share' 
      OR a.activity_name = 'Screen Share'
    ) 
  GROUP BY u.user_id, u.username, u.discriminator
  ORDER BY value_seconds DESC
  LIMIT p_limit;
$function$;
"""

async def apply():
    if not DATABASE_URL:
        print("DATABASE_URL not found.")
        return
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Updating get_highlight_longest_streaming...")
        await conn.execute(SQL_UPDATE)
        print("✅ Success.")
        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(apply())
