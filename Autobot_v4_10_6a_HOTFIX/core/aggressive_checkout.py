"""
Aggressive Checkout Engine - Phase 2B
Never-give-up retry logic for add-to-cart and checkout operations.

Features:
- 100+ add-to-cart retry attempts
- 50+ checkout retry attempts
- Smart error detection and recovery
- Continues even when out-of-stock
- Adaptive retry timing

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Callable, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout


class CheckoutResult(Enum):
    """Checkout attempt results"""
    SUCCESS = "success"
    OUT_OF_STOCK = "out_of_stock"
    ERROR = "error"
    CART_ERROR = "cart_error"
    PAYMENT_ERROR = "payment_error"
    TIMEOUT = "timeout"
    BANNED = "banned"


class AggressiveCheckout:
    """
    Aggressive checkout engine that never gives up.
    
    Philosophy:
    - Try 100+ times to add to cart
    - Try 50+ times to complete checkout
    - Don't stop on OOS - keep monitoring
    - Smart error recovery
    - Adaptive retry timing
    """
    
    def __init__(
        self,
        max_cart_attempts: int = 100,
        max_checkout_attempts: int = 50,
        initial_retry_delay: float = 0.5,
        max_retry_delay: float = 3.0
    ):
        """
        Initialize aggressive checkout.
        
        Args:
            max_cart_attempts: Maximum add-to-cart attempts (default: 100)
            max_checkout_attempts: Maximum checkout attempts (default: 50)
            initial_retry_delay: Starting delay between retries in seconds (default: 0.5)
            max_retry_delay: Maximum delay between retries in seconds (default: 3.0)
        """
        self.max_cart_attempts = max_cart_attempts
        self.max_checkout_attempts = max_checkout_attempts
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        
        # State tracking
        self.cart_attempts = 0
        self.checkout_attempts = 0
        self.errors = []
        self.last_error = None
        self.is_running = False
        self.stop_requested = False
        
    def _get_retry_delay(self, attempt: int) -> float:
        """
        Calculate retry delay with exponential backoff.
        
        Args:
            attempt: Current attempt number
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: 0.5s, 0.75s, 1.0s, 1.5s, 2.0s, 2.5s, 3.0s max
        delay = min(
            self.initial_retry_delay * (1.5 ** (attempt // 10)),
            self.max_retry_delay
        )
        return delay
    
    def _log_error(self, error_type: str, message: str) -> None:
        """Log an error"""
        error = {
            'type': error_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.errors.append(error)
        self.last_error = error
    
    def handle_high_demand_errors(self, page: Page) -> bool:
        """
        Handle common high-demand errors and bottlenecks
        
        Args:
            page: Playwright page object
            
        Returns:
            True if error was handled, False if unrecoverable
        """
        error_patterns = {
            'try again': lambda: self._click_try_again(page),
            'something went wrong': lambda: self._reload_and_retry(page),
            'service unavailable': lambda: self._wait_and_retry(1),
            'rate limit': lambda: self._wait_and_retry(2),
            'too many requests': lambda: self._wait_and_retry(3),
            'temporarily unavailable': lambda: self._wait_and_retry(1),
            'please wait': lambda: self._wait_and_retry(1),
            'high demand': lambda: self._wait_and_retry(2),
            'busy': lambda: self._wait_and_retry(1),
            'queue': lambda: self._handle_queue(page),
        }
        
        try:
            page_text = page.content().lower()
            
            for pattern, handler in error_patterns.items():
                if pattern in page_text:
                    print(f"[Aggressive Checkout] 🔧 Handling: {pattern}")
                    import asyncio
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(handler())
            
            return True  # No errors detected
            
        except Exception as e:
            print(f"[Aggressive Checkout] ⚠️ Error handling failed: {e}")
            return False
    
    async def _click_try_again(self, page: Page) -> bool:
        """Click any 'Try Again' buttons"""
        try_again_selectors = [
            'button:has-text("Try again")',
            'button:has-text("Try Again")',
            'a:has-text("Try again")',
            '[data-test="try-again"]',
            'button:has-text("Retry")'
        ]
        
        for selector in try_again_selectors:
            try:
                button = page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    print("[Aggressive Checkout] Clicked 'Try Again'")
                    await asyncio.sleep(0.5)
                    return True
            except:
                pass
        
        return True
    
    async def _reload_and_retry(self, page: Page) -> bool:
        """Reload page and retry"""
        try:
            print("[Aggressive Checkout] Reloading page...")
            await page.reload()
            await asyncio.sleep(1)
            return True
        except:
            return False
    
    async def _wait_and_retry(self, delay: float = 1.0) -> bool:
        """Wait briefly and continue"""
        print(f"[Aggressive Checkout] Waiting {delay}s before retry...")
        await asyncio.sleep(delay)
        return True
    
    async def _handle_queue(self, page: Page) -> bool:
        """Handle queue/waiting room - stay patient"""
        print("[Aggressive Checkout] In queue/waiting room - staying patient...")
        await asyncio.sleep(5)
        
        # Check if we exited queue
        try:
            current_url = page.url
            if 'queue' not in current_url.lower() and 'wait' not in current_url.lower():
                print("[Aggressive Checkout] ✓ Exited queue!")
        except:
            pass
        
        return True
    
    def verify_not_duplicate_purchase(self, page: Page) -> bool:
        """
        Check if order was already placed to prevent double-purchasing
        
        Args:
            page: Playwright page object
            
        Returns:
            True if safe to continue, False if already purchased
        """
        confirmation_indicators = [
            'text=Thank you',
            'text=Order placed',
            'text=Order confirmed',
            'text=Confirmation',
            'text=Order number',
            'text=Thank you for your order',
            '[data-test="order-confirmation"]',
            '[class*="OrderConfirmation"]',
            'text=Your order has been received'
        ]
        
        for indicator in confirmation_indicators:
            try:
                elem = page.query_selector(indicator)
                if elem and elem.is_visible():
                    print("[Aggressive Checkout] ⚠️ Order confirmation detected - STOPPING!")
                    return False  # Stop - already purchased!
            except:
                pass
        
        return True  # Safe to continue
    
    async def spam_button_until_success(
        self,
        page: Page,
        selectors: list,
        success_check: callable,
        timeout: int = 30,
        check_duplicates: bool = False
    ) -> bool:
        """
        Spam click buttons until success condition is met
        
        Args:
            page: Playwright page object
            selectors: List of button selectors to try
            success_check: Function that returns True when successful
            timeout: Max time to spam (seconds)
            check_duplicates: Whether to check for duplicate purchases
            
        Returns:
            True if successful, False if timeout
        """
        start_time = asyncio.get_event_loop().time()
        click_count = 0
        last_click_time = 0
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            # Duplicate purchase check
            if check_duplicates and not self.verify_not_duplicate_purchase(page):
                return True  # Already done
            
            # Handle errors
            self.handle_high_demand_errors(page)
            
            # Check if success condition met
            try:
                if await success_check():
                    print(f"[Aggressive Checkout] ✓ Success after {click_count} clicks!")
                    return True
            except:
                pass
            
            # Spam buttons (rate limited)
            current_time = asyncio.get_event_loop().time()
            if current_time - last_click_time >= 0.1:  # Max 10 clicks/sec
                for selector in selectors:
                    try:
                        button = page.query_selector(selector)
                        if button and await button.is_visible() and await button.is_enabled():
                            await button.click()
                            click_count += 1
                            last_click_time = current_time
                            
                            if click_count % 10 == 0:
                                print(f"[Aggressive Checkout] Click #{click_count}...")
                            break
                    except:
                        continue
            
            await asyncio.sleep(0.05)
        
        print(f"[Aggressive Checkout] ⏱️ Timed out after {click_count} clicks")
        return False
    
    async def aggressive_add_to_cart(
        self,
        add_to_cart_func: Callable,
        check_stock_func: Optional[Callable] = None
    ) -> tuple[bool, CheckoutResult]:
        """
        Aggressively try to add item to cart with 100+ attempts.
        
        Args:
            add_to_cart_func: Async function that attempts to add to cart
            check_stock_func: Optional function to check if item is in stock
            
        Returns:
            Tuple of (success, result)
        """
        print(f"\n[Aggressive Checkout] 🚀 Starting aggressive add-to-cart")
        print(f"[Aggressive Checkout] Will attempt up to {self.max_cart_attempts} times")
        
        self.cart_attempts = 0
        self.is_running = True
        
        for attempt in range(1, self.max_cart_attempts + 1):
            if self.stop_requested:
                print("[Aggressive Checkout] Stop requested")
                break
            
            self.cart_attempts = attempt
            
            # Progress logging every 10 attempts
            if attempt % 10 == 1:
                print(f"[Aggressive Checkout] 📦 Add-to-cart attempt {attempt}/{self.max_cart_attempts}")
            
            try:
                # Check stock first if function provided
                if check_stock_func:
                    in_stock = await check_stock_func()
                    if not in_stock:
                        if attempt % 10 == 0:
                            print(f"[Aggressive Checkout] ⏳ Out of stock (attempt {attempt})")
                        
                        # Wait before retry
                        await asyncio.sleep(self._get_retry_delay(attempt))
                        continue
                
                # Attempt to add to cart
                result = await add_to_cart_func()
                
                # Check result
                if result == CheckoutResult.SUCCESS:
                    print(f"[Aggressive Checkout] ✅ Added to cart on attempt {attempt}!")
                    self.is_running = False
                    return True, CheckoutResult.SUCCESS
                
                elif result == CheckoutResult.OUT_OF_STOCK:
                    if attempt % 10 == 0:
                        print(f"[Aggressive Checkout] ⏳ OOS - continuing... ({attempt}/{self.max_cart_attempts})")
                    
                elif result == CheckoutResult.BANNED:
                    print(f"[Aggressive Checkout] 🚫 Ban detected on attempt {attempt}")
                    self._log_error("ban", f"Banned on attempt {attempt}")
                    # Wait longer before retry
                    await asyncio.sleep(10)
                    continue
                
                elif result == CheckoutResult.ERROR:
                    if attempt % 10 == 0:
                        print(f"[Aggressive Checkout] ⚠️  Error on attempt {attempt}, retrying...")
                    self._log_error("add_to_cart", f"Error on attempt {attempt}")
                
                # Wait before retry
                await asyncio.sleep(self._get_retry_delay(attempt))
                
            except PlaywrightTimeout:
                if attempt % 10 == 0:
                    print(f"[Aggressive Checkout] ⏱️  Timeout on attempt {attempt}, retrying...")
                self._log_error("timeout", f"Timeout on attempt {attempt}")
                await asyncio.sleep(self._get_retry_delay(attempt))
                
            except Exception as e:
                if attempt % 10 == 0:
                    print(f"[Aggressive Checkout] ❌ Exception on attempt {attempt}: {e}")
                self._log_error("exception", str(e))
                await asyncio.sleep(self._get_retry_delay(attempt))
        
        # Exhausted attempts
        print(f"[Aggressive Checkout] ⚠️  Exhausted {self.max_cart_attempts} add-to-cart attempts")
        self.is_running = False
        return False, CheckoutResult.OUT_OF_STOCK
    
    async def aggressive_checkout(
        self,
        checkout_func: Callable
    ) -> tuple[bool, CheckoutResult]:
        """
        Aggressively try to complete checkout with 50+ attempts.
        
        Args:
            checkout_func: Async function that attempts checkout
            
        Returns:
            Tuple of (success, result)
        """
        print(f"\n[Aggressive Checkout] 💳 Starting aggressive checkout")
        print(f"[Aggressive Checkout] Will attempt up to {self.max_checkout_attempts} times")
        
        self.checkout_attempts = 0
        self.is_running = True
        
        for attempt in range(1, self.max_checkout_attempts + 1):
            if self.stop_requested:
                print("[Aggressive Checkout] Stop requested")
                break
            
            self.checkout_attempts = attempt
            
            # Progress logging every 5 attempts
            if attempt % 5 == 1:
                print(f"[Aggressive Checkout] 💳 Checkout attempt {attempt}/{self.max_checkout_attempts}")
            
            try:
                # Attempt checkout
                result = await checkout_func()
                
                # Check result
                if result == CheckoutResult.SUCCESS:
                    print(f"[Aggressive Checkout] 🎉 Checkout SUCCESS on attempt {attempt}!")
                    print(f"[Aggressive Checkout] 🎊 ORDER PLACED!")
                    self.is_running = False
                    return True, CheckoutResult.SUCCESS
                
                elif result == CheckoutResult.OUT_OF_STOCK:
                    print(f"[Aggressive Checkout] ⏳ Item went OOS during checkout (attempt {attempt})")
                    # Item went OOS during checkout - rare but possible
                    self._log_error("checkout_oos", f"OOS during checkout on attempt {attempt}")
                    await asyncio.sleep(self._get_retry_delay(attempt))
                
                elif result == CheckoutResult.PAYMENT_ERROR:
                    print(f"[Aggressive Checkout] 💳 Payment error on attempt {attempt}, retrying...")
                    self._log_error("payment", f"Payment error on attempt {attempt}")
                    await asyncio.sleep(self._get_retry_delay(attempt))
                
                elif result == CheckoutResult.CART_ERROR:
                    print(f"[Aggressive Checkout] 📦 Cart error on attempt {attempt}, retrying...")
                    self._log_error("cart", f"Cart error on attempt {attempt}")
                    await asyncio.sleep(self._get_retry_delay(attempt))
                
                elif result == CheckoutResult.ERROR:
                    if attempt % 5 == 0:
                        print(f"[Aggressive Checkout] ⚠️  Error on attempt {attempt}, retrying...")
                    self._log_error("checkout", f"Error on attempt {attempt}")
                    await asyncio.sleep(self._get_retry_delay(attempt))
                
            except PlaywrightTimeout:
                print(f"[Aggressive Checkout] ⏱️  Timeout on attempt {attempt}, retrying...")
                self._log_error("timeout", f"Checkout timeout on attempt {attempt}")
                await asyncio.sleep(self._get_retry_delay(attempt))
                
            except Exception as e:
                print(f"[Aggressive Checkout] ❌ Exception on attempt {attempt}: {e}")
                self._log_error("exception", str(e))
                await asyncio.sleep(self._get_retry_delay(attempt))
        
        # Exhausted attempts
        print(f"[Aggressive Checkout] ⚠️  Exhausted {self.max_checkout_attempts} checkout attempts")
        self.is_running = False
        return False, CheckoutResult.ERROR
    
    async def full_aggressive_checkout(
        self,
        add_to_cart_func: Callable,
        checkout_func: Callable,
        check_stock_func: Optional[Callable] = None
    ) -> tuple[bool, CheckoutResult]:
        """
        Complete aggressive checkout flow: add-to-cart + checkout.
        
        Args:
            add_to_cart_func: Add to cart function
            checkout_func: Checkout function
            check_stock_func: Optional stock check function
            
        Returns:
            Tuple of (success, result)
        """
        print("\n" + "="*60)
        print("🚀 STARTING AGGRESSIVE CHECKOUT SEQUENCE")
        print("="*60)
        
        # Step 1: Aggressive add-to-cart
        cart_success, cart_result = await self.aggressive_add_to_cart(
            add_to_cart_func,
            check_stock_func
        )
        
        if not cart_success:
            print("\n[Aggressive Checkout] ❌ Failed to add to cart after all attempts")
            return False, cart_result
        
        # Step 2: Aggressive checkout
        checkout_success, checkout_result = await self.aggressive_checkout(checkout_func)
        
        if checkout_success:
            print("\n" + "="*60)
            print("🎉 AGGRESSIVE CHECKOUT COMPLETE - ORDER PLACED!")
            print(f"   Cart attempts: {self.cart_attempts}")
            print(f"   Checkout attempts: {self.checkout_attempts}")
            print("="*60 + "\n")
            return True, CheckoutResult.SUCCESS
        else:
            print("\n[Aggressive Checkout] ❌ Failed to complete checkout after all attempts")
            return False, checkout_result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get checkout statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            'cart_attempts': self.cart_attempts,
            'checkout_attempts': self.checkout_attempts,
            'total_attempts': self.cart_attempts + self.checkout_attempts,
            'error_count': len(self.errors),
            'last_error': self.last_error,
            'is_running': self.is_running
        }
    
    def reset(self) -> None:
        """Reset state for new checkout attempt"""
        self.cart_attempts = 0
        self.checkout_attempts = 0
        self.errors = []
        self.last_error = None
        self.is_running = False
        self.stop_requested = False
    
    def stop(self) -> None:
        """Request stop"""
        print("[Aggressive Checkout] Stop requested")
        self.stop_requested = True


# Example usage
if __name__ == "__main__":
    async def test_aggressive_checkout():
        """Test aggressive checkout"""
        checkout = AggressiveCheckout(
            max_cart_attempts=10,  # Reduced for testing
            max_checkout_attempts=5
        )
        
        # Mock functions
        attempt_count = {'add': 0, 'checkout': 0}
        
        async def mock_add_to_cart():
            attempt_count['add'] += 1
            # Simulate failure for first 5 attempts
            if attempt_count['add'] < 5:
                return CheckoutResult.OUT_OF_STOCK
            return CheckoutResult.SUCCESS
        
        async def mock_checkout():
            attempt_count['checkout'] += 1
            # Simulate success on second attempt
            if attempt_count['checkout'] < 2:
                return CheckoutResult.ERROR
            return CheckoutResult.SUCCESS
        
        # Test
        success, result = await checkout.full_aggressive_checkout(
            add_to_cart_func=mock_add_to_cart,
            checkout_func=mock_checkout
        )
        
        print(f"\nTest Result: {'SUCCESS' if success else 'FAILED'}")
        print(f"Stats: {checkout.get_stats()}")
    
    # Run test
    print("Testing Aggressive Checkout Engine...")
    asyncio.run(test_aggressive_checkout())
