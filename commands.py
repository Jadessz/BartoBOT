import discord
from discord.ext import commands
import logging
import random
import time
from config import add_banned_word, remove_banned_word, get_banned_words

logger = logging.getLogger('discord_bot')

def register_commands(bot):
    """Register all command functions with the bot."""
    
    @bot.command(name="ping", help="Check the bot's response time")
    async def ping(ctx):
        """Responds with the bot's latency."""
        start_time = time.time()
        message = await ctx.send("Pinging...")
        end_time = time.time()
        
        # Calculate response time
        response_time = round((end_time - start_time) * 1000)
        
        # Calculate websocket latency
        latency = round(bot.latency * 1000)
        
        embed = discord.Embed(title="Pong! 🏓", color=discord.Color.green())
        embed.add_field(name="API Response", value=f"{response_time}ms", inline=True)
        embed.add_field(name="Websocket Latency", value=f"{latency}ms", inline=True)
        
        await message.edit(content=None, embed=embed)
        logger.info(f"Ping command used by {ctx.author} - Response: {response_time}ms, Latency: {latency}ms")

    @bot.command(name="hello", help="Get a friendly greeting from the bot")
    async def hello(ctx):
        """Responds with a friendly greeting."""
        greetings = [
            f"Hello {ctx.author.mention}! How are you today?",
            f"Hey there {ctx.author.mention}! Nice to see you!",
            f"Hi {ctx.author.mention}! How can I help you?",
            f"Greetings {ctx.author.mention}! Hope you're having a great day!",
            f"Hello {ctx.author.mention}! I'm here and ready to assist!"
        ]
        response = random.choice(greetings)
        await ctx.send(response)
        logger.info(f"Hello command used by {ctx.author}")

    @bot.command(name="roll", help="Roll a dice (default: 1d6)")
    async def roll(ctx, dice: str = "1d6"):
        """Roll dice in NdN format."""
        try:
            rolls, limit = map(int, dice.split('d'))
            
            if rolls > 100:
                await ctx.send("I can't roll that many dice at once! (Max: 100)")
                return
                
            if limit > 1000:
                await ctx.send("That's too many sides for a die! (Max: 1000)")
                return
                
            results = [random.randint(1, limit) for _ in range(rolls)]
            
            # Create a nice formatted response
            if len(results) == 1:
                await ctx.send(f"🎲 You rolled a {results[0]}")
            else:
                total = sum(results)
                await ctx.send(f"🎲 You rolled {dice}: {results} (Total: {total})")
            
            logger.info(f"Roll command used by {ctx.author} - Dice: {dice}, Results: {results}")
        except Exception as e:
            await ctx.send(f"Format has to be NdN (like 1d6, 2d20). Error: {str(e)}")
            logger.warning(f"Invalid roll format from {ctx.author}: {dice}")

    @bot.command(name="info", help="Get information about the bot")
    async def info(ctx):
        """Displays information about the bot."""
        embed = discord.Embed(
            title="Bot Information",
            description="A simple Discord bot built with Python and discord.py",
            color=discord.Color.blue()
        )
        
        # Bot statistics
        embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Uptime", value="Since bot started", inline=True)
        embed.add_field(name="Library", value="discord.py", inline=True)
        
        # Add bot author info
        embed.set_footer(text="Type !help to see available commands")
        
        await ctx.send(embed=embed)
        logger.info(f"Info command used by {ctx.author}")

    @bot.group(name="random", help="Generate random values")
    async def random_group(ctx):
        """Group for random generation commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand. Try `!help random` for more info.")

    @random_group.command(name="number", help="Generate a random number between two values")
    async def random_number(ctx, min_value: int = 1, max_value: int = 100):
        """Generates a random number between min and max (inclusive)."""
        if min_value >= max_value:
            await ctx.send("The minimum value must be less than the maximum value.")
            return
            
        number = random.randint(min_value, max_value)
        await ctx.send(f"🎲 Random number between {min_value} and {max_value}: **{number}**")
        logger.info(f"Random number command used by {ctx.author} - Range: {min_value}-{max_value}, Result: {number}")

    @random_group.command(name="choice", help="Choose a random item from a list")
    async def random_choice(ctx, *options):
        """Chooses a random item from the provided options."""
        if len(options) < 2:
            await ctx.send("Please provide at least two options to choose from, separated by spaces.")
            return
            
        choice = random.choice(options)
        await ctx.send(f"🎯 I choose: **{choice}**")
        logger.info(f"Random choice command used by {ctx.author} - Options: {options}, Result: {choice}")

    @bot.command(name="unmute", help="Remove timeout from a user (requires appropriate permissions)")    
    async def unmute(ctx, member: discord.Member):
        """Removes timeout from a specified member. Requires moderate_members permission."""
        try:
            # Get the mod role IDs from config
            from config import load_config
            config = load_config()
            mod_role_ids = config.get('MOD_ROLE_IDS', [])
            
            # Check if the user has direct permission or any of the mod roles
            has_direct_permission = ctx.author.guild_permissions.moderate_members
            author_role_ids = [role.id for role in ctx.author.roles]
            has_mod_role = any(role_id in author_role_ids for role_id in mod_role_ids)
            
            if not (has_direct_permission or has_mod_role):
                await ctx.send("❌ You don't have permission to use this command.")
                return
            
            # Remove the timeout by setting it to None
            await member.timeout(None)
            
            # Send confirmation message
            embed = discord.Embed(
                title="User Unmuted",
                description=f"✅ {member.mention} has been unmuted.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
            logger.info(f"Unmute command used by {ctx.author} on {member}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to remove timeouts!")
            logger.warning(f"Failed to unmute {member} - Missing bot permissions")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logger.error(f"Error in unmute command: {e}")
    
    @unmute.error
    async def unmute_error(ctx, error):
        """Error handler for the unmute command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command. You need the 'Moderate Members' permission.")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found. Please specify a valid member.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")
            logger.error(f"Unmute command error: {error}")
            
    @bot.command(name="addword", help="Add a word to the banned words list (Admin only)")
    @commands.has_permissions(administrator=True)
    async def add_word(ctx, *, word: str):
        """Add a word to the banned words list."""
        # Remove any extra whitespace
        word = word.strip()
        
        if not word:
            await ctx.send("❌ Please provide a word to ban.")
            return
            
        # Try to add the word to the banned list
        success = add_banned_word(word)
        
        if success:
            embed = discord.Embed(
                title="Word Added to Ban List",
                description=f"✅ Added `{word}` to the banned words list.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            logger.info(f"User {ctx.author} added '{word}' to banned words list.")
        else:
            embed = discord.Embed(
                title="Word Already Banned",
                description=f"ℹ️ The word `{word}` is already in the banned words list.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
    
    @add_word.error
    async def add_word_error(ctx, error):
        """Error handler for the add_word command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command. You need the 'Administrator' permission.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")
            logger.error(f"Add word command error: {error}")
    
    @bot.command(name="removeword", help="Remove a word from the banned words list (Admin only)")
    @commands.has_permissions(administrator=True)
    async def remove_word(ctx, *, word: str):
        """Remove a word from the banned words list."""
        # Remove any extra whitespace
        word = word.strip()
        
        if not word:
            await ctx.send("❌ Please provide a word to remove from the ban list.")
            return
            
        # Try to remove the word from the banned list
        success = remove_banned_word(word)
        
        if success:
            embed = discord.Embed(
                title="Word Removed from Ban List",
                description=f"✅ Removed `{word}` from the banned words list.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            logger.info(f"User {ctx.author} removed '{word}' from banned words list.")
        else:
            embed = discord.Embed(
                title="Word Not Found",
                description=f"ℹ️ The word `{word}` was not found in the banned words list.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
    
    @remove_word.error
    async def remove_word_error(ctx, error):
        """Error handler for the remove_word command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command. You need the 'Administrator' permission.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")
            logger.error(f"Remove word command error: {error}")
    
    @bot.command(name="listwords", help="List all banned words (Admin only)")
    @commands.has_permissions(administrator=True)
    async def list_words(ctx):
        """List all banned words."""
        banned_words = get_banned_words()
        
        if not banned_words:
            embed = discord.Embed(
                title="Banned Words List",
                description="There are no banned words in the list.",
                color=discord.Color.blue()
            )
        else:
            # Format the list of banned words
            words_list = "\n".join([f"• `{word}`" for word in banned_words])
            
            embed = discord.Embed(
                title="Banned Words List",
                description=f"The following words are banned:\n\n{words_list}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Total: {len(banned_words)} banned words")
        
        # Send as a direct message to the admin to avoid showing banned words in public channels
        try:
            await ctx.author.send(embed=embed)
            await ctx.send("✅ I've sent you the list of banned words in a direct message.")
            logger.info(f"User {ctx.author} requested the banned words list.")
        except discord.Forbidden:
            await ctx.send("❌ I couldn't send you a direct message. Please enable DMs from server members.")
    
    @list_words.error
    async def list_words_error(ctx, error):
        """Error handler for the list_words command."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command. You need the 'Administrator' permission.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")
            logger.error(f"List words command error: {error}")

    @bot.command(name="mute", help="Timeout a user for a specified duration with a reason (requires appropriate permissions)")    
    async def mute(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        """Applies timeout to a specified member for the given duration. Requires moderate_members permission."""
        try:
            # Get the mod role IDs from config
            from config import load_config
            config = load_config()
            mod_role_ids = config.get('MOD_ROLE_IDS', [])
            
            # Check if the user has direct permission or any of the mod roles
            has_direct_permission = ctx.author.guild_permissions.moderate_members
            author_role_ids = [role.id for role in ctx.author.roles]
            has_mod_role = any(role_id in author_role_ids for role_id in mod_role_ids)
            
            if not (has_direct_permission or has_mod_role):
                await ctx.send("❌ You don't have permission to use this command.")
                return
            
            # Parse the duration string into seconds
            seconds = 0
            if duration.lower().endswith('s'):
                seconds = int(duration[:-1])
            elif duration.lower().endswith('m'):
                seconds = int(duration[:-1]) * 60
            elif duration.lower().endswith('h'):
                seconds = int(duration[:-1]) * 3600
            elif duration.lower().endswith('d'):
                seconds = int(duration[:-1]) * 86400
            else:
                try:
                    # Assume the input is in seconds if no unit is specified
                    seconds = int(duration)
                except ValueError:
                    await ctx.send("❌ Invalid duration format. Use a number followed by s (seconds), m (minutes), h (hours), or d (days).")
                    return
            
            # Apply the timeout
            import datetime
            timeout_duration = datetime.timedelta(seconds=seconds)
            await member.timeout(timeout_duration, reason=reason)
            
            # Format the duration for display
            duration_text = ""
            if seconds >= 86400:
                days = seconds // 86400
                duration_text = f"{days} day{'s' if days > 1 else ''}"
            elif seconds >= 3600:
                hours = seconds // 3600
                duration_text = f"{hours} hour{'s' if hours > 1 else ''}"
            elif seconds >= 60:
                minutes = seconds // 60
                duration_text = f"{minutes} minute{'s' if minutes > 1 else ''}"
            else:
                duration_text = f"{seconds} second{'s' if seconds > 1 else ''}"
            
            # Send confirmation message
            await ctx.send(f"🔇 @{member.display_name} has been muted by {ctx.author.mention} for {duration_text} | Reason: {reason}")
            
            logger.info(f"Mute command used by {ctx.author} on {member} for {duration_text} with reason: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to timeout members!")
            logger.warning(f"Failed to mute {member} - Missing bot permissions")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            logger.error(f"Error in mute command: {e}")
    
    @mute.error
    async def mute_error(ctx, error):
        """Error handler for the mute command."""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Missing required argument. Usage: ?mute @user duration reason")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found. Please specify a valid member.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument. Make sure you're using the correct format.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")
            logger.error(f"Mute command error: {error}")

    logger.info("Commands registered successfully")
