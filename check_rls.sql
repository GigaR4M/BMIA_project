
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE tablename = 'daily_user_stats';

SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'daily_user_stats';
