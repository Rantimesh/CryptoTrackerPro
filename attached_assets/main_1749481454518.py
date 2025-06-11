import requests
import asyncio
import logging
import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests as telegram_requests
import schedule
import threading

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7966679922:AAEaevBL0kPBqjNevm5ghdw_zkRnyQtr_Rs")
CHAT_ID = os.getenv("CHAT_ID", "-1002811295204")

# Bot configuration
CONFIG = {
    "min_market_cap": 10000,     # $10k minimum
    "max_market_cap": 1000000,   # $1M maximum  
    "min_age_seconds": 1,        # 1 second minimum age
    "max_age_seconds": 86400,    # 24 hours maximum age
    "min_liquidity": 500,        # $500 minimum liquidity
    "scan_interval_minutes": 3,   # Scan every 3 minutes
    "max_tokens_per_scan": 50,   # Post max 50 tokens per scan
    "duplicate_check_hours": 6,   # Don't repost within 6 hours
}

class TokenScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_pump_fun_endpoints(self) -> List[str]:
        """Get Pump.fun API endpoints"""
        return [
            "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=created_timestamp&order=DESC",
            "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=market_cap&order=DESC",
            "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=last_trade_timestamp&order=DESC",
        ]

    def get_dexscreener_endpoints(self) -> List[str]:
        """Get DexScreener endpoints for Solana tokens"""
        return [
            "https://api.dexscreener.com/latest/dex/tokens/solana",
            "https://api.dexscreener.com/orders/v1/solana",
            "https://api.dexscreener.com/latest/dex/search/?q=pump",
            "https://api.dexscreener.com/latest/dex/pairs/solana",
        ]

    def fetch_tokens_from_pump_fun(self, endpoint: str) -> List[Dict]:
        """Fetch tokens from Pump.fun API endpoints with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching from Pump.fun (attempt {attempt + 1}): {endpoint}")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                    'Referer': 'https://pump.fun/',
                    'Origin': 'https://pump.fun'
                }
                
                response = self.session.get(endpoint, headers=headers, timeout=30)

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except:
                        logger.error(f"Invalid JSON response from {endpoint}")
                        continue
                    
                    # Handle different response structures from Pump.fun
                    tokens = []
                    if isinstance(data, list):
                        tokens = data
                    elif isinstance(data, dict):
                        if 'coins' in data:
                            tokens = data['coins']
                        elif 'data' in data:
                            tokens = data['data'] if isinstance(data['data'], list) else [data['data']]
                        else:
                            # Single token response
                            tokens = [data]

                    if not tokens:
                        logger.warning(f"No tokens returned from {endpoint}")
                        continue

                    # Filter tokens by age and structure
                    recent_tokens = []
                    current_time = datetime.now()
                    
                    for token in tokens:
                        if not self.is_valid_pump_fun_token(token):
                            continue
                            
                        # Check age requirement
                        created_timestamp = token.get('created_timestamp')
                        if created_timestamp:
                            # Pump.fun timestamps are in seconds, not milliseconds
                            created_time = datetime.fromtimestamp(created_timestamp)
                            age_seconds = (current_time - created_time).total_seconds()
                            
                            # Only include recent tokens (within max age)
                            if age_seconds <= CONFIG["max_age_seconds"] and age_seconds >= CONFIG["min_age_seconds"]:
                                recent_tokens.append(token)

                    # Sort by creation time (newest first)
                    recent_tokens.sort(key=lambda x: x.get('created_timestamp', 0), reverse=True)

                    logger.info(f"Got {len(recent_tokens)} recent tokens from {endpoint}")
                    return recent_tokens[:200]

                elif response.status_code == 503:
                    logger.warning(f"Pump.fun maintenance mode for {endpoint}, retrying in {(attempt + 1) * 10} seconds...")
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 10)
                        continue
                else:
                    logger.error(f"Pump.fun API error {response.status_code} for {endpoint}")
                    break

            except Exception as e:
                logger.error(f"Error fetching from {endpoint} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue

        return []

    def is_valid_pump_fun_token(self, token: Dict) -> bool:
        """Check if Pump.fun token has required structure"""
        try:
            # Required fields for Pump.fun tokens
            required_fields = ['mint', 'name', 'symbol', 'created_timestamp']
            for field in required_fields:
                if not token.get(field):
                    return False

            # Must have market cap data
            if not token.get('market_cap'):
                return False

            return True

        except Exception:
            return False

    def get_solana_token_data(self) -> List[Dict]:
        """Fetch Solana token data from multiple sources"""
        all_tokens = []
        
        # Try multiple DexScreener endpoints
        endpoints = [
            "https://api.dexscreener.com/latest/dex/search/?q=pump.fun",
            "https://api.dexscreener.com/latest/dex/tokens/solana/trending",
            "https://api.dexscreener.com/orders/v1/solana",
            "https://api.dexscreener.com/latest/dex/pairs/solana"
        ]
        
        for endpoint in endpoints:
            try:
                logger.info(f"Trying alternative source: {endpoint}")
                response = self.session.get(endpoint, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    pairs = []
                    
                    # Handle different response structures
                    if isinstance(data, dict):
                        if 'pairs' in data and data['pairs']:
                            pairs = data['pairs']
                        elif 'data' in data and data['data']:
                            pairs = data['data']
                    elif isinstance(data, list):
                        pairs = data
                    
                    if pairs:
                        # Convert DexScreener data to Pump.fun format
                        pump_tokens = []
                        for pair in pairs[:50]:  # Limit to recent tokens
                            base_token = pair.get('baseToken', {})
                            
                            # Check if this might be a Pump.fun token
                            if self.is_likely_pump_fun_token(pair):
                                pump_token = {
                                    'mint': base_token.get('address'),
                                    'name': base_token.get('name'),
                                    'symbol': base_token.get('symbol'),
                                    'market_cap': pair.get('marketCap', 0),
                                    'created_timestamp': pair.get('pairCreatedAt', 0) / 1000 if pair.get('pairCreatedAt') else int(time.time() - 3600),
                                    'virtual_sol_reserves': 100,  # Estimate
                                    'virtual_token_reserves': 1000000000,  # Estimate
                                    'website': '',
                                    'telegram': '',
                                    'twitter': ''
                                }
                                
                                # Extract social links from DexScreener
                                info = pair.get('info', {})
                                if info.get('website'):
                                    pump_token['website'] = info['website']
                                
                                socials = info.get('socials', [])
                                for social in socials:
                                    url_lower = social.get('url', '').lower()
                                    if 'telegram' in url_lower or 't.me' in url_lower:
                                        pump_token['telegram'] = social.get('url', '')
                                    elif 'twitter' in url_lower or 'x.com' in url_lower:
                                        pump_token['twitter'] = social.get('url', '')
                                
                                pump_tokens.append(pump_token)
                        
                        all_tokens.extend(pump_tokens)
                        logger.info(f"Found {len(pump_tokens)} potential tokens from {endpoint}")
                        
                        if pump_tokens:  # If we found tokens, use them
                            break
                
            except Exception as e:
                logger.error(f"Error fetching from {endpoint}: {e}")
                continue
        
        return all_tokens

    def is_likely_pump_fun_token(self, pair: Dict) -> bool:
        """Check if a DexScreener pair is likely a Pump.fun token"""
        try:
            # Pump.fun tokens typically have:
            # - Recent creation (last 24 hours)
            # - Lower market cap range
            # - Solana chain
            
            if pair.get('chainId') != 'solana':
                return False
            
            market_cap = pair.get('marketCap', 0)
            if market_cap > 5000000:  # Skip very high market cap tokens
                return False
            
            # Check age
            created_at = pair.get('pairCreatedAt')
            if created_at:
                created_time = datetime.fromtimestamp(created_at / 1000)
                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                if age_hours > 168:  # Skip tokens older than 7 days
                    return False
            
            return True
            
        except Exception:
            return False

    def fetch_from_dexscreener(self) -> List[Dict]:
        """Fetch token data from DexScreener endpoints"""
        all_tokens = []
        endpoints = self.get_dexscreener_endpoints()
        
        for endpoint in endpoints:
            try:
                logger.info(f"Fetching from DexScreener: {endpoint}")
                response = self.session.get(endpoint, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    tokens = self.process_dexscreener_data(data)
                    all_tokens.extend(tokens)
                    logger.info(f"Got {len(tokens)} tokens from DexScreener")
                    
                    if tokens:  # If we got tokens from this endpoint, that's sufficient
                        break
                        
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error fetching from DexScreener {endpoint}: {e}")
                continue
        
        return all_tokens

    def process_dexscreener_data(self, data: Dict) -> List[Dict]:
        """Process DexScreener data into Pump.fun format"""
        tokens = []
        
        try:
            pairs = []
            if 'pairs' in data and data['pairs']:
                pairs = data['pairs']
            elif isinstance(data, list):
                pairs = data
            
            for pair in pairs[:100]:  # Process up to 100 pairs
                if self.is_valid_dexscreener_pair(pair):
                    token = self.convert_dexscreener_to_pump_format(pair)
                    if token:
                        tokens.append(token)
        
        except Exception as e:
            logger.error(f"Error processing DexScreener data: {e}")
        
        return tokens

    def is_valid_dexscreener_pair(self, pair: Dict) -> bool:
        """Check if DexScreener pair is valid for our purposes"""
        try:
            # Must be Solana chain
            if pair.get('chainId') != 'solana':
                return False
            
            base_token = pair.get('baseToken', {})
            if not base_token.get('address') or not base_token.get('name'):
                return False
            
            # Check for reasonable market cap
            market_cap = pair.get('marketCap', 0)
            if market_cap and (market_cap < 1000 or market_cap > 50000000):
                return False
            
            # Check if token was created recently
            created_at = pair.get('pairCreatedAt')
            if created_at:
                created_time = datetime.fromtimestamp(created_at / 1000)
                age_hours = (datetime.now() - created_time).total_seconds() / 3600
                if age_hours > 72:  # Only include tokens from last 72 hours
                    return False
            
            return True
        except:
            return False



    def scan_pump_fun(self) -> List[Dict]:
        """Scan for new tokens using both Pump.fun and DexScreener sources"""
        all_tokens = []
        
        # First try Pump.fun endpoints
        logger.info("Scanning Pump.fun endpoints...")
        pump_endpoints = self.get_pump_fun_endpoints()
        
        for endpoint in pump_endpoints:
            tokens = self.fetch_tokens_from_pump_fun(endpoint)
            all_tokens.extend(tokens)
            time.sleep(2)  # Rate limiting

        # Also get tokens from DexScreener
        logger.info("Scanning DexScreener endpoints...")
        dex_tokens = self.fetch_from_dexscreener()
        all_tokens.extend(dex_tokens)

        # Remove duplicates by mint address
        seen_mints = set()
        unique_tokens = []

        for token in all_tokens:
            mint = token.get('mint')
            if mint and mint not in seen_mints:
                seen_mints.add(mint)
                unique_tokens.append(token)

        logger.info(f"Found {len(unique_tokens)} unique tokens from all sources")
        return unique_tokens

class TokenFilter:
    @staticmethod
    def passes_criteria(token: Dict) -> bool:
        """Check if Pump.fun token meets all criteria"""
        try:
            # Market cap check
            market_cap = token.get('market_cap')
            if not market_cap:
                return False

            # Convert market cap to USD (Pump.fun returns in lamports/SOL units)
            # Assuming market_cap is already in USD from Pump.fun API
            market_cap_usd = float(market_cap)
            
            if not (CONFIG["min_market_cap"] <= market_cap_usd <= CONFIG["max_market_cap"]):
                return False

            # Age check
            created_timestamp = token.get('created_timestamp')
            if not created_timestamp:
                return False

            created_time = datetime.fromtimestamp(created_timestamp)
            age_seconds = (datetime.now() - created_time).total_seconds()

            if not (CONFIG["min_age_seconds"] <= age_seconds <= CONFIG["max_age_seconds"]):
                return False

            # Liquidity check - use virtual_sol_reserves or usd_market_cap as proxy
            virtual_sol_reserves = token.get('virtual_sol_reserves', 0)
            virtual_token_reserves = token.get('virtual_token_reserves', 0)
            
            # Estimate liquidity based on virtual reserves
            estimated_liquidity = float(virtual_sol_reserves) * 200 if virtual_sol_reserves else market_cap_usd * 0.1
            
            if estimated_liquidity < CONFIG["min_liquidity"]:
                return False

            return True

        except Exception as e:
            logger.error(f"Error filtering Pump.fun token: {e}")
            return False

    @staticmethod
    def has_social_presence(token: Dict) -> bool:
        """Check if Pump.fun token has social media presence"""
        try:
            # Check for website
            if token.get('website'):
                return True

            # Check for social links
            if token.get('telegram'):
                return True
            
            if token.get('twitter'):
                return True

            return False

        except Exception:
            return False

    @staticmethod
    def extract_social_links(token: Dict) -> Dict[str, str]:
        """Extract social media links from Pump.fun token"""
        links = {
            'website': '',
            'telegram': '',
            'twitter': '',
            'discord': ''
        }

        try:
            # Direct fields from Pump.fun
            if token.get('website'):
                links['website'] = token['website']
            
            if token.get('telegram'):
                links['telegram'] = token['telegram']
                
            if token.get('twitter'):
                links['twitter'] = token['twitter']

        except Exception as e:
            logger.error(f"Error extracting social links from Pump.fun token: {e}")

        return links

class MessageFormatter:
    @staticmethod
    def format_pump_fun_message(token: Dict) -> str:
        """Format Pump.fun token data into Telegram message"""
        try:
            name = token['name']
            symbol = token['symbol']
            mint = token['mint']

            # Market data from Pump.fun
            market_cap = float(token.get('market_cap', 0))
            virtual_sol_reserves = float(token.get('virtual_sol_reserves', 0))
            virtual_token_reserves = float(token.get('virtual_token_reserves', 0))
            
            # Calculate price if possible
            price = 0
            if virtual_token_reserves > 0 and virtual_sol_reserves > 0:
                # Price per token in SOL
                price_sol = virtual_sol_reserves / virtual_token_reserves
                # Convert to USD (approximate SOL price - this should ideally fetch real SOL price)
                sol_price_usd = 200  # Approximate SOL price
                price = price_sol * sol_price_usd

            # Calculate age
            created_timestamp = token.get('created_timestamp')
            if created_timestamp:
                created_time = datetime.fromtimestamp(float(created_timestamp))
                age_hours = int((datetime.now() - created_time).total_seconds() / 3600)
                age_display = f"{age_hours}h" if age_hours < 24 else f"{age_hours//24}d {age_hours%24}h"
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

            # Short mint address
            short_mint = f"{mint[:6]}...{mint[-4:]}"

            # Build message
            message = f"""🚀 **NEW PUMP.FUN TOKEN** 🚀

💎 **{name} (${symbol})**
🌅 Solana • Age: {age_display}

📊 **Market Data:**
💰 Market Cap: {format_number(market_cap)}
💧 Virtual SOL: {virtual_sol_reserves:.2f} SOL
🪙 Virtual Tokens: {format_number(virtual_token_reserves)}"""

            if price > 0:
                message += f"\n💵 Estimated Price: ${price:.8f}"

            message += f"""

🔗 **Contract:** `{short_mint}`

🌐 **Links:**"""

            # Add social links
            social_links = TokenFilter.extract_social_links(token)

            if social_links['website']:
                message += f"\n🌍 [Website]({social_links['website']})"
            if social_links['telegram']:
                message += f"\n📱 [Telegram]({social_links['telegram']})"
            if social_links['twitter']:
                message += f"\n🐦 [Twitter]({social_links['twitter']})"

            # Pump.fun links
            pump_fun_url = f"https://pump.fun/{mint}"
            message += f"\n🚀 [Pump.fun]({pump_fun_url})"
            
            # DEX links
            dexscreener_url = f"https://dexscreener.com/solana/{mint}"
            message += f"\n📊 [Chart]({dexscreener_url})"

            # Jupiter swap link for Solana
            jupiter_url = f"https://jup.ag/swap/SOL-{mint}"
            message += f"\n🪐 [Trade on Jupiter]({jupiter_url})"

            message += f"\n\n⚠️ **DYOR - High Risk Investment**"

            return message

        except Exception as e:
            logger.error(f"Error formatting Pump.fun message: {e}")
            return f"Error formatting token data: {str(e)}"

class DuplicateTracker:
    def __init__(self):
        self.posted_tokens = {}

    def is_duplicate(self, mint: str) -> bool:
        """Check if token was posted recently"""
        if mint in self.posted_tokens:
            last_posted = self.posted_tokens[mint]
            hours_since = (datetime.now() - last_posted).total_seconds() / 3600
            return hours_since < CONFIG["duplicate_check_hours"]
        return False

    def mark_posted(self, mint: str):
        """Mark token as posted"""
        self.posted_tokens[mint] = datetime.now()

    def cleanup_old_entries(self):
        """Remove old entries to prevent memory buildup"""
        cutoff = datetime.now() - timedelta(hours=CONFIG["duplicate_check_hours"] * 2)
        self.posted_tokens = {
            mint: timestamp for mint, timestamp in self.posted_tokens.items()
            if timestamp > cutoff
        }

class TelegramBot:
    def __init__(self):
        self.telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
        self.scanner = TokenScanner()
        self.filter = TokenFilter()
        self.formatter = MessageFormatter()
        self.duplicate_tracker = DuplicateTracker()

    def send_message(self, message: str):
        """Send message to Telegram chat using HTTP requests"""
        try:
            url = f"{self.telegram_api_url}/sendMessage"
            data = {
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = telegram_requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                logger.info("Message sent successfully")
                return True
            else:
                logger.error(f"Telegram API error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def scan_and_post(self):
        """Main scanning and posting logic"""
        try:
            logger.info("Starting token scan...")
            
            # Scan Pump.fun for tokens
            tokens = self.scanner.scan_pump_fun()
            
            if not tokens:
                logger.info("No tokens found")
                return

            # Filter tokens
            filtered_tokens = []
            for token in tokens:
                if self.filter.passes_criteria(token):
                    mint = token.get('mint')
                    if mint and not self.duplicate_tracker.is_duplicate(mint):
                        filtered_tokens.append(token)

            logger.info(f"Found {len(filtered_tokens)} new qualifying tokens")

            # Limit tokens per scan
            tokens_to_post = filtered_tokens[:CONFIG["max_tokens_per_scan"]]

            # Post tokens
            for token in tokens_to_post:
                try:
                    message = self.formatter.format_pump_fun_message(token)
                    success = self.send_message(message)
                    
                    if success:
                        mint = token.get('mint')
                        if mint:
                            self.duplicate_tracker.mark_posted(mint)
                        
                        # Rate limiting between messages
                        time.sleep(2)
                    else:
                        logger.error(f"Failed to send message for token {token.get('mint')}")

                except Exception as e:
                    logger.error(f"Error processing token {token.get('mint')}: {e}")

            # Cleanup old duplicate tracking entries
            self.duplicate_tracker.cleanup_old_entries()

        except Exception as e:
            logger.error(f"Error in scan_and_post: {e}")

    def run_scan(self):
        """Run the scanning process"""
        self.scan_and_post()

def main():
    """Main application entry point"""
    logger.info("Starting Pump.fun Token Scanner Bot...")
    
    bot = TelegramBot()
    
    # Schedule regular scans
    schedule.every(CONFIG["scan_interval_minutes"]).minutes.do(bot.run_scan)
    
    # Run initial scan
    logger.info("Running initial scan...")
    bot.run_scan()
    
    # Keep the bot running
    logger.info(f"Bot started. Scanning every {CONFIG['scan_interval_minutes']} minutes...")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()
