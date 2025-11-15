"""
Target.com HIGH-DEMAND Checkout Flow
Implements the exact flow from user's video demonstration

FLOW:
1. Navigate to product page
2. Add to cart (detect high demand if not added in 1 sec)
3. Side banner → Click "View cart and check out"
4. Cart page → Verify quantity → Click "Checkout"
5. Payment page → Select payment
6. SPAM "Place your order" until confirmed
7. Handle all errors between steps
"""

from .base_site import BaseSite
from typing import Dict
import time


class TargetSite(BaseSite):
    """Target.com with complete high-demand checkout flow"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.site_name = "Target"
        self.base_url = "https://www.target.com"
        self.high_demand_detected = False
        
    def extract_product_info(self, url: str) -> Dict:
        """Extract product information from Target product page"""
        try:
            self.wait_for_selector('[data-test="product-title"]', timeout=10000)
            
            name = self.get_text('[data-test="product-title"]')
            price_text = self.get_text('[data-test="product-price"]')
            
            price = 0.0
            if price_text:
                price_cleaned = price_text.replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_cleaned)
                except:
                    pass
            
            image_url = self.get_attribute('img[data-test="product-image"]', 'src')
            
            return {
                'name': name,
                'price': price,
                'image': image_url,
                'url': url
            }
        except Exception as e:
            return {
                'name': 'Unknown',
                'price': 0.0,
                'image': '',
                'url': url,
                'error': str(e)
            }
    
    def add_to_cart(self) -> bool:
        """
        Step 1: Add to cart with high-demand detection
        
        Logic:
        - Click add to cart
        - Wait 1 second
        - Check if item in cart
        - If NOT in cart → HIGH DEMAND MODE (spam clicks)
        - Continue until item appears in cart
        """
        print("[Target] 🛒 Step 1: Adding to cart...")
        
        add_to_cart_selectors = [
            '[data-test="orderPickupButton"]',
            '[data-test="shippingButton"]',
            'button:has-text("Add to cart")',
            'button:has-text("Ship it")',
            'button:has-text("Add to bag")',
        ]
        
        start_time = time.time()
        click_count = 0
        max_time = 60  # 60 seconds max
        
        # First attempt - single click
        print("[Target] First click...")
        clicked = False
        for selector in add_to_cart_selectors:
            try:
                button = self.page.query_selector(selector)
                if button and button.is_visible() and button.is_enabled():
                    button.click()
                    clicked = True
                    click_count += 1
                    break
            except:
                continue
        
        if not clicked:
            print("[Target] ❌ No add-to-cart button found!")
            return False
        
        # Wait 1 second to see if it adds
        time.sleep(1)
        
        # Check if item is in cart
        if self._is_item_in_cart():
            print(f"[Target] ✅ Added to cart on first click!")
            return True
        
        # NOT in cart after 1 second = HIGH DEMAND MODE
        print("[Target] ⚡ HIGH DEMAND DETECTED - Entering spam mode!")
        self.high_demand_detected = True
        
        # SPAM MODE: Click rapidly until item appears in cart
        while time.time() - start_time < max_time:
            # Handle errors
            self._handle_target_errors()
            
            # Spam all add-to-cart buttons
            for selector in add_to_cart_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        button.click()
                        click_count += 1
                        
                        if click_count % 20 == 0:
                            print(f"[Target] Spam click #{click_count}...")
                        
                        # Quick check after every few clicks
                        if click_count % 5 == 0:
                            if self._is_item_in_cart():
                                print(f"[Target] ✅ Item added after {click_count} clicks!")
                                return True
                        
                        time.sleep(0.05)  # 50ms between clicks
                except:
                    continue
            
            # Brief check
            time.sleep(0.1)
        
        # Timeout - final check
        if self._is_item_in_cart():
            print(f"[Target] ✅ Item in cart after timeout check")
            return True
        
        print(f"[Target] ❌ Failed to add to cart after {click_count} clicks")
        return False
    
    def _is_item_in_cart(self) -> bool:
        """Check if item is in cart (cart badge or side banner)"""
        # Method 1: Check cart badge
        try:
            cart_badge = self.page.query_selector('[data-test="cart-count"], [class*="CartBadge"]')
            if cart_badge:
                count_text = cart_badge.inner_text().strip()
                if count_text and count_text != '0':
                    return True
        except:
            pass
        
        # Method 2: Check for side banner
        try:
            side_banner_selectors = [
                '[data-test="add-to-cart-modal"]',
                'text=Added to cart',
                'text=View cart',
                '[class*="AddToCartModal"]',
            ]
            for selector in side_banner_selectors:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    return True
        except:
            pass
        
        return False
    
    def _handle_target_errors(self):
        """Handle Target-specific high-demand errors"""
        try:
            page_content = self.page.content().lower()
            
            # "Try Again" buttons
            if 'try again' in page_content or 'retry' in page_content:
                try:
                    retry_btn = self.page.query_selector('button:has-text("Try again"), button:has-text("Retry")')
                    if retry_btn and retry_btn.is_visible():
                        retry_btn.click()
                        print("[Target] 🔧 Clicked 'Try Again'")
                        time.sleep(0.5)
                except:
                    pass
            
            # High demand messages
            if any(x in page_content for x in ['high demand', 'experiencing high traffic', 'busy']):
                time.sleep(1)
            
            # Rate limiting
            if 'rate limit' in page_content or 'too many requests' in page_content:
                time.sleep(2)
        except:
            pass
    
    def checkout(self, profile: Dict) -> bool:
        """
        Complete checkout flow after item is in cart
        
        Steps:
        2. Click "View cart and check out" (side banner)
        3. Verify quantity in cart
        4. Click "Checkout" button
        5. Select payment
        6. SPAM "Place your order" (if high demand)
        """
        try:
            # Step 2: Click "View cart and check out" from side banner
            if not self._go_to_cart_from_banner():
                # If no banner, go to cart directly
                self._go_to_cart_direct()
            
            time.sleep(1)
            
            # Step 3: Verify we're in cart and check quantity
            if not self._verify_cart_quantity():
                print("[Target] ❌ Cart verification failed!")
                return False
            
            # Step 4: Click "Checkout" button
            if not self._click_checkout_from_cart():
                print("[Target] ❌ Failed to click checkout!")
                return False
            
            time.sleep(2)
            
            # Step 5: Handle payment selection
            if not self._select_payment():
                print("[Target] ⚠️ Payment selection issue (continuing)")
            
            time.sleep(1)
            
            # Step 6: SPAM "Place your order" button
            if self.high_demand_detected:
                print("[Target] ⚡ HIGH DEMAND - Spamming place order!")
                return self._spam_place_order()
            else:
                print("[Target] Normal demand - Single place order click")
                return self._place_order_once()
            
        except Exception as e:
            print(f"[Target] ❌ Checkout error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _go_to_cart_from_banner(self) -> bool:
        """Step 2: Click 'View cart and check out' from side banner"""
        print("[Target] 📋 Step 2: Looking for side banner...")
        
        banner_selectors = [
            'button:has-text("View cart and check out")',
            'a:has-text("View cart and check out")',
            'button:has-text("View cart")',
            'a:has-text("View cart")',
            '[data-test="add-to-cart-modal"] button:has-text("View")',
            '[data-test="add-to-cart-modal"] a:has-text("View")',
        ]
        
        for selector in banner_selectors:
            try:
                button = self.page.query_selector(selector)
                if button and button.is_visible():
                    button.click()
                    print("[Target] ✓ Clicked 'View cart' from banner")
                    return True
            except:
                continue
        
        print("[Target] No side banner found, going to cart directly")
        return False
    
    def _go_to_cart_direct(self):
        """Navigate to cart directly if no banner"""
        print("[Target] Going to cart URL...")
        self.page.goto(f"{self.base_url}/cart")
        time.sleep(2)
    
    def _verify_cart_quantity(self) -> bool:
        """Step 3: Verify item is in cart with correct quantity"""
        print("[Target] 📦 Step 3: Verifying cart quantity...")
        
        try:
            # Wait for cart to load
            self.page.wait_for_selector('[data-test="cart-item"], [class*="CartItem"]', timeout=5000)
            
            # Check for items
            cart_items = self.page.query_selector_all('[data-test="cart-item"], [class*="CartItem"]')
            
            if len(cart_items) > 0:
                print(f"[Target] ✓ Cart has {len(cart_items)} item(s)")
                
                # Check quantity (should be 1 for single item)
                try:
                    qty_selector = 'select[data-test="quantity-selector"], input[type="number"]'
                    qty_element = self.page.query_selector(qty_selector)
                    if qty_element:
                        qty = qty_element.evaluate('el => el.value')
                        print(f"[Target] Quantity: {qty}")
                        
                        if int(qty) != 1:
                            print(f"[Target] ⚠️ WARNING: Quantity is {qty}, not 1!")
                except:
                    print("[Target] Could not verify quantity")
                
                return True
            else:
                print("[Target] ❌ No items in cart!")
                return False
                
        except Exception as e:
            print(f"[Target] Cart verification error: {e}")
            return False
    
    def _click_checkout_from_cart(self) -> bool:
        """Step 4: Click 'Checkout' button from cart page"""
        print("[Target] 💳 Step 4: Clicking checkout...")
        
        checkout_selectors = [
            'button[data-test="checkout-button"]',
            'button:has-text("Checkout")',
            'a:has-text("Checkout")',
            '[data-test="cart-summary"] button',
            'button:has-text("Go to checkout")',
        ]
        
        for selector in checkout_selectors:
            try:
                button = self.page.query_selector(selector)
                if button and button.is_visible() and button.is_enabled():
                    button.click()
                    print("[Target] ✓ Clicked checkout button")
                    return True
            except:
                continue
        
        print("[Target] ❌ Could not find checkout button!")
        return False
    
    def _select_payment(self) -> bool:
        """Step 5: Select payment method if needed"""
        print("[Target] 💳 Step 5: Checking payment...")
        
        try:
            # Wait a moment for page to load
            time.sleep(1)
            
            # Check if payment is already selected
            selected_payment = self.page.query_selector('[data-test="payment-method"][class*="selected"], input[name="payment"]:checked')
            
            if selected_payment:
                print("[Target] ✓ Payment already selected")
                return True
            
            # Try to select first payment method
            payment_selectors = [
                '[data-test="payment-method"]:first-of-type',
                'input[name="payment"]:first-of-type',
                '[data-test="credit-card-option"]',
            ]
            
            for selector in payment_selectors:
                try:
                    payment = self.page.query_selector(selector)
                    if payment:
                        payment.click()
                        print("[Target] ✓ Selected payment method")
                        return True
                except:
                    continue
            
            print("[Target] Could not select payment (may already be selected)")
            return True  # Continue anyway
            
        except Exception as e:
            print(f"[Target] Payment selection error: {e}")
            return True  # Continue anyway
    
    def _place_order_once(self) -> bool:
        """Step 6a: Place order with single click (normal demand)"""
        print("[Target] 📦 Placing order...")
        
        place_order_selectors = [
            'button[data-test="placeOrderButton"]',
            'button:has-text("Place your order")',
            'button:has-text("Place order")',
            'button:has-text("Submit order")',
        ]
        
        for selector in place_order_selectors:
            try:
                button = self.page.query_selector(selector)
                if button and button.is_visible() and button.is_enabled():
                    button.click()
                    print("[Target] ✓ Clicked 'Place your order'")
                    
                    # Wait for confirmation
                    time.sleep(3)
                    
                    if self._check_order_confirmation():
                        print("[Target] 🎉 ORDER CONFIRMED!")
                        return True
                    
                    break
            except:
                continue
        
        return False
    
    def _spam_place_order(self) -> bool:
        """Step 6b: SPAM place order button (high demand mode)"""
        print("[Target] ⚡ SPAMMING 'Place your order' button!")
        
        place_order_selectors = [
            'button[data-test="placeOrderButton"]',
            'button:has-text("Place your order")',
            'button:has-text("Place order")',
            'button:has-text("Submit order")',
        ]
        
        start_time = time.time()
        click_count = 0
        max_time = 60  # 60 seconds max
        
        while time.time() - start_time < max_time:
            # Handle errors
            self._handle_target_errors()
            
            # Check if order already placed (prevent duplicates)
            if self._check_order_confirmation():
                print(f"[Target] 🎉 ORDER CONFIRMED after {click_count} clicks!")
                return True
            
            # Spam all place order buttons
            for selector in place_order_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        button.click()
                        click_count += 1
                        
                        if click_count % 20 == 0:
                            print(f"[Target] Place order click #{click_count}...")
                        
                        time.sleep(0.1)  # 100ms between clicks
                except:
                    continue
            
            # Check every few clicks
            if click_count % 10 == 0:
                if self._check_order_confirmation():
                    print(f"[Target] 🎉 ORDER CONFIRMED after {click_count} clicks!")
                    return True
            
            time.sleep(0.2)
        
        # Final check
        if self._check_order_confirmation():
            print(f"[Target] 🎉 ORDER CONFIRMED!")
            return True
        
        print(f"[Target] ❌ Failed to place order after {click_count} clicks")
        return False
    
    def _check_order_confirmation(self) -> bool:
        """Check if order was successfully placed"""
        confirmation_indicators = [
            'text=Thank you',
            'text=Order placed',
            'text=Order confirmed',
            'text=Order number',
            'text=Confirmation',
            '[data-test="order-confirmation"]',
            '[class*="OrderConfirmation"]',
        ]
        
        for indicator in confirmation_indicators:
            try:
                element = self.page.query_selector(indicator)
                if element and element.is_visible():
                    return True
            except:
                continue
        
        # Check URL
        try:
            if 'confirmation' in self.page.url.lower() or 'order-complete' in self.page.url.lower():
                return True
        except:
            pass
        
        return False
    
    def sign_in(self, profile: Dict) -> bool:
        """Sign in to Target account"""
        try:
            print("[Target] Signing in...")
            
            # Check if already signed in
            try:
                self.page.wait_for_selector('[data-test="account-button"], [data-test="@web/AccountLink"]', timeout=3000)
                print("[Target] Already signed in!")
                return True
            except:
                pass
            
            # Go to account page
            self.page.goto("https://www.target.com/account")
            time.sleep(2)
            
            # Click sign in
            sign_in_selectors = [
                'button:has-text("Sign in")',
                'a:has-text("Sign in")',
                '[data-test="sign-in-button"]'
            ]
            
            for selector in sign_in_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        button.click()
                        break
                except:
                    continue
            
            time.sleep(1)
            
            # Enter credentials
            email = profile.get('email', profile.get('username', ''))
            password = profile.get('password', '')
            
            if not email or not password:
                print("[Target] ❌ No credentials provided!")
                return False
            
            # Fill email
            email_selectors = ['input[type="email"]', 'input[name="username"]', '#username']
            for selector in email_selectors:
                try:
                    self.page.fill(selector, email)
                    break
                except:
                    continue
            
            # Fill password
            password_selectors = ['input[type="password"]', 'input[name="password"]', '#password']
            for selector in password_selectors:
                try:
                    self.page.fill(selector, password)
                    break
                except:
                    continue
            
            # Click sign in
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign in")',
                '[data-test="sign-in-submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button and button.is_visible():
                        button.click()
                        break
                except:
                    continue
            
            time.sleep(3)
            
            # Verify sign in
            try:
                self.page.wait_for_selector('[data-test="account-button"]', timeout=5000)
                print("[Target] ✓ Sign in successful!")
                return True
            except:
                print("[Target] ⚠️ Could not verify sign in")
                return False
            
        except Exception as e:
            print(f"[Target] Sign in error: {e}")
            return False
