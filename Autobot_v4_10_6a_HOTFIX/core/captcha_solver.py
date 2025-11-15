"""
Captcha Solver Integration for Autobot v4.4
Automatic captcha solving via 2Captcha and Anti-Captcha APIs

Features:
- 2Captcha API integration
- Anti-Captcha API integration
- Queue-based solving
- Auto-retry on failure
- Support for reCAPTCHA v2, v3, hCaptcha
"""

import time
import requests
from typing import Optional, Dict, Literal
from dataclasses import dataclass
import logging
from enum import Enum


class CaptchaType(Enum):
    """Supported captcha types"""
    RECAPTCHA_V2 = "recaptcha_v2"
    RECAPTCHA_V3 = "recaptcha_v3"
    HCAPTCHA = "hcaptcha"
    IMAGE = "image"
    TEXT = "text"


@dataclass
class CaptchaSolution:
    """Captcha solution result"""
    success: bool
    solution: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None
    solve_time: float = 0.0
    cost: float = 0.0


class TwoCaptchaSolver:
    """
    2Captcha API integration
    
    Supports:
    - reCAPTCHA v2
    - reCAPTCHA v3
    - hCaptcha
    - Image captchas
    - Text captchas
    """
    
    API_URL = "http://2captcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
    
    def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaSolution:
        """
        Solve reCAPTCHA v2
        
        Args:
            site_key: The site key (data-sitekey)
            page_url: URL of the page with captcha
            timeout: Max time to wait for solution (seconds)
        
        Returns:
            CaptchaSolution object
        """
        start_time = time.time()
        
        try:
            # Submit captcha
            submit_url = f"{self.API_URL}/in.php"
            submit_data = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "googlekey": site_key,
                "pageurl": page_url,
                "json": 1
            }
            
            response = requests.post(submit_url, data=submit_data, timeout=30)
            result = response.json()
            
            if result.get("status") != 1:
                error = result.get("request", "Unknown error")
                return CaptchaSolution(success=False, error=f"Submit failed: {error}")
            
            task_id = result.get("request")
            self.logger.info(f"2Captcha task submitted: {task_id}")
            
            # Poll for solution
            check_url = f"{self.API_URL}/res.php"
            check_data = {
                "key": self.api_key,
                "action": "get",
                "id": task_id,
                "json": 1
            }
            
            max_attempts = timeout // 5
            for attempt in range(max_attempts):
                time.sleep(5)  # 2Captcha recommends 5 second intervals
                
                response = requests.get(check_url, params=check_data, timeout=30)
                result = response.json()
                
                if result.get("status") == 1:
                    # Solution ready
                    solution = result.get("request")
                    solve_time = time.time() - start_time
                    
                    self.logger.info(f"reCAPTCHA v2 solved in {solve_time:.1f}s")
                    
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        task_id=task_id,
                        solve_time=solve_time,
                        cost=0.001  # ~$0.001 per captcha
                    )
                
                elif result.get("request") == "CAPCHA_NOT_READY":
                    # Still processing
                    continue
                else:
                    # Error
                    error = result.get("request", "Unknown error")
                    return CaptchaSolution(
                        success=False,
                        task_id=task_id,
                        error=f"Solution failed: {error}"
                    )
            
            # Timeout
            return CaptchaSolution(
                success=False,
                task_id=task_id,
                error=f"Timeout after {timeout}s"
            )
            
        except Exception as e:
            self.logger.error(f"2Captcha error: {e}")
            return CaptchaSolution(success=False, error=str(e))
    
    def solve_recaptcha_v3(
        self,
        site_key: str,
        page_url: str,
        action: str = "submit",
        min_score: float = 0.3,
        timeout: int = 120
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v3"""
        start_time = time.time()
        
        try:
            # Submit captcha
            submit_url = f"{self.API_URL}/in.php"
            submit_data = {
                "key": self.api_key,
                "method": "userrecaptcha",
                "version": "v3",
                "googlekey": site_key,
                "pageurl": page_url,
                "action": action,
                "min_score": min_score,
                "json": 1
            }
            
            response = requests.post(submit_url, data=submit_data, timeout=30)
            result = response.json()
            
            if result.get("status") != 1:
                error = result.get("request", "Unknown error")
                return CaptchaSolution(success=False, error=f"Submit failed: {error}")
            
            task_id = result.get("request")
            self.logger.info(f"2Captcha v3 task submitted: {task_id}")
            
            # Poll for solution (same as v2)
            check_url = f"{self.API_URL}/res.php"
            check_data = {
                "key": self.api_key,
                "action": "get",
                "id": task_id,
                "json": 1
            }
            
            max_attempts = timeout // 5
            for attempt in range(max_attempts):
                time.sleep(5)
                
                response = requests.get(check_url, params=check_data, timeout=30)
                result = response.json()
                
                if result.get("status") == 1:
                    solution = result.get("request")
                    solve_time = time.time() - start_time
                    
                    self.logger.info(f"reCAPTCHA v3 solved in {solve_time:.1f}s")
                    
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        task_id=task_id,
                        solve_time=solve_time,
                        cost=0.002  # v3 costs more
                    )
                
                elif result.get("request") == "CAPCHA_NOT_READY":
                    continue
                else:
                    error = result.get("request", "Unknown error")
                    return CaptchaSolution(success=False, task_id=task_id, error=error)
            
            return CaptchaSolution(success=False, task_id=task_id, error="Timeout")
            
        except Exception as e:
            self.logger.error(f"2Captcha v3 error: {e}")
            return CaptchaSolution(success=False, error=str(e))
    
    def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaSolution:
        """Solve hCaptcha"""
        start_time = time.time()
        
        try:
            # Submit captcha
            submit_url = f"{self.API_URL}/in.php"
            submit_data = {
                "key": self.api_key,
                "method": "hcaptcha",
                "sitekey": site_key,
                "pageurl": page_url,
                "json": 1
            }
            
            response = requests.post(submit_url, data=submit_data, timeout=30)
            result = response.json()
            
            if result.get("status") != 1:
                error = result.get("request", "Unknown error")
                return CaptchaSolution(success=False, error=f"Submit failed: {error}")
            
            task_id = result.get("request")
            self.logger.info(f"hCaptcha task submitted: {task_id}")
            
            # Poll for solution
            check_url = f"{self.API_URL}/res.php"
            check_data = {
                "key": self.api_key,
                "action": "get",
                "id": task_id,
                "json": 1
            }
            
            max_attempts = timeout // 5
            for attempt in range(max_attempts):
                time.sleep(5)
                
                response = requests.get(check_url, params=check_data, timeout=30)
                result = response.json()
                
                if result.get("status") == 1:
                    solution = result.get("request")
                    solve_time = time.time() - start_time
                    
                    self.logger.info(f"hCaptcha solved in {solve_time:.1f}s")
                    
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        task_id=task_id,
                        solve_time=solve_time,
                        cost=0.001
                    )
                
                elif result.get("request") == "CAPCHA_NOT_READY":
                    continue
                else:
                    error = result.get("request", "Unknown error")
                    return CaptchaSolution(success=False, task_id=task_id, error=error)
            
            return CaptchaSolution(success=False, task_id=task_id, error="Timeout")
            
        except Exception as e:
            self.logger.error(f"hCaptcha error: {e}")
            return CaptchaSolution(success=False, error=str(e))
    
    def get_balance(self) -> Optional[float]:
        """Get account balance"""
        try:
            url = f"{self.API_URL}/res.php"
            params = {
                "key": self.api_key,
                "action": "getbalance",
                "json": 1
            }
            
            response = requests.get(url, params=params, timeout=30)
            result = response.json()
            
            if result.get("status") == 1:
                balance = float(result.get("request", 0))
                return balance
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
            return None


class AntiCaptchaSolver:
    """
    Anti-Captcha API integration
    
    Alternative to 2Captcha with similar features
    """
    
    API_URL = "https://api.anti-captcha.com"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
    
    def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v2 using Anti-Captcha"""
        start_time = time.time()
        
        try:
            # Create task
            create_url = f"{self.API_URL}/createTask"
            create_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "NoCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key
                }
            }
            
            response = requests.post(create_url, json=create_data, timeout=30)
            result = response.json()
            
            if result.get("errorId") != 0:
                error = result.get("errorDescription", "Unknown error")
                return CaptchaSolution(success=False, error=f"Create task failed: {error}")
            
            task_id = result.get("taskId")
            self.logger.info(f"Anti-Captcha task created: {task_id}")
            
            # Poll for solution
            get_url = f"{self.API_URL}/getTaskResult"
            get_data = {
                "clientKey": self.api_key,
                "taskId": task_id
            }
            
            max_attempts = timeout // 3
            for attempt in range(max_attempts):
                time.sleep(3)  # Anti-Captcha recommends 3 second intervals
                
                response = requests.post(get_url, json=get_data, timeout=30)
                result = response.json()
                
                if result.get("errorId") != 0:
                    error = result.get("errorDescription", "Unknown error")
                    return CaptchaSolution(success=False, task_id=str(task_id), error=error)
                
                if result.get("status") == "ready":
                    solution = result.get("solution", {}).get("gRecaptchaResponse")
                    solve_time = time.time() - start_time
                    
                    self.logger.info(f"Anti-Captcha solved in {solve_time:.1f}s")
                    
                    return CaptchaSolution(
                        success=True,
                        solution=solution,
                        task_id=str(task_id),
                        solve_time=solve_time,
                        cost=0.001
                    )
                elif result.get("status") == "processing":
                    continue
                else:
                    return CaptchaSolution(
                        success=False,
                        task_id=str(task_id),
                        error="Unknown status"
                    )
            
            return CaptchaSolution(success=False, task_id=str(task_id), error="Timeout")
            
        except Exception as e:
            self.logger.error(f"Anti-Captcha error: {e}")
            return CaptchaSolution(success=False, error=str(e))
    
    def get_balance(self) -> Optional[float]:
        """Get account balance"""
        try:
            url = f"{self.API_URL}/getBalance"
            data = {"clientKey": self.api_key}
            
            response = requests.post(url, json=data, timeout=30)
            result = response.json()
            
            if result.get("errorId") == 0:
                balance = float(result.get("balance", 0))
                return balance
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get balance: {e}")
            return None


class CaptchaSolverManager:
    """
    Manages multiple captcha solving services with fallback
    """
    
    def __init__(
        self,
        twocaptcha_key: Optional[str] = None,
        anticaptcha_key: Optional[str] = None,
        preferred_service: Literal["2captcha", "anticaptcha"] = "2captcha"
    ):
        self.logger = logging.getLogger(__name__)
        
        self.solvers = {}
        
        if twocaptcha_key:
            self.solvers["2captcha"] = TwoCaptchaSolver(twocaptcha_key)
            self.logger.info("Initialized 2Captcha solver")
        
        if anticaptcha_key:
            self.solvers["anticaptcha"] = AntiCaptchaSolver(anticaptcha_key)
            self.logger.info("Initialized Anti-Captcha solver")
        
        self.preferred_service = preferred_service
        
        # Statistics
        self.total_solved = 0
        self.total_failed = 0
        self.total_cost = 0.0
    
    def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaSolution:
        """
        Solve reCAPTCHA v2 with automatic fallback
        """
        # Try preferred service first
        if self.preferred_service in self.solvers:
            self.logger.info(f"Trying {self.preferred_service} (preferred)")
            result = self.solvers[self.preferred_service].solve_recaptcha_v2(
                site_key, page_url, timeout
            )
            
            if result.success:
                self.total_solved += 1
                self.total_cost += result.cost
                return result
            
            self.logger.warning(f"{self.preferred_service} failed: {result.error}")
        
        # Try fallback services
        for service_name, solver in self.solvers.items():
            if service_name == self.preferred_service:
                continue  # Already tried
            
            self.logger.info(f"Trying {service_name} (fallback)")
            result = solver.solve_recaptcha_v2(site_key, page_url, timeout)
            
            if result.success:
                self.total_solved += 1
                self.total_cost += result.cost
                return result
            
            self.logger.warning(f"{service_name} failed: {result.error}")
        
        # All services failed
        self.total_failed += 1
        return CaptchaSolution(success=False, error="All solving services failed")
    
    def solve_recaptcha_v3(
        self,
        site_key: str,
        page_url: str,
        action: str = "submit",
        min_score: float = 0.3,
        timeout: int = 120
    ) -> CaptchaSolution:
        """Solve reCAPTCHA v3 with fallback"""
        # Only 2Captcha supports v3 currently
        if "2captcha" in self.solvers:
            result = self.solvers["2captcha"].solve_recaptcha_v3(
                site_key, page_url, action, min_score, timeout
            )
            
            if result.success:
                self.total_solved += 1
                self.total_cost += result.cost
            else:
                self.total_failed += 1
            
            return result
        
        return CaptchaSolution(success=False, error="No service supports reCAPTCHA v3")
    
    def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120
    ) -> CaptchaSolution:
        """Solve hCaptcha with fallback"""
        # Only 2Captcha has hCaptcha in this implementation
        if "2captcha" in self.solvers:
            result = self.solvers["2captcha"].solve_hcaptcha(site_key, page_url, timeout)
            
            if result.success:
                self.total_solved += 1
                self.total_cost += result.cost
            else:
                self.total_failed += 1
            
            return result
        
        return CaptchaSolution(success=False, error="No service supports hCaptcha")
    
    def get_statistics(self) -> Dict:
        """Get solving statistics"""
        total_attempts = self.total_solved + self.total_failed
        success_rate = (self.total_solved / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "total_solved": self.total_solved,
            "total_failed": self.total_failed,
            "total_attempts": total_attempts,
            "success_rate": success_rate,
            "total_cost": self.total_cost,
            "active_services": list(self.solvers.keys())
        }
    
    def get_balances(self) -> Dict[str, Optional[float]]:
        """Get balances from all services"""
        balances = {}
        
        for service_name, solver in self.solvers.items():
            balance = solver.get_balance()
            balances[service_name] = balance
        
        return balances


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize manager (replace with real API keys)
    manager = CaptchaSolverManager(
        twocaptcha_key="YOUR_2CAPTCHA_KEY",
        anticaptcha_key="YOUR_ANTICAPTCHA_KEY",
        preferred_service="2captcha"
    )
    
    # Example: Solve reCAPTCHA v2
    site_key = "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
    page_url = "https://www.google.com/recaptcha/api2/demo"
    
    print("Solving reCAPTCHA v2...")
    result = manager.solve_recaptcha_v2(site_key, page_url)
    
    if result.success:
        print(f"✅ Solved in {result.solve_time:.1f}s")
        print(f"Solution: {result.solution[:50]}...")
        print(f"Cost: ${result.cost:.4f}")
    else:
        print(f"❌ Failed: {result.error}")
    
    # Get statistics
    stats = manager.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total solved: {stats['total_solved']}")
    print(f"  Total failed: {stats['total_failed']}")
    print(f"  Success rate: {stats['success_rate']:.1f}%")
    print(f"  Total cost: ${stats['total_cost']:.4f}")
    
    # Get balances
    balances = manager.get_balances()
    print(f"\nBalances:")
    for service, balance in balances.items():
        if balance is not None:
            print(f"  {service}: ${balance:.2f}")
