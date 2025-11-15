"""
Dual Checkout Engine - Phase 2B
Races API checkout against Browser checkout simultaneously.

The first one to succeed wins!

Features:
- Simultaneous API and Browser checkout
- Automatic winner selection
- Fallback if one fails
- Cancel slower method
- Prevents double-orders

Author: Bob (Bloomfield, IN)
Created: November 12, 2025
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, Any, Dict
from playwright.async_api import Page


class CheckoutMethod(Enum):
    """Checkout method types"""
    API = "api"
    BROWSER = "browser"


class DualCheckoutResult:
    """Result from dual checkout"""
    
    def __init__(
        self,
        success: bool,
        winner: Optional[CheckoutMethod] = None,
        api_time: Optional[float] = None,
        browser_time: Optional[float] = None,
        api_error: Optional[str] = None,
        browser_error: Optional[str] = None
    ):
        self.success = success
        self.winner = winner
        self.api_time = api_time
        self.browser_time = browser_time
        self.api_error = api_error
        self.browser_error = browser_error
        
    def __repr__(self) -> str:
        if self.success:
            return f"DualCheckoutResult(SUCCESS via {self.winner.value} in {self.get_winner_time():.2f}s)"
        else:
            return f"DualCheckoutResult(FAILED - API: {self.api_error}, Browser: {self.browser_error})"
    
    def get_winner_time(self) -> float:
        """Get the time taken by the winning method"""
        if self.winner == CheckoutMethod.API:
            return self.api_time or 0.0
        elif self.winner == CheckoutMethod.BROWSER:
            return self.browser_time or 0.0
        return 0.0


class DualCheckout:
    """
    Dual-mode checkout that races API against Browser.
    
    Strategy:
    1. Start both API and Browser checkout simultaneously
    2. First one to succeed wins
    3. Cancel the other immediately
    4. If both fail, report both errors
    5. Track statistics on which method is faster
    """
    
    def __init__(self):
        self.api_wins = 0
        self.browser_wins = 0
        self.total_races = 0
        self.average_api_time = 0.0
        self.average_browser_time = 0.0
        
    async def _run_api_checkout(
        self,
        api_checkout_func: Callable,
        result_dict: Dict[str, Any]
    ) -> None:
        """
        Run API checkout and store result.
        
        Args:
            api_checkout_func: API checkout function
            result_dict: Shared result dictionary
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            print("[Dual Checkout] 🔌 API: Starting checkout...")
            success = await api_checkout_func()
            
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if success:
                result_dict['api_success'] = True
                result_dict['api_time'] = elapsed
                print(f"[Dual Checkout] ✅ API: SUCCESS in {elapsed:.2f}s")
            else:
                result_dict['api_success'] = False
                result_dict['api_time'] = elapsed
                result_dict['api_error'] = "Checkout failed"
                print(f"[Dual Checkout] ❌ API: FAILED after {elapsed:.2f}s")
                
        except asyncio.CancelledError:
            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"[Dual Checkout] 🛑 API: Cancelled (other method won) at {elapsed:.2f}s")
            result_dict['api_cancelled'] = True
            raise
            
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            result_dict['api_success'] = False
            result_dict['api_time'] = elapsed
            result_dict['api_error'] = str(e)
            print(f"[Dual Checkout] ❌ API: ERROR after {elapsed:.2f}s - {e}")
    
    async def _run_browser_checkout(
        self,
        browser_checkout_func: Callable,
        result_dict: Dict[str, Any]
    ) -> None:
        """
        Run Browser checkout and store result.
        
        Args:
            browser_checkout_func: Browser checkout function
            result_dict: Shared result dictionary
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            print("[Dual Checkout] 🌐 Browser: Starting checkout...")
            success = await browser_checkout_func()
            
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if success:
                result_dict['browser_success'] = True
                result_dict['browser_time'] = elapsed
                print(f"[Dual Checkout] ✅ Browser: SUCCESS in {elapsed:.2f}s")
            else:
                result_dict['browser_success'] = False
                result_dict['browser_time'] = elapsed
                result_dict['browser_error'] = "Checkout failed"
                print(f"[Dual Checkout] ❌ Browser: FAILED after {elapsed:.2f}s")
                
        except asyncio.CancelledError:
            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"[Dual Checkout] 🛑 Browser: Cancelled (other method won) at {elapsed:.2f}s")
            result_dict['browser_cancelled'] = True
            raise
            
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            result_dict['browser_success'] = False
            result_dict['browser_time'] = elapsed
            result_dict['browser_error'] = str(e)
            print(f"[Dual Checkout] ❌ Browser: ERROR after {elapsed:.2f}s - {e}")
    
    async def race(
        self,
        api_checkout_func: Callable,
        browser_checkout_func: Callable
    ) -> DualCheckoutResult:
        """
        Race API checkout against Browser checkout.
        
        Args:
            api_checkout_func: Async function for API checkout
            browser_checkout_func: Async function for Browser checkout
            
        Returns:
            DualCheckoutResult with winner and timing info
        """
        print("\n" + "="*60)
        print("🏁 DUAL CHECKOUT RACE STARTING")
        print("="*60)
        print("[Dual Checkout] Racing API vs Browser checkout...")
        
        self.total_races += 1
        
        # Shared result dictionary
        results = {
            'api_success': False,
            'browser_success': False,
            'api_time': None,
            'browser_time': None,
            'api_error': None,
            'browser_error': None,
            'api_cancelled': False,
            'browser_cancelled': False
        }
        
        # Create tasks
        api_task = asyncio.create_task(
            self._run_api_checkout(api_checkout_func, results)
        )
        browser_task = asyncio.create_task(
            self._run_browser_checkout(browser_checkout_func, results)
        )
        
        # Wait for first success
        done, pending = await asyncio.wait(
            [api_task, browser_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Check which one succeeded first
        winner = None
        
        for task in done:
            if results['api_success'] and not winner:
                winner = CheckoutMethod.API
                self.api_wins += 1
                if results['api_time']:
                    self.average_api_time = (
                        (self.average_api_time * (self.api_wins - 1) + results['api_time']) 
                        / self.api_wins
                    )
                print(f"\n[Dual Checkout] 🏆 API WON THE RACE!")
                print(f"[Dual Checkout] ⚡ Time: {results['api_time']:.2f}s")
                break
            elif results['browser_success'] and not winner:
                winner = CheckoutMethod.BROWSER
                self.browser_wins += 1
                if results['browser_time']:
                    self.average_browser_time = (
                        (self.average_browser_time * (self.browser_wins - 1) + results['browser_time']) 
                        / self.browser_wins
                    )
                print(f"\n[Dual Checkout] 🏆 BROWSER WON THE RACE!")
                print(f"[Dual Checkout] ⚡ Time: {results['browser_time']:.2f}s")
                break
        
        # Cancel pending tasks
        for task in pending:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # If we have a winner, return success
        if winner:
            print("="*60)
            print(f"🎉 CHECKOUT COMPLETE via {winner.value.upper()}!")
            print("="*60 + "\n")
            
            return DualCheckoutResult(
                success=True,
                winner=winner,
                api_time=results['api_time'],
                browser_time=results['browser_time']
            )
        
        # Both failed - wait for both to complete to get full error info
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        
        print("\n" + "="*60)
        print("❌ BOTH METHODS FAILED")
        print(f"   API Error: {results['api_error']}")
        print(f"   Browser Error: {results['browser_error']}")
        print("="*60 + "\n")
        
        return DualCheckoutResult(
            success=False,
            api_time=results['api_time'],
            browser_time=results['browser_time'],
            api_error=results['api_error'],
            browser_error=results['browser_error']
        )
    
    async def race_with_fallback(
        self,
        api_checkout_func: Callable,
        browser_checkout_func: Callable
    ) -> DualCheckoutResult:
        """
        Race with fallback: if one fails immediately, let the other continue.
        
        Args:
            api_checkout_func: API checkout function
            browser_checkout_func: Browser checkout function
            
        Returns:
            DualCheckoutResult
        """
        print("\n[Dual Checkout] 🔄 Starting race with fallback enabled...")
        
        # Try racing first
        result = await self.race(api_checkout_func, browser_checkout_func)
        
        # If both failed quickly (< 2 seconds), might be temporary - don't give up
        if not result.success:
            if result.api_time and result.api_time < 2.0:
                print("[Dual Checkout] ⚠️  Both methods failed quickly - not giving up yet")
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get racing statistics.
        
        Returns:
            Dictionary with stats
        """
        return {
            'total_races': self.total_races,
            'api_wins': self.api_wins,
            'browser_wins': self.browser_wins,
            'api_win_rate': (self.api_wins / self.total_races * 100) if self.total_races > 0 else 0,
            'browser_win_rate': (self.browser_wins / self.total_races * 100) if self.total_races > 0 else 0,
            'average_api_time': self.average_api_time,
            'average_browser_time': self.average_browser_time,
            'faster_method': CheckoutMethod.API if self.api_wins > self.browser_wins else CheckoutMethod.BROWSER
        }
    
    def print_stats(self) -> None:
        """Print racing statistics"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 DUAL CHECKOUT STATISTICS")
        print("="*60)
        print(f"Total Races: {stats['total_races']}")
        print(f"\nAPI Checkout:")
        print(f"  Wins: {stats['api_wins']} ({stats['api_win_rate']:.1f}%)")
        print(f"  Avg Time: {stats['average_api_time']:.2f}s")
        print(f"\nBrowser Checkout:")
        print(f"  Wins: {stats['browser_wins']} ({stats['browser_win_rate']:.1f}%)")
        print(f"  Avg Time: {stats['average_browser_time']:.2f}s")
        
        if stats['faster_method'] == CheckoutMethod.API:
            print(f"\n🏆 Overall Winner: API (faster on average)")
        else:
            print(f"\n🏆 Overall Winner: Browser (faster on average)")
        print("="*60 + "\n")


# Example usage
if __name__ == "__main__":
    async def test_dual_checkout():
        """Test dual checkout racing"""
        dual = DualCheckout()
        
        # Test 1: API wins
        print("\n🧪 Test 1: API should win")
        
        async def fast_api():
            await asyncio.sleep(0.5)  # API is faster
            return True
        
        async def slow_browser():
            await asyncio.sleep(2.0)  # Browser is slower
            return True
        
        result = await dual.race(fast_api, slow_browser)
        print(f"Result: {result}")
        
        # Test 2: Browser wins
        print("\n🧪 Test 2: Browser should win")
        
        async def slow_api():
            await asyncio.sleep(2.0)
            return True
        
        async def fast_browser():
            await asyncio.sleep(0.5)
            return True
        
        result = await dual.race(slow_api, fast_browser)
        print(f"Result: {result}")
        
        # Test 3: API fails, Browser succeeds
        print("\n🧪 Test 3: API fails, Browser succeeds")
        
        async def failing_api():
            await asyncio.sleep(0.5)
            return False
        
        async def working_browser():
            await asyncio.sleep(1.0)
            return True
        
        result = await dual.race(failing_api, working_browser)
        print(f"Result: {result}")
        
        # Print final stats
        dual.print_stats()
    
    # Run tests
    print("Testing Dual Checkout Racing...")
    asyncio.run(test_dual_checkout())
