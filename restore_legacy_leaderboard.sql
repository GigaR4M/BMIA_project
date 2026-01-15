-- Drop currently ambiguous functions
DROP FUNCTION IF EXISTS public.get_leaderboard(bigint, integer, integer, timestamp with time zone);
DROP FUNCTION IF EXISTS public.get_leaderboard(bigint, integer, integer, timestamp without time zone);

-- Recreate the original legacy function (best effort reconstruction from dump)
-- It seems it used p_start_date OR p_days to filter interaction_points
-- The default behavior in dashboard was likely "All Time" or "This Year" but user filters apply
-- The dump showed: RANK() OVER (ORDER BY SUM(ip.points) DESC)
-- This implies query on interaction_points and grouping by user.

CREATE OR REPLACE FUNCTION public.get_leaderboard(
    p_guild_id BIGINT,
    p_limit INTEGER DEFAULT 50,
    p_days INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    user_id BIGINT,
    username TEXT,
    discriminator TEXT,
    total_points BIGINT,
    rank BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH UserPoints AS (
        SELECT 
            ip.user_id,
            COALESCE(SUM(ip.points), 0) as points
        FROM interaction_points ip
        WHERE ip.guild_id = p_guild_id
        AND (
            (p_start_date IS NOT NULL AND ip.created_at >= p_start_date)
            OR
            (p_start_date IS NULL AND p_days IS NOT NULL AND ip.created_at >= (NOW() - (p_days || ' days')::INTERVAL))
            OR
            (p_start_date IS NULL AND p_days IS NULL)
        )
        GROUP BY ip.user_id
    )
    SELECT 
        u.user_id,
        u.username,
        u.discriminator,
        up.points as total_points,
        RANK() OVER (ORDER BY up.points DESC) as rank
    FROM UserPoints up
    JOIN users u ON up.user_id = u.user_id
    ORDER BY total_points DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
