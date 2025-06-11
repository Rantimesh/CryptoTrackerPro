"""
Configuration settings for the Pump.fun Token Scanner Bot
"""

import os
from typing import Dict, Any

# Telegram configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7966679922:AAEaevBL0kPBqjNevm5ghdw_zkRnyQtr_Rs")
CHAT_ID = os.getenv("CHAT_ID", "-1002811295204")

# Bot configuration
CONFIG: Dict[str, Any] = {
    # Token filtering criteria
    "min_market_cap": int(os.getenv("MIN_MARKET_CAP", "10000")),     # $10k minimum
    "max_market_cap": int(os.getenv("MAX_MARKET_CAP", "1000000")),   # $1M maximum  
    "min_age_seconds": int(os.getenv("MIN_AGE_SECONDS", "5")),        # 5 seconds minimum age
    "max_age_seconds": int(os.getenv("MAX_AGE_SECONDS", "604800")),    # 1 week maximum age
    "min_liquidity": int(os.getenv("MIN_LIQUIDITY", "500")),          # $500 minimum liquidity
    
    # Bot behavior
    "scan_interval_minutes": int(os.getenv("SCAN_INTERVAL_MINUTES", "2")),   # Scan every 2 minutes
    "max_tokens_per_scan": int(os.getenv("MAX_TOKENS_PER_SCAN", "50")),     # Post max 50 tokens per scan
    "duplicate_check_hours": int(os.getenv("DUPLICATE_CHECK_HOURS", "6")),   # Don't repost within 6 hours
    
    # API settings
    "max_retries": int(os.getenv("MAX_RETRIES", "3")),
    "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
    "rate_limit_delay": float(os.getenv("RATE_LIMIT_DELAY", "1.0")),
}

# API endpoints configuration
PUMP_FUN_ENDPOINTS = [
    "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=created_timestamp&order=DESC",
    "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=market_cap&order=DESC",
    "https://frontend-api.pump.fun/coins?offset=0&limit=100&sort=last_trade_timestamp&order=DESC",
    "https://frontend-api.pump.fun/coins/king-of-the-hill",
]

DEXSCREENER_ENDPOINTS = [
    "https://api.dexscreener.com/token-profiles/latest/v1",
]

# Alternative endpoints for redundancy
FALLBACK_ENDPOINTS = [
    "https://gmgn.ai/api/v1/tokens/sol/pump_new",
    "https://api.solscan.io/token/trending",
    "https://api.birdeye.so/defi/trending_tokens/sol",
]

# Chain information
CHAIN_CONFIGS = {
    'solana': {
        'name': '🌅 Solana',
        'explorer_url': 'https://solscan.io/token/',
        'dex_url': 'https://raydium.io/swap/',
        'chart_url': 'https://dexscreener.com/solana/'
    },
    'ethereum': {
        'name': '🔷 Ethereum',
        'explorer_url': 'https://etherscan.io/token/',
        'dex_url': 'https://app.uniswap.org/#/swap?inputCurrency=ETH&outputCurrency=',
        'chart_url': 'https://dexscreener.com/ethereum/'
    },
    'bsc': {
        'name': '🟡 BSC',
        'explorer_url': 'https://bscscan.com/token/',
        'dex_url': 'https://pancakeswap.finance/swap?inputCurrency=BNB&outputCurrency=',
        'chart_url': 'https://dexscreener.com/bsc/'
    },
    'polygon': {
        'name': '🟣 Polygon',
        'explorer_url': 'https://polygonscan.com/token/',
        'dex_url': 'https://quickswap.exchange/#/swap?inputCurrency=MATIC&outputCurrency=',
        'chart_url': 'https://dexscreener.com/polygon/'
    },
    'arbitrum': {
        'name': '🔵 Arbitrum',
        'explorer_url': 'https://arbiscan.io/token/',
        'dex_url': 'https://app.uniswap.org/#/swap?inputCurrency=ETH&outputCurrency=',
        'chart_url': 'https://dexscreener.com/arbitrum/'
    },
    'base': {
        'name': '🔵 Base',
        'explorer_url': 'https://basescan.org/token/',
        'dex_url': 'https://app.uniswap.org/#/swap?inputCurrency=ETH&outputCurrency=',
        'chart_url': 'https://dexscreener.com/base/'
    }
}

# Request headers
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}
