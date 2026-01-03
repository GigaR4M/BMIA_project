-- Grant execute permissions on updated functions to Supabase roles
GRANT EXECUTE ON FUNCTION get_top_users_by_messages(TEXT, INTEGER, INTEGER, TEXT) TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_top_users_by_voice(TEXT, INTEGER, INTEGER, TEXT) TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_daily_message_stats(TEXT, INTEGER, TEXT, TEXT) TO postgres, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_daily_voice_stats(TEXT, INTEGER, TEXT, TEXT) TO postgres, anon, authenticated, service_role;

-- Ensure table access is still valid (redundant but safe)
GRANT ALL ON daily_user_stats TO postgres, anon, authenticated, service_role;
