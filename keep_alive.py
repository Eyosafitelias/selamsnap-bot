import requests
import time
import threading
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeepAlive:
    def __init__(self, my_url, partner_url, interval_minutes=14):
        """
        my_url: URL of this server (to receive pings)
        partner_url: URL of partner server to ping
        interval_minutes: Ping interval (Render sleeps after 15 min inactivity)
        """
        self.my_url = my_url
        self.partner_url = partner_url
        self.interval = interval_minutes * 60  # Convert to seconds
        self.is_running = False
        
    def ping_partner(self):
        """Send ping to partner server"""
        try:
            # Add timestamp to avoid caching
            url = f"{self.partner_url}/ping?from={self.my_url}&t={int(time.time())}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Pinged {self.partner_url} successfully")
                return True
            else:
                logger.warning(f"⚠️  Partner responded with {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to ping {self.partner_url}: {e}")
            return False
    
    def ping_loop(self):
        """Continuously ping partner server"""
        self.is_running = True
        logger.info(f"🚀 Starting keep-alive loop. Pinging {self.partner_url} every {self.interval//60} minutes")
        
        while self.is_running:
            self.ping_partner()
            # Sleep for interval, but check every minute if we should stop
            for _ in range(self.interval):
                if not self.is_running:
                    break
                time.sleep(1)
    
    def start(self):
        """Start the keep-alive in a background thread"""
        thread = threading.Thread(target=self.ping_loop, daemon=True)
        thread.start()
        logger.info("🔄 Keep-alive thread started")
        return thread
    
    def stop(self):
        """Stop the keep-alive loop"""
        self.is_running = False
        logger.info("🛑 Keep-alive stopped")