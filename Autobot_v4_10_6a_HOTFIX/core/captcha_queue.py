"""
Autobot Captcha Queue System
Handles manual captcha harvesting and distribution to tasks
"""

import threading
import time
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from collections import deque
import uuid


@dataclass
class CaptchaToken:
    """Individual captcha token"""
    token: str
    site: str
    harvested_at: datetime
    expires_at: datetime
    used: bool = False
    used_by: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return datetime.now() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid and usable"""
        return not self.used and not self.is_expired()


@dataclass
class CaptchaRequest:
    """Request for a captcha token from a task"""
    request_id: str
    task_id: str
    site: str
    requested_at: datetime
    timeout: int = 120  # 2 minutes default timeout
    
    def is_timed_out(self) -> bool:
        """Check if request has timed out"""
        return datetime.now() > (self.requested_at + timedelta(seconds=self.timeout))


class CaptchaQueue:
    """
    Manages captcha token pool and distribution
    Supports manual harvesting and task requests
    """
    
    def __init__(self, token_lifetime: int = 120):
        """
        Initialize captcha queue
        
        Args:
            token_lifetime: How long tokens remain valid (seconds)
        """
        self.token_lifetime = token_lifetime
        
        # Token storage
        self.tokens: Dict[str, CaptchaToken] = {}
        self._pending_requests: Dict[str, CaptchaRequest] = {}  # Renamed to avoid conflict
        
        # Site-specific queues
        self.site_queues: Dict[str, deque] = {
            'Target': deque(),
            'Walmart': deque(),
            'Pokemon Center': deque()
        }
        
        # Statistics
        self.total_harvested = 0
        self.total_used = 0
        self.total_expired = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_expired,
            daemon=True
        )
        self.cleanup_thread.start()
    
    def add_token(self, token: str, site: str) -> str:
        """
        Add a manually harvested token to the queue
        
        Args:
            token: The captcha token string
            site: Which site this token is for
            
        Returns:
            token_id: Unique identifier for this token
        """
        with self.lock:
            token_id = str(uuid.uuid4())
            
            captcha_token = CaptchaToken(
                token=token,
                site=site,
                harvested_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=self.token_lifetime)
            )
            
            self.tokens[token_id] = captcha_token
            self.site_queues[site].append(token_id)
            self.total_harvested += 1
            
            # Check if any pending requests can be fulfilled
            self._try_fulfill_requests(site)
            
            return token_id
    
    def request_token(self, task_id: str, site: str, timeout: int = 120) -> Optional[str]:
        """
        Request a captcha token (blocking with timeout)
        
        Args:
            task_id: ID of the task requesting the token
            site: Which site needs the token
            timeout: How long to wait for a token
            
        Returns:
            token: The captcha token string, or None if timeout
        """
        request_id = str(uuid.uuid4())
        
        request = CaptchaRequest(
            request_id=request_id,
            task_id=task_id,
            site=site,
            requested_at=datetime.now(),
            timeout=timeout
        )
        
        with self.lock:
            # Try to get a token immediately
            token = self._get_token_for_site(site)
            if token:
                return token
            
            # Add to pending requests
            self._pending_requests[request_id] = request
        
        # Wait for token to become available
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.lock:
                # Check if request was fulfilled
                if request_id not in self._pending_requests:
                    # Token was assigned
                    token_id = self._find_token_for_task(task_id)
                    if token_id:
                        return self.tokens[token_id].token
                
                # Check if request timed out
                if request.is_timed_out():
                    self._pending_requests.pop(request_id, None)
                    return None
            
            time.sleep(0.5)
        
        # Timeout
        with self.lock:
            self._pending_requests.pop(request_id, None)
        return None
    
    def _get_token_for_site(self, site: str) -> Optional[str]:
        """Get an available token for a site (internal, must hold lock)"""
        queue = self.site_queues.get(site)
        if not queue:
            return None
        
        # Find first valid token
        while queue:
            token_id = queue.popleft()
            token = self.tokens.get(token_id)
            
            if token and token.is_valid():
                token.used = True
                self.total_used += 1
                return token.token
            else:
                # Token expired or invalid
                if token:
                    self.tokens.pop(token_id, None)
        
        return None
    
    def _find_token_for_task(self, task_id: str) -> Optional[str]:
        """Find a token assigned to a specific task"""
        for token_id, token in self.tokens.items():
            if token.used_by == task_id:
                return token_id
        return None
    
    def _try_fulfill_requests(self, site: str):
        """Try to fulfill pending requests for a site (internal, must hold lock)"""
        # Get all pending requests for this site
        site_requests = [
            (req_id, req) for req_id, req in self._pending_requests.items()
            if req.site == site and not req.is_timed_out()
        ]
        
        # Fulfill as many as possible
        for req_id, request in site_requests:
            token_id = self._get_token_for_site(site)
            if token_id:
                # Assign token to task
                token = self.tokens.get(token_id)
                if token:
                    token.used_by = request.task_id
                    self._pending_requests.pop(req_id)
            else:
                break  # No more tokens available
    
    def _cleanup_expired(self):
        """Background thread to clean up expired tokens"""
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            with self.lock:
                expired_ids = []
                
                for token_id, token in self.tokens.items():
                    if token.is_expired() and not token.used:
                        expired_ids.append(token_id)
                
                for token_id in expired_ids:
                    self.tokens.pop(token_id, None)
                    self.total_expired += len(expired_ids)
                
                # Remove from queues
                for site, queue in self.site_queues.items():
                    self.site_queues[site] = deque([
                        tid for tid in queue if tid not in expired_ids
                    ])
    
    def get_available_count(self, site: str) -> int:
        """Get number of available tokens for a site"""
        with self.lock:
            count = 0
            for token_id in self.site_queues.get(site, []):
                token = self.tokens.get(token_id)
                if token and token.is_valid():
                    count += 1
            return count
    
    def get_pending_count(self, site: str) -> int:
        """Get number of pending requests for a site"""
        with self.lock:
            return sum(1 for req in self._pending_requests.values() 
                      if req.site == site)
    
    def get_statistics(self) -> Dict:
        """Get queue statistics"""
        with self.lock:
            site_stats = {}
            for site in self.site_queues.keys():
                site_stats[site] = {
                    'available': self.get_available_count(site),
                    'pending': self.get_pending_count(site)
                }
            
            return {
                'total_harvested': self.total_harvested,
                'total_used': self.total_used,
                'total_expired': self.total_expired,
                'active_tokens': len([t for t in self.tokens.values() if t.is_valid()]),
                'pending_requests': len(self._pending_requests),
                'sites': site_stats
            }
    
    def clear_site_tokens(self, site: str):
        """Clear all tokens for a specific site"""
        with self.lock:
            queue = self.site_queues.get(site, deque())
            for token_id in list(queue):
                self.tokens.pop(token_id, None)
            self.site_queues[site] = deque()
    
    def clear_all_tokens(self):
        """Clear all tokens from all sites"""
        with self.lock:
            self.tokens.clear()
            for site in self.site_queues.keys():
                self.site_queues[site] = deque()
    
    # UI compatibility methods
    def queue_size(self) -> int:
        """Get total number of tokens in queue (UI method)"""
        with self.lock:
            return len([t for t in self.tokens.values() if t.is_valid()])
    
    def pending_requests(self) -> int:
        """Get number of pending requests (UI method)"""
        with self.lock:
            return len(self._pending_requests)
    
    def tokens_available(self) -> int:
        """Get number of available tokens (UI method)"""
        return self.queue_size()


# Global captcha queue instance
captcha_queue = CaptchaQueue()
