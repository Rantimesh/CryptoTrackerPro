"""
Utility functions for the Pump.fun Token Scanner Bot
"""

import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

def setup_logging() -> logging.Logger:
    """Setup logging configuration"""
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"logs/bot_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_filename),
            logging.FileHandler('logs/bot_latest.log')  # Always overwrite latest
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_filename}")
    
    return logger

def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration values"""
    try:
        # Check required numeric values
        required_nums = [
            'min_market_cap', 'max_market_cap', 'min_age_seconds', 
            'max_age_seconds', 'min_liquidity', 'scan_interval_minutes'
        ]
        
        for key in required_nums:
            value = config.get(key)
            if not isinstance(value, (int, float)) or value < 0:
                logging.error(f"Invalid config value for {key}: {value}")
                return False
        
        # Validate ranges
        if config['min_market_cap'] >= config['max_market_cap']:
            logging.error("min_market_cap must be less than max_market_cap")
            return False
        
        if config['min_age_seconds'] >= config['max_age_seconds']:
            logging.error("min_age_seconds must be less than max_age_seconds")
            return False
        
        # Validate scan interval
        if config['scan_interval_minutes'] < 1:
            logging.error("scan_interval_minutes must be at least 1")
            return False
        
        logging.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logging.error(f"Error validating config: {e}")
        return False

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        return f"{days}d {hours}h"

def format_price(price: float) -> str:
    """Format price with appropriate decimal places"""
    if price >= 1:
        return f"${price:.4f}"
    elif price >= 0.01:
        return f"${price:.6f}"
    elif price >= 0.000001:
        return f"${price:.8f}"
    else:
        return f"${price:.2e}"

def format_market_cap(market_cap: float) -> str:
    """Format market cap with appropriate units"""
    if market_cap >= 1e9:
        return f"${market_cap/1e9:.2f}B"
    elif market_cap >= 1e6:
        return f"${market_cap/1e6:.2f}M"
    elif market_cap >= 1e3:
        return f"${market_cap/1e3:.1f}K"
    else:
        return f"${market_cap:.2f}"

def get_risk_level(token: Dict[str, Any]) -> str:
    """Determine risk level based on token metrics"""
    try:
        market_cap = token.get('market_cap', 0)
        liquidity = token.get('liquidity_usd', 0)
        age_seconds = token.get('created_timestamp', 0)
        
        risk_score = 0
        
        # Market cap risk
        if market_cap < 10000:  # Under $10k
            risk_score += 3
        elif market_cap < 100000:  # Under $100k
            risk_score += 2
        elif market_cap < 1000000:  # Under $1M
            risk_score += 1
        
        # Liquidity risk
        if liquidity < 1000:  # Under $1k liquidity
            risk_score += 2
        elif liquidity < 5000:  # Under $5k liquidity
            risk_score += 1
        
        # Age risk (very new tokens are riskier)
        if age_seconds:
            current_time = datetime.now().timestamp()
            age = current_time - age_seconds
            
            if age < 3600:  # Under 1 hour
                risk_score += 2
            elif age < 86400:  # Under 1 day
                risk_score += 1
        
        # Social presence (lack of social links increases risk)
        has_socials = any([
            token.get('website'),
            token.get('telegram'), 
            token.get('twitter')
        ])
        
        if not has_socials:
            risk_score += 1
        
        # Determine risk level
        if risk_score >= 6:
            return "🔴 EXTREME"
        elif risk_score >= 4:
            return "🟠 HIGH"
        elif risk_score >= 2:
            return "🟡 MEDIUM"
        else:
            return "🟢 LOW"
            
    except Exception as e:
        logging.error(f"Error calculating risk level: {e}")
        return "❓ UNKNOWN"

def sanitize_url(url: str) -> str:
    """Sanitize URL for Telegram markdown"""
    if not url:
        return ""
    
    # Remove markdown special characters that could break formatting
    url = url.replace('(', '%28').replace(')', '%29')
    
    # Ensure URL has protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to maximum length with ellipsis"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def is_valid_address(address: str, chain: str = None) -> bool:
    """Basic validation for cryptocurrency addresses"""
    if not address or not isinstance(address, str):
        return False
    
    # Remove whitespace
    address = address.strip()
    
    # Basic length and character checks
    if chain == 'solana':
        # Solana addresses are base58 encoded, typically 32-44 characters
        return len(address) >= 32 and len(address) <= 44 and address.isalnum()
    elif chain == 'ethereum':
        # Ethereum addresses are 42 characters starting with 0x
        return len(address) == 42 and address.startswith('0x') and all(c in '0123456789abcdefABCDEF' for c in address[2:])
    else:
        # Generic validation - at least 20 characters, alphanumeric
        return len(address) >= 20 and address.replace('0x', '').isalnum()

def get_chain_emoji(chain: str) -> str:
    """Get emoji for blockchain"""
    chain_emojis = {
        'ethereum': '🔷',
        'solana': '🌅', 
        'bsc': '🟡',
        'polygon': '🟣',
        'arbitrum': '🔵',
        'base': '🔵',
        'avalanche': '🔺',
        'fantom': '👻'
    }
    return chain_emojis.get(chain.lower(), '⛓️')

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100

def is_honeypot_risk(token: Dict[str, Any]) -> bool:
    """Basic honeypot risk assessment"""
    try:
        # Very low liquidity compared to market cap
        market_cap = token.get('market_cap', 0)
        liquidity = token.get('liquidity_usd', 0)
        
        if market_cap > 0 and liquidity > 0:
            liquidity_ratio = liquidity / market_cap
            if liquidity_ratio < 0.01:  # Less than 1% liquidity ratio
                return True
        
        # No social presence at all
        has_any_social = any([
            token.get('website'),
            token.get('telegram'),
            token.get('twitter')
        ])
        
        # Very new with high market cap but no socials
        if not has_any_social and market_cap > 100000:
            created_timestamp = token.get('created_timestamp', 0)
            if created_timestamp:
                age_hours = (datetime.now().timestamp() - created_timestamp) / 3600
                if age_hours < 1:  # Less than 1 hour old
                    return True
        
        return False
        
    except Exception:
        return False
