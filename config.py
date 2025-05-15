import os
import logging
from dotenv import load_dotenv
from database_manager import DatabaseManager

logger = logging.getLogger('discord_bot')

# Initialize database manager
db_manager = None
try:
    db_manager = DatabaseManager()
except Exception as e:
    logger.error(f"Failed to initialize database manager: {e}")

async def get_banned_words():
    """Get the list of banned words from the database."""
    if db_manager is None:
        logger.error("Database manager not initialized")
        return []
    return await db_manager.get_banned_words()

async def add_banned_word(word):
    """Add a word to the banned words list."""
    if db_manager is None:
        logger.error("Database manager not initialized")
        return False
    return await db_manager.add_banned_word(word)

async def remove_banned_word(word):
    """Remove a word from the banned words list."""
    if db_manager is None:
        logger.error("Database manager not initialized")
        return False
    return await db_manager.remove_banned_word(word)

def load_config():
    """
    Load configuration from environment variables.
    Returns a dictionary containing configuration values.
    """
    # Load environment variables from .env file if it exists
    load_dotenv()
    
    # Get Discord token from environment variables
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        logger.warning("DISCORD_TOKEN not found in environment variables.")
    
    # Set command prefix, fallback to '!' if not specified
    command_prefix = os.getenv("COMMAND_PREFIX", "?")
    
    # Create and return config dictionary

    # List of role IDs that can use moderation commands (customize as needed)
    mod_role_ids = os.getenv("MOD_ROLE_IDS", "").split(",")
    try:
        mod_role_ids = [int(role_id.strip()) for role_id in mod_role_ids if role_id.strip()]
    except ValueError:
        logger.warning("Invalid MOD_ROLE_IDS format in environment variables. Using empty list.")
        mod_role_ids = []

    config = {
        "DISCORD_TOKEN": discord_token,
        "COMMAND_PREFIX": command_prefix,
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "MOD_ROLE_IDS": mod_role_ids,
    }
    
    logger.info(f"Configuration loaded. Command prefix: {command_prefix}")
    return config
