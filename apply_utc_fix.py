import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Correct Logic: 
# v.joined_at is stored as UTC (e.g. 01:00:00 for Jan 1 01:00 UTC).
# We must interpret it as UTC explicitly so it compares correctly with Timestamptz params.
# v.joined_at AT TIME ZONE 'UTC' -> Timestamptz.
# 
# Verification confirmed that treating it as Sao Paulo (Local) added 3 hours, causing inclusion of previous day's data.
# Treating it as UTC should exclude the < 03:00 UTC window (if param is 03:00 UTC).

SQL_CMD = """
CREATE OR REPLACE FUNCTION public.get_top_users_by_voice(p_guild_id bigint, p_days integer DEFAULT 30, p_limit integer DEFAULT 10, p_start_date timestamp with time zone DEFAULT NULL::timestamp with time zone)
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
      (p_start_date IS NOT NULL AND v.joined_at AT TIME ZONE 'UTC' >= p_start_date)
      OR 
      (p_start_date IS NULL AND v.joined_at >= NOW() - (p_days || ' days')::INTERVAL)
    )
    AND (v.channel_id NOT IN (
        1356045946743689236, -- Três mosqueteiros
        1335352978986635468  -- AFK
    ) OR v.channel_id IS NULL)
  GROUP BY u.user_id, u.username, u.discriminator
  ORDER BY total_minutes DESC
  LIMIT p_limit;
$function$;
"""

async def apply_fix():
    if not DATABASE_URL: return
    print("Connecting...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Applying UTC Timezone Fix...")
        await conn.execute(SQL_CMD)
        print("✅ Applied!")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(apply_fix())
