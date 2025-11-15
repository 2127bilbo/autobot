"""
Autobot Smart API Analyzer
Phase 1C - Core Intelligence

Intercepts network requests to learn API patterns automatically.
This allows 10-100x faster checks than browser-based monitoring.

Key Features:
- Network request interception via Playwright
- Automatic API endpoint detection
- Response pattern learning
- JSON path extraction
- Auto-relearning when patterns break
"""

import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass, field


@dataclass
class APIRequest:
    """Captured API request data"""
    url: str
    method: str
    headers: Dict[str, str]
    timestamp: datetime
    response_status: int = 0
    response_data: Optional[Any] = None
    response_time: float = 0.0


@dataclass
class APIPattern:
    """Learned API pattern for a site"""
    site: str
    endpoint_pattern: str  # Regex pattern for API endpoint
    price_path: Optional[str] = None  # JSON path to price
    stock_path: Optional[str] = None  # JSON path to stock status
    name_path: Optional[str] = None  # JSON path to product name
    image_path: Optional[str] = None  # JSON path to image URL
    
    # Metadata
    learned_at: datetime = field(default_factory=datetime.now)
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'site': self.site,
            'endpoint_pattern': self.endpoint_pattern,
            'price_path': self.price_path,
            'stock_path': self.stock_path,
            'name_path': self.name_path,
            'image_path': self.image_path,
            'learned_at': self.learned_at.isoformat(),
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


class SmartAPIAnalyzer:
    """
    Analyzes network traffic to automatically learn API patterns
    
    Workflow:
    1. Load product page with network interception
    2. Capture all XHR/Fetch requests
    3. Find requests that return product data
    4. Learn JSON paths for price, stock, name, image
    5. Save pattern to database
    6. Use learned pattern for fast API checks
    """
    
    def __init__(self, db_manager=None):
        """
        Initialize API analyzer
        
        Args:
            db_manager: DatabaseManager instance for pattern storage
        """
        self.db_manager = db_manager
        self.captured_requests: List[APIRequest] = []
        self.learned_patterns: Dict[str, APIPattern] = {}
        
        # API detection heuristics
        self.api_indicators = [
            '/api/',
            '/v1/', '/v2/', '/v3/',
            'json',
            'ajax',
            'graphql',
            'query',
            'product',
            'item',
            'data'
        ]
        
        # Initialize from database
        self._load_patterns()
    
    def _load_patterns(self):
        """Load learned patterns from database"""
        if not self.db_manager:
            return
        
        try:
            patterns = self.db_manager.get_api_patterns()
            for pattern_dict in patterns:
                pattern = APIPattern(
                    site=pattern_dict['site'],
                    endpoint_pattern=pattern_dict['endpoint_pattern'],
                    price_path=pattern_dict.get('price_path'),
                    stock_path=pattern_dict.get('stock_path'),
                    name_path=pattern_dict.get('name_path'),
                    image_path=pattern_dict.get('image_path'),
                    learned_at=datetime.fromisoformat(pattern_dict['learned_at']),
                    success_count=pattern_dict.get('success_count', 0),
                    failure_count=pattern_dict.get('failure_count', 0),
                    last_used=datetime.fromisoformat(pattern_dict['last_used']) if pattern_dict.get('last_used') else None
                )
                self.learned_patterns[pattern.site] = pattern
        except Exception as e:
            print(f"[API Analyzer] Error loading patterns: {e}")
    
    def load_patterns(self):
        """Public method to reload patterns from database"""
        self._load_patterns()
    
    def has_learned_pattern(self, site: str) -> bool:
        """Check if we have a learned pattern for this site"""
        return site in self.learned_patterns
    
    def get_pattern(self, site: str) -> Optional[APIPattern]:
        """Get learned pattern for a site"""
        return self.learned_patterns.get(site)
    
    async def learn_from_page(self, page, product_url: str, site: str) -> Optional[APIPattern]:
        """
        Learn API pattern from a product page
        
        Args:
            page: Playwright page object
            product_url: Product URL to analyze
            site: Site name (target, walmart, etc.)
        
        Returns:
            APIPattern if learned successfully, None otherwise
        """
        print(f"[API Learning] Starting analysis for {site}...")
        self.captured_requests = []
        
        # Set up request/response interception
        async def handle_request(request):
            """Capture request details"""
            if self._is_api_request(request.url):
                try:
                    api_req = APIRequest(
                        url=request.url,
                        method=request.method,
                        headers=request.headers,
                        timestamp=datetime.now()
                    )
                    self.captured_requests.append(api_req)
                except Exception as e:
                    print(f"[API Learning] Error capturing request: {e}")
        
        async def handle_response(response):
            """Capture response data"""
            if self._is_api_request(response.url):
                try:
                    # Find matching request
                    for req in self.captured_requests:
                        if req.url == response.url and req.response_data is None:
                            req.response_status = response.status
                            
                            # Try to parse JSON response
                            if 'json' in response.headers.get('content-type', '').lower():
                                try:
                                    req.response_data = await response.json()
                                    req.response_time = (datetime.now() - req.timestamp).total_seconds()
                                except:
                                    pass
                            break
                except Exception as e:
                    print(f"[API Learning] Error capturing response: {e}")
        
        # Attach handlers
        page.on("request", handle_request)
        page.on("response", handle_response)
        
        # Load the page
        try:
            await page.goto(product_url, wait_until='networkidle', timeout=30000)
            
            # Give it a moment for all requests to complete
            await asyncio.sleep(2)
            
            print(f"[API Learning] Captured {len(self.captured_requests)} API requests")
            
            # Analyze captured requests to find product data
            pattern = await self._analyze_requests(site, product_url)
            
            if pattern:
                # Save to database
                if self.db_manager:
                    self.db_manager.save_api_pattern(pattern.to_dict())
                
                # Cache in memory
                self.learned_patterns[site] = pattern
                
                print(f"[API Learning] ✅ Successfully learned API pattern for {site}")
                print(f"[API Learning]    Endpoint: {pattern.endpoint_pattern}")
                if pattern.price_path:
                    print(f"[API Learning]    Price path: {pattern.price_path}")
                if pattern.stock_path:
                    print(f"[API Learning]    Stock path: {pattern.stock_path}")
                
                return pattern
            else:
                print(f"[API Learning] ⚠️  Could not learn API pattern for {site}")
                return None
                
        except Exception as e:
            print(f"[API Learning] Error during learning: {e}")
            return None
        finally:
            # Clean up handlers
            page.remove_listener("request", handle_request)
            page.remove_listener("response", handle_response)
    
    def _is_api_request(self, url: str) -> bool:
        """Check if URL looks like an API request"""
        url_lower = url.lower()
        
        # Check for common API indicators
        for indicator in self.api_indicators:
            if indicator in url_lower:
                return True
        
        # Check for JSON in URL
        if url_lower.endswith('.json'):
            return True
        
        return False
    
    async def _analyze_requests(self, site: str, product_url: str) -> Optional[APIPattern]:
        """
        Analyze captured requests to find product data API
        
        Args:
            site: Site name
            product_url: Original product URL
        
        Returns:
            APIPattern if found, None otherwise
        """
        from .api_pattern_matcher import find_json_paths
        
        # Filter requests with JSON responses
        json_requests = [
            req for req in self.captured_requests
            if req.response_data and isinstance(req.response_data, dict)
        ]
        
        if not json_requests:
            print("[API Learning] No JSON responses found")
            return None
        
        print(f"[API Learning] Analyzing {len(json_requests)} JSON responses...")
        
        # Try to find product data in responses
        best_match = None
        best_score = 0
        
        for req in json_requests:
            score = 0
            paths = {}
            
            # Look for price data
            price_paths = find_json_paths(req.response_data, 'price')
            if price_paths:
                paths['price'] = price_paths[0]
                score += 10
            
            # Look for stock data
            stock_keywords = ['stock', 'inventory', 'available', 'availability', 'in_stock']
            for keyword in stock_keywords:
                stock_paths = find_json_paths(req.response_data, keyword)
                if stock_paths:
                    paths['stock'] = stock_paths[0]
                    score += 8
                    break
            
            # Look for product name
            name_keywords = ['name', 'title', 'description']
            for keyword in name_keywords:
                name_paths = find_json_paths(req.response_data, keyword)
                if name_paths:
                    paths['name'] = name_paths[0]
                    score += 5
                    break
            
            # Look for image
            image_keywords = ['image', 'img', 'picture', 'photo']
            for keyword in image_keywords:
                image_paths = find_json_paths(req.response_data, keyword)
                if image_paths:
                    paths['image'] = image_paths[0]
                    score += 3
                    break
            
            # Must have at least price or stock
            if score > best_score and ('price' in paths or 'stock' in paths):
                best_score = score
                best_match = (req, paths)
        
        if best_match:
            req, paths = best_match
            
            # Create pattern
            pattern = APIPattern(
                site=site,
                endpoint_pattern=self._create_endpoint_pattern(req.url, product_url),
                price_path=paths.get('price'),
                stock_path=paths.get('stock'),
                name_path=paths.get('name'),
                image_path=paths.get('image')
            )
            
            return pattern
        
        return None
    
    def _create_endpoint_pattern(self, api_url: str, product_url: str) -> str:
        """
        Create a regex pattern for the API endpoint
        
        Args:
            api_url: The API URL we captured
            product_url: The original product URL
        
        Returns:
            Regex pattern string
        """
        # Extract product ID from original URL
        product_id = self._extract_product_id(product_url)
        
        if product_id and product_id in api_url:
            # Replace product ID with regex placeholder
            pattern = api_url.replace(product_id, r'(\d+)')
            return pattern
        else:
            # Just use the base URL pattern
            parsed = urlparse(api_url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def _extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID from URL"""
        # Try common patterns
        patterns = [
            r'/(\d{7,})',  # 7+ digit number
            r'product[_-]?id[=:](\d+)',
            r'item[_-]?id[=:](\d+)',
            r'/p/[^/]+/(\d+)',
            r'tcin=(\d+)',
            r'skuId=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    async def check_with_api(self, pattern: APIPattern, product_url: str) -> Optional[Dict]:
        """
        Use learned API pattern to check product data
        
        Args:
            pattern: Learned APIPattern
            product_url: Product URL to check
        
        Returns:
            Dict with product data or None if failed
        """
        try:
            # Extract product ID
            product_id = self._extract_product_id(product_url)
            if not product_id:
                return None
            
            # Build API URL from pattern
            api_url = pattern.endpoint_pattern.replace(r'(\d+)', product_id)
            
            # Make API request
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Extract data using learned paths
                        from .api_pattern_matcher import extract_by_path
                        
                        result = {
                            'success': True,
                            'api_url': api_url
                        }
                        
                        if pattern.price_path:
                            result['price'] = extract_by_path(data, pattern.price_path)
                        
                        if pattern.stock_path:
                            result['stock'] = extract_by_path(data, pattern.stock_path)
                        
                        if pattern.name_path:
                            result['name'] = extract_by_path(data, pattern.name_path)
                        
                        if pattern.image_path:
                            result['image'] = extract_by_path(data, pattern.image_path)
                        
                        # Update pattern stats
                        pattern.success_count += 1
                        pattern.last_used = datetime.now()
                        
                        if self.db_manager:
                            self.db_manager.update_api_pattern_stats(
                                pattern.site,
                                success=True
                            )
                        
                        return result
                    else:
                        return None
            
        except Exception as e:
            print(f"[API Check] Error: {e}")
            
            # Update failure count
            pattern.failure_count += 1
            
            if self.db_manager:
                self.db_manager.update_api_pattern_stats(
                    pattern.site,
                    success=False
                )
            
            return None
    
    def should_relearn(self, pattern: APIPattern) -> bool:
        """
        Determine if pattern should be re-learned
        
        Triggers:
        - Multiple consecutive failures
        - Very low success rate
        - No recent successes
        """
        # If 5+ consecutive failures, relearn
        if pattern.failure_count >= 5 and pattern.success_count == 0:
            return True
        
        # If success rate < 50% over 20+ checks, relearn
        total = pattern.success_count + pattern.failure_count
        if total >= 20:
            success_rate = pattern.success_count / total
            if success_rate < 0.5:
                return True
        
        # If no success in last 50 checks, relearn
        if pattern.failure_count - pattern.success_count > 50:
            return True
        
        return False
    
    # === SYNC METHODS FOR MONITOR INTEGRATION ===
    # These methods allow the monitor to use API learning without async/Playwright
    
    def learn_from_response(self, site: str, url: str, response_data: Dict, product_id: str) -> bool:
        """
        Learn API pattern from a successful API response (sync version for monitor)
        
        Args:
            site: Site name (e.g., 'target')
            url: API URL that worked
            response_data: JSON response data
            product_id: Product ID (e.g., TCIN)
            
        Returns:
            True if pattern learned successfully
        """
        try:
            print(f"[Smart API] Learning pattern from response...")
            
            # Create endpoint pattern by replacing product ID with placeholder
            endpoint_pattern = url.replace(product_id, '{product_id}')
            
            # Try to find data paths in the JSON
            stock_path = self._find_json_path(response_data, 'available')
            price_path = self._find_json_path(response_data, 'price')
            name_path = self._find_json_path(response_data, 'title')
            image_path = self._find_json_path(response_data, 'image')
            
            # Create pattern
            pattern = APIPattern(
                site=site,
                endpoint_pattern=endpoint_pattern,
                stock_path=stock_path,
                price_path=price_path,
                name_path=name_path,
                image_path=image_path
            )
            
            # Save pattern
            self.learned_patterns[site] = pattern
            pattern.success_count = 1
            pattern.last_used = datetime.now()
            
            print(f"[Smart API] ✓ Pattern learned for {site}!")
            print(f"[Smart API]   Endpoint: {endpoint_pattern[:80]}...")
            print(f"[Smart API]   Stock path: {stock_path}")
            print(f"[Smart API]   Price path: {price_path}")
            
            return True
            
        except Exception as e:
            print(f"[Smart API] Failed to learn from response: {e}")
            return False
    
    def _find_json_path(self, data: Dict, keyword: str) -> Optional[str]:
        """
        Find JSON path to a field containing keyword
        
        Args:
            data: JSON data to search
            keyword: Keyword to find
            
        Returns:
            JSON path string or None
        """
        def search_dict(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if keyword.lower() in key.lower():
                        return current_path
                    result = search_dict(value, current_path)
                    if result:
                        return result
            elif isinstance(obj, list) and obj:
                return search_dict(obj[0], f"{path}[0]")
            return None
        
        return search_dict(data)
    
    def check_stock_fast(self, site: str, product_id: str, product_url: str) -> Optional[Dict]:
        """
        Fast stock check using learned API pattern (sync version for monitor)
        
        Args:
            site: Site name
            product_id: Product ID
            product_url: Product URL
            
        Returns:
            Dict with stock info or None
        """
        pattern = self.learned_patterns.get(site)
        if not pattern:
            return None
        
        try:
            # Build API URL from pattern
            api_url = pattern.endpoint_pattern.replace('{product_id}', product_id)
            
            # Make request
            import requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract data using learned paths
                result = {
                    'success': True,
                    'in_stock': self._get_by_path(data, pattern.stock_path) if pattern.stock_path else False,
                    'price': self._get_by_path(data, pattern.price_path) if pattern.price_path else 0.0,
                    'name': self._get_by_path(data, pattern.name_path) if pattern.name_path else 'Unknown',
                    'image': self._get_by_path(data, pattern.image_path) if pattern.image_path else None
                }
                
                # Update pattern stats
                pattern.success_count += 1
                pattern.last_used = datetime.now()
                
                return result
            else:
                pattern.failure_count += 1
                return None
                
        except Exception as e:
            print(f"[Smart API] Fast check failed: {e}")
            if pattern:
                pattern.failure_count += 1
            return None
    
    def _get_by_path(self, data: Dict, path: str) -> Any:
        """
        Get value from dict using path string
        
        Args:
            data: Dict to search
            path: Path string like "data.product.price"
            
        Returns:
            Value at path or None
        """
        try:
            parts = path.replace('[0]', '').split('.')
            current = data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
            return current
        except:
            return None


# Global analyzer instance pool
_analyzer_pool = {}
_pool_lock = asyncio.Lock()


async def get_api_analyzer(db_manager=None):
    """Get or create API analyzer instance"""
    async with _pool_lock:
        key = id(db_manager) if db_manager else 'default'
        
        if key not in _analyzer_pool:
            _analyzer_pool[key] = SmartAPIAnalyzer(db_manager)
        
        return _analyzer_pool[key]
