-- Enable Row Level Security (RLS) on internal bot tables
-- This effectively locks down these tables from the public PostgREST API
-- since no policies are defined, denying all access by default.
-- The bot connects directly via Postgres connection string (admin/owner), so it bypasses RLS.

ALTER TABLE IF EXISTS public.server_contexts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.user_bot_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.bot_memories ENABLE ROW LEVEL SECURITY;

-- Verify the changes
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN ('server_contexts', 'user_bot_profiles', 'bot_memories');
