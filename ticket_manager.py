import discord
from discord.ext import commands
import json
import os
import io
from typing import Dict, Optional
from datetime import datetime, timezone

class TicketManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets_data_file = 'tickets.json'
        self.tickets: Dict[str, dict] = self.load_tickets()
        self.last_ticket_number = self._get_last_ticket_number()
        self.transcript_channel_id = None
        self.ticket_access_roles = self.tickets.get('config', {}).get('access_roles', [])

    def add_ticket_access_role(self, role_id: int) -> None:
        """Add a role ID to the list of roles that can access tickets."""
        if 'config' not in self.tickets:
            self.tickets['config'] = {}
        if 'access_roles' not in self.tickets['config']:
            self.tickets['config']['access_roles'] = []
        if role_id not in self.tickets['config']['access_roles']:
            self.tickets['config']['access_roles'].append(role_id)
            self.ticket_access_roles = self.tickets['config']['access_roles']
            self.save_tickets()

    def remove_ticket_access_role(self, role_id: int) -> None:
        """Remove a role ID from the list of roles that can access tickets."""
        if 'config' in self.tickets and 'access_roles' in self.tickets['config']:
            if role_id in self.tickets['config']['access_roles']:
                self.tickets['config']['access_roles'].remove(role_id)
                self.ticket_access_roles = self.tickets['config']['access_roles']
                self.save_tickets()

    async def save_transcript(self, channel: discord.TextChannel) -> Optional[discord.Message]:
        """Save the transcript of a ticket channel with enhanced formatting and information."""
        if not self.transcript_channel_id:
            return None

        transcript_channel = self.bot.get_channel(self.transcript_channel_id)
        if not transcript_channel:
            return None

        # Get ticket information
        ticket_info = self.tickets.get(channel.name, {})
        creator_id = ticket_info.get('user_id')
        creator = channel.guild.get_member(creator_id) if creator_id else None
        created_at = datetime.fromisoformat(ticket_info.get('created_at', '')).replace(tzinfo=timezone.utc) if ticket_info.get('created_at') else None

        # Prepare header
        header_lines = [
            "=== TICKET TRANSCRIPT ===",
            f"Ticket ID: {channel.name}",
            f"Created by: {creator.name} ({creator.id})" if creator else "Creator: Unknown",
            f"Created at: {created_at.strftime('%Y-%m-%d %H:%M:%S')}" if created_at else "Creation time: Unknown",
            f"Channel Topic: {channel.topic or 'No topic set'}",
            "\n=== MESSAGE HISTORY ==="
        ]

        # Collect messages with enhanced formatting
        messages = []
        message_count = 0
        attachment_count = 0

        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            author_roles = ', '.join([role.name for role in message.author.roles if role.name != '@everyone']) or 'No roles'
            
            # Format message content
            content_lines = []
            content_lines.append(f"[{timestamp}] {message.author} ({message.author.id}) [{author_roles}]")
            if message.content:
                content_lines.append(f"Content: {message.content}")
            
            # Add attachments info
            if message.attachments:
                attachment_count += len(message.attachments)
                attachments_info = '\n'.join(f"- {att.filename} ({att.url})" for att in message.attachments)
                content_lines.append(f"Attachments:\n{attachments_info}")
            
            # Add reactions if any
            if message.reactions:
                reactions_info = ' '.join(f"{reaction.emoji}({reaction.count})" for reaction in message.reactions)
                content_lines.append(f"Reactions: {reactions_info}")
            
            messages.append('\n'.join(content_lines))
            message_count += 1

        # Add statistics
        footer_lines = [
            "\n=== TICKET STATISTICS ===",
            f"Total Messages: {message_count}",
            f"Total Attachments: {attachment_count}",
            f"Duration: {(datetime.now(timezone.utc) - created_at).total_seconds() / 3600:.2f} hours" if created_at else "Duration: Unknown",
            "=== END OF TRANSCRIPT ==="
        ]

        # Combine all sections
        transcript_text = '\n\n'.join([
            '\n'.join(header_lines),
            '\n\n'.join(messages),
            '\n'.join(footer_lines)
        ])

        # Create embed with enhanced information
        embed = discord.Embed(
            title=f"Ticket Transcript - {channel.name}",
            description=f"Ticket closed and archived\nMessages: {message_count} | Attachments: {attachment_count}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Create a file with the transcript
        transcript_file = discord.File(
            fp=io.StringIO(transcript_text),
            filename=f"transcript-{channel.name}.txt"
        )
        
        return await transcript_channel.send(embed=embed, file=transcript_file)

    async def close_ticket(self, channel: discord.TextChannel, mod: discord.Member) -> bool:
        """Close a ticket channel and save transcript."""
        ticket_id = channel.name
        if not ticket_id.startswith('ticket-'):
            return False

        if ticket_id not in self.tickets or self.tickets[ticket_id]['status'] != 'open':
            return False

        try:
            # Save transcript before closing
            transcript_msg = await self.save_transcript(channel)
            if not transcript_msg:
                return False

            # Update ticket status
            self.tickets[ticket_id].update({
                'status': 'closed',
                'closed_by': mod.id,
                'closed_at': datetime.now(timezone.utc).isoformat(),
                'transcript_msg_id': transcript_msg.id
            })
            self.save_tickets()

            # Send closing message
            close_embed = discord.Embed(
                title="Ticket Closing",
                description="This ticket is now being closed. A transcript has been saved.",
                color=discord.Color.orange()
            )
            await channel.send(embed=close_embed)

            # Delete the channel after a short delay
            await channel.delete(reason=f"Ticket closed by {mod.name}")
            return True

        except discord.Forbidden:
            return False
        except Exception as e:
            print(f"Error closing ticket: {e}")
            return False

    def set_transcript_channel(self, channel_id: int) -> None:
        """Set the channel where ticket transcripts will be saved."""
        self.transcript_channel_id = channel_id

    async def handle_ticket_reaction(self, reaction: discord.Reaction, user: discord.Member) -> None:
        """Handle reaction to ticket creation message."""
        if user.bot or str(reaction.emoji) != '🎫':
            return

        # Remove all reactions except the bot's
        async for reactor in reaction.users():
            if reactor != self.bot.user:
                await reaction.remove(reactor)

        # Clean up invalid tickets first
        invalid_tickets = []
        for ticket_id, ticket in self.tickets.items():
            if ticket_id != 'config':
                if ticket.get('status') == 'open':
                    try:
                        await self.bot.fetch_channel(ticket.get('channel_id'))
                    except discord.NotFound:
                        invalid_tickets.append(ticket_id)

        # Remove invalid tickets
        for ticket_id in invalid_tickets:
            del self.tickets[ticket_id]
        if invalid_tickets:
            self.save_tickets()

        # Check if user already has an open ticket
        for ticket_id, ticket in self.tickets.items():
            if ticket_id != 'config' and 'user_id' in ticket and 'status' in ticket:
                if ticket['user_id'] == user.id and ticket['status'] == 'open':
                    try:
                        channel = await self.bot.fetch_channel(ticket['channel_id'])
                        await user.send(f"You already have an open ticket: {channel.mention}")
                        return
                    except discord.NotFound:
                        continue

        # Create new ticket channel
        channel = await self.create_ticket_channel(reaction.message.guild, user)
        
        # Create close button
        close_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Close Ticket",
            custom_id="close_ticket"
        )
        
        # Create action row with the button
        view = discord.ui.View()
        view.add_item(close_button)
        
        # Send initial message in ticket channel with close button
        embed = discord.Embed(
            title="Support Ticket",
            description=f"Welcome {user.mention}! Support staff will be with you shortly.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=view)

        # Send DM to user
        try:
            await user.send(f"I've created a ticket for you: {channel.mention}")
        except discord.Forbidden:
            pass  # User has DMs disabled

    async def handle_button_interaction(self, interaction: discord.Interaction) -> None:
        """Handle button interactions for tickets."""
        
        # Check if interaction is not None
        if interaction is None:
            print("Received None interaction")
            return

        # Check if interaction has the data attribute and custom_id
        try:
            custom_id = interaction.data.get('custom_id')
            if not custom_id:
                print("No custom_id found in interaction data")
                return
        except AttributeError:
            print("Interaction does not have data attribute")
            return

        if custom_id != "close_ticket":
            return

        # Check if user has permission to close tickets
        # Check if user has permission to close tickets
        has_permission = False
        if interaction.user.guild_permissions.manage_channels:
            has_permission = True
        else:
            for role in interaction.user.roles:
                if role.id in self.ticket_access_roles:
                    has_permission = True
                    break

        if not has_permission:
            try:
                await interaction.response.send_message(
                    "You don't have permission to close tickets.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    "You don't have permission to close tickets.",
                    ephemeral=True
                )
            return

        # Check if transcript channel is set up
        if not self.transcript_channel_id:
            try:
                await interaction.response.send_message(
                    "The transcript channel has not been set up. Please ask an administrator to set it up.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    "The transcript channel has not been set up. Please ask an administrator to set it up.",
                    ephemeral=True
                )
            return

        transcript_channel = self.bot.get_channel(self.transcript_channel_id)
        if not transcript_channel:
            try:
                await interaction.response.send_message(
                    "The transcript channel is not accessible. Please ask an administrator to check the configuration.",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                await interaction.followup.send(
                    "The transcript channel is not accessible. Please ask an administrator to check the configuration.",
                    ephemeral=True
                )
            return

        try:
            # Acknowledge the interaction first
            await interaction.response.defer()

            # Close the ticket
            success = await self.close_ticket(interaction.channel, interaction.user)
            if not success:
                await interaction.followup.send(
                    "Failed to close the ticket. Please try again.",
                    ephemeral=True
                )
        except Exception as e:
            print(f"Error handling button interaction: {e}")
            try:
                await interaction.followup.send(
                    "An error occurred while processing your request.",
                    ephemeral=True
                )
            except:
                pass

    def load_tickets(self) -> Dict[str, dict]:
        """Load tickets data from file."""
        if os.path.exists(self.tickets_data_file):
            try:
                with open(self.tickets_data_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def save_tickets(self) -> None:
        """Save tickets data to file."""
        with open(self.tickets_data_file, 'w') as f:
            json.dump(self.tickets, f, indent=4)

    def _get_last_ticket_number(self) -> int:
        """Get the last ticket number from existing tickets."""
        if not self.tickets:
            return 0
        ticket_numbers = []
        for ticket_id in self.tickets.keys():
            if ticket_id != 'config' and ticket_id.startswith('ticket-'):
                try:
                    number = int(ticket_id.split('-')[1])
                    ticket_numbers.append(number)
                except (IndexError, ValueError):
                    continue
        return max(ticket_numbers) if ticket_numbers else 0

    async def create_ticket_channel(self, guild: discord.Guild, user: discord.Member,
                                  category: Optional[discord.CategoryChannel] = None) -> discord.TextChannel:
        """Create a new ticket channel at the top of the channel list."""
        self.last_ticket_number += 1
        ticket_id = f'ticket-{self.last_ticket_number:04d}'

        # Set up permissions overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True,
                                                manage_channels=True, manage_messages=True)
        }

        # Add overwrites for configured access roles
        for role_id in self.ticket_access_roles:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Add overwrites for roles with manage_channels permission
        for role in guild.roles:
            if role.permissions.manage_channels:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Create the ticket channel at position 0 (top of the list)
        channel = await guild.create_text_channel(
            name=ticket_id,
            overwrites=overwrites,
            category=category,
            topic=f'Support ticket for {user.name}',
            position=0  # This ensures the channel appears at the top
        )

        # Store ticket information
        self.tickets[ticket_id] = {
            'channel_id': channel.id,
            'user_id': user.id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'status': 'open'
        }
        self.save_tickets()

        return channel

    async def setup_ticket_message(self, channel: discord.TextChannel, message: str) -> discord.Message:
        """Set up the ticket creation message with reaction."""
        embed = discord.Embed(
            title="Support Ticket",
            description=message or "React with 🎫 to create a support ticket.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Click the reaction below to create a ticket")

        message = await channel.send(embed=embed)
        await message.add_reaction('🎫')
        return message