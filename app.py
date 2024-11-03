import requests
import time
from datetime import datetime
import json
import os
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class DiscogsMonitor:
    def __init__(self):
        self.discogs_api_key = os.getenv('DISCOGS_API_KEY')
        self.pushover_token = os.getenv('PUSHOVER_TOKEN')
        self.pushover_user = os.getenv('PUSHOVER_USER')
        
        self._validate_config()
        
        # Correct headers format for Discogs API
        self.headers = {
            'User-Agent': 'DiscogsVinylMonitor/1.0',  # More specific user agent
            'Authorization': f'Discogs token={self.discogs_api_key}'  # Correct auth format
        }
        self.base_url = 'https://api.discogs.com'
        self.pushover_url = 'https://api.pushover.net/1/messages.json'
        
        self.seen_listings = set()
        self.running = True
        
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
    def _validate_config(self):
        required_vars = [
            'DISCOGS_API_KEY', 
            'PUSHOVER_TOKEN', 
            'PUSHOVER_USER'
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    def _handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def send_notification(self, title, message, url=None, priority=1):
        try:
            payload = {
                'token': self.pushover_token,
                'user': self.pushover_user,
                'title': title,
                'message': message,
                'priority': priority,
                'sound': 'cosmic'
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
            # First, get the release information
            release_url = f'{self.base_url}/releases/{release_id}'
            logger.info(f"Fetching release info from: {release_url}")
            
            release_response = requests.get(release_url, headers=self.headers)
            release_response.raise_for_status()
            
            # Then, get the marketplace listings
            marketplace_url = f'{self.base_url}/marketplace/listings'
            params = {
                'release_id': release_id,
                'status': 'For Sale',
                'format': 'Vinyl'
            }
            
            logger.info(f"Fetching marketplace listings from: {marketplace_url}")
            listings_response = requests.get(marketplace_url, headers=self.headers, params=params)
            listings_response.raise_for_status()
            
            data = listings_response.json()
            
            # Log the full response for debugging
            logger.debug(f"API Response: {json.dumps(data, indent=2)}")
            
            if 'listings' in data:
                self.process_listings(data['listings'])
            elif 'results' in data:  # Alternative response format
                self.process_listings(data['results'])
            else:
                logger.info(f"No listings found for release {release_id}")
                logger.debug(f"Response data: {data}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error checking listings: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            
    def process_listings(self, listings):
        logger.info(f"Found {len(listings)} listings")
        
        for listing in listings:
            listing_id = listing['id']
            
            if listing_id not in self.seen_listings:
                self.seen_listings.add(listing_id)
                
                # Handle different price formats
                if isinstance(listing['price'], dict):
                    price = listing['price']
                else:
                    # If price is a string, try to parse it
                    price_value = listing.get('price', '0')
                    currency = listing.get('currency', 'USD')
                    price = {'value': price_value, 'currency': currency}
                
                condition = listing.get('condition', 'Not specified')
                location = listing.get('ships_from', listing.get('location', 'Unknown'))
                
                title = "💿 New Mk.gee - Fool Vinyl Listed!"
                message = (
                    f"Price: {price['value']} {price['currency']}\n"
                    f"Condition: {condition}\n"
                    f"Ships from: {location}"
                )
                
                listing_url = listing.get('uri', listing.get('url', None))
                
                self.send_notification(
                    title=title,
                    message=message,
                    url=listing_url,
                    priority=1
                )
                logger.info(f"New listing found: {listing_id}")
            
    def run(self, release_id='13811316', interval=300):
        """Main monitoring loop"""
        logger.info(f"Starting monitor for release ID {release_id}")
        
        self.send_notification(
            title="Discogs Monitor Started",
            message="Successfully deployed and monitoring for Mk.gee - Fool vinyl listings",
            priority=0
        )
        
        while self.running:
            try:
                self.check_listings(release_id)
                # Sleep in smaller intervals to respond to signals faster
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                time.sleep(60)

if __name__ == '__main__':
    monitor = DiscogsMonitor()
    monitor.run()
