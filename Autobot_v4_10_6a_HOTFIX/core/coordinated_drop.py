"""
Coordinated Drop Manager for Autobot v4.2C

Coordinates multiple products in a drop group with:
- Drop group system
- Wait-for-all logic
- Simultaneous stock checking
- Coordinated checkout

Author: Autobot Development Team
Version: 4.2C
"""

import asyncio
import logging
from typing import List, Dict, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from playwright.async_api import Browser

from .multi_product_cart import MultiProductCart, CartItem

logger = logging.getLogger(__name__)


class DropGroupStatus(Enum):
    """Status of drop group"""
    WAITING = "waiting"  # Waiting for products to be in stock
    READY = "ready"  # All products in stock
    ADDING = "adding"  # Adding to cart
    CHECKOUT = "checkout"  # Checking out
    COMPLETE = "complete"  # Successfully completed
    FAILED = "failed"  # Failed


@dataclass
class ProductStatus:
    """Status of a product in the drop group"""
    url: str
    name: Optional[str] = None
    quantity: int = 1
    in_stock: bool = False
    last_checked: Optional[datetime] = None
    stock_detected_at: Optional[datetime] = None
    check_count: int = 0


class CoordinatedDrop:
    """
    Manages coordinated drops for multiple products.
    
    Features:
    - Create drop groups
    - Monitor multiple products simultaneously
    - Wait for all products to be in stock
    - Add all to cart at once
    - Single coordinated checkout
    """
    
    def __init__(
        self,
        group_name: str,
        browser: Browser,
        wait_for_all: bool = True
    ):
        """
        Initialize coordinated drop manager.
        
        Args:
            group_name: Name of the drop group
            browser: Playwright browser instance
            wait_for_all: Wait for all products to be in stock before proceeding
        """
        self.group_name = group_name
        self.browser = browser
        self.wait_for_all = wait_for_all
        self.products: List[ProductStatus] = []
        self.status = DropGroupStatus.WAITING
        self.cart = MultiProductCart(browser)
        self.stock_check_callback: Optional[Callable] = None
        self._lock = asyncio.Lock()
        self.created_at = datetime.now()
        
        logger.info(f"[Coordinated Drop] Created group: {group_name}")
        logger.info(f"[Coordinated Drop] Strategy: {'Wait for all' if wait_for_all else 'First come first serve'}")
    
    def add_product(
        self,
        product_url: str,
        quantity: int = 1,
        product_name: Optional[str] = None
    ):
        """
        Add a product to the drop group.
        
        Args:
            product_url: URL of the product
            quantity: Desired quantity
            product_name: Optional product name
        """
        product = ProductStatus(
            url=product_url,
            name=product_name,
            quantity=quantity
        )
        
        self.products.append(product)
        logger.info(f"[Coordinated Drop] Added product: {product_name or product_url} (x{quantity})")
    
    def set_stock_check_callback(self, callback: Callable):
        """
        Set callback function for checking stock.
        
        Args:
            callback: Async function that takes (url) and returns (in_stock, product_data)
        """
        self.stock_check_callback = callback
    
    async def monitor_until_ready(self, check_interval: float = 2.0) -> bool:
        """
        Monitor all products until they're ready (all in stock or any in stock).
        
        Args:
            check_interval: Seconds between stock checks
            
        Returns:
            bool: True if ready to proceed
        """
        if not self.products:
            logger.warning("[Coordinated Drop] No products in group")
            return False
        
        if not self.stock_check_callback:
            logger.error("[Coordinated Drop] No stock check callback set")
            return False
        
        logger.info(f"[Coordinated Drop] Monitoring {len(self.products)} products...")
        
        while True:
            # Check all products simultaneously
            in_stock_count = await self._check_all_products()
            
            # Log status
            self._log_status()
            
            # Check if ready
            if self.wait_for_all:
                # Need all products in stock
                if in_stock_count == len(self.products):
                    logger.info("[Coordinated Drop] 🎯 ALL PRODUCTS IN STOCK!")
                    self.status = DropGroupStatus.READY
                    return True
            else:
                # Need at least one product in stock
                if in_stock_count > 0:
                    logger.info(f"[Coordinated Drop] ✅ {in_stock_count} products in stock")
                    self.status = DropGroupStatus.READY
                    return True
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def _check_all_products(self) -> int:
        """
        Check stock status of all products simultaneously.
        
        Returns:
            int: Number of products in stock
        """
        # Create tasks for all products
        tasks = [
            self._check_single_product(product)
            for product in self.products
        ]
        
        # Execute all simultaneously
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count in-stock products
        in_stock_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Coordinated Drop] Product {i+1} check failed: {result}")
            elif result:
                in_stock_count += 1
        
        return in_stock_count
    
    async def _check_single_product(self, product: ProductStatus) -> bool:
        """
        Check stock status of a single product.
        
        Args:
            product: ProductStatus to check
            
        Returns:
            bool: True if in stock
        """
        try:
            # Use callback to check stock
            in_stock, product_data = await self.stock_check_callback(product.url)
            
            # Update product status
            product.in_stock = in_stock
            product.last_checked = datetime.now()
            product.check_count += 1
            
            # Track when stock was detected
            if in_stock and not product.stock_detected_at:
                product.stock_detected_at = datetime.now()
                logger.info(
                    f"[Coordinated Drop] ✅ {product.name or 'Product'} IN STOCK!"
                )
            
            # Update name if available
            if product_data and 'name' in product_data:
                product.name = product_data['name']
            
            return in_stock
        
        except Exception as e:
            logger.error(f"[Coordinated Drop] Error checking product: {e}")
            return False
    
    def _log_status(self):
        """Log current status of all products."""
        logger.info("[Coordinated Drop] Status:")
        for i, product in enumerate(self.products, 1):
            status_icon = "✅" if product.in_stock else "❌"
            logger.info(
                f"[Coordinated Drop]   {i}. {status_icon} "
                f"{product.name or 'Unknown'} "
                f"(checked {product.check_count} times)"
            )
    
    async def add_all_to_cart(self) -> Tuple[int, int]:
        """
        Add all in-stock products to cart simultaneously.
        
        Returns:
            tuple: (success_count, total_count)
        """
        if self.status != DropGroupStatus.READY:
            logger.warning("[Coordinated Drop] Not ready to add to cart")
            return 0, 0
        
        self.status = DropGroupStatus.ADDING
        logger.info("[Coordinated Drop] Adding all products to cart...")
        
        # Add products to cart manager
        for product in self.products:
            if not self.wait_for_all or product.in_stock:
                await self.cart.add_product(
                    product_url=product.url,
                    quantity=product.quantity,
                    product_name=product.name
                )
        
        # Add all to cart simultaneously
        success, total = await self.cart.add_all_to_cart()
        
        if success == total:
            logger.info(f"[Coordinated Drop] ✅ All {total} products added to cart")
        else:
            logger.warning(
                f"[Coordinated Drop] ⚠️ Only {success}/{total} products added to cart"
            )
        
        return success, total
    
    async def verify_and_correct(self) -> bool:
        """
        Verify cart contents and auto-correct if needed.
        
        Returns:
            bool: True if cart is correct
        """
        logger.info("[Coordinated Drop] Verifying cart...")
        
        # Verify cart
        all_correct, issues = await self.cart.verify_cart()
        
        if not all_correct:
            logger.warning(f"[Coordinated Drop] Cart issues found: {issues}")
            
            # Try to auto-correct
            corrections = await self.cart.auto_correct_quantities()
            
            if corrections > 0:
                logger.info(f"[Coordinated Drop] Made {corrections} corrections")
                
                # Verify again
                all_correct, issues = await self.cart.verify_cart()
        
        if all_correct:
            logger.info("[Coordinated Drop] ✅ Cart verified")
        else:
            logger.error("[Coordinated Drop] ❌ Cart verification failed")
        
        return all_correct
    
    async def checkout(self) -> bool:
        """
        Proceed to checkout with coordinated group.
        
        Returns:
            bool: True if checkout successful
        """
        self.status = DropGroupStatus.CHECKOUT
        logger.info("[Coordinated Drop] Proceeding to checkout...")
        
        # Checkout all items
        success = await self.cart.checkout_all()
        
        if success:
            self.status = DropGroupStatus.COMPLETE
            logger.info("[Coordinated Drop] 🎉 ORDER PLACED - All products!")
            
            # Log summary
            summary = await self.cart.get_cart_summary()
            logger.info(f"[Coordinated Drop] Summary: {summary}")
        else:
            self.status = DropGroupStatus.FAILED
            logger.error("[Coordinated Drop] ❌ Checkout failed")
        
        return success
    
    async def execute_coordinated_drop(
        self,
        check_interval: float = 2.0
    ) -> bool:
        """
        Execute the full coordinated drop workflow.
        
        Args:
            check_interval: Seconds between stock checks
            
        Returns:
            bool: True if successful
        """
        logger.info(f"[Coordinated Drop] Starting coordinated drop: {self.group_name}")
        
        try:
            # Step 1: Monitor until ready
            ready = await self.monitor_until_ready(check_interval)
            if not ready:
                logger.error("[Coordinated Drop] Failed to get products in stock")
                self.status = DropGroupStatus.FAILED
                return False
            
            # Step 2: Add all to cart
            success, total = await self.add_all_to_cart()
            if success == 0:
                logger.error("[Coordinated Drop] Failed to add any products to cart")
                self.status = DropGroupStatus.FAILED
                return False
            
            # Step 3: Verify and correct
            verified = await self.verify_and_correct()
            if not verified:
                logger.error("[Coordinated Drop] Cart verification failed")
                self.status = DropGroupStatus.FAILED
                return False
            
            # Step 4: Checkout
            checkout_success = await self.checkout()
            
            return checkout_success
        
        except Exception as e:
            logger.error(f"[Coordinated Drop] Error during execution: {e}")
            self.status = DropGroupStatus.FAILED
            return False
    
    def get_status_report(self) -> Dict:
        """
        Get detailed status report of the drop group.
        
        Returns:
            dict: Status report
        """
        in_stock_count = sum(1 for p in self.products if p.in_stock)
        total_products = len(self.products)
        
        return {
            "group_name": self.group_name,
            "status": self.status.value,
            "wait_for_all": self.wait_for_all,
            "total_products": total_products,
            "in_stock_count": in_stock_count,
            "ready": in_stock_count == total_products if self.wait_for_all else in_stock_count > 0,
            "products": [
                {
                    "name": p.name,
                    "url": p.url,
                    "quantity": p.quantity,
                    "in_stock": p.in_stock,
                    "check_count": p.check_count,
                    "stock_detected_at": p.stock_detected_at.isoformat() if p.stock_detected_at else None
                }
                for p in self.products
            ],
            "created_at": self.created_at.isoformat()
        }
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.cart.cleanup()
        logger.info(f"[Coordinated Drop] Cleaned up group: {self.group_name}")


# Example usage
async def example_usage():
    """Example of how to use CoordinatedDrop"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # Create coordinated drop group
        drop = CoordinatedDrop(
            group_name="Holiday Bundle",
            browser=browser,
            wait_for_all=True  # Wait for ALL products
        )
        
        # Add products to group
        drop.add_product(
            "https://example.com/product1",
            quantity=1,
            product_name="Product 1"
        )
        drop.add_product(
            "https://example.com/product2",
            quantity=2,
            product_name="Product 2"
        )
        drop.add_product(
            "https://example.com/product3",
            quantity=1,
            product_name="Product 3"
        )
        
        # Set stock check callback (mock for example)
        async def mock_stock_check(url):
            """Mock stock check - randomly return in stock"""
            import random
            in_stock = random.choice([True, False])
            product_data = {"name": f"Product {url[-1]}"}
            return in_stock, product_data
        
        drop.set_stock_check_callback(mock_stock_check)
        
        # Execute coordinated drop
        success = await drop.execute_coordinated_drop(check_interval=5.0)
        
        if success:
            print("✅ Coordinated drop successful!")
        else:
            print("❌ Coordinated drop failed")
        
        # Get status report
        report = drop.get_status_report()
        print(f"Status report: {report}")
        
        # Cleanup
        await drop.cleanup()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(example_usage())
