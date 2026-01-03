import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

# Revert to accepted timestamp without time zone but shift it correctly using logic
# Or keep timestamptz and cast field.
# Best approach:
# `v.joined_at` is Timestamp Without Timezone (Local Brazil).
# `p_start_date` is Timestamp With Timezone (e.g. 2026-01-01 00:00:00+00 - UTC).
# If we compare `v.joined_at >= p_start_date`:
# Postgres converts `v.joined_at` to Timestamptz using Session Timezone (UTC).
# So `2026-01-01 00:00:00` (Local) becomes `2026-01-01 00:00:00+00` (UTC).
# Matches `p_start_date`.
# But `2026-01-01 00:00:00` (Local) is arguably `2026-01-01 03:00:00+00` (UTC).
# So we are comparing "Midnight Local" (interpreted as Midnight UTC) vs "Midnight UTC".
# Effectively, we are asking "Is this time >= Midnight UTC?".
# Since Midnight Local happens 3 hours AFTER Midnight UTC (relative to absolute time)... wait.
# Midnight Brazil (03:00 UTC) happens AFTER Midnight UTC (00:00 UTC).
# So `v.joined_at` (00:00 Local) is treated as `00:00 UTC`.
# Comparison: `00:00 UTC` >= `00:00 UTC`? YES.
# BUT, the *real* UTC time of that event was `03:00 UTC`.
#
# The problem is the records from Dec 31st 21:00 UTC (Local 18:00) to Dec 31st 23:59 UTC (Local 21:00)?
# Wait.
# If `v.joined_at` is stored as Local Time.
# Dec 31st 22:00 Local is stored as `2025-12-31 22:00:00`.
# Jan 1st 01:00 Local is stored as `2026-01-01 01:00:00`.
# If `p_start_date` is `2026-01-01 00:00:00+00` (UTC).
# We interpret `v.joined_at` as UTC: `2025-12-31 22:00:00+00`.
# `2025-12-31 22:00:00+00` < `2026-01-01 00:00:00+00`. FALSE. Correctly excluded.
# So `timestamp without time zone` acting as UTC works fine IF the stored date matches the target date string.
#
# BUT, if `p_start_date` is sent as `2026-01-01T00:00:00-03:00` (Brazil Midnight).
# Postgres sees `2026-01-01 03:00:00+00`.
# We interpret `v.joined_at` as UTC: `2026-01-01 01:00:00+00`.
# `01:00+00` >= `03:00+00`? FALSE.
# It excludes 1AM activity!
# This explains why I might check for *missing* data, but here we have *extra* data.
# The user reports 10h 50m (Extra ~5h).
# This implies we are including *too much*.
# This happens if `p_start_date` is `2025-12-31 21:00:00+00`? (Midnight Brazil presented as UTC?)
# Or if `v.joined_at` is interpreted differently.
#
# FIX: Force `v.joined_at` to be treated as Brazil Time explicitly.
# `v.joined_at AT TIME ZONE 'America/Sao_Paulo'` -> converts Local to Timestamptz.
# Then compare with `p_start_date` (Timestamptz).
# This is the most correct semantic comparison.
# `2026-01-01 01:00:00` (Local) -> `2026-01-01 04:00:00+00` (UTC).
# `p_start_date` (`2026-01-01 00:00:00-03:00` i.e. `03:00:00+00`).
# `04:00+00` >= `03:00+00`. TRUE. Included.
# `2025-12-31 22:00:00` (Local) -> `2026-01-01 01:00:00+00` (UTC).
# `01:00+00` >= `03:00+00`. FALSE. Excluded.
# This is Robust.
 
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
      (p_start_date IS NOT NULL AND v.joined_at AT TIME ZONE 'America/Sao_Paulo' >= p_start_date)
      OR 
      (p_start_date IS NULL AND v.joined_at >= NOW() - (p_days || ' days')::INTERVAL) -- Fallback for relative days
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
        print("Applying Robust Timezone Fix...")
        await conn.execute(SQL_CMD)
        print("✅ Applied!")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(apply_fix())
