#!/usr/bin/env python3
"""
Pump.fun Token Scanner Bot - Main Entry Point
Continuously scans cryptocurrency APIs for new tokens and sends Telegram alerts
"""

import asyncio
import logging
import signal
import sys
import time
import threading
from datetime import datetime
import schedule

from config import CONFIG, TELEGRAM_TOKEN, CHAT_ID
from token_scanner import TokenScanner
from telegram_bot import TelegramNotifier
from utils import setup_logging

# Global variables for graceful shutdown
running = True
scanner_thread = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info("Received shutdown signal, stopping bot...")
    running = False
    if scanner_thread:
        scanner_thread.join(timeout=5)
    sys.exit(0)

def scan_and_notify():
    """Main scanning and notification function"""
    if not running:
        return
        
    try:
        logger.info("Starting token scan...")
        
        # Initialize scanner and notifier
        scanner = TokenScanner()
        notifier = TelegramNotifier(TELEGRAM_TOKEN, CHAT_ID)
        
        # Scan for new tokens
        tokens = scanner.scan_all_sources()
        
        if not tokens:
            logger.info("No tokens found")
            return
            
        logger.info(f"Found {len(tokens)} tokens to process")
        
        # Filter and send notifications
        sent_count = 0
        for token in tokens[:CONFIG["max_tokens_per_scan"]]:
            if not running:
                break
                
            try:
                if notifier.should_notify(token) and notifier.send_token_alert(token):
                    sent_count += 1
                    time.sleep(2)  # Rate limit notifications
            except Exception as e:
                logger.error(f"Error processing token {token.get('address', 'unknown')}: {e}")
                continue
                
        logger.info(f"Sent {sent_count} notifications")
        
    except Exception as e:
        logger.error(f"Error in scan_and_notify: {e}")

def run_scheduler():
    """Run the scheduler in a separate thread"""
    logger.info("Starting scheduler thread...")
    while running:
        try:
            schedule.run_pending()
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            time.sleep(10)

def main():
    """Main function"""
    global scanner_thread, logger
    
    # Setup logging
    logger = setup_logging()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Pump.fun Token Scanner Bot...")
    logger.info(f"Configuration: {CONFIG}")
    
    # Validate configuration
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.error("Missing TELEGRAM_TOKEN or CHAT_ID in environment variables")
        sys.exit(1)
    
    try:
        # Schedule scanning
        schedule.every(CONFIG["scan_interval_minutes"]).minutes.do(scan_and_notify)
        
        # Run initial scan
        logger.info("Running initial scan...")
        scan_and_notify()
        
        # Start scheduler thread
        scanner_thread = threading.Thread(target=run_scheduler, daemon=True)
        scanner_thread.start()
        
        logger.info(f"Bot started. Scanning every {CONFIG['scan_interval_minutes']} minutes...")
        
        # Keep main thread alive
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    main()
