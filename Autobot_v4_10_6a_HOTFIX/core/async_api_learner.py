"""
Async API Learning Module - v4.10.3
SEPARATE from sync checkout to avoid Playwright conflicts

This module ONLY learns API patterns using async Playwright.
It does NOT perform checkout - that's handled by the sync code.

Usage:
1. Call learn_api_pattern() BEFORE drop (warmup)
2. Pattern is saved to database
3. Sync checkout code uses saved pattern (no async needed)
"""

import asyncio
import json
import re
from typing import Dict, Optional
from playwright.async_api import async_playwright, Page
from pathlib import Path
from datetime import datetime


class AsyncAPILearner:
    """
    Learns API patterns using async Playwright
    Completely isolated from sync checkout code
    """
    
    def __init__(self, site_name: str, profile_name: str = "default"):
        """
        Initialize async learner
        
        Args:
            site_name: Site to learn (e.g., 'target', 'walmart')
            profile_name: Browser profile to use
        """
        self.site_name = site_name
        self.profile_name = profile_name
        self.profile_dir = Path.home() / ".autobot" / "profiles" / profile_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self.captured_requests = []
        
        # Site URLs
        self.site_urls = {
            'target': 'https://www.target.com',
            'walmart': 'https://www.walmart.com',
            'pokemon_center': 'https://www.pokemoncenter.com'
        }
    
    async def learn_api_pattern(self, product_url: str, db_manager=None) -> Optional[Dict]:
        """
        Learn API pattern by intercepting network requests
        
        Args:
            product_url: Product page URL to learn from
            db_manager: Database manager to save pattern
        
        Returns:
            Learned pattern dict or None
        """
        print(f"[Async API] 🔍 Learning API pattern for {self.site_name}...")
        print(f"[Async API] 📍 Product URL: {product_url}")
        
        pattern = None
        
        async with async_playwright() as p:
            # Launch browser (async version)
            print(f"[Async API] 🌐 Starting async browser...")
            
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,  # Show browser so user can see
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ],
            )
            
            # Create page
            page = await browser.new_page()
            
            # Enable request interception
            self.captured_requests = []
            
            async def handle_request(request):
                """Capture all XHR/Fetch requests"""
                if request.resource_type in ['xhr', 'fetch']:
                    # Capture request details
                    self.captured_requests.append({
                        'url': request.url,
                        'method': request.method,
                        'headers': request.headers
                    })
            
            async def handle_response(response):
                """Capture response data"""
                if response.request.resource_type in ['xhr', 'fetch']:
                    try:
                        # Try to get JSON data
                        data = await response.json()
                        
                        # Match with captured request
                        for req in self.captured_requests:
                            if req['url'] == response.url and 'data' not in req:
                                req['data'] = data
                                req['status'] = response.status
                                break
                    except:
                        pass
            
            # Attach listeners
            page.on('request', handle_request)
            page.on('response', handle_response)
            
            # Navigate to product page
            print(f"[Async API] 📦 Loading product page...")
            await page.goto(product_url, wait_until='networkidle')
            
            # Wait a bit for all requests to complete
            await asyncio.sleep(3)
            
            print(f"[Async API] 📊 Captured {len(self.captured_requests)} API requests")
            
            # Analyze captured requests
            pattern = self._analyze_requests(product_url)
            
            if pattern and db_manager:
                # Save to database
                print(f"[Async API] 💾 Saving pattern to database...")
                try:
                    # Save pattern
                    db_manager.save_api_pattern(
                        site=self.site_name,
                        endpoint_pattern=pattern['endpoint'],
                        price_path=pattern.get('price_path'),
                        stock_path=pattern.get('stock_path'),
                        name_path=pattern.get('name_path'),
                        image_path=pattern.get('image_path')
                    )
                    print(f"[Async API] ✅ Pattern saved!")
                except Exception as e:
                    print(f"[Async API] ⚠️  Could not save to database: {e}")
            
            # Close browser
            await browser.close()
        
        return pattern
    
    def _analyze_requests(self, product_url: str) -> Optional[Dict]:
        """
        Analyze captured requests to find product API
        
        Args:
            product_url: Original product URL
        
        Returns:
            Pattern dict or None
        """
        print(f"[Async API] 🔬 Analyzing requests...")
        
        # Site-specific patterns
        if self.site_name == 'target':
            return self._analyze_target_requests()
        elif self.site_name == 'walmart':
            return self._analyze_walmart_requests()
        else:
            return self._analyze_generic_requests()
    
    def _analyze_target_requests(self) -> Optional[Dict]:
        """Analyze Target API requests"""
        for req in self.captured_requests:
            url = req['url']
            
            # Target uses redsky API
            if 'redsky.target.com' in url and 'pdp' in url.lower():
                print(f"[Async API] ✅ Found Target API: {url[:80]}...")
                
                # Extract pattern
                pattern = {
                    'endpoint': 'https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1',
                    'method': 'GET',
                    'price_path': 'data.product.price.current_retail',
                    'stock_path': 'data.product.fulfillment.is_out_of_stock_in_all_store_locations',
                    'name_path': 'data.product.item.product_description.title',
                    'image_path': 'data.product.item.enrichment.images.primary_image_url'
                }
                
                # Extract parameters from URL
                if 'tcin=' in url:
                    print(f"[Async API] 📋 TCIN parameter found")
                
                return pattern
        
        print(f"[Async API] ⚠️  No Target API found in {len(self.captured_requests)} requests")
        return None
    
    def _analyze_walmart_requests(self) -> Optional[Dict]:
        """Analyze Walmart API requests"""
        for req in self.captured_requests:
            url = req['url']
            
            # Walmart uses tempo API
            if 'walmart.com' in url and ('tempo' in url.lower() or 'api' in url.lower()):
                print(f"[Async API] ✅ Found Walmart API: {url[:80]}...")
                
                pattern = {
                    'endpoint': url.split('?')[0],  # Base endpoint
                    'method': 'GET'
                }
                
                # Try to find JSON paths from response
                if 'data' in req:
                    data = req['data']
                    # Walmart structure varies, would need more analysis
                
                return pattern
        
        return None
    
    def _analyze_generic_requests(self) -> Optional[Dict]:
        """Analyze generic site API requests"""
        # Look for common API patterns
        api_keywords = ['api', 'product', 'item', 'pdp', 'inventory', 'stock']
        
        for req in self.captured_requests:
            url = req['url'].lower()
            
            # Check if URL contains API keywords
            if any(keyword in url for keyword in api_keywords):
                print(f"[Async API] ✅ Found potential API: {req['url'][:80]}...")
                
                pattern = {
                    'endpoint': req['url'].split('?')[0],
                    'method': req['method']
                }
                
                return pattern
        
        return None


# Convenience function for easy import
async def learn_api_for_site(site_name: str, product_url: str, profile_name: str = "default", db_manager=None):
    """
    Learn API pattern for a site (async function)
    
    Args:
        site_name: 'target', 'walmart', etc.
        product_url: Product page URL
        profile_name: Browser profile
        db_manager: Database to save pattern
    
    Returns:
        Learned pattern dict or None
    
    Usage:
        # In async context:
        pattern = await learn_api_for_site('target', 'https://...', 'my_profile', db)
        
        # In sync context (like task_manager):
        loop = asyncio.new_event_loop()
        pattern = loop.run_until_complete(
            learn_api_for_site('target', 'https://...', 'my_profile', db)
        )
        loop.close()
    """
    learner = AsyncAPILearner(site_name, profile_name)
    return await learner.learn_api_pattern(product_url, db_manager)


# Example usage
if __name__ == "__main__":
    async def test():
        # Test with Target
        pattern = await learn_api_for_site(
            'target',
            'https://www.target.com/p/pok--233-mon-trading-card-game---charizard-x-ex-ultra-premium-collection--no-aasa/-/A-94681790',
            'test_profile'
        )
        print(f"Learned pattern: {pattern}")
    
    asyncio.run(test())
