import discord
from datetime import datetime

class MessageFormatter:
    def __init__(self):
        # Default embed color
        self.default_color = discord.Color.blurple()

    async def format_message(self, content: str, *, 
                           title: str = None,
                           color: discord.Color = None,
                           footer: str = None,
                           add_timestamp: bool = True) -> discord.Embed:
        """Format a message into a consistent embed style."""
        # Create embed with default or specified color
        embed = discord.Embed(color=color or self.default_color)
        
        # Set title if provided
        if title:
            embed.title = title
            
        # Set description (main content)
        embed.description = content
        
        # Add footer if provided
        if footer:
            embed.set_footer(text=footer)
            
        # Add timestamp if requested
        if add_timestamp:
            embed.timestamp = datetime.utcnow()
            
        return embed

    async def format_error(self, content: str, **kwargs) -> discord.Embed:
        """Format an error message."""
        kwargs['color'] = discord.Color.red()
        kwargs['title'] = kwargs.get('title', '❌ Error')
        return await self.format_message(content, **kwargs)

    async def format_success(self, content: str, **kwargs) -> discord.Embed:
        """Format a success message."""
        kwargs['color'] = discord.Color.green()
        kwargs['title'] = kwargs.get('title', '✅ Success')
        return await self.format_message(content, **kwargs)

    async def format_warning(self, content: str, **kwargs) -> discord.Embed:
        """Format a warning message."""
        kwargs['color'] = discord.Color.orange()
        kwargs['title'] = kwargs.get('title', '⚠️ Warning')
        return await self.format_message(content, **kwargs)