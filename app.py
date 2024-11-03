import requests
import time
from datetime import datetime
import json
import os
import logging
from logging.handlers import RotatingFileHandler
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('discogs_monitor.log', maxBytes=100000, backupCount=3),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DiscogsMonitor:
    def __init__(self):
        # Load configuration from environment variables
        self.discogs_api_key = os.getenv('DISCOGS_API_KEY')
        self.pushover_token = os.getenv('PUSHOVER_TOKEN')
        self.pushover_user = os.getenv('PUSHOVER_USER')
        
        # Validate configuration
        self._validate_config()
        
        self.headers = {
            'User-Agent': 'DiscogsMonitor/1.0',
            'Authorization': f'Discogs token={self.discogs_api_key}'
        }
        self.base_url = 'https://api.discogs.com'
        self.pushover_url = 'https://api.pushover.net/1/messages.json'
        
        # Track seen listings
        self.seen_listings = set()
        
        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        
    def _validate_config(self):
        """Validate all required environment variables are present"""
        required_vars = [
            'DISCOGS_API_KEY', 
            'PUSHOVER_TOKEN', 
            'PUSHOVER_USER'
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    def _handle_sigterm(self, signum, frame):
        """Handle termination signal gracefully"""
        logger.info("Received shutdown signal, cleaning up...")
        sys.exit(0)
        
    def send_notification(self, title, message, url=None, priority=1):
        """Send notification via Pushover"""
        try:
            payload = {
                'token': self.pushover_token,
                'user': self.pushover_user,
                'title': title,
                'message': message,
                'priority': priority,
                'sound': 'cosmic'  # Use a distinctive sound for new listings
            }
            
            if url:
                payload['url'] = url
                payload['url_title'] = 'View Listing'
            
            response = requests.post(self.pushover_url, data=payload)
            response.raise_for_status()
            logger.info("Pushover notification sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending Pushover notification: {e}")
    
    def check_listings(self, release_id='13811316'):
        """Check current marketplace listings for a specific release"""
        try:
            url = f'{self.base_url}/marketplace/search'
            params = {
                'release_id': release_id,
                'format': 'Vinyl'
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data['listings']:
                self.process_listings(data['listings'])
            else:
                logger.info(f"No listings found for release {release_id}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking listings: {e}")
            
    def process_listings(self, listings):
        """Process listings and send notifications for new ones"""
        logger.info(f"Found {len(listings)} listings")
        
        for listing in listings:
            listing_id = listing['id']
            
            if listing_id not in self.seen_listings:
                self.seen_listings.add(listing_id)
                
                price = listing['price']
                condition = listing['condition']
                location = listing['ships_from']
                
                title = "💿 New Mk.gee - Fool Vinyl Listed!"
                message = (
                    f"Price: {price['value']} {price['currency']}\n"
                    f"Condition: {condition}\n"
                    f"Ships from: {location}"
                )
                
                # Send push notification with direct link to listing
                self.send_notification(
                    title=title,
                    message=message,
                    url=listing['uri'],
                    priority=1  # High priority for new listings
                )
                logger.info(f"New listing found: {listing_id}")
            
    def run(self, release_id='13811316', interval=300):
        """Main monitoring loop"""
        logger.info(f"Starting monitor for release ID {release_id}")
        
        # Send test notification on startup
        self.send_notification(
            title="Discogs Monitor Started",
            message="Successfully deployed and monitoring for Mk.gee - Fool vinyl listings",
            priority=0
        )
        
        while True:
            try:
                self.check_listings(release_id)
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)  # Wait a minute before retrying

if __name__ == '__main__':
    monitor = DiscogsMonitor()
    monitor.run()
