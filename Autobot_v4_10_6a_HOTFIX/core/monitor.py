"""
Autobot Product Monitor
Backend monitoring for early product detection
Phase 3 - IMPLEMENTED
Phase 5 - Image Caching Integration
"""

import threading
import time
import requests
from typing import Dict, List, Callable, Optional
from datetime import datetime
import re
from urllib.parse import urlparse
from core.image_cache import get_cache
from core.ban_detector import get_ban_detector_pool
from core.adaptive_monitor import get_speed_learner
from core.smart_api_analyzer import SmartAPIAnalyzer  # V4.8: Smart API learning
from core.enhanced_api_system import get_enhanced_api  # V5.0 (Autobot 2.0): Enhanced API with retries
from core.hybrid_checker import get_hybrid_checker  # V5.0.1 (Autobot 2.0.1): Hybrid HTML/API checker


class Monitor:
    """Individual product monitor"""
    
    def __init__(self, monitor_id: str, product_url: str, site: str, 
                 check_interval: int = 5, callback: Optional[Callable] = None,
                 settings: Optional[Dict] = None, db_manager=None):
        self.monitor_id = monitor_id
        self.product_url = product_url
        self.site = site
        self.check_interval = check_interval  # seconds
        self.callback = callback
        self.db_manager = db_manager  # For API pattern storage
        
        # Monitor settings (optional behaviors)
        self.settings = settings or {
            'auto_buy': True,
            'discord_notify': True,
            'detailed_log': False,
            # V4.0 defaults
            'target_price': 0.0,
            'zip_code': '',
            'show_stores': True,
            'show_rating': True,
            'show_promotions': True
        }
        
        # Status tracking
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.last_check = None
        self.check_count = 0
        self.in_stock = False
        self.is_preorder = False  # Track if item is pre-order
        self.product_name = "Unknown"
        self.product_price = 0.0
        self.product_regular_price = 0.0  # NEW: Track regular price for sale detection
        self.product_image = ""
        
        # V4.0: Enhanced product data - extract from settings
        self.target_price = float(self.settings.get('target_price', 0.0) or 0.0)
        self.zip_code = self.settings.get('zip_code', '')
        self.show_stores = self.settings.get('show_stores', True)
        self.show_rating = self.settings.get('show_rating', True)
        self.show_promotions = self.settings.get('show_promotions', True)
        self.image_url = None
        self.cached_image_path = None
        self.rating = None
        self.review_count = 0
        self.promotions = None
        self.local_stores = None
        self.scalper_status = None
        
        # Error tracking
        self.error_count = 0
        self.last_error = None
        
        # V4.1: Ban detection
        self.ban_detector = None  # Will be initialized on start
        
        # V4.1B: Adaptive speed learning
        self.speed_learner = None  # Will be initialized on start
        self.adaptive_interval = None  # Dynamic interval from learner
        
        # V4.8: Smart API learning (auto-learns API patterns during monitoring)
        self.api_analyzer = None  # Will be initialized on start
        self.api_learning_attempted = False  # Track if we already tried learning

        # V5.0 (Autobot 2.0): Enhanced API system with intelligent retry
        self.enhanced_api = None  # Will be initialized on start
        self.api_stats = {'api_success': 0, 'html_fallback': 0}  # Track API vs HTML usage

        # V5.0.1 (Autobot 2.0.1): Hybrid HTML/API checker (adapts to API changes)
        self.hybrid_checker = None  # Will be initialized on start
        
    def start(self):
        """Start monitoring this product"""
        if self.is_running:
            return
        
        # V4.1: Initialize ban detector
        ban_pool = get_ban_detector_pool()
        self.ban_detector = ban_pool.get_detector(self.monitor_id)
        
        # V4.1B: Initialize adaptive speed learner
        self.speed_learner = get_speed_learner()
        self.adaptive_interval = self.speed_learner.get_current_interval(
            self.monitor_id, self.site
        )
        print(f"[MONITOR] {self.monitor_id}: Starting with {self.adaptive_interval:.1f}s interval")
        
        # V4.8: Initialize Smart API Analyzer (learns API patterns automatically)
        self.api_analyzer = SmartAPIAnalyzer(db_manager=self.db_manager)
        
        # V4.10.6: Load existing patterns from database
        if self.db_manager:
            self.api_analyzer.load_patterns()

        print(f"[MONITOR] {self.monitor_id}: Smart API learning enabled")

        # V5.0 (Autobot 2.0): Initialize enhanced API system
        self.enhanced_api = get_enhanced_api(self.db_manager)
        print(f"[MONITOR] {self.monitor_id}: Autobot 2.0 Enhanced API active!")

        # V5.0.1 (Autobot 2.0.1): Initialize hybrid checker (adapts to API changes)
        self.hybrid_checker = get_hybrid_checker()
        print(f"[MONITOR] {self.monitor_id}: Hybrid HTML/API checker ready!")
        
        self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop monitoring this product"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                # V4.1: Check if we should proceed (cooldown check)
                if self.ban_detector and not self.ban_detector.should_check_now():
                    cooldown = self.ban_detector.get_cooldown_seconds()
                    print(f"[MONITOR] {self.monitor_id}: In cooldown ({cooldown}s), waiting...")
                    time.sleep(1)  # Short sleep to avoid busy loop
                    continue
                
                self._check_stock()
                self.last_check = datetime.now()
                self.check_count += 1
                
                # Reset error count on success
                if self.error_count > 0:
                    self.error_count = 0
                    self.last_error = None
                
                # V4.1B: Record success and update interval
                if self.speed_learner:
                    self.speed_learner.record_success(self.monitor_id, self.site)
                    self.adaptive_interval = self.speed_learner.get_current_interval(
                        self.monitor_id, self.site
                    )
                    
            except Exception as e:
                self.error_count += 1
                self.last_error = str(e)
                
                # V4.1: Check for ban in error message
                if self.ban_detector:
                    ban_detected = self.ban_detector.detect_ban(
                        error_message=str(e)
                    )
                    if ban_detected:
                        print(f"[MONITOR] {self.monitor_id}: Ban detected, initiating recovery")
                        
                        # V4.1B: Record ban in speed learner
                        if self.speed_learner:
                            self.speed_learner.record_ban(self.monitor_id, self.site)
                            self.adaptive_interval = self.speed_learner.get_current_interval(
                                self.monitor_id, self.site
                            )
                        
                        self.ban_detector.recover_from_ban()
                
                if self.callback:
                    self.callback('error', {
                        'monitor_id': self.monitor_id,
                        'error': str(e),
                        'error_count': self.error_count
                    })
            
            # V4.1B: Sleep using adaptive interval (or fallback to check_interval)
            sleep_time = self.adaptive_interval if self.adaptive_interval else self.check_interval
            time.sleep(sleep_time)
            
    def _check_stock(self):
        """Check product stock status"""
        if self.site == "target":
            self._check_target_stock()
        elif self.site == "walmart":
            self._check_walmart_stock()
        elif self.site == "pokemon_center":
            self._check_pokemon_center_stock()
            
    def _check_target_stock(self):
        """
        Check Target.com stock - Autobot 2.0.1 Hybrid Version

        Process (Updated for Target API changes):
        1. Try Hybrid HTML checker (FAST BeautifulSoup parsing)
        2. Falls back to old HTML method if needed
        3. API discovery happens in background (for when APIs return)
        """
        # Extract TCIN (Target product ID) from URL
        tcin_match = re.search(r'/A-(\d+)', self.product_url)

        if not tcin_match:
            print(f"[MONITOR] {self.monitor_id}: Could not extract TCIN from URL")
            self._check_target_stock_html()
            return

        tcin = tcin_match.group(1)

        # V5.0.1 (Autobot 2.0.1): Try Hybrid HTML checker FIRST (Target APIs deprecated)
        if self.hybrid_checker:
            try:
                print(f"[MONITOR] {self.monitor_id}: Using Hybrid HTML checker...")
                result = self.hybrid_checker.check_stock_fast_html(self.product_url, tcin)

                if result and result.get('success'):
                    # Successfully got data!
                    old_stock_status = self.in_stock

                    self.product_name = result.get('name', 'Unknown')
                    self.product_price = result.get('price', 0.0)
                    self.product_regular_price = result.get('regular_price', self.product_price)
                    self.in_stock = result.get('in_stock', False)

                    if result.get('image'):
                        self.product_image = result['image']

                    # Track success
                    source = result.get('source', 'hybrid')
                    print(f"[MONITOR] {self.monitor_id}: ✓ Success ({source})! {self.product_name} - {'IN STOCK' if self.in_stock else 'OUT OF STOCK'}")

                    # Trigger stock_found callback if stock changed
                    if not old_stock_status and self.in_stock and self.callback:
                        self.callback('stock_found', {
                            'monitor_id': self.monitor_id,
                            'product_url': self.product_url,
                            'product_name': self.product_name,
                            'product_price': self.product_price,
                            'site': self.site
                        })

                    return

                else:
                    print(f"[MONITOR] {self.monitor_id}: Hybrid checker failed, trying fallback...")

            except Exception as e:
                print(f"[MONITOR] {self.monitor_id}: Hybrid checker error: {e}")

        # Fallback to old HTML method if hybrid failed
        print(f"[MONITOR] {self.monitor_id}: Using legacy HTML fallback")
        self._check_target_stock_html()
    
    def _check_target_stock_with_learning(self, tcin: str):
        """
        Check Target stock AND learn API patterns for future fast checks
        This combines browser monitoring with automatic API pattern detection
        """
        # Try multiple Target API endpoints (they change these)
        api_urls = [
            f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&tcin={tcin}&store_id=3991",
            f"https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=ff457966e64d5e877fdbad070f276d18ecec4a01&tcin={tcin}&store_id=3991",
            f"https://redsky.target.com/v3/pdp/tcin/{tcin}?store_id=3991",
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.target.com/',
        }
        
        api_worked = False
        for api_url in api_urls:
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                
                # Skip 400 errors (bad request) - try next endpoint
                if response.status_code == 400:
                    print(f"[MONITOR] API endpoint returned 400, trying next...")
                    continue
                
                # Only treat 403/429 as bans (not API errors!)
                if self.ban_detector and response.status_code in [403, 429]:
                    ban_detected = self.ban_detector.detect_ban(
                        status_code=response.status_code,
                        response_text=response.text
                    )
                    if ban_detected:
                        print(f"[MONITOR] {self.monitor_id}: Real ban detected (not API error)")
                        if self.speed_learner:
                            self.speed_learner.record_ban(self.monitor_id, self.site)
                        self.ban_detector.recover_from_ban()
                        return
                
                if response.status_code == 200:
                    data = response.json()
                    product = data.get('data', {}).get('product', {})
                    
                    if product:
                        # V4.8: Teach the API analyzer this pattern!
                        if self.api_analyzer:
                            self.api_analyzer.learn_from_response(
                                site=self.site,
                                url=api_url,
                                response_data=data,
                                product_id=tcin
                            )
                            print(f"[MONITOR] {self.monitor_id}: ✓ Learned API pattern from this check!")
                        
                        # Extract product data
                        item = product.get('item', {})
                        self.product_name = item.get('product_description', {}).get('title', 'Unknown')
                        
                        price_data = product.get('price', {})
                        self.product_price = float(price_data.get('current_retail', 0.0))
                        self.product_regular_price = float(price_data.get('reg_retail', self.product_price))
                        
                        # Check stock
                        fulfillment = product.get('fulfillment', {}).get('shipping_options', {})
                        available = fulfillment.get('available_to_promise_quantity', 0)
                        
                        old_stock_status = self.in_stock
                        self.in_stock = available > 0
                        
                        # Stock change callback
                        if not old_stock_status and self.in_stock and self.callback:
                            self.callback('stock_found', {
                                'monitor_id': self.monitor_id,
                                'product_url': self.product_url,
                                'product_name': self.product_name,
                                'product_price': self.product_price,
                                'site': self.site
                            })
                        
                        api_worked = True
                        break
                        
            except Exception as e:
                print(f"[MONITOR] API endpoint error: {e}")
                continue
        
        # If no API worked, fall back to HTML scraping
        if not api_worked:
            print(f"[MONITOR] {self.monitor_id}: All API endpoints failed, using HTML fallback")
            self._check_target_stock_html()
    
    def _check_target_stock_html(self):
        """Fallback HTML scraping method when API is unavailable"""
        print(f"[MONITOR] {self.monitor_id}: Checking via HTML...")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html'
            }
            response = requests.get(self.product_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"[MONITOR] HTML check failed: {response.status_code}")
                return
            
            html_lower = response.text.lower()
            html_original = response.text  # Keep original case for accurate matching
            old_stock_status = self.in_stock
            
            # Check stock status - FIXED: Target shows "Add to cart" even when OOS (grayed out)
            # Priority 1: Check for explicit OOS text
            if 'out of stock' in html_lower or 'sold out' in html_lower:
                self.in_stock = False
            # Priority 2: Check if "Add to cart" button is disabled (OOS)
            elif re.search(r'add to cart[^>]*(?:disabled|aria-disabled="true")', html_lower, re.IGNORECASE):
                self.in_stock = False
            # Priority 3: Check for active stock indicators (clickable buttons)
            elif ('ship it' in html_lower or 'pick it up' in html_lower):
                self.in_stock = True
            # Priority 4: If "Add to cart" exists but NOT disabled, likely in stock
            elif 'add to cart' in html_lower and not re.search(r'add to cart[^>]*(?:disabled|aria-disabled)', html_lower, re.IGNORECASE):
                self.in_stock = True
            else:
                # If we can't determine, assume OOS
                self.in_stock = False
            
            # Try to extract product name from title or h1
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_original, re.IGNORECASE)
            if title_match:
                title = title_match.group(1)
                # Clean up Target's title format
                title = title.split(' : Target')[0]
                title = title.split(' - Target')[0]
                if title and len(title) > 3:
                    self.product_name = title.strip()
            
            print(f"[MONITOR] {self.monitor_id}: {self.product_name} - {'IN STOCK' if self.in_stock else 'OUT OF STOCK'}")
            
            # Trigger stock_found callback if stock changed
            if not old_stock_status and self.in_stock:
                if self.callback:
                    self.callback('stock_found', {
                        'monitor_id': self.monitor_id,
                        'product_url': self.product_url,
                        'product_name': self.product_name,
                        'product_price': self.product_price,
                        'site': self.site
                    })
                    
        except Exception as e:
            print(f"[MONITOR] HTML check error: {e}")
    
    def _check_target_stock_html_fallback(self):
        """Fallback HTML scraping method (used if API fails)"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(self.product_url, headers=headers, timeout=10)
        
        # V4.1: Check for ban before processing response
        if self.ban_detector:
            ban_detected = self.ban_detector.detect_ban(
                response_text=response.text if response else "",
                status_code=response.status_code if response else 0
            )
            if ban_detected:
                print(f"[MONITOR] {self.monitor_id}: Ban detected in HTML response")
                self.ban_detector.recover_from_ban()
                return  # Skip this check cycle
        
        response.raise_for_status()
        
        html = response.text
        
        # Extract product name
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if name_match:
            self.product_name = name_match.group(1).strip()
        
        # Extract prices (regular and sale) - ULTRA-IMPROVED ACCURACY v3.1.1
        # Priority order: JSON data > Sale pattern > Price near title > Highest price
        
        # Pattern 0: Try to find price in JSON data (most reliable!)
        json_price_match = re.search(r'"price":\s*"?(\d+\.\d{2})"?', html)
        json_current_price = re.search(r'"current_price".*?"formatted_price":\s*"\$(\d+\.\d{2})"', html, re.DOTALL)
        
        if json_current_price:
            self.product_price = float(json_current_price.group(1))
            # Look for original price too
            json_reg_price = re.search(r'"original_price".*?"formatted_price":\s*"\$(\d+\.\d{2})"', html, re.DOTALL)
            if json_reg_price:
                self.product_regular_price = float(json_reg_price.group(1))
            else:
                self.product_regular_price = self.product_price
        elif json_price_match:
            self.product_price = float(json_price_match.group(1))
            self.product_regular_price = self.product_price
        else:
            # Pattern 1: Look for "Sale" followed by price (Target's sale format)
            sale_match = re.search(r'<span[^>]*>\s*\$(\d+\.\d{2})\s*</span>.*?reg\s+\$(\d+\.\d{2})', html, re.IGNORECASE | re.DOTALL)
            
            if sale_match:
                # Found sale price with regular price
                self.product_price = float(sale_match.group(1))
                self.product_regular_price = float(sale_match.group(2))
            else:
                # Pattern 2: Look for price near h1 (product title) - most reliable for HTML
                # This catches the price within 500 chars of the title (avoids "plans" section)
                h1_section = re.search(r'<h1[^>]*>.*?</h1>(.{0,500}?)<span[^>]*>\s*\$(\d+\.\d{2})', html, re.DOTALL)
                
                if h1_section:
                    self.product_price = float(h1_section.group(2))
                    self.product_regular_price = self.product_price
                else:
                    # Pattern 3: Smart filtering - find main product price
                    all_prices = re.findall(r'\$(\d+\.\d{2})', html)
                    if all_prices:
                        price_floats = [float(p) for p in all_prices]
                        
                        # Filter out protection plan prices ($5-$30 range)
                        # and tiny prices (shipping, etc)
                        main_prices = [p for p in price_floats if p > 30.0]
                        
                        if main_prices:
                            # Get the most common price in the high range
                            from collections import Counter
                            price_counts = Counter(main_prices)
                            # Get top 2 most common prices
                            top_prices = price_counts.most_common(2)
                            
                            # If there's a clear winner (appears 2+ times), use it
                            if len(top_prices) > 0 and top_prices[0][1] >= 2:
                                self.product_price = top_prices[0][0]
                                self.product_regular_price = self.product_price
                            else:
                                # Otherwise use highest price (actual product)
                                self.product_price = max(main_prices)
                                self.product_regular_price = self.product_price
                        else:
                            # Fallback to highest price found (even if low)
                            self.product_price = max(price_floats) if price_floats else 0.0
                            self.product_regular_price = self.product_price
        
        # Check stock status
        old_stock_status = self.in_stock
        
        # Pre-order/Coming Soon patterns (STRICT - these mean NOT available NOW)
        preorder_patterns = [
            'preorder',
            'pre-order',
            'pre order',
            'coming soon',
            'coming fri',
            'coming mon',
            'coming tue',
            'coming wed',
            'coming thu',
            'coming sat',
            'coming sun',
            'releases on',
            'available on',
            'ships on',
            'release date',
            'check back on',
            'releasing',
            'not yet available'
        ]
        
        # Out of stock patterns (STRICT)
        out_of_stock_patterns = [
            'out of stock',
            'unavailable',
            'sold out',
            'not available',
            'currently unavailable',
            '"availability":"OutOfStock"',
            '"availability": "OutOfStock"',
            'preorders have sold out',
            'this item is no longer available',
            'pickup.*not available',
            'delivery.*not available',
            'temporarily out of stock'
        ]
        
        # Buttons that mean NOT actually in stock (false positives)
        fake_stock_buttons = [
            'preorder',
            'pre-order',
            'notify me',
            'email me',
            'find stores',
            'check stores',
            'check availability',
            'see similar items',
            'sign up for alerts'
        ]
        
        # REAL in stock patterns (VERY STRICT - only these mean truly available NOW)
        in_stock_patterns = [
            'add to cart',
            '"availability":"InStock"',
            '"availability": "InStock"',
            '"inventory_status":"in_stock"',
            'pickup.*ready within',
            'add to bag'
        ]
        
        html_lower = html.lower()
        
        # Step 1: Check if pre-order (but not yet available)
        is_preorder = any(pattern.lower() in html_lower for pattern in preorder_patterns)
        
        # Step 2: Check for fake stock buttons
        has_fake_button = any(pattern.lower() in html_lower for pattern in fake_stock_buttons)
        
        # Step 3: Check if out of stock
        is_out_of_stock = any(pattern.lower() in html_lower for pattern in out_of_stock_patterns)
        
        # Step 4: Check if REALLY in stock (case-sensitive for JSON, case-insensitive for buttons)
        has_add_to_cart = 'add to cart' in html_lower or 'add to bag' in html_lower
        has_json_stock = '"availability":"InStock"' in html or '"availability": "InStock"' in html
        is_in_stock = has_add_to_cart or has_json_stock
        
        # DEBUG: Log what we found (only if detailed_log is enabled)
        if self.settings.get('detailed_log', False):
            print(f"\n[DEBUG] Stock Check for {self.monitor_id}:")
            print(f"  - Pre-order detected: {is_preorder}")
            print(f"  - Fake button detected: {has_fake_button}")
            print(f"  - OOS pattern detected: {is_out_of_stock}")
            print(f"  - 'Add to cart' found: {has_add_to_cart}")
            print(f"  - JSON InStock found: {has_json_stock}")
            print(f"  - Final in_stock: {is_in_stock and not is_out_of_stock and not is_preorder and not has_fake_button}")
        
        # Step 5: Final determination (STRICT LOGIC)
        # Must have positive indicator AND no negative indicators
        if is_preorder:
            # It's a pre-order, not available yet
            self.in_stock = False
            self.is_preorder = True
        elif has_fake_button:
            # Has fake buttons like "notify me" - definitely not in stock
            self.in_stock = False
            self.is_preorder = False
        elif is_out_of_stock:
            # Explicitly out of stock
            self.in_stock = False
            self.is_preorder = False
        elif is_in_stock:
            # Has "Add to cart" or InStock JSON - truly available
            self.in_stock = True
            self.is_preorder = False
        else:
            # No clear indicators - assume OOS to be safe
            self.in_stock = False
            self.is_preorder = False
        
        # Only trigger callback if status changed from OOS to truly IN STOCK
        if not old_stock_status and self.in_stock:
            if self.callback:
                self.callback('stock_found', {
                    'monitor_id': self.monitor_id,
                    'product_url': self.product_url,
                    'product_name': self.product_name,
                    'product_price': self.product_price,
                    'product_regular_price': getattr(self, 'product_regular_price', self.product_price),
                    'site': self.site,
                    'was_preorder': False
                })
        
        # Send one-time preorder detection notification
        if self.is_preorder and self.callback and self.check_count == 1:
            self.callback('preorder_detected', {
                'monitor_id': self.monitor_id,
                'product_url': self.product_url,
                'product_name': self.product_name,
                'product_price': self.product_price,
                'site': self.site
            })
                
    def _check_walmart_stock(self):
        """Check Walmart.com stock via HTTP"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(self.product_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        html_lower = html.lower()
        
        # Basic stock detection for Walmart
        old_stock_status = self.in_stock
        
        is_out_of_stock = 'out of stock' in html_lower or 'unavailable' in html_lower
        is_in_stock = 'add to cart' in html_lower
        
        self.in_stock = is_in_stock and not is_out_of_stock
        
        if not old_stock_status and self.in_stock:
            if self.callback:
                self.callback('stock_found', {
                    'monitor_id': self.monitor_id,
                    'product_url': self.product_url,
                    'product_name': self.product_name,
                    'product_price': self.product_price,
                    'site': self.site
                })
                
    def _check_pokemon_center_stock(self):
        """Check Pokemon Center stock via HTTP"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(self.product_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        html_lower = html.lower()
        
        # Basic stock detection
        old_stock_status = self.in_stock
        
        is_out_of_stock = 'out of stock' in html_lower or 'sold out' in html_lower
        is_in_stock = 'add to cart' in html_lower or 'add to bag' in html_lower
        
        self.in_stock = is_in_stock and not is_out_of_stock
        
        if not old_stock_status and self.in_stock:
            if self.callback:
                self.callback('stock_found', {
                    'monitor_id': self.monitor_id,
                    'product_url': self.product_url,
                    'product_name': self.product_name,
                    'product_price': self.product_price,
                    'site': self.site
                })
    
    # ============ V4.0 ENHANCED DATA EXTRACTION METHODS ============
    
    def _extract_v4_data(self, product: Dict, full_response: Dict):
        """Extract all v4.0 enhanced data from Target API response"""
        try:
            # Extract image URL
            self.image_url = self._extract_image(product)
            
            # Cache image if enabled and URL available
            if self.image_url and self.settings.get('image_cache_enabled', True):
                try:
                    cache = get_cache()
                    self.cached_image_path = cache.download_and_cache(self.image_url)
                except Exception as e:
                    print(f"Warning: Image caching failed: {e}")
            
            # Extract rating data
            rating_data = self._extract_rating(product)
            self.rating = rating_data.get('rating')
            self.review_count = rating_data.get('count', 0)
            
            # Extract promotions
            self.promotions = self._extract_promotions(product)
            
            # Extract local stores (if zip code available)
            zip_code = self.settings.get('zip_code') if self.settings else None
            if zip_code:
                self.local_stores = self._get_local_stores(product, zip_code)
            
            # Calculate scalper status
            if self.target_price:
                self.scalper_status = self._get_scalper_status(
                    self.product_price, 
                    self.target_price
                )
                
        except Exception as e:
            # Don't fail the whole check if v4 data extraction fails
            print(f"Warning: v4.0 data extraction failed: {e}")
    
    def _extract_image(self, product: Dict) -> Optional[str]:
        """Extract primary product image URL"""
        try:
            images = product.get('item', {}).get('enrichment', {}).get('images', {})
            primary_url = images.get('primary_image_url')
            
            # Return full resolution image URL
            if primary_url:
                return primary_url
            
            # Fallback to alternate images
            alternates = images.get('alternate_image_urls', [])
            if alternates:
                return alternates[0]
            
            return None
        except Exception:
            return None
    
    def _extract_rating(self, product: Dict) -> Dict:
        """Extract average rating and review count"""
        try:
            stats = product.get('ratings_and_reviews', {}).get('statistics', {})
            rating_data = stats.get('rating', {})
            
            return {
                'rating': rating_data.get('average'),
                'count': rating_data.get('count', 0)
            }
        except Exception:
            return {'rating': None, 'count': 0}
    
    def _extract_promotions(self, product: Dict) -> List[str]:
        """Extract active promotions"""
        try:
            promos = product.get('promotions', [])
            
            # Extract description from each promotion
            descriptions = []
            for promo in promos[:5]:  # Limit to top 5
                desc = promo.get('description', '')
                if desc and desc not in descriptions:
                    descriptions.append(desc)
            
            return descriptions
        except Exception:
            return []
    
    def _get_local_stores(self, product: Dict, zip_code: str) -> List[Dict]:
        """Extract local store inventory"""
        try:
            stores = []
            fulfillment = product.get('fulfillment', {})
            
            # Get store options
            store_options = fulfillment.get('store_options', [])
            
            for store_opt in store_options[:10]:  # Get up to 10 stores
                try:
                    # Extract location data
                    loc_avail = store_opt.get('location_availability', {})
                    store_info = loc_avail.get('store', {})
                    
                    # Get store details
                    store_name = store_info.get('location_name', 'Unknown')
                    store_id = store_info.get('location_id')
                    
                    # Get stock quantity
                    stock_qty = loc_avail.get('available_to_promise_quantity', 0)
                    
                    # Get distance (if available)
                    distance_info = store_info.get('distance', {})
                    distance = distance_info.get('value', 0)
                    
                    # Get address
                    address = store_info.get('address', {})
                    address_line = address.get('address_line1', '')
                    city = address.get('city', '')
                    state = address.get('state', '')
                    
                    store_data = {
                        'name': store_name,
                        'id': store_id,
                        'stock': stock_qty,
                        'distance': round(distance, 1) if distance else 0,
                        'address': f"{address_line}, {city}, {state}".strip(', '),
                        'in_stock': stock_qty > 0
                    }
                    
                    stores.append(store_data)
                    
                except Exception as e:
                    # Skip stores with extraction errors
                    continue
            
            # Sort by distance (closest first)
            stores.sort(key=lambda x: x['distance'])
            
            return stores[:5]  # Return top 5 closest
            
        except Exception:
            return []
    
    def _get_scalper_status(self, current_price: float, target_price: float) -> Optional[Dict]:
        """Determine if product is scalped based on target price"""
        if not target_price or target_price <= 0:
            return None
        
        # Calculate markup percentage
        markup_percent = ((current_price - target_price) / target_price) * 100
        
        # Determine status based on markup
        if markup_percent <= 0:
            return {
                'color': 'green',
                'label': 'GREAT DEAL',
                'emoji': '🟢',
                'percent': markup_percent
            }
        elif markup_percent <= 20:
            return {
                'color': 'yellow',
                'label': 'SLIGHT MARKUP',
                'emoji': '🟡',
                'percent': markup_percent
            }
        else:
            return {
                'color': 'red',
                'label': 'SCALPED!',
                'emoji': '🔴',
                'percent': markup_percent
            }


class ProductMonitor:
    """
    Backend product monitoring system
    Monitors products and auto-creates tasks when stock is found
    """
    
    def __init__(self, task_manager=None, webhook=None, db_manager=None):
        self.monitors: Dict[str, Monitor] = {}
        self.task_manager = task_manager
        self.webhook = webhook
        self.db_manager = db_manager  # For API pattern storage
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
    def set_task_manager(self, task_manager):
        """Set the task manager for auto-task creation"""
        self.task_manager = task_manager
        
    def set_webhook(self, webhook):
        """Set the webhook for notifications"""
        self.webhook = webhook
        
    def add_callback(self, callback: Callable):
        """Add a callback for monitor events"""
        self.callbacks.append(callback)
        
    def _detect_site(self, url: str) -> str:
        """Detect site from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if 'target.com' in domain:
            return 'target'
        elif 'walmart.com' in domain:
            return 'walmart'
        elif 'pokemoncenter.com' in domain:
            return 'pokemon_center'
        else:
            return 'unknown'
            
    def add_monitor(self, product_url: str, check_interval: int = 5, settings: Optional[Dict] = None) -> str:
        """
        Add a product to monitor
        
        Args:
            product_url: URL of the product page
            check_interval: Check interval in seconds (default 5)
            settings: Optional dict with 'auto_buy', 'discord_notify', 'detailed_log'
            
        Returns:
            monitor_id: Unique ID for this monitor
        """
        with self._lock:
            # Generate monitor ID
            monitor_id = f"MON_{len(self.monitors) + 1}_{int(time.time())}"
            
            # Detect site
            site = self._detect_site(product_url)
            
            # Create monitor with settings
            monitor = Monitor(
                monitor_id=monitor_id,
                product_url=product_url,
                site=site,
                check_interval=check_interval,
                callback=self._handle_monitor_event,
                settings=settings,
                db_manager=self.db_manager  # V4.10.6: Pass db_manager for API learning
            )
            
            self.monitors[monitor_id] = monitor
            
            # Notify callbacks
            self._emit_event('monitor_added', {
                'monitor_id': monitor_id,
                'product_url': product_url,
                'site': site,
                'check_interval': check_interval
            })
            
            return monitor_id
            
    def start_monitor(self, monitor_id: str):
        """Start a specific monitor"""
        with self._lock:
            if monitor_id in self.monitors:
                monitor = self.monitors[monitor_id]
                monitor.start()
                
                self._emit_event('monitor_started', {
                    'monitor_id': monitor_id,
                    'product_url': monitor.product_url
                })
                
    def stop_monitor(self, monitor_id: str):
        """Stop a specific monitor"""
        with self._lock:
            if monitor_id in self.monitors:
                monitor = self.monitors[monitor_id]
                monitor.stop()
                
                self._emit_event('monitor_stopped', {
                    'monitor_id': monitor_id,
                    'product_url': monitor.product_url
                })
                
    def delete_monitor(self, monitor_id: str):
        """Delete a monitor"""
        with self._lock:
            if monitor_id in self.monitors:
                monitor = self.monitors[monitor_id]
                monitor.stop()
                del self.monitors[monitor_id]
                
                self._emit_event('monitor_deleted', {
                    'monitor_id': monitor_id
                })
                
    def start_all(self):
        """Start all monitors"""
        with self._lock:
            for monitor in self.monitors.values():
                if not monitor.is_running:
                    monitor.start()
                    
            self._emit_event('all_monitors_started', {
                'count': len(self.monitors)
            })
            
    def stop_all(self):
        """Stop all monitors"""
        with self._lock:
            for monitor in self.monitors.values():
                monitor.stop()
                
            self._emit_event('all_monitors_stopped', {
                'count': len(self.monitors)
            })
            
    def get_monitor(self, monitor_id: str) -> Optional[Monitor]:
        """Get a specific monitor"""
        return self.monitors.get(monitor_id)
        
    def get_all_monitors(self) -> List[Monitor]:
        """Get all monitors"""
        return list(self.monitors.values())
        
    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        total = len(self.monitors)
        running = sum(1 for m in self.monitors.values() if m.is_running)
        in_stock = sum(1 for m in self.monitors.values() if m.in_stock)
        total_checks = sum(m.check_count for m in self.monitors.values())
        
        return {
            'total_monitors': total,
            'running_monitors': running,
            'products_in_stock': in_stock,
            'total_checks': total_checks
        }
        
    def _handle_monitor_event(self, event_type: str, data: Dict):
        """Handle events from individual monitors"""
        if event_type == 'stock_found':
            # Get the monitor to check its settings
            monitor = self.monitors.get(data['monitor_id'])
            
            if monitor:
                # Auto-create task only if enabled
                if monitor.settings.get('auto_buy', True) and self.task_manager:
                    self._auto_create_task(data)
                
                # Send webhook notification only if enabled (v4.0: pass monitor object)
                if monitor.settings.get('discord_notify', True) and self.webhook:
                    # Add monitor object to data for v4.0 webhook
                    data_with_monitor = {**data, 'monitor': monitor}
                    self._send_stock_alert(data_with_monitor)
                
        # Emit to UI callbacks
        self._emit_event(event_type, data)
        
    def _auto_create_task(self, data: Dict):
        """Automatically create a task when stock is found"""
        try:
            # Create task for this product
            task_data = {
                'url': data['product_url'],  # Fixed: use 'url' not 'product_url'
                'site': data['site'],
                'quantity': 1,
                'monitor_id': data['monitor_id'],  # Link task to monitor for auto-restart
                # No profile needed - uses persistent browser login
            }
            
            # Create task using task manager
            task_id = self.task_manager.create_task(**task_data)
            
            # AUTO-START task immediately (uses persistent login browser)
            # If purchase fails (OOS), monitor will create new task on next restock
            self.task_manager.start_task(task_id)
            
            self._emit_event('auto_task_created', {
                'task_id': task_id,
                'monitor_id': data['monitor_id'],
                'product_name': data['product_name'],
                'product_price': data.get('product_price', 0.0),
                'auto_started': True
            })
            
        except Exception as e:
            print(f"Auto-task creation error: {e}")
            self._emit_event('auto_task_error', {
                'monitor_id': data['monitor_id'],
                'error': str(e)
            })
            
    def _send_stock_alert(self, data: Dict):
        """Send Discord webhook alert for stock found"""
        try:
            # Get monitor object to access v4.0 data
            monitor = data.get('monitor')
            
            if monitor:
                # V4.0: Send rich data notification
                self.webhook.send_v4_monitor_alert({
                    # Basic info
                    'monitor_id': monitor.monitor_id,
                    'product_name': monitor.product_name,
                    'product_price': monitor.product_price,
                    'product_regular_price': getattr(monitor, 'product_regular_price', 0),
                    'product_url': monitor.product_url,
                    'site': monitor.site,
                    'in_stock': monitor.in_stock,
                    'is_preorder': getattr(monitor, 'is_preorder', False),
                    # V4.0 enhanced data
                    'target_price': getattr(monitor, 'target_price', 0),
                    'image_url': getattr(monitor, 'image_url', None),
                    'rating': getattr(monitor, 'rating', None),
                    'review_count': getattr(monitor, 'review_count', 0),
                    'promotions': getattr(monitor, 'promotions', None),
                    'local_stores': getattr(monitor, 'local_stores', None),
                    # Display settings
                    'show_rating': getattr(monitor, 'show_rating', True),
                    'show_promotions': getattr(monitor, 'show_promotions', True),
                    'show_stores': getattr(monitor, 'show_stores', True)
                })
            else:
                # Fallback to v3.1.3 basic alert
                self.webhook.send_monitor_alert({
                    'product_name': data.get('product_name', 'Unknown'),
                    'price': data.get('product_price', 0),
                    'url': data.get('product_url', ''),
                    'site': data.get('site', 'Unknown'),
                    'status': 'in_stock'
                })
        except Exception as e:
            print(f"Webhook error: {e}")
            
    def _emit_event(self, event_type: str, data: Dict):
        """Emit event to all callbacks"""
        for callback in self.callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                print(f"Callback error: {e}")


# Global monitor instance
product_monitor = ProductMonitor()
