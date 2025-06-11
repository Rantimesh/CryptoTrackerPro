#!/usr/bin/env python3
"""
Test script to verify API connectivity and bot functionality
"""

import requests
import json
from config import TELEGRAM_TOKEN, CHAT_ID, DEXSCREENER_ENDPOINTS, FALLBACK_ENDPOINTS
from telegram_bot import TelegramNotifier

def test_telegram_connection():
    """Test Telegram bot connection"""
    print("Testing Telegram connection...")
    notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
    
    if notifier.test_connection():
        print("✅ Telegram connection successful")
        # Send test message
        test_msg = "🤖 Bot test - API connectivity check"
        if notifier.send_status_message(test_msg):
            print("✅ Test message sent successfully")
        else:
            print("❌ Failed to send test message")
    else:
        print("❌ Telegram connection failed")

def test_dexscreener_apis():
    """Test DexScreener API endpoints"""
    print("\nTesting DexScreener APIs...")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    working_endpoints = []
    
    for endpoint in DEXSCREENER_ENDPOINTS[:3]:  # Test first 3 endpoints
        try:
            print(f"Testing: {endpoint}")
            response = session.get(endpoint, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if we got valid data
                pairs = []
                if isinstance(data, dict):
                    if 'pairs' in data and data['pairs']:
                        pairs = data['pairs']
                    elif 'data' in data and data['data']:
                        pairs = data['data']
                elif isinstance(data, list):
                    pairs = data
                
                if pairs:
                    print(f"✅ Working - Found {len(pairs)} pairs")
                    working_endpoints.append(endpoint)
                else:
                    print(f"⚠️  API responded but no data found")
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return working_endpoints

def test_fallback_apis():
    """Test fallback API endpoints"""
    print("\nTesting fallback APIs...")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    working_endpoints = []
    
    for endpoint in FALLBACK_ENDPOINTS:
        try:
            print(f"Testing: {endpoint}")
            response = session.get(endpoint, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ Working - Response type: {type(data)}")
                    working_endpoints.append(endpoint)
                except:
                    print(f"⚠️  API responded but not JSON")
            else:
                print(f"❌ HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return working_endpoints

def test_sample_token_processing():
    """Test token processing with sample data"""
    print("\nTesting token processing...")
    
    # Sample DexScreener-style token data
    sample_token = {
        'address': '7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr',
        'name': 'Test Token',
        'symbol': 'TEST',
        'chain': 'solana',
        'market_cap': 50000,
        'price_usd': 0.00012345,
        'liquidity_usd': 2500,
        'volume_24h': 1500,
        'price_change_24h': 15.5,
        'created_timestamp': 1704067200,  # Recent timestamp
        'pair_created_at': 1704067200000,
        'website': 'https://example.com',
        'telegram': 'https://t.me/testtoken',
        'twitter': 'https://twitter.com/testtoken',
        'source': 'test'
    }
    
    try:
        notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
        
        # Test message formatting
        message = notifier._format_token_message(sample_token)
        print("✅ Token message formatting successful")
        print("Sample message preview:")
        print(message[:200] + "..." if len(message) > 200 else message)
        
        # Test sending (commented out to avoid spam)
        # if notifier.send_token_alert(sample_token):
        #     print("✅ Sample token alert sent successfully")
        
    except Exception as e:
        print(f"❌ Error processing token: {e}")

if __name__ == "__main__":
    print("🔍 Running API and Bot Connectivity Tests\n")
    
    # Test Telegram connection
    test_telegram_connection()
    
    # Test data sources
    working_dex = test_dexscreener_apis()
    working_fallback = test_fallback_apis()
    
    # Test token processing
    test_sample_token_processing()
    
    print(f"\n📊 Test Summary:")
    print(f"Working DexScreener endpoints: {len(working_dex)}")
    print(f"Working fallback endpoints: {len(working_fallback)}")
    
    if working_dex or working_fallback:
        print("✅ Bot should be able to find token data from alternative sources")
    else:
        print("❌ No working data sources found - check API endpoints")