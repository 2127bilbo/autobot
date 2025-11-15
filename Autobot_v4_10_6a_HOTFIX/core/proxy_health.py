"""
Proxy Health Monitoring System for Autobot v4.4
Monitors proxy health, detects dead proxies, and auto-rotates

Features:
- Health check scheduler
- Response time monitoring
- Dead proxy detection
- Auto-rotation
- Statistics tracking
"""

import time
import requests
import threading
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from collections import deque


@dataclass
class ProxyHealth:
    """Health information for a single proxy"""
    proxy_url: str
    is_alive: bool = True
    last_check: float = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=10))
    total_checks: int = 0
    failed_checks: int = 0
    last_error: Optional[str] = None
    blacklisted: bool = False
    blacklist_reason: Optional[str] = None
    
    def average_response_time(self) -> float:
        """Get average response time"""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def success_rate(self) -> float:
        """Get success rate percentage"""
        if self.total_checks == 0:
            return 0.0
        return ((self.total_checks - self.failed_checks) / self.total_checks) * 100
    
    def is_healthy(self, max_response_time: float = 5.0, min_success_rate: float = 70.0) -> bool:
        """Check if proxy is healthy based on thresholds"""
        if self.blacklisted or not self.is_alive:
            return False
        
        avg_time = self.average_response_time()
        success = self.success_rate()
        
        return avg_time < max_response_time and success >= min_success_rate


class ProxyHealthMonitor:
    """
    Monitors proxy health and automatically rotates to healthy proxies
    
    Features:
    - Periodic health checks
    - Response time tracking
    - Dead proxy detection
    - Auto-removal of dead proxies
    - Statistics and analytics
    """
    
    def __init__(
        self,
        check_interval: int = 300,  # 5 minutes
        test_url: str = "https://www.google.com",
        timeout: int = 10,
        max_failures: int = 3
    ):
        self.check_interval = check_interval
        self.test_url = test_url
        self.timeout = timeout
        self.max_failures = max_failures
        
        self.logger = logging.getLogger(__name__)
        
        # Proxy health tracking
        self.proxies: Dict[str, ProxyHealth] = {}
        self.healthy_proxies: List[str] = []
        self.dead_proxies: List[str] = []
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.total_checks = 0
        self.total_removals = 0
        self.last_cleanup = time.time()
    
    def add_proxy(self, proxy_url: str):
        """Add a proxy to monitor"""
        if proxy_url not in self.proxies:
            self.proxies[proxy_url] = ProxyHealth(proxy_url=proxy_url)
            self.logger.info(f"Added proxy to monitoring: {proxy_url}")
    
    def remove_proxy(self, proxy_url: str):
        """Remove a proxy from monitoring"""
        if proxy_url in self.proxies:
            del self.proxies[proxy_url]
            if proxy_url in self.healthy_proxies:
                self.healthy_proxies.remove(proxy_url)
            if proxy_url in self.dead_proxies:
                self.dead_proxies.remove(proxy_url)
            self.logger.info(f"Removed proxy from monitoring: {proxy_url}")
    
    def check_proxy_health(self, proxy_url: str) -> Tuple[bool, float, Optional[str]]:
        """
        Check if a proxy is alive and measure response time
        
        Returns:
            (is_alive, response_time, error_message)
        """
        start_time = time.time()
        
        try:
            proxies = {
                "http": proxy_url,
                "https": proxy_url
            }
            
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            response_time = time.time() - start_time
            
            # Consider 2xx and 3xx as success
            is_alive = response.status_code < 400
            
            return is_alive, response_time, None
            
        except requests.exceptions.ProxyError as e:
            response_time = time.time() - start_time
            return False, response_time, f"Proxy error: {str(e)}"
        
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            return False, response_time, "Timeout"
        
        except requests.exceptions.ConnectionError as e:
            response_time = time.time() - start_time
            return False, response_time, f"Connection error: {str(e)}"
        
        except Exception as e:
            response_time = time.time() - start_time
            return False, response_time, f"Unknown error: {str(e)}"
    
    def update_proxy_health(self, proxy_url: str):
        """Update health status for a single proxy"""
        if proxy_url not in self.proxies:
            return
        
        health = self.proxies[proxy_url]
        
        # Check health
        is_alive, response_time, error = self.check_proxy_health(proxy_url)
        
        # Update stats
        health.total_checks += 1
        health.last_check = time.time()
        
        if is_alive:
            health.is_alive = True
            health.response_times.append(response_time)
            health.last_error = None
            
            # Add to healthy list if not already there
            if proxy_url not in self.healthy_proxies:
                self.healthy_proxies.append(proxy_url)
                self.logger.info(f"✅ Proxy recovered: {proxy_url} ({response_time:.2f}s)")
            
            # Remove from dead list
            if proxy_url in self.dead_proxies:
                self.dead_proxies.remove(proxy_url)
        else:
            health.failed_checks += 1
            health.last_error = error
            
            # Check if should be marked as dead
            if health.failed_checks >= self.max_failures:
                health.is_alive = False
                
                # Remove from healthy list
                if proxy_url in self.healthy_proxies:
                    self.healthy_proxies.remove(proxy_url)
                
                # Add to dead list
                if proxy_url not in self.dead_proxies:
                    self.dead_proxies.append(proxy_url)
                    self.logger.warning(f"❌ Proxy marked as dead: {proxy_url} (failures: {health.failed_checks})")
            else:
                self.logger.warning(f"⚠️ Proxy check failed: {proxy_url} ({error})")
        
        self.total_checks += 1
    
    def check_all_proxies(self):
        """Check health of all proxies"""
        if not self.proxies:
            self.logger.warning("No proxies to check")
            return
        
        self.logger.info(f"Checking health of {len(self.proxies)} proxies...")
        
        for proxy_url in list(self.proxies.keys()):
            self.update_proxy_health(proxy_url)
            time.sleep(0.5)  # Small delay between checks
        
        # Log summary
        healthy_count = len(self.healthy_proxies)
        dead_count = len(self.dead_proxies)
        self.logger.info(f"Health check complete: {healthy_count} healthy, {dead_count} dead")
    
    def auto_remove_dead_proxies(self):
        """Automatically remove dead proxies"""
        if not self.dead_proxies:
            return
        
        removed = []
        for proxy_url in list(self.dead_proxies):
            health = self.proxies.get(proxy_url)
            if health and not health.is_alive:
                self.remove_proxy(proxy_url)
                removed.append(proxy_url)
                self.total_removals += 1
        
        if removed:
            self.logger.info(f"🗑️ Auto-removed {len(removed)} dead proxies")
    
    def get_best_proxy(self) -> Optional[str]:
        """Get the best performing healthy proxy"""
        if not self.healthy_proxies:
            self.logger.warning("No healthy proxies available!")
            return None
        
        # Find proxy with best response time
        best_proxy = None
        best_time = float('inf')
        
        for proxy_url in self.healthy_proxies:
            health = self.proxies.get(proxy_url)
            if health and health.is_healthy():
                avg_time = health.average_response_time()
                if avg_time < best_time and avg_time > 0:
                    best_time = avg_time
                    best_proxy = proxy_url
        
        if best_proxy:
            self.logger.info(f"Best proxy: {best_proxy} ({best_time:.2f}s)")
        
        return best_proxy
    
    def get_random_healthy_proxy(self) -> Optional[str]:
        """Get a random healthy proxy"""
        if not self.healthy_proxies:
            return None
        
        import random
        return random.choice(self.healthy_proxies)
    
    def rotate_to_healthy_proxy(self, current_proxy: str) -> Optional[str]:
        """Rotate from current proxy to a different healthy one"""
        healthy_alternatives = [p for p in self.healthy_proxies if p != current_proxy]
        
        if not healthy_alternatives:
            self.logger.warning("No healthy alternative proxies available")
            return None
        
        new_proxy = self.get_best_proxy()
        if new_proxy == current_proxy and len(healthy_alternatives) > 1:
            # Pick a different one
            new_proxy = healthy_alternatives[0]
        
        self.logger.info(f"Rotated proxy: {current_proxy} → {new_proxy}")
        return new_proxy
    
    def start_monitoring(self):
        """Start continuous health monitoring"""
        if self.monitoring:
            self.logger.warning("Monitoring already running")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"Started proxy health monitoring (interval: {self.check_interval}s)")
    
    def stop_monitoring(self):
        """Stop continuous health monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Stopped proxy health monitoring")
    
    def _monitor_loop(self):
        """Continuous monitoring loop"""
        while self.monitoring:
            try:
                # Check all proxies
                self.check_all_proxies()
                
                # Auto-remove dead proxies
                self.auto_remove_dead_proxies()
                
                # Update last cleanup time
                self.last_cleanup = time.time()
                
                # Wait for next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics"""
        total_proxies = len(self.proxies)
        healthy_count = len(self.healthy_proxies)
        dead_count = len(self.dead_proxies)
        
        # Calculate average response time for healthy proxies
        avg_response_time = 0.0
        if self.healthy_proxies:
            times = []
            for proxy_url in self.healthy_proxies:
                health = self.proxies.get(proxy_url)
                if health:
                    avg_time = health.average_response_time()
                    if avg_time > 0:
                        times.append(avg_time)
            if times:
                avg_response_time = sum(times) / len(times)
        
        return {
            "total_proxies": total_proxies,
            "healthy_proxies": healthy_count,
            "dead_proxies": dead_count,
            "health_percentage": (healthy_count / total_proxies * 100) if total_proxies > 0 else 0,
            "average_response_time": avg_response_time,
            "total_checks": self.total_checks,
            "total_removals": self.total_removals,
            "monitoring_active": self.monitoring,
            "last_check": self.last_cleanup,
            "check_interval": self.check_interval
        }
    
    def get_proxy_details(self) -> List[Dict]:
        """Get detailed information about all proxies"""
        details = []
        
        for proxy_url, health in self.proxies.items():
            details.append({
                "proxy": proxy_url,
                "alive": health.is_alive,
                "healthy": health.is_healthy(),
                "avg_response_time": health.average_response_time(),
                "success_rate": health.success_rate(),
                "total_checks": health.total_checks,
                "failed_checks": health.failed_checks,
                "last_error": health.last_error,
                "blacklisted": health.blacklisted,
                "last_check": health.last_check
            })
        
        # Sort by success rate (best first)
        details.sort(key=lambda x: x['success_rate'], reverse=True)
        
        return details
    
    def blacklist_proxy(self, proxy_url: str, reason: str = "Manual blacklist"):
        """Manually blacklist a proxy"""
        if proxy_url in self.proxies:
            health = self.proxies[proxy_url]
            health.blacklisted = True
            health.blacklist_reason = reason
            health.is_alive = False
            
            if proxy_url in self.healthy_proxies:
                self.healthy_proxies.remove(proxy_url)
            if proxy_url not in self.dead_proxies:
                self.dead_proxies.append(proxy_url)
            
            self.logger.warning(f"🚫 Blacklisted proxy: {proxy_url} ({reason})")
    
    def unblacklist_proxy(self, proxy_url: str):
        """Remove proxy from blacklist"""
        if proxy_url in self.proxies:
            health = self.proxies[proxy_url]
            health.blacklisted = False
            health.blacklist_reason = None
            health.failed_checks = 0  # Reset failures
            
            # Re-check immediately
            self.update_proxy_health(proxy_url)
            
            self.logger.info(f"✅ Removed from blacklist: {proxy_url}")


# Convenience function
def create_proxy_monitor(
    proxies: List[str],
    check_interval: int = 300,
    auto_start: bool = True
) -> ProxyHealthMonitor:
    """Quick setup for proxy health monitoring"""
    monitor = ProxyHealthMonitor(check_interval=check_interval)
    
    for proxy in proxies:
        monitor.add_proxy(proxy)
    
    if auto_start:
        monitor.start_monitoring()
    
    return monitor


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test proxies (replace with real proxies)
    test_proxies = [
        "http://proxy1.example.com:8080",
        "http://proxy2.example.com:8080",
        "http://proxy3.example.com:8080"
    ]
    
    # Create monitor
    monitor = ProxyHealthMonitor(check_interval=60)
    
    # Add proxies
    for proxy in test_proxies:
        monitor.add_proxy(proxy)
    
    # Check health once
    print("\nChecking proxy health...")
    monitor.check_all_proxies()
    
    # Get statistics
    stats = monitor.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total proxies: {stats['total_proxies']}")
    print(f"  Healthy: {stats['healthy_proxies']}")
    print(f"  Dead: {stats['dead_proxies']}")
    print(f"  Health: {stats['health_percentage']:.1f}%")
    
    # Get best proxy
    best = monitor.get_best_proxy()
    print(f"\nBest proxy: {best}")
    
    # Get details
    print("\nProxy details:")
    for detail in monitor.get_proxy_details():
        print(f"  {detail['proxy']}")
        print(f"    Alive: {detail['alive']}")
        print(f"    Success rate: {detail['success_rate']:.1f}%")
        print(f"    Avg response: {detail['avg_response_time']:.2f}s")
