import discord
from discord.ext import commands
import logging
import time
import asyncio
import io
from datetime import timedelta
from typing import Dict, Callable, Optional
from message_formatter import MessageFormatter
from moderation_tracker import ModerationTracker
from ticket_manager import TicketManager
from blackjack_manager import BlackjackManager
from ai_manager import AIManager

logger = logging.getLogger('discord_bot')

class CommandHandler:
    def __init__(self, bot: commands.Bot, database_manager):
        self.bot = bot
        self.database_manager = database_manager
        self.commands: Dict[str, dict] = {}
        self.message_formatter = MessageFormatter()
        self.mod_tracker = ModerationTracker()
        self.ticket_manager = TicketManager(bot)
        self.blackjack_manager = BlackjackManager(bot)
        self.ai_manager = AIManager(bot)

    def register_command(self, name: str, func: Callable, help_text: str,
                        required_permissions: Optional[list] = None,
                        required_roles: Optional[list] = None,
                        parent_group: Optional[str] = None):
        """Register a command with the handler."""
        command_info = {
            'function': func,
            'help': help_text,
            'permissions': required_permissions or [],
            'roles': required_roles or [],
            'parent_group': parent_group
        }
        self.commands[name] = command_info

    async def check_role_hierarchy(self, ctx: commands.Context, target: discord.Member) -> bool:
        """Check if the command user has a higher role than the target user."""
        if ctx.author.top_role <= target.top_role:
            error_embed = await self.message_formatter.format_error(
                "❌ You cannot moderate a member with an equal or higher role than you."
            )
            await ctx.send(embed=error_embed, delete_after=10)
            return False
        return True

    async def check_permissions(self, ctx: commands.Context, command_name: str) -> bool:
        """Check if user has required permissions and roles for a command."""
        if command_name not in self.commands:
            return False

        command = self.commands[command_name]

        # Check permissions
        for permission in command['permissions']:
            if not getattr(ctx.author.guild_permissions, permission, False):
                error_embed = await self.message_formatter.format_error(f"You need the '{permission}' permission to use this command.")
                await ctx.send(embed=error_embed, delete_after=10)
                return False

        # Check roles
        if command['roles']:
            user_roles = [role.id for role in ctx.author.roles]
            if not any(role_id in user_roles for role_id in command['roles']):
                error_embed = await self.message_formatter.format_error("You don't have the required role to use this command.")
                await ctx.send(embed=error_embed, delete_after=10)
                return False

        return True

    def setup_commands(self):
        """Set up all registered commands with the bot."""
        # Set up ticket system event handlers
        self.setup_ticket_system()
        
        # Register banned word management commands
        from config import add_banned_word, remove_banned_word, get_banned_words
        
        @self.bot.command(name="addword", help="Add a word to the banned words list (Admin only)")
        @commands.has_permissions(administrator=True)
        async def add_word(ctx, *, word: str):
            word = word.strip()
            if not word:
                await ctx.send("❌ Please provide a word to ban.")
                return
            success = await add_banned_word(word)
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
        
        @self.bot.command(name="removeword", help="Remove a word from the banned words list (Admin only)")
        @commands.has_permissions(administrator=True)
        async def remove_word(ctx, *, word: str):
            word = word.strip()
            if not word:
                await ctx.send("❌ Please provide a word to remove from the ban list.")
                return
            success = await remove_banned_word(word)
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
        
        @self.bot.command(name="listwords", help="List all banned words (Admin only)")
        @commands.has_permissions(administrator=True)
        async def list_words(ctx):
            banned_words = await get_banned_words()
            if not banned_words:
                embed = discord.Embed(
                    title="Banned Words List",
                    description="There are no banned words in the list.",
                    color=discord.Color.blue()
                )
            else:
                words_list = "\n".join([f"• `{word}`" for word in banned_words])
                embed = discord.Embed(
                    title="Banned Words List",
                    description=f"The following words are banned:\n\n{words_list}",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Total: {len(banned_words)} banned words")
            # For large lists (more than 20 words), send as a text file
            if len(banned_words) > 20:
                words_content = "\n".join(banned_words)
                file = discord.File(
                    io.StringIO(words_content),
                    filename="banned_words.txt"
                )
                await ctx.send(
                    "📄 Here's the complete list of banned words:",
                    file=file
                )
            else:
                # For smaller lists, send directly in the channel
                await ctx.send(embed=embed)
            logger.info(f"User {ctx.author} requested the banned words list.")



        # Ticket role management commands
        @self.bot.command(
            name="addticketrole",
            help="Add a role that can access and manage tickets\n\nUsage: ?addticketrole <@role>\n\nParameters:\n- @role: Mention the role to add\n\nExample:\n?addticketrole @Moderator"
        )
        @commands.has_permissions(administrator=True)
        async def add_ticket_role(ctx, role: discord.Role):
            self.ticket_manager.add_ticket_access_role(role.id)
            success_embed = await self.message_formatter.format_success(
                f"Added {role.mention} to ticket access roles",
                title="Role Added ✅"
            )
            await ctx.send(embed=success_embed)

        @self.bot.command(
            name="removeticketrole",
            help="Remove a role from ticket access\n\nUsage: ?removeticketrole <@role>\n\nParameters:\n- @role: Mention the role to remove\n\nExample:\n?removeticketrole @Moderator"
        )
        @commands.has_permissions(administrator=True)
        async def remove_ticket_role(ctx, role: discord.Role):
            self.ticket_manager.remove_ticket_access_role(role.id)
            success_embed = await self.message_formatter.format_success(
                f"Removed {role.mention} from ticket access roles",
                title="Role Removed ✅"
            )
            await ctx.send(embed=success_embed)

        # Set up reaction event handlers
        @self.bot.event
        async def on_raw_reaction_add(payload):
            if payload.member and payload.member.bot:
                return

            channel = self.bot.get_channel(payload.channel_id)
            try:
                message = await channel.fetch_message(payload.message_id)
                reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
                await self.ticket_manager.handle_ticket_reaction(reaction, payload.member)
            except (discord.NotFound, discord.Forbidden):
                pass

        @self.bot.event
        async def on_interaction(interaction):
            if interaction.type == discord.InteractionType.component:
                await self.ticket_manager.handle_button_interaction(interaction)

        # Blackjack command
        @self.bot.command(
            name="blackjack",
            aliases=["bj"],
            help="Play a game of blackjack against the bot\n\nUsage: ?blackjack or ?bj\n\nReact with:\n- ⬆️ to hit (draw another card)\n- ⏹️ to stand (end your turn)"
        )
        async def blackjack(ctx):
            # Start new game
            game_state = self.blackjack_manager.start_game(ctx.author.id)
            if not game_state:
                error_embed = await self.message_formatter.format_error(
                    "You already have an active game!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            # Send initial game state
            game_embed = self.blackjack_manager.format_game_embed(game_state, ctx.author)
            game_message = await ctx.send(embed=game_embed)

            # Add reaction controls
            await game_message.add_reaction("⬆️")  # hit
            await game_message.add_reaction("⏹️")  # stand

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬆️", "⏹️"] and reaction.message.id == game_message.id

            while game_state['status'] == 'playing':
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                    await reaction.remove(user)

                    if str(reaction.emoji) == "⬆️":
                        game_state = await self.blackjack_manager.hit(ctx.author.id)
                    elif str(reaction.emoji) == "⏹️":
                        game_state = await self.blackjack_manager.stand(ctx.author.id, game_message)

                    if game_state:
                        show_dealer = game_state['status'] != 'playing'
                        game_embed = self.blackjack_manager.format_game_embed(game_state, ctx.author, show_dealer)
                        await game_message.edit(embed=game_embed)

                except TimeoutError:
                    # Auto-stand if player takes too long
                    game_state = self.blackjack_manager.stand(ctx.author.id)
                    if game_state:
                        game_embed = self.blackjack_manager.format_game_embed(game_state, ctx.author, True)
                        await game_message.edit(embed=game_embed)
                    break

            # Clean up the game
            self.blackjack_manager.end_game(ctx.author.id)

        @self.bot.command(
            name="bjstats",
            help="View your blackjack statistics\n\nUsage: ?bjstats\n\nDisplays:\n- Total wins\n- Total losses\n- Total draws\n- Win rate"
        )
        async def bjstats(ctx):
            stats_embed = self.blackjack_manager.stats.format_stats_embed(
                str(ctx.author.id),
                ctx.author.display_name
            )
            await ctx.send(embed=stats_embed)

        @self.bot.command(
            name="am",
            help="[Admin Only] Ask the AI assistant a question\n\nUsage: ?am <question>\n\nParameters:\n- question: The question or prompt you want to ask the AI\n\nExample:\n?am How do I make a chocolate cake?"
        )
        @commands.has_permissions(administrator=True)
        async def am(ctx, *, question: str):
            # Check if OpenAI API key is configured
            if not self.ai_manager.api_key:
                error_embed = await self.message_formatter.format_error(
                    "AI features are not available. Please configure the OpenAI API key."
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            # Get AI response
            response, should_format = await self.ai_manager.get_ai_response(question, self.database_manager)
            if not response:
                error_embed = await self.message_formatter.format_error(
                    "Failed to get a response from the AI."
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            # Send response based on formatting flag
            if should_format:
                response_embed = await self.ai_manager.format_ai_response(question, response)
                await ctx.send(embed=response_embed)
            else:
                await ctx.send(response)
            
            logger.info(f"AI command used by {ctx.author} with question: {question}")

        @self.bot.command(
            name="aistatus",
            help="[Admin Only] Get or set the AI command status\n\nUsage:\n?aistatus - Check current status\n?aistatus <On/Off> - Set status\n\nExample:\n?aistatus Off"
        )
        @commands.has_permissions(administrator=True)
        async def aistatus(ctx, status: str = None):
            if status is None:
                # Get current status
                current_status = await self.database_manager.get_ai_status()
                status_embed = await self.message_formatter.format_success(
                    f"AI commands are currently {current_status}",
                    title="AI Status 🤖"
                )
                await ctx.send(embed=status_embed)
                return

            # Set new status
            status = status.capitalize()
            if status not in ['On', 'Off']:
                error_embed = await self.message_formatter.format_error(
                    "Status must be either 'On' or 'Off'"
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            success = await self.database_manager.set_ai_status(status)
            if success:
                status_embed = await self.message_formatter.format_success(
                    f"AI commands have been turned {status}",
                    title="AI Status Updated 🤖"
                )
                await ctx.send(embed=status_embed)
                logger.info(f"AI status set to {status} by {ctx.author}")
            else:
                error_embed = await self.message_formatter.format_error(
                    "Failed to update AI status"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        @self.bot.command(
            name="bjguide",
            help="Learn how to play blackjack and understand card values\n\nUsage: ?bjguide\n\nDisplays comprehensive information about:\n- Basic rules of blackjack\n- Card values\n- How to play the game\n- Basic strategy tips"
        )
        async def bjguide(ctx):
            embed = discord.Embed(
                title="🎰 Blackjack Guide",
                color=discord.Color.gold()
            )

            # Basic Rules
            embed.add_field(
                name="📖 Basic Rules",
                value="Blackjack is a card game where you compete against the dealer. The goal is to get a hand value closer to 21 than the dealer without going over (busting).",
                inline=False
            )

            # Card Values
            embed.add_field(
                name="🎴 Card Values",
                value="• Number cards (2-10): Worth their face value\n• Face cards (J, Q, K): Worth 10\n• Ace (A): Worth 1 or 11 (whichever benefits you more)",
                inline=False
            )

            # Add How to Play field
            embed.add_field(
                name="🎮 How to Play",
                value="1. Start a game with `?blackjack` or `?bj`\n2. You'll get 2 cards, and the dealer shows one card\n3. Choose your action:\n   • ⬆️ Hit: Get another card\n   • ⏹️ Stand: Keep your current hand\n4. Try to get closer to 21 than the dealer!",
                inline=False
            )

            # Strategy Tips
            embed.add_field(
                name="💡 Basic Strategy Tips",
                value="• Stand on 17 or higher\n• Hit on 11 or below\n• Consider the dealer's visible card\n• Remember: The dealer must hit on 16 and below",
                inline=False
            )

            # Create button
            button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Got it!",
                custom_id="guide_confirm"
            )

            # Create view and add button
            view = discord.ui.View(timeout=180)  # 3 minutes timeout
            view.add_item(button)

            # Button callback
            async def button_callback(interaction: discord.Interaction):
                if interaction.user.id == ctx.author.id:
                    await interaction.message.delete()
                else:
                    await interaction.response.send_message("Only the user who requested the guide can dismiss it!", ephemeral=True)

            button.callback = button_callback

            # Send the embed with the view and set up auto-deletion
            message = await ctx.send(embed=embed, view=view)

            # Set up auto-deletion after 3 minutes
            async def delete_after_timeout():
                await asyncio.sleep(180)  # 3 minutes
                try:
                    await message.delete()
                except discord.NotFound:
                    pass  # Message was already deleted by button

            self.bot.loop.create_task(delete_after_timeout())
            logger.info(f"Blackjack guide command used by {ctx.author}")

        # Override default help command
        self.bot.remove_command('help')

        @self.bot.command(
            name='help',
            help='Shows this help message'
        )
        async def help(ctx, command_name: str = None):
            if command_name is None:
                # Initialize command categories
                staff_commands = {
                    "moderation": [],
                    "ticket": [],
                    "ai": []
                }
                fun_commands = []
                utility_commands = []

                for cmd in self.bot.commands:
                    if cmd.hidden:
                        continue

                    command_name = cmd.name.lower()
                    help_text = cmd.help.split('\n')[0] if cmd.help else 'No description available'
                    aliases = f" (or {', '.join(f'`{ctx.prefix}{alias}`' for alias in cmd.aliases)})" if cmd.aliases else ""
                    command_info = f"`{ctx.prefix}{cmd.name}`{aliases} - {help_text}"

                    # Categorize commands
                    if command_name in ['ban', 'unban', 'mute', 'unmute', 'kick', 'purge', 'rmod']:
                        staff_commands["moderation"].append(command_info)
                    elif command_name in ['setticketlog', 'setupticket', 'addticketrole', 'removeticketrole']:
                        staff_commands["ticket"].append(command_info)
                    elif command_name == 'am':
                        staff_commands["ai"].append(command_info)
                    elif command_name in ['blackjack', 'bjstats', 'bjguide', 'coinflip', 'roll']:
                        fun_commands.append(command_info)
                    elif command_name in ['addword', 'removeword', 'listwords']:
                        # Skip these commands as they'll be shown in word filter management section
                        continue
                    else:
                        utility_commands.append(command_info)

                # Create pages for different categories
                pages = []
                
                # Fun Commands Page
                if fun_commands:
                    fun_embed = discord.Embed(title="🎮 Fun Commands", color=discord.Color.purple())
                    fun_embed.description = "\n".join(fun_commands)
                    pages.append(fun_embed)

                # Utility Commands Page
                if utility_commands:
                    utility_embed = discord.Embed(title="🛠️ Utility Commands", color=discord.Color.blue())
                    utility_embed.description = "\n".join(utility_commands)
                    pages.append(utility_embed)

                # Staff Commands Pages
                if any(staff_commands.values()):
                    # Moderation Commands
                    if staff_commands["moderation"]:
                        mod_embed = discord.Embed(title="🛡️ Moderation Commands", color=discord.Color.red())
                        mod_embed.description = "\n".join(staff_commands["moderation"])
                        # Add word filter management
                        mod_embed.add_field(
                            name="📝 Word Filter Management",
                            value="\n".join([
                                f"`{ctx.prefix}addword` - Add a word to the banned words list",
                                f"`{ctx.prefix}removeword` - Remove a word from the banned words list",
                                f"`{ctx.prefix}listwords` - List all banned words"
                            ]),
                            inline=False
                        )
                        pages.append(mod_embed)

                    # Ticket System Commands
                    if staff_commands["ticket"]:
                        ticket_embed = discord.Embed(title="🎫 Ticket System Commands", color=discord.Color.green())
                        ticket_embed.description = "\n".join(staff_commands["ticket"])
                        pages.append(ticket_embed)

                    # AI Commands
                    if staff_commands["ai"]:
                        ai_embed = discord.Embed(title="🤖 AI Commands", color=discord.Color.gold())
                        ai_embed.description = "\n".join(staff_commands["ai"])
                        pages.append(ai_embed)

                if not pages:  # If no commands available
                    error_embed = await self.message_formatter.format_error("No commands available.")
                    await ctx.send(embed=error_embed)
                    return

                # Add page numbers to embeds
                for i, page in enumerate(pages):
                    page.set_footer(text=f"Page {i+1}/{len(pages)} | Use ⬅️ ➡️ to navigate | ❌ to close")

                # Send first page
                current_page = 0
                message = await ctx.send(embed=pages[current_page])

                # Add navigation reactions
                await message.add_reaction("⬅️")
                await message.add_reaction("➡️")
                await message.add_reaction("❌")

                def check(reaction, user):
                    return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️", "❌"] and reaction.message.id == message.id

                while True:
                    try:
                        reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)

                        if str(reaction.emoji) == "❌":
                            await message.delete()
                            break
                        elif str(reaction.emoji) == "➡️":
                            current_page = (current_page + 1) % len(pages)
                        elif str(reaction.emoji) == "⬅️":
                            current_page = (current_page - 1) % len(pages)

                        await message.edit(embed=pages[current_page])
                        await reaction.remove(user)

                    except asyncio.TimeoutError:
                        await message.clear_reactions()
                        break

            else:
                # Show specific command help
                cmd = self.bot.get_command(command_name)
                if cmd is None:
                    error_embed = await self.message_formatter.format_error(f"Command '{command_name}' not found.")
                    await ctx.send(embed=error_embed, delete_after=10)
                    return

                embed = discord.Embed(title=f"Help: {ctx.prefix}{cmd.name}", color=discord.Color.blue())
                embed.description = cmd.help or 'No description available'

                # Add aliases if any
                if cmd.aliases:
                    embed.add_field(name="Aliases", value=f"`{'`, `'.join(cmd.aliases)}`", inline=False)

                # Add permission information if command requires special permissions
                requires_special_perms = False
                if cmd.checks:
                    for check in cmd.checks:
                        if any(isinstance(check, check_type) for check_type in [
                            commands.has_permissions,
                            commands.has_role,
                            commands.has_any_role,
                            commands.has_guild_permissions
                        ]):
                            requires_special_perms = True
                            break

                if requires_special_perms:
                    embed.add_field(name="Note", value="⚠️ This command requires special permissions or roles to use.", inline=False)

                await ctx.send(embed=embed)
        # Coinflip command
        @self.bot.command(
            name="coinflip",
            aliases=["cf"],
            help="Flip a coin and guess the outcome\n\nUsage: ?coinflip [guess]\n\nParameters:\n- guess: Optional. Your guess (heads or tails). If not provided, defaults to 'heads'\n\nExamples:\n?coinflip\n?coinflip heads\n?cf tails"
        )
        async def coinflip(ctx, guess: str = None):
            import random
            result = random.choice(["Heads", "Tails"])

            # Default to 'Heads' if no guess is provided
            if guess is None:
                guess = "heads"

            # Normalize the guess to handle case insensitivity
            normalized_guess = guess.lower().strip()
            if normalized_guess in ["heads", "head", "h"]:
                normalized_guess = "Heads"
            elif normalized_guess in ["tails", "tail", "t"]:
                normalized_guess = "Tails"
            else:
                error_embed = await self.message_formatter.format_error(
                    f"Invalid guess! Please use 'heads' or 'tails'."
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            # Check if user won or lost
            if normalized_guess == result:
                win_status = "\n🎉 You guessed correctly! You win! 🎉"
            else:
                win_status = "\n😔 You guessed wrong! Better luck next time! 😔"

            # Include the user's guess in the message
            guess_text = "" if guess == "heads" and normalized_guess == "Heads" else f" (You guessed: {normalized_guess})"

            embed = await self.message_formatter.format_success(
                f"{ctx.author.mention} flipped a coin and got: **{result}**{guess_text}{win_status}",
                title="Coin Flip 🪙"
            )
            await ctx.send(embed=embed)
            logger.info(f"Coinflip command used by {ctx.author}, result: {result}, guess: {normalized_guess}, won: {win_status.find('win') > 0}")

        # Basic utility commands
        @self.bot.command(
            name="ping",
            help="Check the bot's response time\n\nUsage: ?ping\n\nDisplays:\n- API Response time in milliseconds\n- Websocket Latency in milliseconds\n\nExample:\n?ping"
        )
        async def ping(ctx):
            start_time = time.time()
            message = await ctx.send("Pinging...")
            end_time = time.time()

            response_time = round((end_time - start_time) * 1000)
            latency = round(self.bot.latency * 1000)

            content = f"**API Response:** {response_time}ms\n**Websocket Latency:** {latency}ms"
            embed = await self.message_formatter.format_success(
                content,
                title="Pong! 🏓"
            )
            await message.edit(content=None, embed=embed)
            logger.info(f"Ping command used by {ctx.author}")

        # Fun commands
        @self.bot.command(
            name="roll",
            help="Roll multiple dice\n\nUsage: ?roll [number_of_dice]\n\nParameters:\n- number_of_dice: Number of dice to roll (default: 1, max: 5)\n\nExamples:\n?roll\n?roll 3"
        )
        async def roll(ctx, number_of_dice: int = 1):
            import random
            if number_of_dice < 1:
                error_embed = await self.message_formatter.format_error(
                    "You must roll at least 1 die!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            if number_of_dice > 5:
                error_embed = await self.message_formatter.format_error(
                    "You can only roll up to 5 dice at once!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            results = [random.randint(1, 6) for _ in range(number_of_dice)]
            dice_emojis = " ".join("🎲" for _ in range(number_of_dice))
            results_text = ", ".join(str(r) for r in results)

            embed = await self.message_formatter.format_success(
                f"{dice_emojis}\n{ctx.author.mention} rolled: {results_text}",
                title="Dice Roll"
            )
            await ctx.send(embed=embed)
            logger.info(f"Roll command used by {ctx.author}, rolled {number_of_dice} dice: {results_text}")

        # Moderation commands - Mute/Unmute
        # Register mute command with required permissions
        self.register_command("mute", None, "Mute a user for a specified duration", ["moderate_members"])
        @self.bot.command(
            name="mute",
            help="Mute a user for a specified duration\n\nUsage: ?mute <@user> <duration> [reason]\n\nParameters:\n- @user: Mention the user to mute\n- Duration: Time duration (e.g. 30s, 5m, 2h, 1d)\n- Reason: Optional reason for the mute\n\nExamples:\n?mute @user 5m Spamming\n?mute @user 1h"
        )
        async def mute(ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
            if not await self.check_permissions(ctx, "mute") or not await self.check_role_hierarchy(ctx, member):
                return

            # Convert duration string to seconds
            try:
                duration_seconds = self.parse_duration(duration)
            except ValueError:
                error_embed = await self.message_formatter.format_error(
                    "Invalid duration format. Use a number followed by s, m, h, or d."
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            try:
                await member.timeout(timedelta(seconds=duration_seconds), reason=reason)
                # Track the moderation action
                self.mod_tracker.add_action("mute", ctx.author, member, reason, duration)
                success_embed = await self.message_formatter.format_success(
                    f"{member.mention} has been muted by {ctx.author.mention} for {duration}\nReason: {reason}",
                    title="User Muted 🔇"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Mute command used by {ctx.author} on {member} for {duration}")
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to timeout members!"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        # Register unmute command with required permissions
        self.register_command("unmute", None, "Remove timeout from a muted user", ["moderate_members"])
        @self.bot.command(
            name="unmute",
            help="Remove timeout from a muted user\n\nUsage: ?unmute <@user>\n\nParameters:\n- @user: Mention the user to unmute\n\nExample:\n?unmute @user"
        )
        async def unmute(ctx, member: discord.Member):
            if not await self.check_permissions(ctx, "unmute") or not await self.check_role_hierarchy(ctx, member):
                return

            try:
                await member.timeout(None)
                # Track the moderation action
                self.mod_tracker.add_action("unmute", ctx.author, member)
                success_embed = await self.message_formatter.format_success(
                    f"{member.mention} has been unmuted by {ctx.author.mention}",
                    title="User Unmuted 🔊"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Unmute command used by {ctx.author} on {member}")
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to remove timeouts!"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        # Moderation commands - Ban/Unban
        # Register ban and unban commands with required permissions
        self.register_command("ban", None, "Ban a user from the server", ["ban_members"])
        self.register_command("unban", None, "Unban a user from the server", ["ban_members"])
        @self.bot.command(
            name="ban",
            help="Ban a user from the server\n\nUsage: ?ban <@user> [reason]\n\nParameters:\n- @user: Mention the user to ban\n- Reason: Optional reason for the ban\n\nExample:\n?ban @user Violating server rules"
        )
        async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
            if not await self.check_permissions(ctx, "ban") or not await self.check_role_hierarchy(ctx, member):
                return

            try:
                await member.ban(reason=reason)
                success_embed = await self.message_formatter.format_success(
                    f"{member.mention} has been banned by {ctx.author.mention}\nReason: {reason}",
                    title="User Banned 🔨"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Ban command used by {ctx.author} on {member}")
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to ban members!"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        # Moderation tracking commands
        # Register recent moderation command
        self.register_command("rmod", None, "Show the most recent moderation action", ["moderate_members"])
        @self.bot.command(
            name="rmod",
            help="Show the most recent moderation action\n\nUsage: ?rmod\n\nDisplays information about the most recent moderation action taken by any moderator."
        )
        async def rmod(ctx):
            if not await self.check_permissions(ctx, "rmod"):
                return

            latest_action = self.mod_tracker.get_latest_action()
            formatted_action = self.mod_tracker.format_action(latest_action)

            embed = await self.message_formatter.format_message(
                formatted_action,
                title="Recent Moderation Action 🛡️",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            logger.info(f"Recent moderation command used by {ctx.author}")

        # Ticket system commands
        # Register ticket transcript channel setup command
        self.register_command("setticketlog", None, "Set a channel for ticket transcripts", ["manage_channels"])
        @self.bot.command(
            name="setticketlog",
            help="Set a channel for ticket transcripts\n\nUsage: ?setticketlog <#channel>\n\nParameters:\n- #channel: The channel to use for ticket transcripts\n\nExample:\n?setticketlog #ticket-logs"
        )
        async def setticketlog(ctx, channel: discord.TextChannel):
            if not await self.check_permissions(ctx, "setticketlog"):
                return

            try:
                # Check if the bot has necessary permissions in the channel
                if not channel.permissions_for(ctx.guild.me).send_messages:
                    error_embed = await self.message_formatter.format_error(
                        "I don't have permission to send messages in that channel!"
                    )
                    await ctx.send(embed=error_embed, delete_after=10)
                    return

                # Set the transcript channel in ticket manager
                self.ticket_manager.set_transcript_channel(channel.id)

                success_embed = await self.message_formatter.format_success(
                    f"Ticket transcripts will now be sent to {channel.mention}",
                    title="Ticket Log Channel Set 📝"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Ticket transcript channel set to {channel.name} by {ctx.author} in {ctx.guild.name}")

            except Exception as e:
                error_embed = await self.message_formatter.format_error(
                    f"An error occurred while setting the ticket transcript channel: {str(e)}"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        # Register unban command with required permissions
        self.register_command("unban", None, "Unban a user from the server", ["ban_members"])
        @self.bot.command(
            name="unban",
            help="Unban a user from the server\n\nUsage: ?unban <user_id> [reason]\n\nParameters:\n- user_id: The ID of the user to unban\n- Reason: Optional reason for the unban\n\nExample:\n?unban 123456789 User apologized"
        )
        async def unban(ctx, user_id: str, *, reason: str = "No reason provided"):
            if not await self.check_permissions(ctx, "unban"):
                return

            try:
                # Convert user_id to int and fetch the ban entry
                user_id = int(user_id)
                banned_users = [ban_entry async for ban_entry in ctx.guild.bans()]
                user = discord.Object(id=user_id)

                # Check if the user is actually banned
                if not any(ban_entry.user.id == user_id for ban_entry in banned_users):
                    error_embed = await self.message_formatter.format_error(
                        f"User with ID {user_id} is not banned!"
                    )
                    await ctx.send(embed=error_embed, delete_after=10)
                    return

                await ctx.guild.unban(user, reason=reason)
                success_embed = await self.message_formatter.format_success(
                    f"User with ID {user_id} has been unbanned by {ctx.author.mention}\nReason: {reason}",
                    title="User Unbanned 🔓"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Unban command used by {ctx.author} on user {user_id}")

            except ValueError:
                error_embed = await self.message_formatter.format_error(
                    "Please provide a valid user ID!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
            except discord.NotFound:
                error_embed = await self.message_formatter.format_error(
                    f"Could not find a banned user with ID {user_id}"
                )
                await ctx.send(embed=error_embed, delete_after=10)
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to unban members!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
            except Exception as e:
                error_embed = await self.message_formatter.format_error(
                    f"An error occurred while unbanning the user: {str(e)}"
                )
                await ctx.send(embed=error_embed, delete_after=10)


        # Register kick command with required permissions
        self.register_command("kick", None, "Kick a user from the server", ["kick_members"])
        @self.bot.command(
            name="kick",
            help="Kick a user from the server\n\nUsage: ?kick <@user> [reason]\n\nParameters:\n- @user: Mention the user to kick\n- Reason: Optional reason for the kick\n\nExample:\n?kick @user Breaking rules"
        )
        async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
            if not await self.check_permissions(ctx, "kick") or not await self.check_role_hierarchy(ctx, member):
                return

            try:
                await member.kick(reason=reason)
                success_embed = await self.message_formatter.format_success(
                    f"{member.mention} has been kicked by {ctx.author.mention}\nReason: {reason}",
                    title="User Kicked 👢"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Kick command used by {ctx.author} on {member}")
            except discord.Forbidden:
                error_embed = awaitself.message_formatter.format_error(
                    "I don't have permission to kick members!"
                )
                await ctx.send(embed=error_embed, delete_after=10)

        # Register purge command with required permissions
        self.register_command("purge", None, "Bulk delete messages in a channel", ["manage_messages"])

        # Register ticket setup command with required permissions
        self.register_command("setupticket", None, "Set up a ticket creation message in a channel", ["manage_channels"])
        @self.bot.command(
            name="setupticket",
            help="Set up a ticket creation message in a channel\n\nUsage: ?setupticket <#channel> [message]\n\nParameters:\n- #channel: The channel to set up the ticket message in\n- message: Optional custom message for the ticket embed\n\nExample:\n?setupticket #support Need help? Create a ticket!"
        )
        async def setupticket(ctx, channel: discord.TextChannel, *, message: str = None):
            if not await self.check_permissions(ctx, "setupticket"):
                return

            try:
                ticket_msg = await self.ticket_manager.setup_ticket_message(channel, message)
                success_embed = await self.message_formatter.format_success(
                    f"Ticket system has been set up in {channel.mention}",
                    title="Ticket System Setup ✅"
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Ticket system set up by {ctx.author} in {channel}")
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to send messages or add reactions in that channel!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
        @self.bot.command(
            name="purge",
            help="Bulk delete messages in a channel\n\nUsage: ?purge <amount> [@user]\n\nParameters:\n- amount: Number of messages to delete (max: 50)\n- @user: Optional mention to delete messages only from this user\n\nNotes:\n- Cannot delete messages older than 7 days\n- Maximum 50 messages per command\n\nExamples:\n?purge 10\n?purge 20 @user"
        )
        async def purge(ctx, amount: int, member: discord.Member = None):
            if not await self.check_permissions(ctx, "purge"):
                return

            if amount < 1 or amount > 50:
                error_embed = await self.message_formatter.format_error(
                    "You cannot delete more than 50 messages at once. Please specify a number between 1 and 50."
                )
                await ctx.send(embed=error_embed, delete_after=10)
                return

            try:
                def check_message(message):
                    # Check both user and message age (7 days = 604800 seconds)
                    message_age = (ctx.message.created_at - message.created_at).total_seconds()
                    return (member is None or message.author == member) and message_age <= 604800

                deleted = await ctx.channel.purge(
                    limit=amount + 1,  # +1 to include command message
                    check=check_message,
                    before=ctx.message
                )
                # Subtract 1 from count to exclude the command message
                count = len(deleted) - 1
                target = f" from {member.mention}" if member else ""

                success_embed = await self.message_formatter.format_success(
                    f"Successfully deleted {count} message(s){target}.",
                    title="Messages Purged 🧹"
                )
                response = await ctx.send(embed=success_embed)
                await response.delete(delay=5)
                logger.info(f"Purge command used by {ctx.author}, deleted {count} messages{' from ' + str(member) if member else ''} in {ctx.channel}")
            except discord.Forbidden:
                error_embed = await self.message_formatter.format_error(
                    "I don't have permission to delete messages!"
                )
                await ctx.send(embed=error_embed, delete_after=10)
            except discord.HTTPException as e:
                error_embed = await self.message_formatter.format_error(
                    f"Failed to delete messages: {str(e)}"
                )
                await ctx.send(embed=error_embed, delete_after=10)

    def parse_duration(self, duration: str) -> int:
        """Convert a duration string to seconds."""
        units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }

        if not duration[-1].isalpha():
            return int(duration)  # Assume seconds if no unit specified

        unit = duration[-1].lower()
        if unit not in units:
            raise ValueError("Invalid duration unit")

        try:
            value = int(duration[:-1])
            return value * units[unit]
        except ValueError:
            raise ValueError("Invalid duration format")

    async def setup_ticket_system(self):
        """Set up the ticket system event handlers."""
        @self.bot.event
        async def on_raw_reaction_add(payload):
            if payload.user_id == self.bot.user.id:
                return

            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return

            try:
                message = await channel.fetch_message(payload.message_id)
                reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
                user = await self.bot.fetch_user(payload.user_id)
                member = await message.guild.fetch_member(user.id)
                await self.ticket_manager.handle_ticket_reaction(reaction, member)
            except (discord.NotFound, discord.Forbidden):
                pass

        @self.bot.command(
            name="coinflip",
            aliases=["cf"],
            help="Flip a coin and get heads or tails\n\nUsage: ?coinflip [choice]\n\nParameters:\n- choice: Optional. Guess 'heads' or 'tails'\n\nExamples:\n?coinflip\n?cf heads"
        )
        async def coinflip(ctx, choice: str = None):
            import random
            result = random.choice(["heads", "tails"])

            # Format the result message
            if choice:
                choice = choice.lower()
                if choice not in ["heads", "tails"]:
                    error_embed = await self.message_formatter.format_error(
                        "Invalid choice! Please use 'heads' or 'tails'."
                    )
                    await ctx.send(embed=error_embed, delete_after=10)
                    return

                if choice == result:
                    description = f"🎯 The coin landed on **{result}**\nCongratulations, you guessed correctly!"
                else:
                    description = f"❌ The coin landed on **{result}**\nSorry, better luck next time!"
            else:
                description = f"🎲 The coin landed on **{result}**!"

            # Send the result
            embed = await self.message_formatter.format_success(
                description,
                title="Coin Flip 🪙"
            )
            await ctx.send(embed=embed)
            logger.info(f"Coinflip command used by {ctx.author}, result: {result}")