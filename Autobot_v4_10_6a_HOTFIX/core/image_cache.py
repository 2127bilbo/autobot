"""
Autobot Image Cache Module
Handles downloading, caching, and managing product images
"""

import os
import hashlib
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
import requests
from PIL import Image
import io


class ImageCache:
    """
    Image caching system for Autobot
    Downloads, resizes, and caches product images locally
    """
    
    def __init__(self, cache_dir: str = "cache/images", max_size_mb: int = 100):
        """
        Initialize image cache
        
        Args:
            cache_dir: Directory to store cached images
            max_size_mb: Maximum cache size in megabytes
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.lock = threading.Lock()
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache metadata
        self.metadata_file = self.cache_dir / "cache_metadata.txt"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata from file"""
        if not self.metadata_file.exists():
            return {}
        
        metadata = {}
        try:
            with open(self.metadata_file, 'r') as f:
                for line in f:
                    if '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) >= 4:
                            url_hash = parts[0]
                            metadata[url_hash] = {
                                'url': parts[1],
                                'timestamp': float(parts[2]),
                                'size': int(parts[3])
                            }
        except Exception as e:
            print(f"Error loading cache metadata: {e}")
        
        return metadata
    
    def _save_metadata(self):
        """Save cache metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                for url_hash, data in self.metadata.items():
                    f.write(f"{url_hash}|{data['url']}|{data['timestamp']}|{data['size']}\n")
        except Exception as e:
            print(f"Error saving cache metadata: {e}")
    
    def _get_url_hash(self, url: str) -> str:
        """Generate hash for URL to use as filename"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, url_hash: str, extension: str = '.png') -> Path:
        """Get full path for cached image"""
        return self.cache_dir / f"{url_hash}{extension}"
    
    def download_and_cache(self, url: str, max_size: Tuple[int, int] = (200, 200)) -> Optional[str]:
        """
        Download image from URL, resize, and cache locally
        
        Args:
            url: Image URL to download
            max_size: Maximum dimensions (width, height) for resized image
            
        Returns:
            Path to cached image file, or None if failed
        """
        if not url:
            return None
        
        with self.lock:
            # Check if already cached
            url_hash = self._get_url_hash(url)
            cache_path = self._get_cache_path(url_hash)
            
            if cache_path.exists():
                # Update access time in metadata
                if url_hash in self.metadata:
                    self.metadata[url_hash]['timestamp'] = time.time()
                    self._save_metadata()
                return str(cache_path)
            
            # Download image
            try:
                response = requests.get(url, timeout=10, stream=True)
                response.raise_for_status()
                
                # Open image with PIL
                img = Image.open(io.BytesIO(response.content))
                
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                # Resize image while maintaining aspect ratio
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save to cache
                img.save(cache_path, 'PNG', optimize=True)
                
                # Update metadata
                file_size = cache_path.stat().st_size
                self.metadata[url_hash] = {
                    'url': url,
                    'timestamp': time.time(),
                    'size': file_size
                }
                self._save_metadata()
                
                # Check cache size and cleanup if needed
                self._cleanup_if_needed()
                
                return str(cache_path)
                
            except Exception as e:
                print(f"Error caching image from {url}: {e}")
                return None
    
    def get_cached_path(self, url: str) -> Optional[str]:
        """
        Get path to cached image if it exists
        
        Args:
            url: Original image URL
            
        Returns:
            Path to cached image, or None if not cached
        """
        if not url:
            return None
        
        url_hash = self._get_url_hash(url)
        cache_path = self._get_cache_path(url_hash)
        
        if cache_path.exists():
            return str(cache_path)
        
        return None
    
    def is_cached(self, url: str) -> bool:
        """Check if image is already cached"""
        return self.get_cached_path(url) is not None
    
    def get_cache_size(self) -> int:
        """Get total size of cache in bytes"""
        total = 0
        for url_hash, data in self.metadata.items():
            total += data['size']
        return total
    
    def get_cache_size_mb(self) -> float:
        """Get cache size in megabytes"""
        return self.get_cache_size() / (1024 * 1024)
    
    def get_cache_count(self) -> int:
        """Get number of cached images"""
        return len(self.metadata)
    
    def _cleanup_if_needed(self):
        """Clean up old images if cache size exceeds limit"""
        current_size = self.get_cache_size()
        
        if current_size > self.max_size_bytes:
            # Sort by timestamp (oldest first)
            sorted_items = sorted(
                self.metadata.items(),
                key=lambda x: x[1]['timestamp']
            )
            
            # Remove oldest images until under limit
            for url_hash, data in sorted_items:
                if current_size <= self.max_size_bytes * 0.8:  # Remove to 80% of limit
                    break
                
                cache_path = self._get_cache_path(url_hash)
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                        current_size -= data['size']
                        del self.metadata[url_hash]
                    except Exception as e:
                        print(f"Error removing cached image: {e}")
            
            self._save_metadata()
    
    def clear_cache(self):
        """Clear entire cache"""
        with self.lock:
            for url_hash in list(self.metadata.keys()):
                cache_path = self._get_cache_path(url_hash)
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                    except Exception as e:
                        print(f"Error removing cached image: {e}")
            
            self.metadata.clear()
            self._save_metadata()
    
    def clear_old_cache(self, days: int = 30):
        """
        Clear cache entries older than specified days
        
        Args:
            days: Remove entries older than this many days
        """
        with self.lock:
            cutoff_time = time.time() - (days * 24 * 60 * 60)
            
            for url_hash, data in list(self.metadata.items()):
                if data['timestamp'] < cutoff_time:
                    cache_path = self._get_cache_path(url_hash)
                    if cache_path.exists():
                        try:
                            cache_path.unlink()
                            del self.metadata[url_hash]
                        except Exception as e:
                            print(f"Error removing old cached image: {e}")
            
            self._save_metadata()
    
    def remove_cached_image(self, url: str) -> bool:
        """
        Remove specific image from cache
        
        Args:
            url: URL of image to remove
            
        Returns:
            True if removed, False if not found
        """
        with self.lock:
            url_hash = self._get_url_hash(url)
            
            if url_hash not in self.metadata:
                return False
            
            cache_path = self._get_cache_path(url_hash)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except Exception as e:
                    print(f"Error removing cached image: {e}")
                    return False
            
            del self.metadata[url_hash]
            self._save_metadata()
            return True
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'total_images': self.get_cache_count(),
            'total_size_mb': round(self.get_cache_size_mb(), 2),
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'cache_dir': str(self.cache_dir),
            'usage_percent': round((self.get_cache_size() / self.max_size_bytes) * 100, 1)
        }


# Global cache instance
_cache_instance = None


def get_cache() -> ImageCache:
    """Get global image cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ImageCache()
    return _cache_instance
