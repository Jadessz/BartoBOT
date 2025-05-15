import os
import asyncio
import cohere
import discord
from typing import Optional
from discord.ext import commands
from message_formatter import MessageFormatter
from supabase import create_client, Client

class AIManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_formatter = MessageFormatter()
        self.api_key = os.getenv('COHERE_API_KEY')
        self.client = None
        if self.api_key:
            self.client = cohere.Client(api_key=self.api_key)

    async def get_ai_response(self, query: str) -> Optional[str]:
        """Get a response from Cohere's API."""
        if not self.client:
            return None

        try:
            response = await asyncio.to_thread(
                self.client.generate,
                prompt=query,
                model='command',
                max_tokens=1000,
                temperature=0.7
            )
            return response.generations[0].text.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    async def format_ai_response(self, query: str, response: str) -> discord.Embed:
        """Format the AI response into a Discord embed."""
        embed = await self.message_formatter.format_success(
            response,
            title="AI Response 🤖"
        )
        embed.add_field(name="Your Question", value=query, inline=False)
        return embed