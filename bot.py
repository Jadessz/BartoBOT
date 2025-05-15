import os
import logging
import discord
from discord.ext import commands
import time
from datetime import timedelta
from config import load_config
from command_handler import CommandHandler
from message_formatter import MessageFormatter
from database_manager import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

def run_bot():
    """Initialize and run the Discord bot."""
    # Load configuration
    config = load_config()
    
    # Initialize message formatter and database manager
    message_formatter = MessageFormatter()
    database_manager = DatabaseManager()
    
    # Set up the bot with command prefix from config
    intents = discord.Intents.default()
    intents.message_content = True  # Enable message content intent
    intents.members = True  # Enable server members intent
    
    bot = commands.Bot(command_prefix=config['COMMAND_PREFIX'], intents=intents)
    
    # Initialize command handler
    command_handler = CommandHandler(bot)
    command_handler.setup_commands()

    # Register event handlers
    @bot.event
    async def on_ready():
        """Event fired when the bot is ready and connected to Discord."""
        logger.info(f'Bot connected as {bot.user.name} (ID: {bot.user.id})')
        logger.info(f'Connected to {len(bot.guilds)} guilds')
        
        # Set bot activity
        activity = discord.Game(name=f"{config['COMMAND_PREFIX']}help")
        await bot.change_presence(activity=activity)
    
    @bot.event
    async def on_guild_join(guild):
        """Event fired when the bot joins a new server/guild."""
        logger.info(f'Joined new guild: {guild.name} (ID: {guild.id})')

    @bot.event
    async def on_message(message):
        """Handle incoming messages and filter banned words."""
        # Don't process messages from the bot itself
        if message.author == bot.user:
            return

        # Skip word filter for administrators and moderators
        if message.author.guild_permissions.administrator or message.author.guild_permissions.moderate_members:
            await bot.process_commands(message)
            return

        # Check for banned words from database
        content_lower = message.content.lower()
        # Get banned words from database
        banned_words = await database_manager.get_banned_words()
        # Split message into words and check each word against banned words
        message_words = content_lower.split()
        found_banned_words = [word for word in banned_words if word in message_words]
        
        if found_banned_words:
            # Delete the message
            await message.delete()
            
            # Warn the user with formatted message
            warning_content = f"{message.author.mention} Your message was removed for containing banned word(s)."
            
            # Log the incident
            logger.warning(f"Removed message from {message.author} containing banned words.")
            
            # Create formatted warning message
            warning_embed = await message_formatter.format_warning(
                warning_content,
                title="Message Removed",
                add_timestamp=True
            )
            # Send and delete warning after 10 seconds
            warning = await message.channel.send(embed=warning_embed)
            await warning.delete(delay=10)
        
        # Process commands after filtering
        await bot.process_commands(message)
    
    # Ticket system reaction handling is now managed by CommandHandler

    @bot.event
    async def on_command_error(ctx, error):
        """Global error handler for command errors."""
        if isinstance(error, commands.CommandNotFound):
            error_embed = await message_formatter.format_error(
                f"Command not found. Try `{config['COMMAND_PREFIX']}help` to see available commands."
            )
            error_msg = await ctx.send(embed=error_embed)
            await error_msg.delete(delay=10)  # Delete after 10 seconds
        elif isinstance(error, commands.MissingRequiredArgument):
            error_embed = await message_formatter.format_error(
                f"Missing required arguments. Try `{config['COMMAND_PREFIX']}help {ctx.command}` for info."
            )
            error_msg = await ctx.send(embed=error_embed)
            await error_msg.delete(delay=10)  # Delete after 10 seconds
        else:
            logger.error(f'Command error: {error}')
            error_embed = await message_formatter.format_error(f"An error occurred: {str(error)}")
            error_msg = await ctx.send(embed=error_embed)
            await error_msg.delete(delay=10)  # Delete after 10 seconds
    
    # Run the bot
    token = config['DISCORD_TOKEN']
    if not token:
        logger.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
        return
    
    while True:
        try:
            logger.info("Starting bot...")
            bot.run(token, reconnect=True)
        except discord.errors.LoginFailure:
            logger.error("Invalid Discord token. Please check your DISCORD_TOKEN environment variable.")
            break  # Exit if token is invalid
        except (discord.errors.ConnectionClosed, discord.errors.GatewayNotFound,
                discord.errors.HTTPException) as e:
            logger.error(f"Connection error: {e}. Retrying in 60 seconds...")
            time.sleep(60)  # Wait before reconnecting
            continue
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in 60 seconds...")
            time.sleep(60)  # Wait before reconnecting
            continue

if __name__ == "__main__":
    run_bot()