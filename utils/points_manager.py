import logging
from database import Database
from datetime import datetime

logger = logging.getLogger(__name__)

class PointsManager:
    def __init__(self, db: Database):
        self.db = db
        # Cache for voice/activity start times: {user_id: start_time}
        self.voice_sessions = {}
        self.activity_sessions = {}

    async def add_points(self, user_id: int, points: int, interaction_type: str, username: str = "Unknown", discriminator: str = "0000"):
        """Adds points to a user for a specific interaction type."""
        try:
            # Ensure user exists
            await self.db.upsert_user(user_id, username, discriminator)
            
            await self.db.add_interaction_point(user_id, points, interaction_type)
            logger.info(f"Added {points} points to user {user_id} for {interaction_type}")
        except Exception as e:
            logger.error(f"Error adding points for user {user_id}: {e}")

    def start_voice_session(self, user_id: int):
        self.voice_sessions[user_id] = datetime.now()

    async def end_voice_session(self, user_id: int):
        start_time = self.voice_sessions.pop(user_id, None)
        if start_time:
            duration = (datetime.now() - start_time).total_seconds()
            minutes = int(duration // 60)
            if minutes > 0:
                await self.add_points(user_id, minutes, 'voice')

    def start_activity_session(self, user_id: int):
        self.activity_sessions[user_id] = datetime.now()

    async def end_activity_session(self, user_id: int):
        start_time = self.activity_sessions.pop(user_id, None)
        if start_time:
            duration = (datetime.now() - start_time).total_seconds()
            minutes = int(duration // 60)
            if minutes > 0:
                await self.add_points(user_id, minutes, 'activity')
