"""
Autobot Smart Ban Detection & Auto-Recovery
Phase 1A - Core Intelligence
Detects bans, clears cookies/cache, implements adaptive cooldown
"""

import time
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import re


class BanDetector:
    """Detects bans and implements auto-recovery strategies"""
    
    # Ban detection patterns
    BAN_PATTERNS = [
        # Access denied patterns
        r'access\s+denied',
        r'forbidden',
        r'403\s+forbidden',
        r'you\s+don\'?t\s+have\s+permission',
        r'unauthorized\s+access',
        
        # Rate limiting patterns
        r'too\s+many\s+requests',
        r'rate\s+limit(?!ed\s+edition)',  # Avoid "Limited Edition" products
        r'slow\s+down',
        r'429\s+too\s+many',
        
        # Captcha patterns (strict matching)
        r'please\s+complete.*captcha',
        r'recaptcha',
        r'bot\s+detection',
        r'verify.*you.*human',
        r'security\s+check.*required',
        
        # IP/Session blocks (stricter patterns)
        r'ip.*blocked',
        r'ip.*ban',
        r'temporary\s+block',
        r'suspicious\s+activity\s+detected',
        r'unusual\s+traffic\s+detected',
        r'blocked\s+due\s+to',
        r'your\s+access.*blocked',
    ]
    
    # Patterns that should NOT trigger bans (legitimate messages)
    SAFE_PATTERNS = [
        r'out\s+of\s+stock',
        r'sold\s+out',
        r'temporarily\s+unavailable',
        r'not\s+available',
        r'item.*not.*found',
        r'cart.*empty',
        r'no\s+items',
        r'high\s+demand',  # High demand is NOT a ban
        r'limited\s+quantity',
        r'please\s+wait',  # Queue waiting is not a ban
        r'queue',  # Queue pages are not bans
        r'in\s+line',
        r'add.*cart',  # "Add to cart" buttons
        r'checkout',  # Checkout pages
        r'payment',  # Payment pages
        r'shipping',  # Shipping pages
    ]
    
    # Adaptive cooldown stages (in seconds)
    COOLDOWN_STAGES = [10, 30, 60, 120]  # 10s → 30s → 60s → 2min
    
    # Ban counter reset time (1 hour)
    RESET_TIME = 3600  # seconds
    
    def __init__(self, monitor_id: str, db_manager=None):
        """
        Initialize ban detector for a monitor
        
        Args:
            monitor_id: Unique monitor identifier
            db_manager: Database manager for tracking history
        """
        self.monitor_id = monitor_id
        self.db_manager = db_manager
        
        # Ban tracking
        self.ban_count = 0
        self.last_ban_time = None
        self.current_cooldown = 0
        self.recovery_in_progress = False
        
        # Detection state
        self.consecutive_errors = 0
        self.last_detection_time = None
        
    def detect_ban(self, response_text: str = "", status_code: int = 200,
                   error_message: str = "") -> bool:
        """
        Detect if a ban/block has occurred
        
        Args:
            response_text: HTML response text
            status_code: HTTP status code
            error_message: Error message if any
            
        Returns:
            True if ban detected, False otherwise
        """
        ban_detected = False
        ban_type = "unknown"
        
        # First, check if this is a safe/legitimate message (NOT a ban)
        combined_text = f"{response_text} {error_message}".lower()
        for safe_pattern in self.SAFE_PATTERNS:
            if re.search(safe_pattern, combined_text, re.IGNORECASE):
                # This is a legitimate message, not a ban
                self.consecutive_errors = 0  # Reset error counter
                return False
        
        # Check HTTP status codes (explicit bans only)
        if status_code in [403, 429]:  # Removed 503 - it's often just temporary
            ban_detected = True
            ban_type = f"http_{status_code}"
            self.consecutive_errors = 0  # Reset since this is explicit
        
        # Check response text for ban patterns (only if no safe pattern matched)
        if not ban_detected and response_text:
            response_lower = response_text.lower()
            for pattern in self.BAN_PATTERNS:
                if re.search(pattern, response_lower, re.IGNORECASE):
                    ban_detected = True
                    ban_type = "pattern_match"
                    break
        
        # Check error messages (strict matching)
        if not ban_detected and error_message:
            error_lower = error_message.lower()
            # Only count as ban if explicitly mentioned
            if any(word in error_lower for word in ['ip blocked', 'account blocked', 'captcha required']):
                ban_detected = True
                ban_type = "error_message"
        
        # Track consecutive errors (increased to 15 to reduce false positives)
        # Only count errors that aren't explicit bans
        if not ban_detected and (status_code >= 400 or error_message):
            self.consecutive_errors += 1
            # Require 15 consecutive errors before treating as ban
            if self.consecutive_errors >= 15:
                ban_detected = True
                ban_type = "consecutive_errors"
                print(f"[BAN] {self.monitor_id}: 15 consecutive errors - treating as soft ban")
        elif not ban_detected:
            # Successful request - reset counter
            self.consecutive_errors = 0
        
        if ban_detected:
            self._handle_ban_detection(ban_type)
            
        return ban_detected
    
    def _handle_ban_detection(self, ban_type: str):
        """
        Handle ban detection - increment counter, update cooldown
        
        Args:
            ban_type: Type of ban detected
        """
        detection_time = datetime.now()
        
        # Reset ban counter if more than 1 hour since last ban
        if self.last_ban_time:
            time_since_last = (detection_time - self.last_ban_time).total_seconds()
            if time_since_last > self.RESET_TIME:
                print(f"[BAN] Monitor {self.monitor_id}: Ban counter reset (1+ hour clean)")
                self.ban_count = 0
        
        # Increment ban counter
        self.ban_count += 1
        self.last_ban_time = detection_time
        self.last_detection_time = detection_time
        
        # Calculate adaptive cooldown based on ban count
        stage_index = min(self.ban_count - 1, len(self.COOLDOWN_STAGES) - 1)
        self.current_cooldown = self.COOLDOWN_STAGES[stage_index]
        
        print(f"[BAN] Monitor {self.monitor_id}: Ban #{self.ban_count} detected ({ban_type})")
        print(f"[BAN] Cooldown: {self.current_cooldown}s")
        
        # Save to database if available
        if self.db_manager:
            self._save_ban_history(ban_type)
    
    def _save_ban_history(self, ban_type: str):
        """
        Save ban detection to database
        
        Args:
            ban_type: Type of ban detected
        """
        try:
            if self.db_manager:
                # Save ban event to database
                self.db_manager.execute(
                    """
                    INSERT INTO ban_history 
                    (monitor_id, ban_type, ban_count, cooldown_applied, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.monitor_id,
                        ban_type,
                        self.ban_count,
                        self.current_cooldown,
                        'detected'
                    )
                )
                print(f"[BAN] Saved to database: {self.monitor_id} - {ban_type}")
        except Exception as e:
            print(f"[BAN] Failed to save ban history: {e}")
    
    def clear_cookies(self, browser_context=None):
        """
        Clear browser cookies for this monitor
        
        Args:
            browser_context: Playwright browser context (if available)
        """
        try:
            if browser_context:
                # Clear cookies from Playwright context
                browser_context.clear_cookies()
                print(f"[BAN] Monitor {self.monitor_id}: Cookies cleared (Playwright)")
            else:
                # Clear any stored session cookies from cache
                cache_dir = Path("cache/sessions")
                if cache_dir.exists():
                    session_file = cache_dir / f"{self.monitor_id}_cookies.json"
                    if session_file.exists():
                        session_file.unlink()
                        print(f"[BAN] Monitor {self.monitor_id}: Session cookies cleared")
        except Exception as e:
            print(f"[BAN] Failed to clear cookies: {e}")
    
    def clear_cache(self):
        """Clear browser cache for this monitor"""
        try:
            # Clear Playwright cache
            cache_dir = Path("cache/playwright")
            if cache_dir.exists():
                monitor_cache = cache_dir / self.monitor_id
                if monitor_cache.exists():
                    shutil.rmtree(monitor_cache)
                    print(f"[BAN] Monitor {self.monitor_id}: Browser cache cleared")
            
            # Clear any stored data cache
            data_cache_dir = Path("cache/data")
            if data_cache_dir.exists():
                data_file = data_cache_dir / f"{self.monitor_id}_data.json"
                if data_file.exists():
                    data_file.unlink()
                    print(f"[BAN] Monitor {self.monitor_id}: Data cache cleared")
        except Exception as e:
            print(f"[BAN] Failed to clear cache: {e}")
    
    def recover_from_ban(self, browser_context=None) -> bool:
        """
        Execute full recovery workflow
        
        Args:
            browser_context: Playwright browser context (if available)
            
        Returns:
            True if recovery initiated successfully
        """
        if self.recovery_in_progress:
            return False
        
        try:
            self.recovery_in_progress = True
            recovery_start = time.time()
            
            print(f"[BAN] Monitor {self.monitor_id}: Starting recovery workflow")
            
            # Step 1: Clear cookies
            self.clear_cookies(browser_context)
            time.sleep(0.5)
            
            # Step 2: Clear cache
            self.clear_cache()
            time.sleep(0.5)
            
            # Step 3: Apply cooldown
            print(f"[BAN] Monitor {self.monitor_id}: Applying {self.current_cooldown}s cooldown")
            time.sleep(self.current_cooldown)
            
            recovery_time = time.time() - recovery_start
            print(f"[BAN] Monitor {self.monitor_id}: Recovery complete ({recovery_time:.1f}s)")
            
            self.recovery_in_progress = False
            return True
            
        except Exception as e:
            print(f"[BAN] Recovery failed: {e}")
            self.recovery_in_progress = False
            return False
    
    def get_cooldown_seconds(self) -> int:
        """
        Get current cooldown duration in seconds
        
        Returns:
            Cooldown duration in seconds
        """
        return self.current_cooldown
    
    def get_ban_stats(self) -> Dict:
        """
        Get ban detection statistics
        
        Returns:
            Dictionary with ban statistics
        """
        return {
            'ban_count': self.ban_count,
            'current_cooldown': self.current_cooldown,
            'last_ban_time': self.last_ban_time.isoformat() if self.last_ban_time else None,
            'recovery_in_progress': self.recovery_in_progress,
            'consecutive_errors': self.consecutive_errors
        }
    
    def should_check_now(self) -> bool:
        """
        Check if enough time has passed since last ban
        
        Returns:
            True if monitor can proceed with check
        """
        if not self.last_detection_time:
            return True
        
        time_since_detection = (datetime.now() - self.last_detection_time).total_seconds()
        return time_since_detection >= self.current_cooldown


class BanDetectorPool:
    """Manages ban detectors for all monitors"""
    
    def __init__(self, db_manager=None):
        """
        Initialize ban detector pool
        
        Args:
            db_manager: Database manager for tracking history
        """
        self.db_manager = db_manager
        self.detectors: Dict[str, BanDetector] = {}
    
    def get_detector(self, monitor_id: str) -> BanDetector:
        """
        Get or create ban detector for a monitor
        
        Args:
            monitor_id: Monitor identifier
            
        Returns:
            BanDetector instance
        """
        if monitor_id not in self.detectors:
            self.detectors[monitor_id] = BanDetector(monitor_id, self.db_manager)
        return self.detectors[monitor_id]
    
    def remove_detector(self, monitor_id: str):
        """
        Remove ban detector for a monitor
        
        Args:
            monitor_id: Monitor identifier
        """
        if monitor_id in self.detectors:
            del self.detectors[monitor_id]
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Get ban statistics for all monitors
        
        Returns:
            Dictionary of monitor_id -> ban stats
        """
        return {
            monitor_id: detector.get_ban_stats()
            for monitor_id, detector in self.detectors.items()
        }


# Global ban detector pool
_ban_detector_pool = None


def get_ban_detector_pool(db_manager=None) -> BanDetectorPool:
    """
    Get global ban detector pool instance
    
    Args:
        db_manager: Database manager (optional)
        
    Returns:
        BanDetectorPool instance
    """
    global _ban_detector_pool
    if _ban_detector_pool is None:
        _ban_detector_pool = BanDetectorPool(db_manager)
    return _ban_detector_pool
