import requests
import json

# Test different Pump.fun endpoints to find working ones
endpoints = [
    "https://pump.fun/board",
    "https://pump.fun/api/coins",
    "https://gmgn.ai/api/v1/tokens/sol/pump_new",
    "https://api.pump.fun/coins",
    "https://frontend-api.pump.fun/coins",
    "https://pumpapi.fun/api/coins",
]

for endpoint in endpoints:
    try:
        print(f"\nTesting: {endpoint}")
        response = requests.get(endpoint, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response type: {type(data)}")
                if isinstance(data, dict):
                    print(f"Keys: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"List length: {len(data)}")
                    if data and isinstance(data[0], dict):
                        print(f"First item keys: {list(data[0].keys())}")
            except:
                print("Not JSON response")
    except Exception as e:
        print(f"Error: {e}")