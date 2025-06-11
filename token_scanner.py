"""
Token Scanner - Fetches and processes token data from multiple sources
"""

import requests
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import json

from config import CONFIG, PUMP_FUN_ENDPOINTS, DEXSCREENER_ENDPOINTS, FALLBACK_ENDPOINTS, DEFAULT_HEADERS

logger = logging.getLogger(__name__)

class TokenScanner:
    """Scans multiple cryptocurrency APIs for new token listings"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.seen_tokens: Set[str] = set()
        self.last_cleanup = datetime.now()
        
    def cleanup_seen_tokens(self):
        """Clean up old entries from seen_tokens set"""
        if (datetime.now() - self.last_cleanup).total_seconds() > 3600:  # Cleanup every hour
            self.seen_tokens.clear()
            self.last_cleanup = datetime.now()
            logger.info("Cleaned up seen tokens cache")
    
    def scan_all_sources(self) -> List[Dict]:
        """Scan both DexScreener and Pump.fun sources"""
        self.cleanup_seen_tokens()
        
        all_tokens = []
        
        # Scan DexScreener profiles first
        logger.info("Starting DexScreener profile scan...")
        dex_tokens = self._scan_dexscreener()
        all_tokens.extend(dex_tokens)
        logger.info(f"DexScreener found {len(dex_tokens)} tokens")
        
        # Also scan Pump.fun as backup
        logger.info("Starting Pump.fun scan...")
        pump_tokens = self._scan_pump_fun()
        all_tokens.extend(pump_tokens)
        logger.info(f"Pump.fun found {len(pump_tokens)} tokens")
        
        # Remove duplicates and filter by age and profile requirements
        unique_tokens = self._deduplicate_tokens(all_tokens)
        filtered_tokens = self._filter_tokens(unique_tokens)
        
        logger.info(f"Scan summary - Total: {len(all_tokens)}, Unique: {len(unique_tokens)}, Filtered: {len(filtered_tokens)}")
        
        return filtered_tokens
    
    def _scan_pump_fun(self) -> List[Dict]:
        """Scan Pump.fun API endpoints"""
        logger.info("Scanning Pump.fun endpoints...")
        tokens = []
        maintenance_count = 0
        
        for endpoint in PUMP_FUN_ENDPOINTS:
            try:
                endpoint_tokens = self._fetch_pump_fun_endpoint(endpoint)
                if endpoint_tokens:
                    tokens.extend(endpoint_tokens)
                else:
                    maintenance_count += 1
                time.sleep(CONFIG["rate_limit_delay"])
            except Exception as e:
                logger.error(f"Error scanning Pump.fun endpoint {endpoint}: {e}")
                maintenance_count += 1
                continue
        
        if maintenance_count >= len(PUMP_FUN_ENDPOINTS):
            logger.warning("All Pump.fun endpoints appear to be in maintenance mode")
        
        logger.info(f"Found {len(tokens)} tokens from Pump.fun")
        return tokens
    
    def _fetch_pump_fun_endpoint(self, endpoint: str) -> List[Dict]:
        """Fetch tokens from a single Pump.fun endpoint with retry logic"""
        for attempt in range(CONFIG["max_retries"]):
            try:
                logger.info(f"Fetching Pump.fun (attempt {attempt + 1}): {endpoint}")
                
                headers = {
                    **DEFAULT_HEADERS,
                    'Referer': 'https://pump.fun/',
                    'Origin': 'https://pump.fun'
                }
                
                response = self.session.get(
                    endpoint, 
                    headers=headers, 
                    timeout=CONFIG["request_timeout"]
                )
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        tokens = self._process_pump_fun_response(data)
                        logger.info(f"Successfully fetched {len(tokens)} tokens from {endpoint}")
                        return tokens
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response from {endpoint}")
                        continue
                
                elif response.status_code == 503:
                    logger.warning(f"Pump.fun maintenance mode for {endpoint}, skipping remaining retries")
                    break  # Skip retries for maintenance mode to speed up scanning
                
                else:
                    logger.error(f"Pump.fun API error {response.status_code} for {endpoint}")
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {endpoint} (attempt {attempt + 1}): {e}")
                if attempt < CONFIG["max_retries"] - 1:
                    time.sleep(5)
                    continue
                    
        return []
    
    def _process_pump_fun_response(self, data: Any) -> List[Dict]:
        """Process Pump.fun API response and extract token data"""
        tokens = []
        
        try:
            # Handle different response structures
            if isinstance(data, list):
                raw_tokens = data
            elif isinstance(data, dict):
                if 'coins' in data:
                    raw_tokens = data['coins']
                elif 'data' in data:
                    raw_tokens = data['data'] if isinstance(data['data'], list) else [data['data']]
                else:
                    raw_tokens = [data]  # Single token response
            else:
                return tokens
            
            current_time = datetime.now()
            
            for token in raw_tokens:
                if not self._is_valid_pump_fun_token(token):
                    continue
                
                # Check token age
                created_timestamp = token.get('created_timestamp')
                if created_timestamp:
                    created_time = datetime.fromtimestamp(created_timestamp)
                    age_seconds = (current_time - created_time).total_seconds()
                    
                    if CONFIG["min_age_seconds"] <= age_seconds <= CONFIG["max_age_seconds"]:
                        # Convert to standard format
                        standardized_token = self._standardize_pump_fun_token(token)
                        if standardized_token:
                            tokens.append(standardized_token)
            
            # Sort by creation time (newest first)
            tokens.sort(key=lambda x: x.get('created_timestamp', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"Error processing Pump.fun response: {e}")
        
        return tokens[:100]  # Limit to 100 most recent
    
    def _is_valid_pump_fun_token(self, token: Dict) -> bool:
        """Validate Pump.fun token structure"""
        try:
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
    
    def _standardize_pump_fun_token(self, token: Dict) -> Optional[Dict]:
        """Convert Pump.fun token to standard format"""
        try:
            return {
                'address': token['mint'],
                'name': token['name'],
                'symbol': token['symbol'],
                'chain': 'solana',
                'market_cap': token.get('market_cap', 0),
                'price_usd': token.get('usd_market_cap', 0) / token.get('market_cap', 1) if token.get('market_cap', 0) > 0 else 0,
                'liquidity_usd': token.get('virtual_sol_reserves', 0) * 100,  # Estimate
                'volume_24h': token.get('volume_24h', 0),
                'price_change_24h': 0,  # Not available in Pump.fun API
                'created_timestamp': token['created_timestamp'],
                'pair_created_at': token['created_timestamp'] * 1000,  # Convert to milliseconds
                'website': token.get('website', ''),
                'telegram': token.get('telegram', ''),
                'twitter': token.get('twitter', ''),
                'source': 'pump.fun'
            }
        except Exception as e:
            logger.error(f"Error standardizing Pump.fun token: {e}")
            return None
    
    def _scan_dexscreener(self) -> List[Dict]:
        """Scan DexScreener token profiles endpoint only"""
        logger.info("Scanning DexScreener token profiles...")
        tokens = []
        
        # Only use the token-profiles endpoint
        for endpoint in DEXSCREENER_ENDPOINTS:
            try:
                endpoint_tokens = self._fetch_dexscreener_endpoint(endpoint)
                if endpoint_tokens:
                    tokens.extend(endpoint_tokens)
                    logger.info(f"Successfully got {len(endpoint_tokens)} tokens from profiles endpoint")
                time.sleep(CONFIG["rate_limit_delay"])
            except Exception as e:
                logger.error(f"Error scanning DexScreener profiles endpoint {endpoint}: {e}")
                continue
        
        logger.info(f"Found {len(tokens)} tokens from DexScreener profiles")
        return tokens
    
    def _fetch_dexscreener_endpoint(self, endpoint: str) -> List[Dict]:
        """Fetch tokens from a single DexScreener endpoint"""
        try:
            logger.info(f"Fetching DexScreener: {endpoint}")
            
            response = self.session.get(endpoint, timeout=CONFIG["request_timeout"])
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"DexScreener API response type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                if isinstance(data, list) and len(data) > 0:
                    logger.info(f"First item structure: {list(data[0].keys()) if isinstance(data[0], dict) else 'Not a dict'}")
                elif isinstance(data, dict):
                    logger.info(f"Response keys: {list(data.keys())}")
                
                tokens = self._process_dexscreener_response(data)
                logger.info(f"Successfully fetched {len(tokens)} tokens from DexScreener")
                return tokens
            else:
                logger.error(f"DexScreener API error {response.status_code} for {endpoint}: {response.text}")
                
        except Exception as e:
            logger.error(f"Error fetching DexScreener endpoint {endpoint}: {e}")
            
        return []
    
    def _process_dexscreener_response(self, data: Any) -> List[Dict]:
        """Process DexScreener token profiles response"""
        tokens = []
        
        try:
            logger.info(f"Processing DexScreener response of type: {type(data)}")
            
            # Handle token-profiles endpoint (list format)
            if isinstance(data, list):
                logger.info(f"Processing {len(data)} items from list response")
                processed_count = 0
                skipped_no_address = 0
                skipped_age = 0
                
                for item in data:
                    if isinstance(item, dict):
                        processed_count += 1
                        
                        # Handle new DexScreener token-profiles format
                        token_address = item.get('tokenAddress')
                        chain_id = item.get('chainId', 'solana')
                        
                        if not token_address:
                            skipped_no_address += 1
                            continue
                        
                        # Extract token name and symbol from the URL or use defaults
                        url = item.get('url', '')
                        token_name = f"Token {token_address[:8]}"
                        token_symbol = token_address[:6].upper()
                        
                        # Try to extract name from description if available
                        description = item.get('description', '')
                        if description and len(description) > 0:
                            # Use first part of description as name
                            token_name = description.split(' ')[0] if description else token_name
                        
                        # Try to get real market data for this token
                        real_pair_data = self._fetch_token_market_data(token_address, chain_id)
                        
                        # Rate limit the API calls
                        time.sleep(0.1)  # 100ms delay between requests
                        
                        if real_pair_data:
                            # Use real market data
                            fake_pair = real_pair_data
                            # Update token name and symbol from real data if available
                            base_token = real_pair_data.get('baseToken', {})
                            if base_token.get('name'):
                                token_name = base_token['name']
                            if base_token.get('symbol'):
                                token_symbol = base_token['symbol']
                        else:
                            # Fallback to estimated data structure
                            fake_pair = {
                                'chainId': chain_id,
                                'baseToken': {
                                    'address': token_address,
                                    'name': token_name,
                                    'symbol': token_symbol
                                },
                                'priceUsd': 0.0001,  # Default estimate
                                'marketCap': 50000,  # Default estimate
                                'liquidity': {'usd': 1000},  # Default estimate
                                'volume': {'h24': 500},  # Default estimate
                                'priceChange': {'h24': 0},
                                'pairCreatedAt': int(datetime.now().timestamp() * 1000) - 3600000,  # 1 hour ago
                                'info': {
                                    'website': '',
                                    'socials': []
                                }
                            }
                        
                        # Extract social links if available
                        links = item.get('links', [])
                        if links:
                            socials = []
                            for link in links:
                                if isinstance(link, dict) and link.get('url'):
                                    url = link['url'].lower()
                                    if 'twitter' in url or 'x.com' in url:
                                        socials.append({'type': 'twitter', 'url': link['url']})
                                    elif 'telegram' in url or 't.me' in url:
                                        socials.append({'type': 'telegram', 'url': link['url']})
                                    elif 'http' in url:
                                        fake_pair['info']['website'] = link['url']
                            fake_pair['info']['socials'] = socials
                        
                        # Apply age filter (tokens with profiles are likely newer)
                        created_time = datetime.fromtimestamp(fake_pair['pairCreatedAt'] / 1000)
                        age_seconds = (datetime.now() - created_time).total_seconds()
                        
                        if CONFIG["min_age_seconds"] <= age_seconds <= CONFIG["max_age_seconds"]:
                            standardized_token = self._standardize_dexscreener_pair(fake_pair)
                            if standardized_token:
                                tokens.append(standardized_token)
                        else:
                            skipped_age += 1
                
                logger.info(f"DexScreener processing stats - Processed: {processed_count}, No address: {skipped_no_address}, Age filtered: {skipped_age}, Final tokens: {len(tokens)}")
            
            elif isinstance(data, dict):
                logger.info(f"Got dict response with keys: {list(data.keys())}")
                # Handle different dict response formats
                if 'pairs' in data:
                    logger.info("Processing pairs from dict response")
                    # Process pairs format if available
                elif 'tokens' in data:
                    logger.info("Processing tokens from dict response")
                    # Process tokens format if available
                else:
                    logger.warning("Unknown dict response format from DexScreener")
            
            else:
                logger.warning(f"Unexpected DexScreener response format: {type(data)}")
            
            # Sort by creation time (newest first)
            tokens.sort(key=lambda x: x.get('pair_created_at', 0), reverse=True)
            
        except Exception as e:
            logger.error(f"Error processing DexScreener profiles response: {e}")
        
        return tokens[:50]  # Limit to 50 most recent
    
    def _is_valid_dexscreener_pair(self, pair: Dict) -> bool:
        """Validate DexScreener pair structure"""
        try:
            base_token = pair.get('baseToken')
            if not base_token:
                return False
            
            required_fields = ['address', 'name', 'symbol']
            for field in required_fields:
                if not base_token.get(field):
                    return False
            
            # Must have price and liquidity data
            if not pair.get('priceUsd') or not pair.get('liquidity', {}).get('usd'):
                return False
                
            return True
            
        except Exception:
            return False
    
    def _standardize_dexscreener_pair(self, pair: Dict) -> Optional[Dict]:
        """Convert DexScreener pair to standard format"""
        try:
            base_token = pair['baseToken']
            
            # Extract social links
            social_links = self._extract_social_links(pair)
            
            return {
                'address': base_token['address'],
                'name': base_token['name'],
                'symbol': base_token['symbol'],
                'chain': pair.get('chainId', 'unknown'),
                'market_cap': pair.get('marketCap', 0),
                'price_usd': float(pair.get('priceUsd', 0)),
                'liquidity_usd': pair.get('liquidity', {}).get('usd', 0),
                'volume_24h': pair.get('volume', {}).get('h24', 0),
                'price_change_24h': pair.get('priceChange', {}).get('h24', 0),
                'created_timestamp': pair.get('pairCreatedAt', 0) // 1000,
                'pair_created_at': pair.get('pairCreatedAt', 0),
                'website': social_links.get('website', ''),
                'telegram': social_links.get('telegram', ''),
                'twitter': social_links.get('twitter', ''),
                'source': 'dexscreener'
            }
        except Exception as e:
            logger.error(f"Error standardizing DexScreener pair: {e}")
            return None
    
    def _fetch_token_market_data(self, token_address: str, chain_id: str) -> Optional[Dict]:
        """Fetch real market data for a token from DexScreener pairs API"""
        try:
            # Use DexScreener tokens API to get real market data
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
            
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                
                if pairs:
                    # Get the pair with highest liquidity for this token
                    best_pair = max(pairs, key=lambda p: p.get('liquidity', {}).get('usd', 0))
                    
                    # Validate the pair has good data
                    if (best_pair.get('priceUsd') and 
                        best_pair.get('liquidity', {}).get('usd', 0) > 100 and
                        best_pair.get('baseToken', {}).get('address') == token_address):
                        
                        logger.info(f"Found real market data for {token_address}")
                        return best_pair
                        
        except Exception as e:
            logger.debug(f"Could not fetch market data for {token_address}: {e}")
            
        return None
    
    def _extract_social_links(self, pair: Dict) -> Dict[str, str]:
        """Extract social media links from DexScreener pair"""
        links = {'website': '', 'telegram': '', 'twitter': ''}
        
        try:
            info = pair.get('info', {})
            
            # Website
            if info.get('website'):
                links['website'] = info['website']
            
            # Social links
            socials = info.get('socials', [])
            for social in socials:
                url = social.get('url', '').lower()
                if 'telegram' in url or 't.me' in url:
                    links['telegram'] = social.get('url', '')
                elif 'twitter' in url or 'x.com' in url:
                    links['twitter'] = social.get('url', '')
                    
        except Exception as e:
            logger.error(f"Error extracting social links: {e}")
        
        return links
    
    def _is_pump_fun_candidate(self, pair: Dict) -> bool:
        """Check if a DexScreener pair might be a Pump.fun token"""
        try:
            # Check if it's on Solana (where Pump.fun operates)
            if pair.get('chainId', '').lower() != 'solana':
                return False
            
            # Check market cap range typical for Pump.fun tokens
            market_cap = pair.get('marketCap', 0)
            if market_cap and (1000 <= market_cap <= 5000000):  # $1k to $5M range
                
                # Check for recent creation
                pair_created_at = pair.get('pairCreatedAt')
                if pair_created_at:
                    created_time = datetime.fromtimestamp(pair_created_at / 1000)
                    age_hours = (datetime.now() - created_time).total_seconds() / 3600
                    
                    # Tokens created in last 7 days are more likely Pump.fun
                    if age_hours <= 168:  # 7 days
                        return True
                
                # Check DEX - Pump.fun tokens often appear on Raydium
                dex_id = pair.get('dexId', '').lower()
                if 'raydium' in dex_id:
                    return True
                
                # Check for certain characteristics in the name/symbol
                base_token = pair.get('baseToken', {})
                name = base_token.get('name', '').lower()
                symbol = base_token.get('symbol', '').lower()
                
                # Common Pump.fun token patterns
                pump_indicators = ['pump', 'moon', 'gem', 'degen', 'pepe', 'wojak', 'chad', 'based']
                if any(indicator in name or indicator in symbol for indicator in pump_indicators):
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking pump.fun candidate: {e}")
            return False
    
    def _scan_fallback_endpoints(self) -> List[Dict]:
        """Scan fallback endpoints when primary sources fail"""
        logger.info("Scanning fallback endpoints...")
        tokens = []
        
        for endpoint in FALLBACK_ENDPOINTS:
            try:
                response = self.session.get(endpoint, timeout=CONFIG["request_timeout"])
                if response.status_code == 200:
                    # Basic processing for fallback endpoints
                    data = response.json()
                    # Process based on endpoint type
                    endpoint_tokens = self._process_fallback_response(endpoint, data)
                    tokens.extend(endpoint_tokens)
                    
                time.sleep(CONFIG["rate_limit_delay"])
                
            except Exception as e:
                logger.error(f"Error scanning fallback endpoint {endpoint}: {e}")
                continue
        
        logger.info(f"Found {len(tokens)} tokens from fallback endpoints")
        return tokens
    
    def _process_fallback_response(self, endpoint: str, data: Any) -> List[Dict]:
        """Process responses from fallback endpoints"""
        # This is a simplified processor for fallback data
        # In a real implementation, you'd add specific handlers for each endpoint
        return []
    
    def _deduplicate_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Remove duplicate tokens based on address"""
        seen_addresses = set()
        unique_tokens = []
        
        for token in tokens:
            address = token.get('address')
            if address and address not in seen_addresses:
                seen_addresses.add(address)
                unique_tokens.append(token)
        
        return unique_tokens
    
    def _filter_tokens(self, tokens: List[Dict]) -> List[Dict]:
        """Filter tokens based on configured criteria"""
        filtered_tokens = []
        
        for token in tokens:
            if self._passes_criteria(token):
                # Check if token has Telegram social link
                if not token.get('telegram'):
                    continue
                
                # Check if we've seen this token recently
                token_id = f"{token.get('chain', '')}:{token.get('address', '')}"
                if token_id not in self.seen_tokens:
                    # Add only tokens with Telegram socials
                    self.seen_tokens.add(token_id)
                    filtered_tokens.append(token)
        
        return filtered_tokens
    
    def _passes_criteria(self, token: Dict) -> bool:
        """Check if token meets all filtering criteria"""
        try:
            # Basic validation first
            if not token.get('address') or not token.get('name') or not token.get('symbol'):
                return False
            
            # Market cap check - be more lenient for Pump.fun candidates
            market_cap = token.get('market_cap', 0)
            is_pump_candidate = token.get('is_pump_candidate', False)
            
            if is_pump_candidate:
                # More permissive for Pump.fun candidates
                min_cap = max(1000, CONFIG["min_market_cap"] // 10)  # Lower minimum
                max_cap = CONFIG["max_market_cap"] * 5  # Higher maximum
            else:
                min_cap = CONFIG["min_market_cap"]
                max_cap = CONFIG["max_market_cap"]
            
            if market_cap > 0 and not (min_cap <= market_cap <= max_cap):
                return False
            
            # Age check - more lenient for Pump.fun candidates
            created_timestamp = token.get('created_timestamp', 0)
            if created_timestamp:
                created_time = datetime.fromtimestamp(created_timestamp)
                age_seconds = (datetime.now() - created_time).total_seconds()
                
                # Extended age limit for Pump.fun candidates
                max_age = CONFIG["max_age_seconds"] * 7 if is_pump_candidate else CONFIG["max_age_seconds"]
                
                if not (CONFIG["min_age_seconds"] <= age_seconds <= max_age):
                    return False
            
            # Liquidity check - reduced minimum for Pump.fun candidates
            liquidity = token.get('liquidity_usd', 0)
            min_liquidity = CONFIG["min_liquidity"] // 5 if is_pump_candidate else CONFIG["min_liquidity"]
            
            if liquidity > 0 and liquidity < min_liquidity:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error filtering token: {e}")
            return False
