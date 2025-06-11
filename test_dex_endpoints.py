#!/usr/bin/env python3
"""
Quick test for DexScreener endpoints
"""

import requests
import json

endpoints = [
    "https://api.dexscreener.com/latest/dex/search/?q=solana",
    "https://api.dexscreener.com/latest/dex/search/?q=raydium", 
    "https://api.dexscreener.com/latest/dex/tokens/solana",
    "https://api.dexscreener.com/token-boosts/latest/v1",
    "https://api.dexscreener.com/token-profiles/latest/v1",
]

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

for endpoint in endpoints:
    try:
        print(f"\nTesting: {endpoint}")
        response = session.get(endpoint, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check data structure
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
                if 'pairs' in data:
                    pairs = data['pairs']
                    print(f"Pairs found: {len(pairs) if pairs else 0}")
                    if pairs and len(pairs) > 0:
                        first_pair = pairs[0]
                        print(f"First pair chain: {first_pair.get('chainId')}")
                        print(f"First pair has baseToken: {'baseToken' in first_pair}")
                elif 'data' in data:
                    print(f"Data type: {type(data['data'])}")
                    if isinstance(data['data'], list):
                        print(f"Data length: {len(data['data'])}")
            elif isinstance(data, list):
                print(f"List length: {len(data)}")
        else:
            print(f"Error: {response.text[:100]}")
            
    except Exception as e:
        print(f"Exception: {e}")