import time
from collections import defaultdict, deque

class SpamDetector:
    def __init__(self, max_messages=5, time_window=5):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_messages = defaultdict(deque)

    def is_spam(self, user_id):
        current_time = time.time()

        # Limpeza periódica de usuários inativos para evitar memory leak
        if len(self.user_messages) > 100:
            inactive = [
                uid for uid, ts in self.user_messages.items()
                if not ts or ts[-1] < current_time - self.time_window
            ]
            for uid in inactive:
                del self.user_messages[uid]

        timestamps = self.user_messages[user_id]

        # Remove old timestamps
        while timestamps and timestamps[0] < current_time - self.time_window:
            timestamps.popleft()

        # Add current timestamp
        timestamps.append(current_time)

        # Check if spam
        if len(timestamps) > self.max_messages:
            return True
        
        return False
