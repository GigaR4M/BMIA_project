-- Grant permissions to new table
GRANT ALL ON daily_user_stats TO postgres, anon, authenticated, service_role;

-- Update get_top_users_by_messages for robustness
CREATE OR REPLACE FUNCTION get_top_users_by_messages(
  p_guild_id BIGINT,
  p_days INTEGER DEFAULT 30,
  p_limit INTEGER DEFAULT 10,
  p_start_date TEXT DEFAULT NULL
)
RETURNS TABLE (
  user_id BIGINT,
  username TEXT,
  discriminator TEXT,
  message_count BIGINT,
  last_seen TIMESTAMP
)
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT 
    u.user_id,
    u.username,
    u.discriminator,
    SUM(s.messages_count) as message_count,
    u.last_seen
  FROM daily_user_stats s
  INNER JOIN users u ON s.user_id = u.user_id
  WHERE s.guild_id = p_guild_id
    AND (p_start_date IS NULL OR p_start_date = '' OR s.date >= p_start_date::DATE)
    AND (
        (p_start_date IS NOT NULL AND p_start_date != '') 
        OR p_days IS NULL 
        OR s.date >= (CURRENT_DATE - (p_days || ' days')::INTERVAL)::DATE
    )
    AND u.is_bot = FALSE
  GROUP BY u.user_id, u.username, u.discriminator, u.last_seen
  HAVING SUM(s.messages_count) > 0
  ORDER BY message_count DESC
  LIMIT p_limit;
$$;

-- Update get_top_users_by_voice for robustness
CREATE OR REPLACE FUNCTION get_top_users_by_voice(
  p_guild_id BIGINT,
  p_days INTEGER DEFAULT 30,
  p_limit INTEGER DEFAULT 10,
  p_start_date TEXT DEFAULT NULL
)
RETURNS TABLE (
  user_id BIGINT,
  username TEXT,
  discriminator TEXT,
  total_minutes BIGINT,
  last_seen TIMESTAMP
)
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT 
    u.user_id,
    u.username,
    u.discriminator,
    COALESCE(SUM(s.voice_seconds) / 60, 0) as total_minutes,
    u.last_seen
  FROM daily_user_stats s
  INNER JOIN users u ON s.user_id = u.user_id
  WHERE s.guild_id = p_guild_id
    AND (p_start_date IS NULL OR p_start_date = '' OR s.date >= p_start_date::DATE)
    AND (
        (p_start_date IS NOT NULL AND p_start_date != '') 
        OR p_days IS NULL 
        OR s.date >= (CURRENT_DATE - (p_days || ' days')::INTERVAL)::DATE
    )
    AND u.is_bot = FALSE
  GROUP BY u.user_id, u.username, u.discriminator, u.last_seen
  HAVING SUM(s.voice_seconds) > 0
  ORDER BY total_minutes DESC
  LIMIT p_limit;
$$;

-- Update get_daily_message_stats for robustness
CREATE OR REPLACE FUNCTION get_daily_message_stats(
  p_guild_id BIGINT,
  p_days INTEGER DEFAULT 30,
  p_timezone TEXT DEFAULT 'America/Sao_Paulo',
  p_start_date TEXT DEFAULT NULL
)
RETURNS TABLE (
  date DATE,
  message_count BIGINT,
  active_users BIGINT
)
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    s.date as date,
    SUM(s.messages_count) as message_count,
    COUNT(DISTINCT s.user_id) FILTER (WHERE s.messages_count > 0) as active_users
  FROM daily_user_stats s
  INNER JOIN users u ON s.user_id = u.user_id
  WHERE s.guild_id = p_guild_id
    AND (p_start_date IS NULL OR p_start_date = '' OR s.date >= p_start_date::DATE)
    AND (
        (p_start_date IS NOT NULL AND p_start_date != '') 
        OR p_days IS NULL 
        OR s.date >= (CURRENT_DATE - (p_days || ' days')::INTERVAL)::DATE
    )
    AND u.is_bot = FALSE
  GROUP BY 1
  ORDER BY 1;
$$;

-- Update get_daily_voice_stats for robustness
CREATE OR REPLACE FUNCTION get_daily_voice_stats(
  p_guild_id BIGINT,
  p_days INTEGER DEFAULT 30,
  p_timezone TEXT DEFAULT 'America/Sao_Paulo',
  p_start_date TEXT DEFAULT NULL
)
RETURNS TABLE (
  date DATE,
  total_minutes BIGINT,
  active_users BIGINT
)
LANGUAGE SQL
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    s.date as date,
    COALESCE(SUM(s.voice_seconds) / 60, 0) as total_minutes,
    COUNT(DISTINCT s.user_id) FILTER (WHERE s.voice_seconds > 0) as active_users
  FROM daily_user_stats s
  INNER JOIN users u ON s.user_id = u.user_id
  WHERE s.guild_id = p_guild_id
    AND (p_start_date IS NULL OR p_start_date = '' OR s.date >= p_start_date::DATE)
    AND (
        (p_start_date IS NOT NULL AND p_start_date != '') 
        OR p_days IS NULL 
        OR s.date >= (CURRENT_DATE - (p_days || ' days')::INTERVAL)::DATE
    )
    AND u.is_bot = FALSE
  GROUP BY 1
  ORDER BY 1;
$$;
