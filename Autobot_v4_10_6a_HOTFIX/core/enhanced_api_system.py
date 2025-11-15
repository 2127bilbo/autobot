"""
Autobot 2.0 - Enhanced API System
Dramatically improved API reliability with intelligent retries and validation

KEY IMPROVEMENTS over v1:
1. Multiple API discovery strategies (not just one attempt)
2. Exponential backoff retry logic
3. Endpoint health tracking and rotation
4. Pattern validation before use
5. Session-level endpoint caching
6. Only falls back to HTML after exhausting ALL API options
"""

import requests
import time
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json


@dataclass
class APIEndpoint:
    """Tracked API endpoint with health metrics"""
    url_template: str
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def is_healthy(self) -> bool:
        """Check if endpoint is considered healthy"""
        # Unhealthy if 5+ consecutive failures
        if self.consecutive_failures >= 5:
            return False
        # Unhealthy if success rate < 20% after 10+ attempts
        if (self.success_count + self.failure_count) >= 10 and self.success_rate < 0.2:
            return False
        return True

    def record_success(self, response_time: float):
        """Record successful request"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.consecutive_failures = 0

        # Update rolling average response time
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.7) + (response_time * 0.3)

    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.consecutive_failures += 1


class EnhancedTargetAPI:
    """
    Enhanced Target API handler with intelligent retry and fallback

    Features:
    - Multiple endpoint discovery
    - Exponential backoff retries
    - Endpoint health tracking
    - Automatic rotation
    - Pattern validation
    """

    def __init__(self, db_manager=None):
        self.db_manager = db_manager

        # Endpoint pool with health tracking
        self.endpoints: Dict[str, APIEndpoint] = {}

        # Initialize known Target API endpoints
        self._init_target_endpoints()

        # Request configuration
        self.max_retries = 3
        self.base_backoff = 0.5  # seconds
        self.timeout = 10

        # Session-level cache
        self.working_endpoint = None  # Cache last working endpoint
        self.cache_duration = timedelta(minutes=5)
        self.cache_timestamp = None

    def _init_target_endpoints(self):
        """Initialize known Target API endpoint templates"""
        # Primary endpoints (most reliable based on research)
        primary_endpoints = [
            "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=9f36aeafbe60771e321a7cc95a78140772ab3e96&tcin={tcin}&store_id=3991",
            "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=ff457966e64d5e877fdbad070f276d18ecec4a01&tcin={tcin}&store_id=3991",
            "https://redsky.target.com/redsky_aggregations/v1/web/pdp_client_v1?key=eb2551e4accc14f38cc42d32fbc2b2ea&tcin={tcin}&store_id=3991",
        ]

        # Alternative endpoints (fallback)
        alternative_endpoints = [
            "https://redsky.target.com/v3/pdp/tcin/{tcin}?store_id=3991",
            "https://redsky.target.com/v2/pdp/tcin/{tcin}?store_id=3991",
            "https://api.target.com/products/v3/{tcin}?store_id=3991",
        ]

        # Add all endpoints to pool
        for url_template in primary_endpoints + alternative_endpoints:
            endpoint_key = self._get_endpoint_key(url_template)
            self.endpoints[endpoint_key] = APIEndpoint(url_template=url_template)

    def _get_endpoint_key(self, url_template: str) -> str:
        """Generate unique key for endpoint"""
        # Extract pattern from URL (without params)
        base = url_template.split('?')[0]
        return base

    def check_stock(self, tcin: str, product_url: str) -> Optional[Dict]:
        """
        Check stock using enhanced API with intelligent retry

        Process:
        1. Try cached working endpoint first
        2. Try all healthy endpoints with retries
        3. Try unhealthy endpoints as last resort
        4. Return None only if ALL endpoints exhausted

        Args:
            tcin: Target product ID
            product_url: Product page URL

        Returns:
            Dict with product data or None if all APIs failed
        """
        print(f"[Enhanced API] Starting stock check for TCIN: {tcin}")

        # Strategy 1: Try cached working endpoint first (if recent)
        if self._has_valid_cache():
            result = self._try_endpoint_with_retry(self.working_endpoint, tcin)
            if result:
                print(f"[Enhanced API] ✓ Cached endpoint worked!")
                return result
            else:
                print(f"[Enhanced API] Cached endpoint failed, trying others...")
                self.working_endpoint = None  # Invalidate cache

        # Strategy 2: Try all healthy endpoints (sorted by success rate)
        healthy_endpoints = [
            (key, ep) for key, ep in self.endpoints.items()
            if ep.is_healthy
        ]

        # Sort by success rate (best first)
        healthy_endpoints.sort(key=lambda x: x[1].success_rate, reverse=True)

        print(f"[Enhanced API] Trying {len(healthy_endpoints)} healthy endpoints...")

        for key, endpoint in healthy_endpoints:
            result = self._try_endpoint_with_retry(endpoint, tcin)
            if result:
                # Cache this working endpoint
                self.working_endpoint = endpoint
                self.cache_timestamp = datetime.now()
                print(f"[Enhanced API] ✓ Found working endpoint! Caching for future use.")
                return result

        # Strategy 3: Try unhealthy endpoints as last resort
        unhealthy_endpoints = [
            (key, ep) for key, ep in self.endpoints.items()
            if not ep.is_healthy
        ]

        if unhealthy_endpoints:
            print(f"[Enhanced API] All healthy endpoints failed. Trying {len(unhealthy_endpoints)} unhealthy endpoints...")

            for key, endpoint in unhealthy_endpoints:
                result = self._try_endpoint_with_retry(endpoint, tcin, max_retries=1)
                if result:
                    # Endpoint recovered!
                    self.working_endpoint = endpoint
                    self.cache_timestamp = datetime.now()
                    print(f"[Enhanced API] ✓ Unhealthy endpoint recovered!")
                    return result

        # All endpoints exhausted
        print(f"[Enhanced API] ❌ All API endpoints failed ({len(self.endpoints)} tried)")
        return None

    def _has_valid_cache(self) -> bool:
        """Check if cached endpoint is still valid"""
        if not self.working_endpoint or not self.cache_timestamp:
            return False

        age = datetime.now() - self.cache_timestamp
        return age < self.cache_duration

    def _try_endpoint_with_retry(self, endpoint: APIEndpoint, tcin: str, max_retries: int = None) -> Optional[Dict]:
        """
        Try an endpoint with exponential backoff retry

        Args:
            endpoint: APIEndpoint to try
            tcin: Target product ID
            max_retries: Override default max retries

        Returns:
            Product data dict or None if failed
        """
        retries = max_retries if max_retries is not None else self.max_retries

        for attempt in range(retries):
            try:
                # Build URL from template
                url = endpoint.url_template.format(tcin=tcin)

                # Make request
                start_time = time.time()
                response = requests.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                        'Referer': 'https://www.target.com/',
                    },
                    timeout=self.timeout
                )
                response_time = time.time() - start_time

                # Handle response
                if response.status_code == 200:
                    data = response.json()

                    # Validate response contains product data
                    if self._validate_response(data):
                        # Extract product info
                        result = self._extract_product_data(data)

                        # Record success
                        endpoint.record_success(response_time)

                        return result
                    else:
                        # Invalid response structure
                        if attempt < retries - 1:
                            print(f"[Enhanced API] Invalid response structure, retrying...")
                            time.sleep(self.base_backoff * (2 ** attempt))
                            continue

                elif response.status_code == 400:
                    # Bad request - endpoint likely deprecated
                    print(f"[Enhanced API] 400 error (bad endpoint format)")
                    endpoint.record_failure()
                    return None  # Don't retry, this endpoint is bad

                elif response.status_code in [403, 429]:
                    # Rate limit or ban - wait longer before retry
                    if attempt < retries - 1:
                        wait_time = self.base_backoff * (3 ** attempt)  # Longer backoff for rate limits
                        print(f"[Enhanced API] Rate limit detected, waiting {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue

                elif response.status_code >= 500:
                    # Server error - worth retrying
                    if attempt < retries - 1:
                        wait_time = self.base_backoff * (2 ** attempt)
                        print(f"[Enhanced API] Server error {response.status_code}, retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)
                        continue

                # Record failure if we get here
                endpoint.record_failure()

                if attempt < retries - 1:
                    wait_time = self.base_backoff * (2 ** attempt)
                    time.sleep(wait_time)

            except requests.Timeout:
                print(f"[Enhanced API] Timeout on attempt {attempt + 1}")
                endpoint.record_failure()
                if attempt < retries - 1:
                    time.sleep(self.base_backoff * (2 ** attempt))

            except Exception as e:
                print(f"[Enhanced API] Error: {e}")
                endpoint.record_failure()
                if attempt < retries - 1:
                    time.sleep(self.base_backoff * (2 ** attempt))

        # All retries exhausted
        return None

    def _validate_response(self, data: Dict) -> bool:
        """Validate API response contains expected product data"""
        try:
            # Check for Target's standard structure
            if 'data' in data and 'product' in data['data']:
                return True

            # Check for alternative structures
            if 'product' in data:
                return True

            return False
        except:
            return False

    def _extract_product_data(self, data: Dict) -> Dict:
        """
        Extract product information from Target API response

        Handles multiple response formats
        """
        result = {
            'success': True,
            'in_stock': False,
            'name': 'Unknown',
            'price': 0.0,
            'regular_price': 0.0,
            'image': None,
            'available_quantity': 0
        }

        try:
            # Standard format: data.product
            product = data.get('data', {}).get('product', data.get('product', {}))

            if not product:
                return result

            # Extract name
            item = product.get('item', {})
            desc = item.get('product_description', {})
            result['name'] = desc.get('title', 'Unknown')

            # Extract price
            price_data = product.get('price', {})
            result['price'] = float(price_data.get('current_retail', 0.0))
            result['regular_price'] = float(price_data.get('reg_retail', result['price']))

            # Extract stock
            fulfillment = product.get('fulfillment', {}).get('shipping_options', {})
            available = fulfillment.get('available_to_promise_quantity', 0)
            result['available_quantity'] = available
            result['in_stock'] = available > 0

            # Extract image
            images = item.get('enrichment', {}).get('images', {})
            result['image'] = images.get('primary_image_url')

        except Exception as e:
            print(f"[Enhanced API] Data extraction error: {e}")

        return result

    def get_stats(self) -> Dict:
        """Get API endpoint health statistics"""
        healthy = sum(1 for ep in self.endpoints.values() if ep.is_healthy)
        total = len(self.endpoints)

        # Get best endpoint
        best_endpoint = None
        best_rate = 0.0
        for key, ep in self.endpoints.items():
            if ep.success_rate > best_rate:
                best_rate = ep.success_rate
                best_endpoint = key

        return {
            'total_endpoints': total,
            'healthy_endpoints': healthy,
            'unhealthy_endpoints': total - healthy,
            'best_endpoint': best_endpoint,
            'best_success_rate': best_rate,
            'cached_endpoint': self.working_endpoint.url_template if self.working_endpoint else None,
            'cache_valid': self._has_valid_cache()
        }

    def reset_endpoint_health(self, endpoint_key: str = None):
        """Reset health stats for an endpoint (or all)"""
        if endpoint_key:
            if endpoint_key in self.endpoints:
                ep = self.endpoints[endpoint_key]
                ep.success_count = 0
                ep.failure_count = 0
                ep.consecutive_failures = 0
        else:
            # Reset all
            for ep in self.endpoints.values():
                ep.success_count = 0
                ep.failure_count = 0
                ep.consecutive_failures = 0


# Global instance
_enhanced_api_instance = None

def get_enhanced_api(db_manager=None) -> EnhancedTargetAPI:
    """Get or create enhanced API instance"""
    global _enhanced_api_instance
    if _enhanced_api_instance is None:
        _enhanced_api_instance = EnhancedTargetAPI(db_manager)
    return _enhanced_api_instance
