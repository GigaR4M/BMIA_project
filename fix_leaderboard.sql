DROP FUNCTION IF EXISTS get_leaderboard(BIGINT, INTEGER, INTEGER, TIMESTAMP);

CREATE OR REPLACE FUNCTION get_leaderboard(
    p_guild_id BIGINT,
    p_limit INTEGER DEFAULT 50,
    p_days INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    user_id TEXT,
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
            -- If start_date is provided, use it
            (p_start_date IS NOT NULL AND ip.created_at >= p_start_date)
            OR
            -- If days is provided and start_date is NULL, use relative window (from NOW)
            (p_start_date IS NULL AND p_days IS NOT NULL AND ip.created_at >= (NOW() - (p_days || ' days')::INTERVAL))
            OR
            -- If both are NULL, return all time
            (p_start_date IS NULL AND p_days IS NULL)
        )
        GROUP BY ip.user_id
    )
    SELECT 
        u.user_id::TEXT,
        u.username,
        u.discriminator,
        up.points as total_points,
        RANK() OVER (ORDER BY up.points DESC) as rank
    FROM UserPoints up
    JOIN users u ON up.user_id = u.user_id
    WHERE u.is_bot = FALSE
    ORDER BY total_points DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;
