"""
Session Warmer - Phase 2B
Prepares browser sessions before drops to enable instant checkout.

Features:
- Cookie preparation and warming
- Cart pre-population
- Session validation
- Pre-authentication
- Connection warming

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from playwright.async_api import Page, BrowserContext, Cookie


class SessionWarmingResult:
    """Result from session warming"""
    
    def __init__(
        self,
        success: bool,
        cookies_ready: bool = False,
        cart_ready: bool = False,
        session_valid: bool = False,
        errors: List[str] = None
    ):
        self.success = success
        self.cookies_ready = cookies_ready
        self.cart_ready = cart_ready
        self.session_valid = session_valid
        self.errors = errors or []
        self.warmed_at = datetime.now()
        
    def __repr__(self) -> str:
        if self.success:
            return f"SessionWarmingResult(SUCCESS - Cookies: {self.cookies_ready}, Cart: {self.cart_ready}, Valid: {self.session_valid})"
        else:
            return f"SessionWarmingResult(FAILED - Errors: {len(self.errors)})"
    
    def is_ready_for_checkout(self) -> bool:
        """Check if session is ready for immediate checkout"""
        return self.cookies_ready and self.session_valid


class SessionWarmer:
    """
    Warms up browser sessions before drops.
    
    Benefits:
    - Cookies are already loaded
    - Session is authenticated
    - Cart may be pre-populated
    - Connections are warm
    - Ready for instant checkout
    """
    
    def __init__(self):
        self.last_warming = None
        self.warm_sessions = {}  # site_url -> warming result
        self.warming_in_progress = set()
        
    async def warm_cookies(
        self,
        context: BrowserContext,
        site_url: str,
        stored_cookies: Optional[List[Dict]] = None
    ) -> bool:
        """
        Warm up cookies for a site.
        
        Args:
            context: Browser context
            site_url: Site URL
            stored_cookies: Optional pre-stored cookies to load
            
        Returns:
            True if cookies are ready
        """
        print(f"[Session Warmer] 🍪 Warming cookies for {site_url}")
        
        try:
            # If we have stored cookies, load them
            if stored_cookies:
                print(f"[Session Warmer] Loading {len(stored_cookies)} stored cookies...")
                
                # Convert stored cookies to Playwright format if needed
                playwright_cookies = []
                for cookie in stored_cookies:
                    playwright_cookie = {
                        'name': cookie.get('name'),
                        'value': cookie.get('value'),
                        'domain': cookie.get('domain', site_url),
                        'path': cookie.get('path', '/'),
                        'expires': cookie.get('expires', -1),
                        'httpOnly': cookie.get('httpOnly', False),
                        'secure': cookie.get('secure', False),
                        'sameSite': cookie.get('sameSite', 'Lax')
                    }
                    playwright_cookies.append(playwright_cookie)
                
                await context.add_cookies(playwright_cookies)
                print(f"[Session Warmer] ✅ Loaded stored cookies")
            
            # Visit the site to activate cookies
            page = await context.new_page()
            print(f"[Session Warmer] Visiting {site_url} to activate cookies...")
            
            try:
                await page.goto(site_url, wait_until='domcontentloaded', timeout=10000)
                print(f"[Session Warmer] ✅ Site visited, cookies activated")
                
                # Get fresh cookies
                fresh_cookies = await context.cookies()
                print(f"[Session Warmer] ✅ {len(fresh_cookies)} cookies now active")
                
                return True
                
            finally:
                await page.close()
                
        except Exception as e:
            print(f"[Session Warmer] ❌ Cookie warming failed: {e}")
            return False
    
    async def pre_populate_cart(
        self,
        page: Page,
        product_url: str,
        add_to_cart_func: Optional[callable] = None
    ) -> bool:
        """
        Pre-populate cart with the product before drop.
        
        Args:
            page: Playwright page
            product_url: Product URL
            add_to_cart_func: Optional custom add-to-cart function
            
        Returns:
            True if cart is pre-populated
        """
        print(f"[Session Warmer] 🛒 Pre-populating cart...")
        
        try:
            # Navigate to product page
            print(f"[Session Warmer] Navigating to product...")
            await page.goto(product_url, wait_until='domcontentloaded', timeout=15000)
            
            # If custom function provided, use it
            if add_to_cart_func:
                print(f"[Session Warmer] Using custom add-to-cart function...")
                success = await add_to_cart_func(page)
                
                if success:
                    print(f"[Session Warmer] ✅ Cart pre-populated via custom function")
                    return True
                else:
                    print(f"[Session Warmer] ⚠️  Custom add-to-cart failed")
                    return False
            
            # Otherwise, try to find and click add-to-cart button
            print(f"[Session Warmer] Looking for add-to-cart button...")
            
            # Common add-to-cart button selectors
            selectors = [
                'button[data-test="add-to-cart"]',
                'button[id*="add-to-cart"]',
                'button[class*="add-to-cart"]',
                'button:has-text("Add to Cart")',
                'button:has-text("Add to Bag")',
                '[data-automation*="add-to-cart"]',
                '#add-to-cart-button',
                '.add-to-cart-button'
            ]
            
            for selector in selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=1000):
                        print(f"[Session Warmer] Found button: {selector}")
                        await button.click()
                        
                        # Wait a moment for cart to update
                        await asyncio.sleep(1)
                        
                        print(f"[Session Warmer] ✅ Cart pre-populated")
                        return True
                        
                except:
                    continue
            
            print(f"[Session Warmer] ⚠️  Could not find add-to-cart button")
            print(f"[Session Warmer] ℹ️  Cart pre-population optional - can still checkout")
            return False
            
        except Exception as e:
            print(f"[Session Warmer] ⚠️  Cart pre-population failed: {e}")
            print(f"[Session Warmer] ℹ️  Will add to cart during drop instead")
            return False
    
    async def validate_session(
        self,
        page: Page,
        site_url: str,
        validation_checks: Optional[List[callable]] = None
    ) -> bool:
        """
        Validate that the session is ready for checkout.
        
        Args:
            page: Playwright page
            site_url: Site URL
            validation_checks: Optional list of validation functions
            
        Returns:
            True if session is valid
        """
        print(f"[Session Warmer] 🔍 Validating session...")
        
        try:
            # Basic check: can we reach the site?
            try:
                await page.goto(site_url, wait_until='domcontentloaded', timeout=10000)
                print(f"[Session Warmer] ✅ Site is reachable")
            except:
                print(f"[Session Warmer] ❌ Cannot reach site")
                return False
            
            # Check if we have cookies
            context = page.context
            cookies = await context.cookies()
            
            if len(cookies) == 0:
                print(f"[Session Warmer] ⚠️  No cookies found")
                return False
            
            print(f"[Session Warmer] ✅ {len(cookies)} cookies present")
            
            # Run custom validation checks if provided
            if validation_checks:
                print(f"[Session Warmer] Running {len(validation_checks)} custom validation checks...")
                
                for i, check_func in enumerate(validation_checks, 1):
                    try:
                        result = await check_func(page)
                        if not result:
                            print(f"[Session Warmer] ❌ Validation check {i} failed")
                            return False
                        print(f"[Session Warmer] ✅ Validation check {i} passed")
                    except Exception as e:
                        print(f"[Session Warmer] ❌ Validation check {i} error: {e}")
                        return False
            
            print(f"[Session Warmer] ✅ Session validated")
            return True
            
        except Exception as e:
            print(f"[Session Warmer] ❌ Session validation failed: {e}")
            return False
    
    async def warm_session(
        self,
        context: BrowserContext,
        site_url: str,
        product_url: Optional[str] = None,
        stored_cookies: Optional[List[Dict]] = None,
        pre_populate_cart: bool = False,
        add_to_cart_func: Optional[callable] = None,
        validation_checks: Optional[List[callable]] = None
    ) -> SessionWarmingResult:
        """
        Complete session warming process.
        
        Args:
            context: Browser context
            site_url: Site URL
            product_url: Optional product URL for cart pre-population
            stored_cookies: Optional stored cookies to load
            pre_populate_cart: Whether to pre-populate cart
            add_to_cart_func: Optional custom add-to-cart function
            validation_checks: Optional validation functions
            
        Returns:
            SessionWarmingResult with status
        """
        print("\n" + "="*60)
        print("🔥 STARTING SESSION WARMING")
        print("="*60)
        print(f"[Session Warmer] Target: {site_url}")
        print(f"[Session Warmer] Pre-populate cart: {pre_populate_cart}")
        
        # Check if already warming this site
        if site_url in self.warming_in_progress:
            print(f"[Session Warmer] ⚠️  Already warming {site_url}")
            return SessionWarmingResult(success=False, errors=["Already warming"])
        
        self.warming_in_progress.add(site_url)
        errors = []
        
        try:
            # Step 1: Warm cookies
            cookies_ready = await self.warm_cookies(context, site_url, stored_cookies)
            
            if not cookies_ready:
                errors.append("Cookie warming failed")
            
            # Step 2: Pre-populate cart (optional)
            cart_ready = False
            if pre_populate_cart and product_url:
                page = await context.new_page()
                try:
                    cart_ready = await self.pre_populate_cart(
                        page,
                        product_url,
                        add_to_cart_func
                    )
                finally:
                    await page.close()
            
            # Step 3: Validate session
            page = await context.new_page()
            try:
                session_valid = await self.validate_session(
                    page,
                    site_url,
                    validation_checks
                )
            finally:
                await page.close()
            
            if not session_valid:
                errors.append("Session validation failed")
            
            # Create result
            success = cookies_ready and session_valid
            result = SessionWarmingResult(
                success=success,
                cookies_ready=cookies_ready,
                cart_ready=cart_ready,
                session_valid=session_valid,
                errors=errors
            )
            
            # Store result
            self.warm_sessions[site_url] = result
            self.last_warming = datetime.now()
            
            if success:
                print("\n" + "="*60)
                print("✅ SESSION WARMING COMPLETE")
                print(f"   Cookies: {'✅' if cookies_ready else '❌'}")
                print(f"   Cart: {'✅' if cart_ready else 'N/A'}")
                print(f"   Valid: {'✅' if session_valid else '❌'}")
                print("="*60 + "\n")
            else:
                print("\n" + "="*60)
                print("⚠️  SESSION WARMING PARTIAL")
                print(f"   Errors: {', '.join(errors)}")
                print("="*60 + "\n")
            
            return result
            
        except Exception as e:
            print(f"\n[Session Warmer] ❌ Session warming error: {e}")
            errors.append(str(e))
            return SessionWarmingResult(success=False, errors=errors)
            
        finally:
            self.warming_in_progress.discard(site_url)
    
    def is_session_warm(self, site_url: str, max_age_minutes: int = 30) -> bool:
        """
        Check if a session is already warm and still valid.
        
        Args:
            site_url: Site URL
            max_age_minutes: Maximum age of warming in minutes
            
        Returns:
            True if session is warm and valid
        """
        if site_url not in self.warm_sessions:
            return False
        
        result = self.warm_sessions[site_url]
        
        # Check age
        age = datetime.now() - result.warmed_at
        if age > timedelta(minutes=max_age_minutes):
            print(f"[Session Warmer] ⚠️  Session for {site_url} is too old ({age.seconds // 60} min)")
            return False
        
        return result.is_ready_for_checkout()
    
    async def refresh_if_needed(
        self,
        context: BrowserContext,
        site_url: str,
        max_age_minutes: int = 30,
        **warming_kwargs
    ) -> SessionWarmingResult:
        """
        Refresh session warming if needed.
        
        Args:
            context: Browser context
            site_url: Site URL
            max_age_minutes: Maximum age before refresh
            **warming_kwargs: Additional warming arguments
            
        Returns:
            SessionWarmingResult
        """
        if self.is_session_warm(site_url, max_age_minutes):
            print(f"[Session Warmer] ✅ Session for {site_url} is still warm")
            return self.warm_sessions[site_url]
        
        print(f"[Session Warmer] 🔄 Refreshing session for {site_url}")
        return await self.warm_session(context, site_url, **warming_kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get warming statistics"""
        total_warmed = len(self.warm_sessions)
        successful = sum(1 for r in self.warm_sessions.values() if r.success)
        
        return {
            'total_warmed': total_warmed,
            'successful': successful,
            'in_progress': len(self.warming_in_progress),
            'last_warming': self.last_warming.isoformat() if self.last_warming else None
        }


# Example usage
if __name__ == "__main__":
    async def test_session_warmer():
        """Test session warmer"""
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            warmer = SessionWarmer()
            
            # Test warming
            result = await warmer.warm_session(
                context=context,
                site_url="https://example.com",
                pre_populate_cart=False
            )
            
            print(f"\nResult: {result}")
            print(f"Ready for checkout: {result.is_ready_for_checkout()}")
            print(f"\nStats: {warmer.get_stats()}")
            
            await browser.close()
    
    print("Testing Session Warmer...")
    asyncio.run(test_session_warmer())
