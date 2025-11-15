"""
Base Site Class - ENHANCED v4.10.3
Foundation for all site-specific automation
NEW: Better stealth, login-only mode, async/sync separation
"""

from abc import ABC, abstractmethod
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from typing import Dict, Optional
from pathlib import Path
import time


class BaseSite(ABC):
    """Abstract base class for site automation"""
    
    def __init__(self, headless: bool = True, profile_name: str = "default"):
        """
        Initialize base site
        
        Args:
            headless: Run browser in headless mode
            profile_name: Name for persistent browser profile (saves login sessions)
        """
        self.headless = headless
        self.profile_name = profile_name
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        # Enhanced user agent (looks more real)
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Profile directory for persistent sessions
        self.profile_dir = Path.home() / ".autobot" / "profiles" / profile_name
        self.profile_dir.mkdir(parents=True, exist_ok=True)
    
    def start_browser(self, login_only: bool = False):
        """
        Start browser instance with persistent profile
        
        Args:
            login_only: If True, just open browser to homepage (for manual login)
        """
        self.playwright = sync_playwright().start()
        
        # ENHANCED STEALTH - Makes Chrome think it's a regular browser
        launch_args = [
            # Core stealth
            '--disable-blink-features=AutomationControlled',
            
            # Look like a real browser
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            
            # Performance (helps with speed)
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            
            # Avoid detection
            '--disable-infobars',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            
            # Look less automated
            '--window-size=1920,1080',
            '--start-maximized',
        ]
        
        # Launch browser with persistent context
        self.browser = self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=self.headless,
            args=launch_args,
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            
            # Login persistence
            accept_downloads=True,
            bypass_csp=True,
            
            # ENHANCED PERMISSIONS (looks more real)
            permissions=['geolocation', 'notifications'],
            geolocation={'latitude': 39.1653, 'longitude': -86.5264},  # Bloomington, IN
            
            # Ignore HTTPS errors (some sites have cert issues)
            ignore_https_errors=True,
        )
        
        # ENHANCED STEALTH SCRIPTS
        # Make the browser look completely normal
        self.browser.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Mock plugins (empty plugins = bot)
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Mock chrome object (only exists in real Chrome)
            window.chrome = {
                runtime: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock screen properties (makes it look like real monitor)
            Object.defineProperty(screen, 'availWidth', {
                get: () => 1920
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => 1080
            });
        """)
        
        # Get or create first page
        if len(self.browser.pages) > 0:
            self.page = self.browser.pages[0]
        else:
            self.page = self.browser.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(30000)
        
        print(f"[Browser] 🔐 Using profile: {self.profile_name}")
        print(f"[Browser] 📁 Profile location: {self.profile_dir}")
        
        if login_only:
            print(f"[Browser] 🔑 LOGIN MODE - Browser staying open for manual login")
            print(f"[Browser] ℹ️  Navigate to your site and login, then close this window")
            # Go to homepage, not product page
            if hasattr(self, 'base_url'):
                self.page.goto(self.base_url)
                print(f"[Browser] 🌐 Opened {self.base_url}")
            else:
                print(f"[Browser] ⚠️  No base_url set, browser at blank page")
        else:
            print(f"[Browser] ✅ Login sessions will be remembered!")
    
    def stop_browser(self):
        """Stop browser and cleanup (profile is saved automatically)"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        
        print(f"[Browser] 💾 Profile saved! Login will be remembered for next time.")
    
    def navigate(self, url: str, wait_until: str = 'load'):
        """Navigate to URL"""
        self.page.goto(url, wait_until=wait_until)
        time.sleep(1)  # Small delay for stability
    
    def wait_for_selector(self, selector: str, timeout: int = 30000):
        """Wait for element to appear"""
        return self.page.wait_for_selector(selector, timeout=timeout)
    
    def click(self, selector: str):
        """Click an element"""
        self.page.click(selector)
        time.sleep(0.5)
    
    def fill(self, selector: str, value: str):
        """Fill input field"""
        self.page.fill(selector, value)
        time.sleep(0.3)
    
    def get_text(self, selector: str) -> str:
        """Get text content from element"""
        element = self.page.query_selector(selector)
        return element.inner_text() if element else ""
    
    def get_attribute(self, selector: str, attribute: str) -> str:
        """Get attribute from element"""
        element = self.page.query_selector(selector)
        return element.get_attribute(attribute) if element else ""
    
    def screenshot(self, path: str):
        """Take screenshot"""
        self.page.screenshot(path=path)
    
    @abstractmethod
    def extract_product_info(self, url: str) -> Dict:
        """Extract product information from product page"""
        pass
    
    @abstractmethod
    def add_to_cart(self) -> bool:
        """Add product to cart"""
        pass
    
    @abstractmethod
    def fill_shipping_info(self, profile: Dict) -> bool:
        """Fill shipping information"""
        pass
    
    @abstractmethod
    def fill_payment_info(self, profile: Dict) -> bool:
        """Fill payment information"""
        pass
    
    @abstractmethod
    def submit_order(self) -> bool:
        """Submit the order"""
        pass
    
    def checkout(self, url: str, profile: Dict, captcha_queue=None, api_data=None) -> Dict:
        """
        Complete checkout flow
        
        Args:
            url: Product URL
            profile: User profile with shipping/payment info
            captcha_queue: Captcha queue for manual solving
            api_data: Pre-fetched API data (if available from Smart API)
        
        Returns:
            Result dictionary with success status and details
        """
        result = {
            'success': False,
            'message': '',
            'product_info': {},
            'error': None
        }
        
        try:
            print(f"[Checkout] Starting checkout flow for {url}")
            
            # If we have API data, use it
            if api_data and api_data.get('success'):
                print(f"[Checkout] Using pre-fetched API data")
                result['product_info'] = {
                    'name': api_data.get('name', 'Unknown'),
                    'price': api_data.get('price', 0.0),
                    'image': api_data.get('image', ''),
                    'url': url
                }
            
            # Start browser (NOT login_only mode)
            print("[Checkout] Starting browser...")
            self.start_browser(login_only=False)
            
            # Navigate to product
            print("[Checkout] Navigating to product page...")
            self.navigate(url)
            
            # Extract product info (if not from API)
            if not api_data or not api_data.get('success'):
                print("[Checkout] Extracting product info...")
                product_info = self.extract_product_info(url)
                result['product_info'] = product_info
                print(f"[Checkout] Product: {product_info.get('name', 'Unknown')}, Price: ${product_info.get('price', 0)}")
            else:
                print(f"[Checkout] Product: {result['product_info']['name']}, Price: ${result['product_info']['price']}")
            
            # Add to cart
            print("[Checkout] Adding to cart...")
            if not self.add_to_cart():
                result['message'] = 'Failed to add to cart'
                print(f"[Checkout] ✗ {result['message']}")
                print("[Checkout] Waiting 5 seconds to inspect cart page...")
                time.sleep(5)
                return result
            print("[Checkout] ✓ Added to cart")
            
            # Sign in (if site supports it)
            if hasattr(self, 'sign_in'):
                print("[Checkout] Attempting sign in...")
                if not self.sign_in(profile):
                    result['message'] = 'Failed to sign in'
                    print(f"[Checkout] ✗ {result['message']}")
                    input("Press Enter to close browser and continue...")
                    return result
                print("[Checkout] ✓ Signed in")
            
            # Fill shipping
            print("[Checkout] Filling shipping info...")
            if not self.fill_shipping_info(profile):
                result['message'] = 'Failed to fill shipping info'
                print(f"[Checkout] ✗ {result['message']}")
                input("Press Enter to close browser and continue...")
                return result
            print("[Checkout] ✓ Shipping info filled")
            
            # Fill payment
            print("[Checkout] Filling payment info...")
            if not self.fill_payment_info(profile):
                result['message'] = 'Failed to fill payment info'
                print(f"[Checkout] ✗ {result['message']}")
                input("Press Enter to close browser and continue...")
                return result
            print("[Checkout] ✓ Payment info filled")
            
            # Handle captcha if needed
            if self.detect_captcha():
                print("[Checkout] Captcha detected...")
                if captcha_queue:
                    token = captcha_queue.request_captcha(timeout=300)
                    if token:
                        self.solve_captcha(token)
                    else:
                        result['message'] = 'Captcha timeout'
                        print(f"[Checkout] ✗ {result['message']}")
                        input("Press Enter to close browser and continue...")
                        return result
                else:
                    result['message'] = 'Captcha required but no queue available'
                    print(f"[Checkout] ✗ {result['message']}")
                    input("Press Enter to close browser and continue...")
                    return result
            
            # Submit order
            print("[Checkout] Submitting order...")
            if self.submit_order():
                result['success'] = True
                result['message'] = 'Order submitted successfully'
                print("[Checkout] ✓ Order submitted successfully!")
            else:
                result['message'] = 'Failed to submit order'
                print(f"[Checkout] ✗ {result['message']}")
            
        except Exception as e:
            result['error'] = str(e)
            result['message'] = f'Checkout failed: {e}'
            print(f"[Checkout] ✗ Exception: {e}")
            import traceback
            traceback.print_exc()
            # Keep browser open to see the error
            input("Press Enter to close browser and continue...")
        
        finally:
            print("[Checkout] Closing browser...")
            self.stop_browser()
        
        return result
    
    def detect_captcha(self) -> bool:
        """Check if captcha is present"""
        # Override in subclass if needed
        return False
    
    def solve_captcha(self, token: str) -> bool:
        """Solve captcha with token"""
        # Override in subclass if needed
        return False
