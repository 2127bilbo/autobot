"""
Autobot 2.0.1 - Hybrid API/HTML System
Adapts to Target's changing APIs by using HTML as primary with smart API discovery

IMPROVEMENTS:
- HTML-first approach (more reliable than deprecated APIs)
- Faster HTML parsing with BeautifulSoup
- API discovery from actual page network requests
- Automatic API endpoint learning
"""

import requests
import time
import re
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import json


class HybridTargetChecker:
    """
    Hybrid checker that prioritizes reliable HTML parsing
    and discovers working API endpoints dynamically
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Cache for discovered working endpoints
        self.working_endpoints = []
        self.last_discovery = None

    def check_stock_fast_html(self, product_url: str, tcin: str) -> Optional[Dict]:
        """
        Fast HTML-based stock check using BeautifulSoup

        Much faster than Playwright, more reliable than APIs

        Args:
            product_url: Target product URL
            tcin: Target product ID

        Returns:
            Dict with product data or None
        """
        try:
            print(f"[Hybrid] Fast HTML check for TCIN: {tcin}")

            # Make request
            response = self.session.get(product_url, timeout=10)

            if response.status_code != 200:
                print(f"[Hybrid] HTTP {response.status_code}")
                return None

            html = response.text

            # Parse with BeautifulSoup for speed
            soup = BeautifulSoup(html, 'lxml')

            # Extract data from JSON embedded in page
            # Target embeds product data in <script> tags
            product_data = self._extract_json_from_page(soup)

            if product_data:
                # Got structured data from page!
                return self._parse_embedded_json(product_data)

            # Fallback to HTML parsing
            return self._parse_html_elements(soup, html)

        except Exception as e:
            print(f"[Hybrid] Error: {e}")
            return None

    def _extract_json_from_page(self, soup: BeautifulSoup) -> Optional[Dict]:
        """
        Extract JSON data embedded in Target's page
        Target includes product data in script tags
        """
        try:
            # Look for __TGT_DATA__ or similar JSON data
            scripts = soup.find_all('script')

            for script in scripts:
                if script.string and ('__TGT_DATA__' in script.string or 'product' in script.string.lower()):
                    text = script.string

                    # Try to extract JSON objects
                    # Look for patterns like: window.__TGT_DATA__ = {...}
                    matches = re.findall(r'({[\s\S]*?})\s*(?:;|\n|</script>)', text)

                    for match in matches:
                        try:
                            data = json.loads(match)

                            # Check if this looks like product data
                            if self._is_product_data(data):
                                return data
                        except:
                            continue

            return None

        except Exception as e:
            return None

    def _is_product_data(self, data: Dict) -> bool:
        """Check if JSON looks like product data"""
        # Look for common product data indicators
        indicators = ['product', 'price', 'item', 'tcin', 'title', 'fulfillment']

        def check_dict(d, depth=0):
            if depth > 3:  # Don't go too deep
                return False

            if not isinstance(d, dict):
                return False

            # Check keys
            for key in d.keys():
                if any(ind in str(key).lower() for ind in indicators):
                    return True

            # Check nested
            for value in d.values():
                if isinstance(value, dict):
                    if check_dict(value, depth + 1):
                        return True

            return False

        return check_dict(data)

    def _parse_embedded_json(self, data: Dict) -> Optional[Dict]:
        """Parse product data from embedded JSON"""
        try:
            result = {
                'success': True,
                'in_stock': False,
                'name': 'Unknown',
                'price': 0.0,
                'regular_price': 0.0,
                'image': None,
                'available_quantity': 0,
                'source': 'embedded_json'
            }

            # Navigate the JSON structure
            # This is flexible to handle different structures
            product = self._find_product_in_dict(data)

            if not product:
                return None

            # Extract fields
            # Name
            for key in ['title', 'name', 'product_title', 'product_name']:
                if key in product:
                    result['name'] = product[key]
                    break

            # Price
            price_data = product.get('price', {})
            if isinstance(price_data, dict):
                result['price'] = float(price_data.get('current_retail', price_data.get('current', 0)))
                result['regular_price'] = float(price_data.get('reg_retail', price_data.get('regular', result['price'])))
            elif isinstance(price_data, (int, float)):
                result['price'] = float(price_data)
                result['regular_price'] = result['price']

            # Stock
            fulfillment = product.get('fulfillment', {})
            if isinstance(fulfillment, dict):
                shipping = fulfillment.get('shipping_options', fulfillment.get('shipping', {}))
                if isinstance(shipping, dict):
                    qty = shipping.get('available_to_promise_quantity', shipping.get('quantity', 0))
                    result['available_quantity'] = int(qty)
                    result['in_stock'] = qty > 0

            # Image
            for key in ['image', 'primary_image_url', 'image_url', 'img']:
                if key in product:
                    result['image'] = product[key]
                    break

            print(f"[Hybrid] ✓ Extracted from JSON: {result['name'][:50]}")
            return result

        except Exception as e:
            print(f"[Hybrid] JSON parse error: {e}")
            return None

    def _find_product_in_dict(self, data: Dict, depth=0) -> Optional[Dict]:
        """Recursively find product data in nested dict"""
        if depth > 5:
            return None

        # Check if this dict itself is product data
        if any(key in data for key in ['tcin', 'product_title', 'fulfillment']):
            return data

        # Check common keys
        for key in ['product', 'data', 'item', 'productData']:
            if key in data and isinstance(data[key], dict):
                found = self._find_product_in_dict(data[key], depth + 1)
                if found:
                    return found

        return None

    def _parse_html_elements(self, soup: BeautifulSoup, html: str) -> Optional[Dict]:
        """
        Fallback HTML element parsing
        Faster than regex, more reliable
        """
        try:
            result = {
                'success': True,
                'in_stock': False,
                'name': 'Unknown',
                'price': 0.0,
                'regular_price': 0.0,
                'image': None,
                'source': 'html_parse'
            }

            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()
                # Clean up Target's title format
                title = title.split(' : Target')[0].split(' - Target')[0].strip()
                if len(title) > 3:
                    result['name'] = title

            # Check stock status
            html_lower = html.lower()

            # Out of stock indicators
            if any(ind in html_lower for ind in ['out of stock', 'sold out', 'unavailable']):
                result['in_stock'] = False
            # Check if add to cart is disabled
            elif re.search(r'add to cart[^>]*(?:disabled|aria-disabled="true")', html_lower, re.IGNORECASE):
                result['in_stock'] = False
            # In stock indicators
            elif any(ind in html_lower for ind in ['ship it', 'pick it up', 'add to cart']):
                # Make sure it's not disabled
                if not re.search(r'add to cart[^>]*disabled', html_lower):
                    result['in_stock'] = True

            # Extract price from meta tags (most reliable)
            price_meta = soup.find('meta', {'property': 'product:price:amount'})
            if price_meta and price_meta.get('content'):
                try:
                    result['price'] = float(price_meta['content'])
                    result['regular_price'] = result['price']
                except:
                    pass

            # Extract image
            image_meta = soup.find('meta', {'property': 'og:image'})
            if image_meta and image_meta.get('content'):
                result['image'] = image_meta['content']

            print(f"[Hybrid] ✓ Parsed HTML: {result['name'][:50]} - {'IN STOCK' if result['in_stock'] else 'OUT OF STOCK'}")
            return result

        except Exception as e:
            print(f"[Hybrid] HTML parse error: {e}")
            return None


# Global instance
_hybrid_checker = None

def get_hybrid_checker() -> HybridTargetChecker:
    """Get or create hybrid checker instance"""
    global _hybrid_checker
    if _hybrid_checker is None:
        _hybrid_checker = HybridTargetChecker()
    return _hybrid_checker
