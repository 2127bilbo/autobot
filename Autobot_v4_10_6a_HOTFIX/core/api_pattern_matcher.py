"""
Autobot API Pattern Matcher
Phase 1C - Core Intelligence

Utilities for finding and extracting data from JSON responses.
Implements recursive JSON path search and extraction.
"""

from typing import Any, List, Optional, Union


def find_json_paths(obj: Any, keyword: str, current_path: str = "", max_depth: int = 10) -> List[str]:
    """
    Recursively search JSON for paths containing keyword
    
    Args:
        obj: JSON object to search
        keyword: Keyword to search for in keys
        current_path: Current path (for recursion)
        max_depth: Maximum recursion depth
    
    Returns:
        List of JSON paths that match
    
    Example:
        data = {"product": {"price": {"current": 29.99}}}
        paths = find_json_paths(data, "price")
        # Returns: ["product.price.current"]
    """
    if max_depth <= 0:
        return []
    
    paths = []
    keyword_lower = keyword.lower()
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower()
            new_path = f"{current_path}.{key}" if current_path else key
            
            # Check if this key matches
            if keyword_lower in key_lower:
                # If value is a simple type, this is a leaf node
                if isinstance(value, (int, float, str, bool)):
                    paths.append(new_path)
                # If value is complex, still add this path and search deeper
                elif isinstance(value, dict):
                    # Check if any nested keys also match
                    nested_paths = find_json_paths(value, keyword, new_path, max_depth - 1)
                    if nested_paths:
                        paths.extend(nested_paths)
                    else:
                        # No nested matches, use this level
                        paths.append(new_path)
            else:
                # Key doesn't match, search value
                nested_paths = find_json_paths(value, keyword, new_path, max_depth - 1)
                paths.extend(nested_paths)
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{current_path}[{i}]"
            nested_paths = find_json_paths(item, keyword, new_path, max_depth - 1)
            paths.extend(nested_paths)
    
    return paths


def extract_by_path(obj: Any, path: str) -> Any:
    """
    Extract value from JSON using dot-notation path
    
    Args:
        obj: JSON object
        path: Dot-notation path (e.g., "product.price.current")
    
    Returns:
        Extracted value or None if path doesn't exist
    
    Example:
        data = {"product": {"price": {"current": 29.99}}}
        value = extract_by_path(data, "product.price.current")
        # Returns: 29.99
    """
    if not path or not obj:
        return None
    
    try:
        current = obj
        parts = path.split('.')
        
        for part in parts:
            # Handle array indices like [0]
            if '[' in part and ']' in part:
                key = part[:part.index('[')]
                index = int(part[part.index('[') + 1:part.index(']')])
                
                if key:
                    current = current[key]
                current = current[index]
            else:
                current = current[part]
        
        return current
    
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def find_price_value(obj: Any) -> Optional[float]:
    """
    Smart price finder - looks for numeric values that look like prices
    
    Args:
        obj: JSON object to search
    
    Returns:
        Price as float, or None if not found
    """
    # Common price field names
    price_keywords = [
        'price', 'current_retail', 'sale_price', 'list_price',
        'amount', 'cost', 'value', 'retail'
    ]
    
    # Try each keyword
    for keyword in price_keywords:
        paths = find_json_paths(obj, keyword)
        
        for path in paths:
            value = extract_by_path(obj, path)
            
            # Check if value looks like a price
            if isinstance(value, (int, float)) and 0 < value < 100000:
                return float(value)
            
            # Try parsing string price
            if isinstance(value, str):
                # Remove currency symbols and parse
                cleaned = value.replace('$', '').replace(',', '').strip()
                try:
                    price = float(cleaned)
                    if 0 < price < 100000:
                        return price
                except ValueError:
                    pass
    
    return None


def find_stock_status(obj: Any) -> Optional[bool]:
    """
    Smart stock finder - looks for availability indicators
    
    Args:
        obj: JSON object to search
    
    Returns:
        True if in stock, False if out of stock, None if unknown
    """
    # Stock-related keywords
    stock_keywords = [
        'stock', 'inventory', 'available', 'availability',
        'in_stock', 'inStock', 'is_available'
    ]
    
    # In-stock indicators
    in_stock_values = [
        'in_stock', 'in stock', 'available', 'yes', 'true', 
        'in-stock', 'instock', 'active', 'purchasable'
    ]
    
    # Out-of-stock indicators
    out_of_stock_values = [
        'out_of_stock', 'out of stock', 'unavailable', 'no', 'false',
        'out-of-stock', 'outofstock', 'sold out', 'soldout'
    ]
    
    # Try each keyword
    for keyword in stock_keywords:
        paths = find_json_paths(obj, keyword)
        
        for path in paths:
            value = extract_by_path(obj, path)
            
            if value is None:
                continue
            
            # Boolean check
            if isinstance(value, bool):
                return value
            
            # String check
            if isinstance(value, str):
                value_lower = value.lower().strip()
                
                if value_lower in in_stock_values:
                    return True
                
                if value_lower in out_of_stock_values:
                    return False
            
            # Numeric check (quantity)
            if isinstance(value, (int, float)):
                return value > 0
    
    return None


def find_product_name(obj: Any) -> Optional[str]:
    """
    Find product name in JSON
    
    Args:
        obj: JSON object to search
    
    Returns:
        Product name string or None
    """
    name_keywords = ['name', 'title', 'product_name', 'description']
    
    for keyword in name_keywords:
        paths = find_json_paths(obj, keyword)
        
        for path in paths:
            value = extract_by_path(obj, path)
            
            if isinstance(value, str) and len(value) > 3:
                # Skip very short names (likely not product names)
                return value.strip()
    
    return None


def find_image_url(obj: Any) -> Optional[str]:
    """
    Find product image URL in JSON
    
    Args:
        obj: JSON object to search
    
    Returns:
        Image URL string or None
    """
    image_keywords = ['image', 'img', 'picture', 'photo', 'thumbnail', 'primary_image']
    
    for keyword in image_keywords:
        paths = find_json_paths(obj, keyword)
        
        for path in paths:
            value = extract_by_path(obj, path)
            
            if isinstance(value, str):
                # Check if it looks like a URL
                if value.startswith('http') or value.startswith('//'):
                    return value.strip()
    
    return None


def analyze_json_structure(obj: Any, max_depth: int = 5, current_path: str = "", depth: int = 0) -> List[str]:
    """
    Analyze JSON structure and return all paths
    
    Args:
        obj: JSON object to analyze
        max_depth: Maximum depth to analyze
        current_path: Current path (for recursion)
        depth: Current depth
    
    Returns:
        List of all paths in the JSON
    """
    if depth >= max_depth:
        return []
    
    paths = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{current_path}.{key}" if current_path else key
            paths.append(new_path)
            
            # Recurse if value is complex
            if isinstance(value, (dict, list)):
                nested = analyze_json_structure(value, max_depth, new_path, depth + 1)
                paths.extend(nested)
    
    elif isinstance(obj, list) and len(obj) > 0:
        # Just analyze first item as sample
        new_path = f"{current_path}[0]"
        nested = analyze_json_structure(obj[0], max_depth, new_path, depth + 1)
        paths.extend(nested)
    
    return paths


def match_api_response(data: Any, site: str) -> dict:
    """
    Analyze API response and extract all useful data
    
    Args:
        data: JSON response data
        site: Site name for site-specific rules
    
    Returns:
        Dict with extracted data
    """
    result = {
        'price': find_price_value(data),
        'stock': find_stock_status(data),
        'name': find_product_name(data),
        'image': find_image_url(data)
    }
    
    # Site-specific adjustments
    if site == 'target':
        # Target-specific patterns
        if 'data' in data:
            if 'product' in data['data']:
                product = data['data']['product']
                
                # Price from Target API
                if 'price' in product:
                    if 'current_retail' in product['price']:
                        result['price'] = product['price']['current_retail']
                
                # Stock from Target API
                if 'fulfillment' in product:
                    if 'availability' in product['fulfillment']:
                        avail = product['fulfillment']['availability']
                        result['stock'] = avail not in ['OUT_OF_STOCK', 'UNAVAILABLE']
    
    elif site == 'walmart':
        # Walmart-specific patterns
        if 'product' in data:
            product = data['product']
            
            # Price
            if 'priceInfo' in product:
                if 'currentPrice' in product['priceInfo']:
                    result['price'] = product['priceInfo']['currentPrice'].get('price')
            
            # Stock
            if 'availabilityStatus' in product:
                result['stock'] = product['availabilityStatus'] == 'IN_STOCK'
    
    return result


def validate_extracted_data(data: dict) -> bool:
    """
    Validate that extracted data looks reasonable
    
    Args:
        data: Extracted data dict
    
    Returns:
        True if data looks valid
    """
    # Must have at least price or stock
    if data.get('price') is None and data.get('stock') is None:
        return False
    
    # If price exists, validate it
    if data.get('price') is not None:
        price = data['price']
        if not isinstance(price, (int, float)):
            return False
        if price <= 0 or price > 100000:
            return False
    
    # If stock exists, validate it
    if data.get('stock') is not None:
        stock = data['stock']
        if not isinstance(stock, bool):
            return False
    
    return True


# Helper function for debugging
def print_json_structure(obj: Any, indent: int = 0, max_depth: int = 5):
    """
    Print JSON structure for debugging
    
    Args:
        obj: JSON object
        indent: Indentation level
        max_depth: Maximum depth to print
    """
    if max_depth <= 0:
        return
    
    prefix = "  " * indent
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            value_type = type(value).__name__
            
            if isinstance(value, (dict, list)):
                print(f"{prefix}{key}: {value_type}")
                print_json_structure(value, indent + 1, max_depth - 1)
            else:
                print(f"{prefix}{key}: {value_type} = {value}")
    
    elif isinstance(obj, list):
        print(f"{prefix}[list with {len(obj)} items]")
        if len(obj) > 0:
            print(f"{prefix}Sample item [0]:")
            print_json_structure(obj[0], indent + 1, max_depth - 1)


class APIPatternMatcher:
    """
    Wrapper class for API pattern matching functions
    Provides object-oriented interface to utility functions
    """
    
    @staticmethod
    def find_json_paths(obj: Any, keyword: str, current_path: str = "", max_depth: int = 10) -> List[str]:
        """
        Find JSON paths containing keyword
        
        Args:
            obj: JSON object to search
            keyword: Keyword to search for
            current_path: Current path (internal)
            max_depth: Maximum recursion depth
        
        Returns:
            List of matching paths
        """
        return find_json_paths(obj, keyword, current_path, max_depth)
    
    @staticmethod
    def extract_from_path(obj: Any, path: str) -> Any:
        """
        Extract value from JSON path
        
        Args:
            obj: JSON object
            path: Dot-notation path
        
        Returns:
            Value at path or None
        """
        return extract_from_path(obj, path)
    
    @staticmethod
    def find_and_extract(obj: Any, keyword: str) -> dict:
        """
        Find paths containing keyword and extract values
        
        Args:
            obj: JSON object
            keyword: Keyword to search for
        
        Returns:
            Dict mapping paths to values
        """
        paths = find_json_paths(obj, keyword)
        results = {}
        for path in paths:
            value = extract_from_path(obj, path)
            if value is not None:
                results[path] = value
        return results
    
    @staticmethod
    def find_best_path(obj: Any, keywords: List[str], preferred: Optional[List[str]] = None) -> Optional[str]:
        """
        Find best matching path
        
        Args:
            obj: JSON object
            keywords: Keywords to search for
            preferred: Preferred path patterns
        
        Returns:
            Best matching path or None
        """
        return find_best_path(obj, keywords, preferred)
