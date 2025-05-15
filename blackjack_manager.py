import discord
from discord.ext import commands
import random
import asyncio
from typing import Dict, List, Optional
from blackjack_stats import BlackjackStats

class Card:
    def __init__(self, suit: str, value: str):
        self.suit = suit
        self.value = value
        self.numeric_value = self._get_numeric_value()

    def _get_numeric_value(self) -> int:
        if self.value in ['J', 'Q', 'K']:
            return 10
        elif self.value == 'A':
            return 11
        return int(self.value)

    def __str__(self) -> str:
        suit_symbols = {'Hearts': '♥️', 'Diamonds': '♦️', 'Clubs': '♣️', 'Spades': '♠️'}
        return f"{self.value}{suit_symbols[self.suit]}"

class BlackjackManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.games: Dict[int, dict] = {}
        self.deck: List[Card] = []
        self.stats = BlackjackStats()

    def _create_deck(self) -> None:
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.deck = [Card(suit, value) for suit in suits for value in values]
        random.shuffle(self.deck)

    def _calculate_hand_value(self, hand: List[Card], count_aces: bool = False) -> tuple[int, int] | int:
        value = 0
        aces = 0

        for card in hand:
            if card.value == 'A':
                aces += 1
            else:
                value += card.numeric_value

        # Calculate final value considering aces
        final_value = value
        soft_aces = 0  # Count of aces being used as 11
        
        for _ in range(aces):
            if final_value + 11 <= 21:
                final_value += 11
                soft_aces += 1
            else:
                final_value += 1

        if count_aces:
            return final_value, soft_aces
        return final_value

    def _draw_card(self) -> Optional[Card]:
        if not self.deck:
            self._create_deck()
        return self.deck.pop() if self.deck else None

    def _is_blackjack(self, hand: List[Card]) -> bool:
        """Check if a hand is a natural blackjack (Ace + 10-value card in first two cards)"""
        return len(hand) == 2 and self._calculate_hand_value(hand) == 21

    def _has_ten_or_ace(self, card: Card) -> bool:
        """Check if a card is a 10-value card or an Ace"""
        return card.numeric_value >= 10 or card.value == 'A'

    def start_game(self, player_id: int) -> dict:
        if player_id in self.games:
            return None

        if not self.deck:
            self._create_deck()

        player_hand = [self._draw_card(), self._draw_card()]
        dealer_hand = [self._draw_card(), self._draw_card()]

        player_has_blackjack = self._is_blackjack(player_hand)
        dealer_upcard = dealer_hand[0]
        
        game_state = {
            'player_hand': player_hand,
            'dealer_hand': dealer_hand,
            'status': 'playing'
        }

        # Check for blackjack scenarios
        if player_has_blackjack:
            if self._has_ten_or_ace(dealer_upcard):
                # Dealer has potential blackjack, check their hand
                dealer_has_blackjack = self._is_blackjack(dealer_hand)
                if dealer_has_blackjack:
                    game_state['status'] = 'tie'  # Both have blackjack
                else:
                    game_state['status'] = 'player_win'  # Only player has blackjack
            else:
                # Dealer can't have blackjack, player wins immediately
                game_state['status'] = 'player_win'
        elif self._is_blackjack(dealer_hand):
            # Only dealer has blackjack
            game_state['status'] = 'dealer_win'

        self.games[player_id] = game_state
        return game_state

    async def hit(self, player_id: int) -> Optional[dict]:
        if player_id not in self.games:
            return None

        game = self.games[player_id]
        if game['status'] != 'playing':
            return None

        new_card = self._draw_card()
        if not new_card:
            return None

        game['player_hand'].append(new_card)
        player_value = self._calculate_hand_value(game['player_hand'])

        if player_value > 21:
            game['status'] = 'dealer_win'
        elif player_value == 21:
            # Player reached 21 (not a natural blackjack), automatically stand
            game = await self.stand(player_id)  # Proceed to dealer's turn

        return game

    async def stand(self, player_id: int, message: discord.Message = None) -> Optional[dict]:
        if player_id not in self.games:
            return None

        game = self.games[player_id]
        if game['status'] != 'playing':
            return None

        # Get player's value
        player_value = self._calculate_hand_value(game['player_hand'])
        
        # First reveal the dealer's hidden card with a delay
        if message:
            game_embed = self.format_game_embed(game, message.author, True)
            await message.edit(embed=game_embed)
            await asyncio.sleep(2.5)  # 2.5 second delay for revealing hidden card
            
        # Dealer's turn - must hit on 16 or below, stand on any 17 (soft or hard)
        while True:
            dealer_value, soft_aces = self._calculate_hand_value(game['dealer_hand'], count_aces=True)
            
            # Stand on any 17 or higher (including soft 17)
            if dealer_value >= 17:
                break
                
            # Must hit on 16 or below
            new_card = self._draw_card()
            if not new_card:
                break
                
            game['dealer_hand'].append(new_card)
            
            # Update the game display with a delay between each card
            if message:
                game_embed = self.format_game_embed(game, message.author, True)
                await message.edit(embed=game_embed)
                await asyncio.sleep(2.5)  # 2.5 second delay between cards

        # Get final values and determine winner
        dealer_value = self._calculate_hand_value(game['dealer_hand'])

        if dealer_value > 21:
            game['status'] = 'player_win'
        elif dealer_value > player_value:
            game['status'] = 'dealer_win'
        elif dealer_value < player_value:
            game['status'] = 'player_win'
        else:
            game['status'] = 'tie'

        return game

    def format_game_embed(self, game: dict, player: discord.Member, show_dealer_hand: bool = False) -> discord.Embed:
        player_hand = game['player_hand']
        dealer_hand = game['dealer_hand']
        player_value = self._calculate_hand_value(player_hand)
        
        embed = discord.Embed(title="🎰 Blackjack Game", color=discord.Color.gold())
        embed.set_author(name=f"{player.display_name}'s game", icon_url=player.avatar.url if player.avatar else None)

        # Show player's hand
        player_cards = ' '.join(str(card) for card in player_hand)
        embed.add_field(name="Your Hand", value=f"{player_cards} (Value: {player_value})", inline=False)

        # Show dealer's hand
        if show_dealer_hand:
            dealer_cards = ' '.join(str(card) for card in dealer_hand)
            dealer_value = self._calculate_hand_value(dealer_hand)
            embed.add_field(name="Dealer's Hand", value=f"{dealer_cards} (Value: {dealer_value})", inline=False)
        else:
            dealer_cards = f"{str(dealer_hand[0])} 🎴"
            dealer_first_card_value = self._calculate_hand_value([dealer_hand[0]])
            embed.add_field(name="Dealer's Hand", value=f"{dealer_cards} (Visible Value: {dealer_first_card_value})", inline=False)

        # Show game status
        if game['status'] != 'playing':
            status_messages = {
                'player_win': '🎉 You win!',
                'dealer_win': '😔 Dealer wins!',
                'tie': '🤝 It\'s a tie!'
            }
            embed.add_field(name="Game Result", value=status_messages[game['status']], inline=False)

        return embed

    def end_game(self, player_id: int) -> None:
        if player_id in self.games:
            game = self.games[player_id]
            if game['status'] != 'playing':
                self.stats.update_stats(str(player_id), game['status'])
            del self.games[player_id]