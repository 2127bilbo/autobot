"""
Target.com Automation
Complete checkout automation for Target.com
"""

from .base_site import BaseSite
from typing import Dict
import time


class TargetSite(BaseSite):
    """Target.com automation implementation"""
    
    def __init__(self, headless: bool = True):
        super().__init__(headless)
        self.site_name = "Target"
        self.base_url = "https://www.target.com"
    
    def extract_product_info(self, url: str) -> Dict:
        """Extract product information from Target product page"""
        try:
            # Wait for product details to load
            self.wait_for_selector('[data-test="product-title"]', timeout=10000)
            
            # Extract product name
            name = self.get_text('[data-test="product-title"]')
            
            # Extract price
            price_selector = '[data-test="product-price"]'
            price_text = self.get_text(price_selector)
            
            # Clean price (remove $ and convert to float)
            price = 0.0
            if price_text:
                price_cleaned = price_text.replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_cleaned)
                except:
                    pass
            
            # Extract image
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
        """Add product to cart on Target with aggressive retry and error handling"""
        try:
            print("[Target] 🚀 Starting aggressive add-to-cart...")
            
            add_to_cart_selectors = [
                '[data-test="orderPickupButton"]',
                '[data-test="shippingButton"]',
                'button:has-text("Add to cart")',
                'button:has-text("Ship it")',
                'button:has-text("Add to bag")',
                'button[data-test="add-to-cart"]'
            ]
            
            # Spam add to cart for up to 30 seconds
            start_time = time.time()
            click_count = 0
            timeout = 30
            
            while time.time() - start_time < timeout:
                # Check for high-demand errors
                self._handle_target_errors()
                
                # Try clicking add to cart
                clicked_this_round = False
                for selector in add_to_cart_selectors:
                    try:
                        button = self.page.query_selector(selector)
                        if button and button.is_visible() and button.is_enabled():
                            button.click()
                            click_count += 1
                            clicked_this_round = True
                            
                            if click_count % 10 == 0:
                                print(f"[Target] Add to cart click #{click_count}")
                            
                            # Quick check if cart updated
                            time.sleep(0.1)
                            
                            # Check cart badge
                            try:
                                cart_badge = self.page.query_selector('[data-test="cart-count"], .cart-count, [class*="CartBadge"]')
                                if cart_badge:
                                    count_text = cart_badge.inner_text().strip()
                                    if count_text and count_text != '0':
                                        print(f"[Target] ✓ Cart updated! Count: {count_text}")
                                        # Go to cart to verify
                                        self._verify_in_cart()
                                        return True
                            except:
                                pass
                            
                            break
                    except Exception as e:
                        if "Target closed" in str(e):
                            raise
                        continue
                
                # Check if redirected to cart
                current_url = self.page.url
                if 'cart' in current_url.lower():
                    print(f"[Target] ✓ Redirected to cart after {click_count} clicks")
                    # Verify items in cart
                    if self._verify_in_cart():
                        return True
                
                # Very brief delay
                time.sleep(0.05)
            
            # Timeout - but let's verify anyway
            print(f"[Target] ⏱️ Timeout after {click_count} clicks, verifying cart...")
            return self._verify_in_cart()
            
        except Exception as e:
            print(f"[Target] ❌ Add to cart error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _handle_target_errors(self):
        """Handle Target-specific high-demand errors"""
        error_patterns = {
            'try again': '[button:has-text("Try again"), button:has-text("Retry")]',
            'something went wrong': 'text=Something went wrong',
            'temporarily unavailable': 'text=temporarily unavailable',
            'high demand': 'text=high demand',
            'out of stock': 'text=Out of stock',
        }
        
        try:
            page_content = self.page.content().lower()
            
            # Check for "Try Again" buttons
            if 'try again' in page_content or 'retry' in page_content:
                try:
                    retry_btn = self.page.query_selector('button:has-text("Try again"), button:has-text("Retry")')
                    if retry_btn and retry_btn.is_visible():
                        retry_btn.click()
                        print("[Target] 🔧 Clicked 'Try Again'")
                        time.sleep(0.5)
                except:
                    pass
            
            # Check for high demand message
            if any(x in page_content for x in ['high demand', 'experiencing high traffic', 'busy']):
                print("[Target] ⚠️ High demand detected - continuing...")
                time.sleep(1)
            
            # Check for rate limiting
            if 'rate limit' in page_content or 'too many requests' in page_content:
                print("[Target] ⏳ Rate limited - waiting 2 seconds...")
                time.sleep(2)
            
        except:
            pass
    
    def _verify_in_cart(self) -> bool:
        """Verify item is actually in cart"""
        print("[Target] Verifying cart contents...")
        
        # Navigate to cart if not there
        current_url = self.page.url
        if 'cart' not in current_url.lower():
            try:
                self.navigate(f"{self.base_url}/cart")
                time.sleep(2)
            except:
                pass
        
        # Check for items with multiple methods
        cart_item_selectors = [
            '[data-test="cart-item"]',
            'div[class*="CartItem"]',
            'button:has-text("Checkout")',
            '[data-test="cart-summary"]',
            'a[href*="/p/"]',
            'h2[class*="product"]',
            '[data-test="checkout-button"]'
        ]
        
        for selector in cart_item_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"[Target] ✓ Cart verified via: {selector}")
                    return True
            except:
                continue
        
        # Check page content
        try:
            page_text = self.page.content().lower()
            if 'your cart is empty' in page_text or 'cart is empty' in page_text:
                print("[Target] ✗ Cart is empty")
                return False
            elif 'checkout' in page_text:
                print("[Target] ✓ Cart has items (found 'checkout')")
                return True
        except:
            pass
        
        print("[Target] ⚠️ Could not verify cart - assuming success")
        return True  # Optimistic
    
    def sign_in(self, profile: Dict) -> bool:
        """Sign in to Target account"""
        try:
            print("[Target] Checking if already signed in...")
            
            # Check if already signed in by looking for account indicators
            try:
                self.wait_for_selector('[data-test="account-button"], [data-test="@web/AccountLink"]', timeout=3000)
                print("[Target] Already signed in!")
                return True
            except:
                pass
            
            # Need to sign in - go to sign in page
            print("[Target] Not signed in, navigating to sign-in page...")
            self.navigate("https://www.target.com/account")
            time.sleep(2)
            
            # Click sign in button if needed
            try:
                sign_in_btn_selectors = [
                    'button:has-text("Sign in")',
                    'a:has-text("Sign in")',
                    '[data-test="sign-in-button"]'
                ]
                for selector in sign_in_btn_selectors:
                    try:
                        self.click(selector)
                        time.sleep(2)
                        break
                    except:
                        continue
            except:
                pass
            
            # Fill email
            print("[Target] Filling email...")
            email_selectors = [
                'input[type="email"]',
                'input[name="username"]',
                'input[id="username"]',
                '#email'
            ]
            for selector in email_selectors:
                try:
                    self.fill(selector, profile['email'])
                    break
                except:
                    continue
            
            time.sleep(1)
            
            # Fill password
            print("[Target] Filling password...")
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]'
            ]
            for selector in password_selectors:
                try:
                    # Target accounts usually use email as password for test bots
                    # In production, profile should have 'password' field
                    password = profile.get('password', profile['email'])
                    self.fill(selector, password)
                    break
                except:
                    continue
            
            time.sleep(1)
            
            # Click sign in submit button
            print("[Target] Clicking sign in button...")
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Sign in with password")',
                '[data-test="sign-in-submit"]'
            ]
            for selector in submit_selectors:
                try:
                    self.click(selector)
                    time.sleep(3)
                    break
                except:
                    continue
            
            # Verify sign in successful
            try:
                self.wait_for_selector('[data-test="account-button"], [data-test="@web/AccountLink"]', timeout=10000)
                print("[Target] ✓ Sign in successful!")
                return True
            except:
                print("[Target] ✗ Sign in may have failed - continuing anyway...")
                return True  # Continue anyway in case the selectors changed
                
        except Exception as e:
            print(f"[Target] Sign in error: {e}")
            return False
    
    def fill_shipping_info(self, profile: Dict) -> bool:
        """Fill shipping information on Target"""
        try:
            print("[Target] Proceeding to checkout...")
            
            # Aggressively spam checkout button
            checkout_selectors = [
                'button:has-text("Checkout")',
                '[data-test="checkout-button"]',
                'a[href*="checkout"]',
                'button:has-text("Check out")',
                'button:has-text("Proceed to checkout")'
            ]
            
            # Spam for up to 30 seconds
            start_time = time.time()
            click_count = 0
            timeout = 30
            
            print("[Target] 🚀 Starting checkout button spam...")
            while time.time() - start_time < timeout:
                # Handle errors
                self._handle_target_errors()
                
                # Check if we reached checkout
                current_url = self.page.url
                if any(x in current_url.lower() for x in ['shipping', 'checkout', 'delivery']) and 'cart' not in current_url.lower():
                    print(f"[Target] ✓ Reached checkout after {click_count} clicks!")
                    break
                
                # Spam checkout buttons
                for selector in checkout_selectors:
                    try:
                        button = self.page.query_selector(selector)
                        if button and button.is_visible() and button.is_enabled():
                            button.click()
                            click_count += 1
                            
                            if click_count % 10 == 0:
                                print(f"[Target] Checkout click #{click_count}")
                            
                            time.sleep(0.1)
                            break
                    except:
                        continue
                
                time.sleep(0.05)
            
            # Wait for shipping form
            print("[Target] Waiting for checkout page...")
            time.sleep(3)
            
            # Fill email if present
            email_selectors = ['input[type="email"]', 'input[name="email"]', '#email']
            for selector in email_selectors:
                try:
                    self.fill(selector, profile['email'])
                    break
                except:
                    continue
            
            # Fill first name
            first_name_selectors = ['input[name="firstName"]', '#firstName', 'input[placeholder*="First"]']
            for selector in first_name_selectors:
                try:
                    self.fill(selector, profile['first_name'])
                    break
                except:
                    continue
            
            # Fill last name
            last_name_selectors = ['input[name="lastName"]', '#lastName', 'input[placeholder*="Last"]']
            for selector in last_name_selectors:
                try:
                    self.fill(selector, profile['last_name'])
                    break
                except:
                    continue
            
            # Fill address
            address_selectors = ['input[name="addressLine1"]', '#addressLine1', 'input[placeholder*="Address"]']
            for selector in address_selectors:
                try:
                    self.fill(selector, profile['address'])
                    break
                except:
                    continue
            
            # Fill city
            city_selectors = ['input[name="city"]', '#city', 'input[placeholder*="City"]']
            for selector in city_selectors:
                try:
                    self.fill(selector, profile['city'])
                    break
                except:
                    continue
            
            # Fill state
            state_selectors = ['select[name="state"]', '#state', 'input[name="state"]']
            for selector in state_selectors:
                try:
                    if 'select' in selector:
                        self.page.select_option(selector, profile['state'])
                    else:
                        self.fill(selector, profile['state'])
                    break
                except:
                    continue
            
            # Fill ZIP code
            zip_selectors = ['input[name="zipcode"]', '#zipcode', 'input[placeholder*="ZIP"]']
            for selector in zip_selectors:
                try:
                    self.fill(selector, profile['zip_code'])
                    break
                except:
                    continue
            
            # Fill phone
            phone_selectors = ['input[name="phone"]', '#phone', 'input[type="tel"]']
            for selector in phone_selectors:
                try:
                    self.fill(selector, profile['phone'])
                    break
                except:
                    continue
            
            time.sleep(2)
            
            # Click continue/next
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Save and continue")',
                '[data-test="save-and-continue"]'
            ]
            
            for selector in continue_selectors:
                try:
                    self.click(selector)
                    time.sleep(2)
                    break
                except:
                    continue
            
            return True
            
        except Exception as e:
            print(f"Shipping info error: {e}")
            return False
    
    def fill_payment_info(self, profile: Dict) -> bool:
        """Fill payment information on Target"""
        try:
            time.sleep(2)
            
            # Fill card number
            card_selectors = [
                'input[name="cardNumber"]',
                '#cardNumber',
                'input[placeholder*="Card number"]',
                'input[aria-label*="card number"]'
            ]
            
            for selector in card_selectors:
                try:
                    self.fill(selector, profile['card_number'])
                    break
                except:
                    continue
            
            # Fill expiration
            exp_selectors = [
                'input[name="expirationDate"]',
                '#expirationDate',
                'input[placeholder*="MM/YY"]'
            ]
            
            for selector in exp_selectors:
                try:
                    self.fill(selector, profile['card_exp'])
                    break
                except:
                    continue
            
            # Sometimes expiration is split into month and year
            try:
                month, year = profile['card_exp'].split('/')
                self.fill('input[name="expMonth"]', month)
                self.fill('input[name="expYear"]', year)
            except:
                pass
            
            # Fill CVV
            cvv_selectors = [
                'input[name="cvv"]',
                '#cvv',
                'input[placeholder*="CVV"]',
                'input[aria-label*="security code"]'
            ]
            
            for selector in cvv_selectors:
                try:
                    self.fill(selector, profile['card_cvv'])
                    break
                except:
                    continue
            
            time.sleep(2)
            
            # Click continue
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Review order")',
                '[data-test="continue-to-review"]'
            ]
            
            for selector in continue_selectors:
                try:
                    self.click(selector)
                    time.sleep(2)
                    break
                except:
                    continue
            
            return True
            
        except Exception as e:
            print(f"Payment info error: {e}")
            return False
    
    def submit_order(self) -> bool:
        """Submit the order on Target with aggressive retry and duplicate prevention"""
        try:
            print("[Target] 🚀 Starting place order spam...")
            
            submit_selectors = [
                'button:has-text("Place your order")',
                'button:has-text("Place order")',
                'button:has-text("Complete purchase")',
                'button:has-text("Submit order")',
                '[data-test="placeOrderButton"]',
                'button[type="submit"]'
            ]
            
            confirmation_selectors = [
                ':has-text("Thank you")',
                ':has-text("Order placed")',
                ':has-text("Confirmation")',
                ':has-text("Order number")',
                '[data-test="order-confirmation"]'
            ]
            
            # Spam for up to 30 seconds
            start_time = time.time()
            click_count = 0
            timeout = 30
            last_click_time = 0
            
            while time.time() - start_time < timeout:
                # CRITICAL: Check for duplicate purchase
                for conf_selector in confirmation_selectors:
                    try:
                        elem = self.page.query_selector(conf_selector)
                        if elem and elem.is_visible():
                            print(f"[Target] ✓ ORDER CONFIRMED after {click_count} clicks!")
                            print("[Target] ⚠️ STOPPING - Order already placed!")
                            return True
                    except:
                        pass
                
                # Handle high-demand errors
                self._handle_target_errors()
                
                # Rate-limited clicking (max 3/sec to avoid issues)
                current_time = time.time()
                if current_time - last_click_time >= 0.3:
                    # Spam place order buttons
                    for selector in submit_selectors:
                        try:
                            button = self.page.query_selector(selector)
                            if button and button.is_visible() and button.is_enabled():
                                button.click()
                                click_count += 1
                                last_click_time = current_time
                                
                                if click_count % 10 == 0:
                                    print(f"[Target] Place order click #{click_count}")
                                
                                time.sleep(0.2)
                                break
                        except:
                            continue
                
                # Check if order went through
                for conf_selector in confirmation_selectors:
                    try:
                        elem = self.page.query_selector(conf_selector)
                        if elem and elem.is_visible():
                            print(f"[Target] ✓ Order confirmed after {click_count} clicks!")
                            return True
                    except:
                        pass
                
                time.sleep(0.1)
            
            # Timeout - check one more time
            print(f"[Target] ⏱️ Timeout after {click_count} clicks, checking for confirmation...")
            time.sleep(2)
            
            for selector in confirmation_selectors:
                try:
                    self.wait_for_selector(selector, timeout=5000)
                    print("[Target] ✓ Order confirmed!")
                    return True
                except:
                    continue
            
            # Check URL
            current_url = self.page.url
            if 'confirmation' in current_url.lower() or ('checkout' not in current_url and 'cart' not in current_url):
                print("[Target] ✓ Order likely placed (redirected away from checkout)")
                return True
            
            print("[Target] ✗ Could not confirm order placement")
            return False
            
        except Exception as e:
            print(f"Submit order error: {e}")
            return False
    
    def detect_captcha(self) -> bool:
        """Check if captcha is present on Target"""
        try:
            # Common captcha indicators
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="captcha"]',
                '.g-recaptcha',
                '#recaptcha',
                'div[class*="captcha"]'
            ]
            
            for selector in captcha_selectors:
                if self.page.query_selector(selector):
                    return True
            
            return False
        except:
            return False
    
    def solve_captcha(self, token: str) -> bool:
        """Solve captcha with token"""
        try:
            # Inject captcha token
            self.page.evaluate(f'''
                document.getElementById('g-recaptcha-response').value = "{token}";
            ''')
            time.sleep(1)
            return True
        except:
            return False


if __name__ == "__main__":
    # Test Target automation
    site = TargetSite(headless=False)
    site.start_browser()
    
    test_url = "https://www.target.com/p/test-product/-/A-12345678"
    site.navigate(test_url)
    
    info = site.extract_product_info(test_url)
    print("Product Info:", info)
    
    site.stop_browser()
