"""
Telegram Bot - Handles sending notifications to Telegram channels
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
import requests
import json

from config import CONFIG, CHAIN_CONFIGS

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles Telegram notifications for new tokens"""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.sent_tokens: Set[str] = set()
        self.last_cleanup = datetime.now()

    def cleanup_sent_tokens(self):
        """Clean up old entries from sent_tokens set"""
        if (datetime.now() - self.last_cleanup
            ).total_seconds() > CONFIG["duplicate_check_hours"] * 3600:
            self.sent_tokens.clear()
            self.last_cleanup = datetime.now()
            logger.info("Cleaned up sent tokens cache")

    def should_notify(self, token: Dict) -> bool:
        """Check if we should send a notification for this token"""
        self.cleanup_sent_tokens()

        token_id = f"{token.get('chain', '')}:{token.get('address', '')}"

        # Check if already sent
        if token_id in self.sent_tokens:
            return False

        # Add to sent tokens to prevent duplicates
        self.sent_tokens.add(token_id)
        return True

    def send_token_alert(self, token: Dict) -> bool:
        """Send a token alert to Telegram, checking for duplicate tokens"""
        try:
            if not self.should_notify(token):
                return False  # Skip sending if we've already sent this token
            message = self._format_token_message(token)
            return self._send_message(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error sending token alert: {e}")
            return False

    def _format_token_message(self, token: Dict) -> str:
        """Format token data into a Telegram message"""
        try:
            name = token['name']
            symbol = token['symbol']
            address = token['address']
            chain = token.get('chain', 'unknown')

            # Market data
            price = float(token.get('price_usd', 0))
            market_cap = token.get('market_cap', 0)
            liquidity = token.get('liquidity_usd', 0)
            volume_24h = token.get('volume_24h', 0)
            price_change = token.get('price_change_24h', 0)

            # Chain info
            chain_config = CHAIN_CONFIGS.get(chain, {})
            chain_name = chain_config.get('name', f'⛓️ {chain.title()}')

            # Calculate exact age
            created_timestamp = token.get('created_timestamp', 0)
            if created_timestamp:
                created_time = datetime.fromtimestamp(created_timestamp)
                age_seconds = (datetime.now() - created_time).total_seconds()
                days = int(age_seconds // 86400)
                hours = int((age_seconds % 86400) // 3600)
                minutes = int((age_seconds % 3600) // 60)
                seconds_remaining = int(age_seconds % 60)
                age_display = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m {seconds_remaining}s" if hours else f"{minutes}m {seconds_remaining}s"
            else:
                age_display = "Unknown"

            # Format numbers
            def format_number(num):
                if num >= 1e6:
                    return f"${num/1e6:.2f}M"
                elif num >= 1e3:
                    return f"${num/1e3:.1f}K"
                else:
                    return f"${num:.2f}"

            # Price change emoji
            change_emoji = ("🚀" if price_change > 5 else
                            "🟢" if price_change > 0 else "💥" if price_change <
                            -10 else "🔴" if price_change < 0 else "🟡")

            # Short address for display
            short_address = f"{address[:6]}...{address[-4:]}"

            # Build message
            message = f"""🚀 **NEW TOKEN: {name} (${symbol})**

    **Chain:** {chain_name} 
    **Age:** {age_display} 
    **Contract:** `{short_address}`

    **Price:** ${price:.8f} {change_emoji} {price_change:.2f}%
    **Market Cap:** {format_number(market_cap)} 💰
    **Liquidity:** {format_number(liquidity)} 💧
    **Volume 24h:** {format_number(volume_24h)} 📊

    **Links:**"""

            # Use a set to avoid duplicate links
            links = set()
            if token.get('website'):
                links.add(f"[Website]({token['website']}) 🌐")
            if token.get('telegram'):
                links.add(f"[Telegram]({token['telegram']}) 📱")
            if token.get('twitter'):
                links.add(f"[Twitter]({token['twitter']}) 🐦")

            # Add chain-specific links
            if chain_config:
                chart_url = f"{chain_config.get('chart_url', '')}{address}"
                links.add(f"[Chart]({chart_url}) 📈")

                if chain_config.get('dex_url'):
                    trade_url = f"{chain_config['dex_url']}{address}"
                    dex_name = self._get_dex_name(chain)
                    links.add(f"[Trade]({trade_url}) 💹")

                if chain_config.get('explorer_url'):
                    explorer_url = f"{chain_config['explorer_url']}{address}"
                    links.add(f"[Explorer]({explorer_url}) 🔍")

            # Join all links with separators, ensuring no duplicates
            if links:
                message += f"\n{' | '.join(links)}"

            # Source and warnings
            source = token.get('source', 'unknown')
            footer = f"Source: {source.title()}"
            if market_cap < 50000:  # Under $50k market cap
                footer += " | ⚠️ **HIGH RISK - Do Your Own Research!**"

            message += f"\n\n{footer}"

            return message

        except Exception as e:
            logger.error(f"Error formatting token message: {e}")
            return f"Error formatting message for token {token.get('address', 'unknown')}"

    def _get_dex_name(self, chain: str) -> str:
        """Get the primary DEX name for a chain"""
        dex_names = {
            'ethereum': 'Uniswap',
            'solana': 'Raydium',
            'bsc': 'PancakeSwap',
            'polygon': 'QuickSwap',
            'arbitrum': 'Uniswap',
            'base': 'Uniswap'
        }
        return dex_names.get(chain, 'DEX')

    def _send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send a message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"

            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
                'disable_web_page_preview': False
            }

            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info("Message sent successfully to Telegram")
                    return True
                else:
                    logger.error(
                        f"Telegram API error: {result.get('description', 'Unknown error')}"
                    )
                    return False
            else:
                logger.error(
                    f"HTTP error {response.status_code} when sending to Telegram"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}")
            return False

    def send_status_message(self, message: str) -> bool:
        """Send a status/info message to Telegram"""
        try:
            status_message = f"🤖 **Bot Status**\n\n{message}"
            return self._send_message(status_message)
        except Exception as e:
            logger.error(f"Error sending status message: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the Telegram bot connection"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    bot_info = result.get('result', {})
                    logger.info(
                        f"Telegram bot connected: {bot_info.get('username', 'Unknown')}"
                    )
                    return True

            logger.error("Failed to connect to Telegram bot")
            return False

        except Exception as e:
            logger.error(f"Error testing Telegram connection: {e}")
            return False
