
import os
import logging
from supabase import create_client, Client
from dotenv import load_dotenv

logger = logging.getLogger('discord_bot')

class DatabaseManager:
    def __init__(self):
        load_dotenv()
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("Supabase credentials not found in environment variables")
            raise ValueError("Missing Supabase credentials")
            
        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            logger.info("Successfully connected to Supabase")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            raise
    
    async def get_banned_words(self) -> list:
        """Get all banned words from the database."""
        try:
            response = self.supabase.table('banned_words').select('word').execute()
            return [record['word'] for record in response.data]
        except Exception as e:
            logger.error(f"Error getting banned words: {e}")
            return []
    
    async def add_banned_word(self, word: str) -> bool:
        """Add a word to the banned words list."""
        try:
            word = word.lower().strip()
            # Check if word already exists
            response = self.supabase.table('banned_words').select('word').eq('word', word).execute()
            if response.data:
                return False  # Word already exists
            
            # Add the new word
            self.supabase.table('banned_words').insert({'word': word}).execute()
            return True
        except Exception as e:
            logger.error(f"Error adding banned word: {e}")
            return False
    
    async def remove_banned_word(self, word: str) -> bool:
        """Remove a word from the banned words list."""
        try:
            word = word.lower().strip()
            response = self.supabase.table('banned_words').delete().eq('word', word).execute()
            return len(response.data) > 0  # Returns True if a word was deleted
        except Exception as e:
            logger.error(f"Error removing banned word: {e}")
            return False
            
    async def get_ai_status(self) -> str:
        """Get the AI command status from the database."""
        try:
            response = self.supabase.table('ai-access').select('aistatus').single().execute()
            if response.data:
                return response.data['aistatus']
            return 'On'  # Default to On if no status is set
        except Exception as e:
            logger.error(f"Error getting AI status: {e}")
            return 'On'  # Default to On in case of error
    
    async def set_ai_status(self, status: str) -> bool:
        """Set the AI command status in the database."""
        try:
            status = status.capitalize()  # Ensure proper formatting (On/Off)
            if status not in ['On', 'Off']:
                return False
                
            # Update or insert the status
            response = self.supabase.table('ai-access').upsert({'aistatus': status}).execute()
            return True
        except Exception as e:
            logger.error(f"Error setting AI status: {e}")
            return False
