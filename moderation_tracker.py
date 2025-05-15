from collections import deque
from datetime import datetime
import discord

class ModerationTracker:
    def __init__(self):
        # Store last 100 moderation actions
        self.mod_history = deque(maxlen=100)
    
    def add_action(self, action_type: str, moderator: discord.Member, target: discord.Member, reason: str = None, duration: str = None):
        """Add a moderation action to the history."""
        action = {
            'timestamp': datetime.now(),
            'type': action_type,
            'moderator': moderator,
            'target': target,
            'reason': reason,
            'duration': duration
        }
        self.mod_history.appendleft(action)
    
    def get_latest_action(self):
        """Get the most recent moderation action."""
        return self.mod_history[0] if self.mod_history else None
    
    def format_action(self, action):
        """Format a moderation action into a readable string."""
        if not action:
            return "No recent moderation actions found."
        
        time_diff = datetime.now() - action['timestamp']
        minutes = int(time_diff.total_seconds() / 60)
        hours = int(minutes / 60)
        days = int(hours / 24)
        
        if days > 0:
            time_ago = f"{days} day{'s' if days != 1 else ''} ago"
        elif hours > 0:
            time_ago = f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            time_ago = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
        action_str = f"**Action:** {action['type']}\n"
        action_str += f"**Moderator:** {action['moderator'].mention}\n"
        action_str += f"**Target:** {action['target'].mention}\n"
        if action['duration']:
            action_str += f"**Duration:** {action['duration']}\n"
        if action['reason']:
            action_str += f"**Reason:** {action['reason']}\n"
        action_str += f"**When:** {time_ago}"
        
        return action_str