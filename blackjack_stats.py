import json
import os
from typing import Dict, Optional

class BlackjackStats:
    def __init__(self):
        self.stats_file = 'blackjack_stats.json'
        self.stats: Dict[str, dict] = self._load_stats()

    def _load_stats(self) -> dict:
        """Load stats from file or return empty dict if file doesn't exist"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_stats(self) -> None:
        """Save stats to file"""
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f)

    def get_player_stats(self, player_id: str) -> dict:
        """Get stats for a specific player"""
        if player_id not in self.stats:
            self.stats[player_id] = {
                'wins': 0,
                'losses': 0,
                'draws': 0
            }
            self._save_stats()
        return self.stats[player_id]

    def update_stats(self, player_id: str, game_result: str) -> None:
        """Update player stats based on game result"""
        stats = self.get_player_stats(player_id)
        
        if game_result == 'player_win':
            stats['wins'] += 1
        elif game_result == 'dealer_win':
            stats['losses'] += 1
        elif game_result == 'tie':
            stats['draws'] += 1

        self._save_stats()

    def format_stats_embed(self, player_id: str, player_name: str) -> 'discord.Embed':
        """Format player stats as a Discord embed"""
        import discord
        
        stats = self.get_player_stats(player_id)
        total_games = stats['wins'] + stats['losses'] + stats['draws']
        win_rate = (stats['wins'] / total_games * 100) if total_games > 0 else 0

        embed = discord.Embed(
            title="🎰 Blackjack Statistics",
            color=discord.Color.gold()
        )
        embed.set_author(name=f"{player_name}'s Stats")

        # Add stats fields
        embed.add_field(name="Wins 🏆", value=str(stats['wins']), inline=True)
        embed.add_field(name="Losses 💔", value=str(stats['losses']), inline=True)
        embed.add_field(name="Draws 🤝", value=str(stats['draws']), inline=True)
        
        # Add total games and win rate
        embed.add_field(
            name="Total Games 🎲",
            value=str(total_games),
            inline=True
        )
        embed.add_field(
            name="Win Rate 📊",
            value=f"{win_rate:.1f}%",
            inline=True
        )

        return embed