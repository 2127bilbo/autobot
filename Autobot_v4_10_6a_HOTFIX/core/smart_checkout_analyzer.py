"""
Smart Checkout Analyzer - Phase 2B
Automatically learns checkout flows by observing network traffic and user interactions.

Similar to Phase 1C API learning, but focused on checkout processes:
- Captures add-to-cart requests
- Learns checkout button selectors
- Identifies form fields
- Detects success indicators

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, Route, Request, Response


class CheckoutPattern:
    """Represents a learned checkout flow pattern"""
    
    def __init__(self):
        self.add_to_cart = {
            'selector': None,
            'api_endpoint': None,
            'method': 'POST',
            'payload': {}
        }
        self.checkout_button = {
            'selector': None,
            'url': None
        }
        self.form_fields = []
        self.success_indicators = []
        self.cart_api = None
        self.checkout_api = None
        
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage"""
        return {
            'add_to_cart': self.add_to_cart,
            'checkout_button': self.checkout_button,
            'form_fields': self.form_fields,
            'success_indicators': self.success_indicators,
            'cart_api': self.cart_api,
            'checkout_api': self.checkout_api
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CheckoutPattern':
        """Create from dictionary"""
        pattern = cls()
        pattern.add_to_cart = data.get('add_to_cart', pattern.add_to_cart)
        pattern.checkout_button = data.get('checkout_button', pattern.checkout_button)
        pattern.form_fields = data.get('form_fields', [])
        pattern.success_indicators = data.get('success_indicators', [])
        pattern.cart_api = data.get('cart_api')
        pattern.checkout_api = data.get('checkout_api')
        return pattern


class SmartCheckoutAnalyzer:
    """
    Learns checkout flows by monitoring network traffic and interactions.
    
    Learning Process:
    1. Intercept all network requests during checkout
    2. Identify add-to-cart endpoints
    3. Capture checkout API calls
    4. Learn form field names
    5. Detect success indicators
    """
    
    def __init__(self):
        self.captured_requests = []
        self.captured_responses = []
        self.interactions = []
        self.learned_pattern = None
        self.is_learning = False
        
    async def start_learning(self, page: Page) -> None:
        """
        Start learning mode - intercept all traffic.
        
        Args:
            page: Playwright page to monitor
        """
        self.is_learning = True
        self.captured_requests = []
        self.captured_responses = []
        self.interactions = []
        
        print("[Checkout Analyzer] Starting learning mode...")
        print("[Checkout Analyzer] Monitoring network traffic and interactions...")
        
        # Intercept requests
        async def handle_request(route: Route, request: Request) -> None:
            """Capture and analyze requests"""
            try:
                # Store request info
                request_data = {
                    'url': request.url,
                    'method': request.method,
                    'headers': request.headers,
                    'post_data': request.post_data,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Check if this looks like an add-to-cart or checkout request
                if self._is_cart_request(request):
                    print(f"[Checkout Analyzer] 📦 Detected cart request: {request.method} {request.url}")
                    request_data['type'] = 'cart'
                elif self._is_checkout_request(request):
                    print(f"[Checkout Analyzer] 💳 Detected checkout request: {request.method} {request.url}")
                    request_data['type'] = 'checkout'
                
                self.captured_requests.append(request_data)
                
                # Continue the request
                await route.continue_()
                
            except Exception as e:
                print(f"[Checkout Analyzer] Error handling request: {e}")
                await route.continue_()
        
        # Intercept responses
        async def handle_response(response: Response) -> None:
            """Capture and analyze responses"""
            try:
                # Only capture JSON responses
                if 'application/json' in response.headers.get('content-type', ''):
                    try:
                        body = await response.json()
                        
                        response_data = {
                            'url': response.url,
                            'status': response.status,
                            'body': body,
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Check if this is a cart or checkout response
                        if self._is_cart_request_url(response.url):
                            response_data['type'] = 'cart'
                            print(f"[Checkout Analyzer] 📦 Cart response received")
                        elif self._is_checkout_request_url(response.url):
                            response_data['type'] = 'checkout'
                            print(f"[Checkout Analyzer] 💳 Checkout response received")
                        
                        self.captured_responses.append(response_data)
                        
                    except:
                        # Not JSON or error parsing
                        pass
                        
            except Exception as e:
                print(f"[Checkout Analyzer] Error handling response: {e}")
        
        # Set up interception
        await page.route('**/*', handle_request)
        page.on('response', handle_response)
        
        print("[Checkout Analyzer] ✅ Learning mode active")
    
    def _is_cart_request(self, request: Request) -> bool:
        """Check if request is related to cart operations"""
        url = request.url.lower()
        method = request.method.upper()
        
        # Common cart patterns
        cart_patterns = [
            'cart', 'basket', 'bag', 'addtocart', 'add-to-cart',
            'add_to_cart', 'atc', 'additem'
        ]
        
        # Check URL
        if any(pattern in url for pattern in cart_patterns):
            # POST requests are usually add-to-cart
            if method == 'POST':
                return True
        
        return False
    
    def _is_cart_request_url(self, url: str) -> bool:
        """Check if URL is related to cart"""
        url = url.lower()
        cart_patterns = ['cart', 'basket', 'bag', 'addtocart']
        return any(pattern in url for pattern in cart_patterns)
    
    def _is_checkout_request(self, request: Request) -> bool:
        """Check if request is related to checkout"""
        url = request.url.lower()
        method = request.method.upper()
        
        # Common checkout patterns
        checkout_patterns = [
            'checkout', 'payment', 'placeorder', 'place-order',
            'submitorder', 'purchase', 'buy'
        ]
        
        # Check URL
        if any(pattern in url for pattern in checkout_patterns):
            if method in ['POST', 'PUT']:
                return True
        
        return False
    
    def _is_checkout_request_url(self, url: str) -> bool:
        """Check if URL is related to checkout"""
        url = url.lower()
        checkout_patterns = ['checkout', 'payment', 'placeorder', 'purchase']
        return any(pattern in url for pattern in checkout_patterns)
    
    async def analyze_captured_data(self) -> CheckoutPattern:
        """
        Analyze captured network traffic to learn checkout pattern.
        
        Returns:
            Learned checkout pattern
        """
        print("\n[Checkout Analyzer] Analyzing captured data...")
        pattern = CheckoutPattern()
        
        # Analyze cart requests
        cart_requests = [r for r in self.captured_requests if r.get('type') == 'cart']
        if cart_requests:
            # Use the most recent cart request
            latest_cart = cart_requests[-1]
            pattern.cart_api = latest_cart['url']
            pattern.add_to_cart['api_endpoint'] = latest_cart['url']
            pattern.add_to_cart['method'] = latest_cart['method']
            
            # Try to parse payload
            if latest_cart.get('post_data'):
                try:
                    payload = json.loads(latest_cart['post_data'])
                    pattern.add_to_cart['payload'] = payload
                except:
                    pass
            
            print(f"[Checkout Analyzer] ✅ Learned cart API: {pattern.cart_api}")
        
        # Analyze checkout requests
        checkout_requests = [r for r in self.captured_requests if r.get('type') == 'checkout']
        if checkout_requests:
            latest_checkout = checkout_requests[-1]
            pattern.checkout_api = latest_checkout['url']
            pattern.checkout_button['url'] = latest_checkout['url']
            
            print(f"[Checkout Analyzer] ✅ Learned checkout API: {pattern.checkout_api}")
        
        # Analyze responses for success indicators
        for response in self.captured_responses:
            if response.get('type') in ['cart', 'checkout']:
                body = response.get('body', {})
                
                # Look for success indicators
                if isinstance(body, dict):
                    # Common success fields
                    if body.get('success') == True:
                        pattern.success_indicators.append({'field': 'success', 'value': True})
                    if 'orderId' in body or 'order_id' in body:
                        pattern.success_indicators.append({'field': 'orderId', 'exists': True})
                    if 'confirmationNumber' in body:
                        pattern.success_indicators.append({'field': 'confirmationNumber', 'exists': True})
        
        if pattern.success_indicators:
            print(f"[Checkout Analyzer] ✅ Found {len(pattern.success_indicators)} success indicators")
        
        self.learned_pattern = pattern
        return pattern
    
    async def learn_from_page(self, page: Page, simulate_checkout: bool = False) -> CheckoutPattern:
        """
        Learn checkout flow by observing a page.
        
        Args:
            page: Playwright page
            simulate_checkout: If True, will try to simulate checkout (testing only)
            
        Returns:
            Learned checkout pattern
        """
        # Start learning
        await self.start_learning(page)
        
        # If simulating, wait for user to perform checkout
        if simulate_checkout:
            print("[Checkout Analyzer] Waiting for checkout actions...")
            print("[Checkout Analyzer] Please add item to cart and proceed to checkout")
            
            # Wait for some time to capture traffic
            # In real use, this would be triggered by actual user actions
            import asyncio
            await asyncio.sleep(5)
        
        # Analyze what we captured
        pattern = await self.analyze_captured_data()
        
        # Stop learning
        self.is_learning = False
        print("[Checkout Analyzer] Learning complete!")
        
        return pattern
    
    def save_pattern(self, db_path: str, site_url: str, pattern: CheckoutPattern) -> None:
        """
        Save learned pattern to database.
        
        Args:
            db_path: Path to database
            site_url: URL of the site
            pattern: Learned pattern
        """
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if we already have a pattern for this site
            cursor.execute("""
                SELECT id FROM learned_checkout_patterns 
                WHERE site_url = ?
            """, (site_url,))
            
            existing = cursor.fetchone()
            
            pattern_json = json.dumps(pattern.to_dict())
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE learned_checkout_patterns 
                    SET pattern = ?,
                        last_validated = ?,
                        success_count = success_count + 1
                    WHERE site_url = ?
                """, (pattern_json, now, site_url))
                print(f"[Checkout Analyzer] Updated pattern for {site_url}")
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO learned_checkout_patterns 
                    (site_url, pattern, learned_at, last_validated, success_count, failure_count)
                    VALUES (?, ?, ?, ?, 0, 0)
                """, (site_url, pattern_json, now, now))
                print(f"[Checkout Analyzer] Saved new pattern for {site_url}")
            
            conn.commit()
            
        except Exception as e:
            print(f"[Checkout Analyzer] Error saving pattern: {e}")
            conn.rollback()
        
        finally:
            conn.close()
    
    def load_pattern(self, db_path: str, site_url: str) -> Optional[CheckoutPattern]:
        """
        Load learned pattern from database.
        
        Args:
            db_path: Path to database
            site_url: URL of the site
            
        Returns:
            Learned pattern or None if not found
        """
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT pattern FROM learned_checkout_patterns 
                WHERE site_url = ?
            """, (site_url,))
            
            row = cursor.fetchone()
            
            if row:
                pattern_data = json.loads(row[0])
                pattern = CheckoutPattern.from_dict(pattern_data)
                print(f"[Checkout Analyzer] Loaded pattern for {site_url}")
                return pattern
            else:
                print(f"[Checkout Analyzer] No pattern found for {site_url}")
                return None
                
        except Exception as e:
            print(f"[Checkout Analyzer] Error loading pattern: {e}")
            return None
        
        finally:
            conn.close()
    
    async def validate_pattern(self, page: Page, pattern: CheckoutPattern) -> bool:
        """
        Validate that a learned pattern still works.
        
        Args:
            page: Playwright page
            pattern: Pattern to validate
            
        Returns:
            True if pattern is still valid
        """
        print("[Checkout Analyzer] Validating pattern...")
        
        # Check if cart API endpoint is still accessible
        if pattern.cart_api:
            try:
                response = await page.request.get(pattern.cart_api.split('?')[0])
                if response.status < 500:  # Any response except server error means endpoint exists
                    print("[Checkout Analyzer] ✅ Cart API endpoint valid")
                    return True
            except:
                pass
        
        print("[Checkout Analyzer] ⚠️  Pattern may need re-learning")
        return False


# Example usage
if __name__ == "__main__":
    print("Smart Checkout Analyzer - Phase 2B")
    print("This module learns checkout flows automatically by observing network traffic.")
    print("\nUsage:")
    print("  analyzer = SmartCheckoutAnalyzer()")
    print("  pattern = await analyzer.learn_from_page(page)")
    print("  analyzer.save_pattern('autobot.db', 'https://example.com', pattern)")
