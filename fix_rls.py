import asyncio
import os
from dotenv import load_dotenv
from database import Database

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def main():
    if not DATABASE_URL:
        print("DATABASE_URL not found")
        return

    db = Database(DATABASE_URL)
    await db.connect()
    
    print("Adding RLS policy to 'channels' table...")
    
    try:
        async with db.pool.acquire() as conn:
            # Check if policy exists
            policy_exists = await conn.fetchval("""
                SELECT 1 FROM pg_policies 
                WHERE tablename = 'channels' AND policyname = 'Enable read access for all users'
            """)
            
            if not policy_exists:
                await conn.execute("""
                    CREATE POLICY "Enable read access for all users" 
                    ON "public"."channels" 
                    AS PERMISSIVE FOR SELECT 
                    TO public 
                    USING (true);
                """)
                print("✅ Policy created successfully.")
            else:
                print("ℹ️ Policy already exists.")
                
            # Also check for 'embed_requests' table, might need insert access
            # The frontend inserts into 'embed_requests'.
            # We need a policy for INSERT for anon/public if we want anyone to send embeds, 
            # OR we need to be authenticated.
            # For now, let's enable INSERT for public for embed_requests too.
            
            # Check if RLS is enabled on embed_requests
            rls_embed = await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE relname = 'embed_requests'")
            if rls_embed:
                print("RLS is enabled on 'embed_requests'. Adding INSERT policy...")
                policy_insert_exists = await conn.fetchval("""
                    SELECT 1 FROM pg_policies 
                    WHERE tablename = 'embed_requests' AND policyname = 'Enable insert for all users'
                """)
                
                if not policy_insert_exists:
                    await conn.execute("""
                        CREATE POLICY "Enable insert for all users" 
                        ON "public"."embed_requests" 
                        AS PERMISSIVE FOR INSERT 
                        TO public 
                        WITH CHECK (true);
                    """)
                    print("✅ Insert policy created for 'embed_requests'.")
                else:
                    print("ℹ️ Insert policy already exists for 'embed_requests'.")
            else:
                print("RLS not enabled on 'embed_requests' (or table not found).")
                # If table exists but RLS is off, it's fine (open access). 
                # But usually Supabase enables it by default if created via dashboard? 
                # I created it via SQL in main.py? No, I haven't created embed_requests table in main.py yet!
                # Wait, I did in a previous turn?
                # Let's check if embed_requests table exists.
                
            table_exists = await conn.fetchval("SELECT to_regclass('public.embed_requests')")
            if not table_exists:
                print("⚠️ Table 'embed_requests' does NOT exist! Creating it...")
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS embed_requests (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        message_data JSONB NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                    ALTER TABLE embed_requests ENABLE ROW LEVEL SECURITY;
                    CREATE POLICY "Enable insert for all users" ON "public"."embed_requests" FOR INSERT TO public WITH CHECK (true);
                    CREATE POLICY "Enable read for all users" ON "public"."embed_requests" FOR SELECT TO public USING (true); -- Bot needs to read
                """)
                print("✅ Table 'embed_requests' created.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
