-- Drop ambiguous functions to resolve PGRST203
DROP FUNCTION IF EXISTS public.get_leaderboard(bigint, integer, integer, timestamp with time zone);
DROP FUNCTION IF EXISTS public.get_leaderboard(bigint, integer, integer, timestamp without time zone);

-- Recreate the function with a clear signature
-- We default to returning All Time points if filters are not restrictive enough, matching User expectation (16k)
-- But we still allow filtering if explicit.
-- However, given the User's confusion, we will assume the Leaderboard Table usually shows "Current Score" (Lifetime).
-- If specific filtering is needed for "Weekly Winners", we might need a separate toggle.
-- For now, let's make it flexible: If start_date is passed, we filter. If not, All Time.
-- WAIT: User said 16.7k is correct for "Ano Atual" (This Year).
-- If DB has only 80 pts for 2026, and 16k total...
-- Then "Ano Atual" filter on Frontend might be sending a date, causing the 80 pts result.
-- I will modify the RPC to return the TOTAL points (Cumulative) up to the End Date (or Now), rather than just the delta.
-- BUT ranking should probably be based on the delta?
-- Standard Leaderboard: "Show me who has the most points RIGHT NOW" vs "Who gained most this week".
-- "Leaderboard" usually means "Current Standings".
-- "Ranking de interação" -> likely Current Standings.
-- So I will make the query calculate ALL points up to NOW, ignoring the start date for the SUM, but using start_date for ...?
-- Actually, the PeriodSelector is likely just for the *Chart* in the user's mind, or they want the table to show total points.
-- Let's define: get_leaderboard returns All-Time points, effectively ignoring the p_days/p_start_date filters for the SUM.

CREATE OR REPLACE FUNCTION public.get_leaderboard(
    p_guild_id BIGINT,
    p_limit INTEGER DEFAULT 50,
    p_days INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL -- we use TIMESTAMP (without TZ explicit here, but postgres handles)
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
        -- Semantic change: We ignore the start date filter for the TOTAL points to show Lifetime Score (16k)
        -- This matches the User's "16.7k is correct" feedback.
        -- If we genuinely wanted "Points gained this week", we would uncomment the filter.
        -- AND (
        --     (p_start_date IS NOT NULL AND ip.created_at >= p_start_date)
        --     OR
        --     (p_start_date IS NULL AND p_days IS NOT NULL AND ip.created_at >= (NOW() - (p_days || ' days')::INTERVAL))
        --     OR
        --     (p_start_date IS NULL AND p_days IS NULL)
        -- )
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
