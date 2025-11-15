"""
Autobot Checkout Flows
Shared checkout logic across sites
"""

from typing import Dict, Optional
from playwright.async_api import Page


class CheckoutFlow:
    """
    Base checkout flow that can be extended for different sites
    """
    
    def __init__(self, page: Page, profile: Dict):
        self.page = page
        self.profile = profile
    
    async def fill_shipping(self):
        """
        Fill shipping information
        Should be overridden by site-specific implementations
        """
        raise NotImplementedError("Subclasses must implement fill_shipping")
    
    async def fill_payment(self):
        """
        Fill payment information
        Should be overridden by site-specific implementations
        """
        raise NotImplementedError("Subclasses must implement fill_payment")
    
    async def submit_order(self):
        """
        Submit the order
        Should be overridden by site-specific implementations
        """
        raise NotImplementedError("Subclasses must implement submit_order")
    
    async def verify_success(self) -> bool:
        """
        Verify order was placed successfully
        Should be overridden by site-specific implementations
        """
        raise NotImplementedError("Subclasses must implement verify_success")


class TargetCheckoutFlow(CheckoutFlow):
    """
    Target-specific checkout implementation
    Currently implemented in sites/target.py
    """
    pass
