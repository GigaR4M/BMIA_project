
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
                # We use DISTINCT ON (user_id) to get only the top 1 per user
                recent_games = await conn.fetch("""
                    WITH UserGameStats AS (
                        SELECT user_id, activity_name, SUM(duration_seconds) as total_duration
                        FROM user_activities
                        WHERE guild_id = $1
                          AND started_at >= NOW() - INTERVAL '30 days'
                          AND activity_type NOT IN ('streaming', 'listening', 'custom', 'hang status')
                        GROUP BY user_id, activity_name
                    )
                    SELECT DISTINCT ON (user_id) 
                        user_id, activity_name, total_duration
                    FROM UserGameStats
                    ORDER BY user_id, total_duration DESC
                """, guild.id)
                
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

                for row in recent_games:
                    uid = row['user_id']
                    if uid not in user_stats: user_stats[uid] = {}
                    user_stats[uid]['most_played_game'] = row['activity_name']

                # Batch Update Profiles
                for uid, stats in user_stats.items():
                    # We only update if we have meaningful data
                    try:
                        # Convert to JSON string
                        stats_json = json.dumps(stats)
                        
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
