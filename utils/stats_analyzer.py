
import logging
import json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StatsAnalyzer:
    def __init__(self, db):
        self.db = db

    async def execute_analysis_loop(self, guilds):
        """Runs the analysis for all guilds."""
        for guild in guilds:
            logger.info(f"📊 Running deterministic stats analysis for {guild.name}...")
            try:
                await self.analyze_guild(guild)
            except Exception as e:
                logger.error(f"Error analyzing guild {guild.name}: {e}")

    async def analyze_guild(self, guild):
        """Computes ranks and stats for users in a guild."""
        
        # 1. Compute Message Ranks
        # We need a query that gives us user_id and their rank based on total messages
        # Assuming 'daily_user_stats' has all history or we use 'interaction_points'?
        # Let's use 'daily_user_stats' context for 'messages_count'.
        
        async with self.db.pool.acquire() as conn:
            # Helper to fetch and update
            async def fetch_and_update():
                # Get Message Ranks (Top 1000 to save resources, or all)
                msg_ranks = await conn.fetch("""
                    WITH user_totals AS (
                        SELECT user_id, SUM(messages_count) as total_msgs
                        FROM daily_user_stats
                        WHERE guild_id = $1
                        GROUP BY user_id
                    )
                    SELECT user_id, total_msgs, 
                           RANK() OVER (ORDER BY total_msgs DESC) as msg_rank
                    FROM user_totals
                    WHERE total_msgs > 0
                """, guild.id)
                
                # Get Voice Ranks
                voice_ranks = await conn.fetch("""
                    WITH user_totals AS (
                        SELECT user_id, SUM(voice_seconds) as total_voice
                        FROM daily_user_stats
                        WHERE guild_id = $1
                        GROUP BY user_id
                    )
                    SELECT user_id, total_voice,
                           RANK() OVER (ORDER BY total_voice DESC) as voice_rank
                    FROM user_totals
                    WHERE total_voice > 0
                """, guild.id)
                
                # Get Favorite Game (Most played in last 30 days)
                # This is trickier, maybe just get top 1 game per user
                # Assuming 'user_activities' exists? Or 'voice_sessions'? 
                # Provide simplest "Top Game" if table exists. 
                # Checking database.py, we have `user_activites` table? 
                # Wait, I need to check schema for games. earlier log mentioned `user_activities` but I didn't verify its schema.
                # I'll rely on `daily_user_stats` just for messages/voice first. 
                # I will skip Game for now to avoid breaking SQL if table differs, 
                # unless I see `get_top_games` in database.py.
                
                # Consolidate results
                user_stats = {}
                
                for row in msg_ranks:
                    uid = row['user_id']
                    if uid not in user_stats: user_stats[uid] = {}
                    user_stats[uid]['msg_rank'] = row['msg_rank']
                    user_stats[uid]['total_msgs'] = row['total_msgs']

                for row in voice_ranks:
                    uid = row['user_id']
                    if uid not in user_stats: user_stats[uid] = {}
                    user_stats[uid]['voice_rank'] = row['voice_rank']
                    user_stats[uid]['total_voice_hours'] = round(row['total_voice'] / 3600, 1)

                # Batch Update Profiles
                for uid, stats in user_stats.items():
                    # We only update if we have meaningful data (Top 10? or just save the rank?)
                    # Let's save the rank for everyone.
                    try:
                        # Convert to JSON string
                        stats_json = json.dumps(stats)
                        
                        # We used a generic update method in database.py `update_user_bot_profile`
                        # It performs an UPSERT.
                        # However, calling it one by one for 1000 users is slow. 
                        # But loop runs in background. It's acceptable for now.
                        
                        # We need to call self.db.update_user_bot_profile WITHOUT re-acquiring pool if possible,
                        # but the method acquires it. So we can't call it from here inside a transaction block easily if 
                        # `update_user_bot_profile` does `async with self.pool.acquire()`.
                        # Nesting acquire is fine with asyncpg pool usually, but potentially deadlock prone if transaction?
                        # No, `acquire` just gives a connection.
                        # Better to just collect data here and update outside or use raw query here.
                        
                        await conn.execute("""
                            INSERT INTO user_bot_profiles (user_id, guild_id, computed_stats, updated_at)
                            VALUES ($1, $2, $3, NOW())
                            ON CONFLICT (user_id, guild_id)
                            DO UPDATE SET computed_stats = EXCLUDED.computed_stats, updated_at = NOW()
                        """, uid, guild.id, stats_json)
                        
                    except Exception as ex:
                        logger.error(f"Failed to update stats for {uid}: {ex}")

            await fetch_and_update()
            logger.info(f"✅ Context stats updated for {guild.name}")
