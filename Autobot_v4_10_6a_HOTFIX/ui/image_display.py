"""
Autobot Image Display System
Handles loading and displaying product images in the UI with PIL/CTkImage
"""

import os
from pathlib import Path
from typing import Optional, Dict
import threading
from PIL import Image
import customtkinter as ctk
from core.image_cache import ImageCache


class ImageDisplayManager:
    """
    Manages image display in the UI
    Downloads, caches, and displays product images as thumbnails
    """
    
    def __init__(self, cache_dir: str = "cache/images", max_cache_mb: int = 100):
        """
        Initialize image display manager
        
        Args:
            cache_dir: Directory for image cache
            max_cache_mb: Maximum cache size in MB
        """
        self.cache = ImageCache(cache_dir, max_cache_mb)
        self.lock = threading.Lock()
        
        # In-memory PIL Image cache for quick access
        self.pil_cache: Dict[str, Image.Image] = {}
        
        # CTkImage cache (widget-ready images)
        self.ctk_cache: Dict[str, ctk.CTkImage] = {}
        
        # Default/placeholder images
        self.placeholder_image = self._create_placeholder()
        self.error_image = self._create_error_image()
    
    def _create_placeholder(self) -> ctk.CTkImage:
        """Create a placeholder image for when image is loading"""
        # Create a simple gray placeholder
        img = Image.new('RGB', (80, 80), color='#2B2B2B')
        return ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
    
    def _create_error_image(self) -> ctk.CTkImage:
        """Create an error image for when image fails to load"""
        # Create a red-tinted error placeholder
        img = Image.new('RGB', (80, 80), color='#3B2B2B')
        return ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
    
    def get_image(self, image_url: str, size: tuple = (80, 80), force_refresh: bool = False) -> ctk.CTkImage:
        """
        Get a CTkImage for display in the UI
        
        Args:
            image_url: URL of the image to load
            size: Tuple of (width, height) for the image
            force_refresh: Force download even if cached
        
        Returns:
            CTkImage ready for display
        """
        if not image_url:
            return self.placeholder_image
        
        # Check if we have it cached
        cache_key = f"{image_url}_{size[0]}x{size[1]}"
        
        with self.lock:
            if cache_key in self.ctk_cache and not force_refresh:
                return self.ctk_cache[cache_key]
        
        # Try to get from image cache (downloads if needed)
        try:
            image_path = self.cache.get_image(image_url, thumbnail_size=size)
            
            if image_path and os.path.exists(image_path):
                # Load the PIL image
                pil_img = Image.open(image_path)
                
                # Create CTkImage
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
                
                # Cache it
                with self.lock:
                    self.ctk_cache[cache_key] = ctk_img
                
                return ctk_img
            else:
                return self.placeholder_image
        
        except Exception as e:
            print(f"Error loading image {image_url}: {e}")
            return self.error_image
    
    def get_image_async(self, image_url: str, callback, size: tuple = (80, 80)):
        """
        Get image asynchronously and call callback when ready
        
        Args:
            image_url: URL of image
            callback: Function to call with CTkImage when ready
            size: Image size tuple
        """
        def _load():
            img = self.get_image(image_url, size)
            callback(img)
        
        thread = threading.Thread(target=_load, daemon=True)
        thread.start()
    
    def preload_images(self, image_urls: list, size: tuple = (80, 80)):
        """
        Preload multiple images in background
        
        Args:
            image_urls: List of image URLs to preload
            size: Image size
        """
        def _preload():
            for url in image_urls:
                if url:
                    try:
                        self.get_image(url, size)
                    except:
                        pass
        
        thread = threading.Thread(target=_preload, daemon=True)
        thread.start()
    
    def clear_cache(self):
        """Clear all cached images"""
        with self.lock:
            self.ctk_cache.clear()
            self.pil_cache.clear()
        
        self.cache.clear_cache()
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics
        
        Returns:
            Dict with cache stats
        """
        stats = self.cache.get_stats()
        
        with self.lock:
            stats['ctk_cached_images'] = len(self.ctk_cache)
        
        return stats
    
    def cleanup_old_images(self, days: int = 7):
        """
        Clean up images older than specified days
        
        Args:
            days: Number of days
        """
        self.cache.cleanup_old_images(days)


# Global image display manager
_image_manager = None


def get_image_manager() -> ImageDisplayManager:
    """
    Get the global image display manager
    
    Returns:
        ImageDisplayManager instance
    """
    global _image_manager
    if _image_manager is None:
        _image_manager = ImageDisplayManager()
    return _image_manager


# Convenience functions
def get_product_image(url: str, size: tuple = (80, 80)) -> ctk.CTkImage:
    """Get a product image for display"""
    return get_image_manager().get_image(url, size)


def get_product_image_async(url: str, callback, size: tuple = (80, 80)):
    """Get a product image asynchronously"""
    get_image_manager().get_image_async(url, callback, size)


def preload_product_images(urls: list, size: tuple = (80, 80)):
    """Preload multiple product images"""
    get_image_manager().preload_images(urls, size)


def clear_image_cache():
    """Clear the image cache"""
    get_image_manager().clear_cache()


def get_cache_stats() -> dict:
    """Get image cache statistics"""
    return get_image_manager().get_cache_stats()
