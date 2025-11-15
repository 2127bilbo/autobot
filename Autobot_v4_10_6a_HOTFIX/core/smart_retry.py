"""
Autobot Smart Retry - Phase 3C
Intelligent retry logic with adaptive backoff

This module provides smart retry strategies:
- Exponential backoff
- Adaptive retry counts based on error type
- Success rate learning
- Circuit breaker pattern
- Retry budget management

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import time
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import random


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"
    FIXED = "fixed"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = 1      # Retry aggressively
    MEDIUM = 2   # Normal retry
    HIGH = 3     # Retry cautiously
    CRITICAL = 4 # Minimal retry


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, don't retry
    HALF_OPEN = "half_open"  # Testing if recovered


class SmartRetry:
    """
    Smart retry handler with adaptive behavior.
    
    Features:
    - Multiple retry strategies
    - Exponential backoff with jitter
    - Error severity classification
    - Circuit breaker protection
    - Success rate tracking
    - Retry budget management
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        jitter: bool = True,
        circuit_threshold: int = 5,
        circuit_timeout: float = 60.0
    ):
        """
        Initialize smart retry handler.
        
        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay cap (seconds)
            strategy: Retry strategy to use
            jitter: Add random jitter to delays
            circuit_threshold: Failures before opening circuit
            circuit_timeout: Circuit open duration (seconds)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.jitter = jitter
        self.circuit_threshold = circuit_threshold
        self.circuit_timeout = circuit_timeout
        
        # Circuit breaker state
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.circuit_opened_at = None
        
        # Retry statistics
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt.
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.EXPONENTIAL:
            # 2^attempt * base_delay
            delay = self.base_delay * (2 ** attempt)
        
        elif self.strategy == RetryStrategy.LINEAR:
            # attempt * base_delay
            delay = self.base_delay * (attempt + 1)
        
        elif self.strategy == RetryStrategy.FIBONACCI:
            # Fibonacci sequence * base_delay
            fib = self._fibonacci(attempt + 1)
            delay = self.base_delay * fib
        
        else:  # FIXED
            delay = self.base_delay
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.2  # ±20%
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b
    
    def should_retry(
        self,
        attempt: int,
        error: Exception,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> bool:
        """
        Determine if should retry based on attempt and error.
        
        Args:
            attempt: Current attempt number
            error: Exception that occurred
            severity: Error severity level
            
        Returns:
            True if should retry
        """
        # Check circuit breaker
        if not self._check_circuit():
            return False
        
        # Adjust max retries based on severity
        effective_max = self._get_effective_max_retries(severity)
        
        if attempt >= effective_max:
            return False
        
        # Check if error is retryable
        if not self._is_retryable_error(error):
            return False
        
        return True
    
    def _get_effective_max_retries(self, severity: ErrorSeverity) -> int:
        """Get effective max retries based on severity."""
        if severity == ErrorSeverity.LOW:
            return self.max_retries * 2  # Retry more
        elif severity == ErrorSeverity.MEDIUM:
            return self.max_retries
        elif severity == ErrorSeverity.HIGH:
            return max(1, self.max_retries // 2)  # Retry less
        else:  # CRITICAL
            return 0  # Don't retry
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error type is retryable."""
        # Network errors - retryable
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            OSError,
        )
        
        # Non-retryable errors
        non_retryable = (
            ValueError,
            TypeError,
            KeyError,
        )
        
        if isinstance(error, retryable_errors):
            return True
        
        if isinstance(error, non_retryable):
            return False
        
        # Default: retry
        return True
    
    def _check_circuit(self) -> bool:
        """Check circuit breaker state."""
        if self.circuit_state == CircuitState.CLOSED:
            return True
        
        elif self.circuit_state == CircuitState.OPEN:
            # Check if timeout elapsed
            if self.circuit_opened_at:
                elapsed = (datetime.now() - self.circuit_opened_at).total_seconds()
                if elapsed >= self.circuit_timeout:
                    # Move to half-open
                    self.circuit_state = CircuitState.HALF_OPEN
                    print(f"[SmartRetry] Circuit moved to HALF_OPEN")
                    return True
            return False
        
        else:  # HALF_OPEN
            # Allow one attempt
            return True
    
    def record_success(self):
        """Record a successful attempt."""
        self.total_attempts += 1
        self.total_successes += 1
        self.success_count += 1
        self.failure_count = 0  # Reset failure count
        
        # Close circuit if in half-open
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED
            print(f"[SmartRetry] Circuit CLOSED")
    
    def record_failure(self):
        """Record a failed attempt."""
        self.total_attempts += 1
        self.total_failures += 1
        self.failure_count += 1
        self.success_count = 0  # Reset success count
        self.last_failure_time = datetime.now()
        
        # Check circuit breaker
        if self.failure_count >= self.circuit_threshold:
            if self.circuit_state == CircuitState.CLOSED:
                self.circuit_state = CircuitState.OPEN
                self.circuit_opened_at = datetime.now()
                print(f"[SmartRetry] Circuit OPENED (failures: {self.failure_count})")
            
            elif self.circuit_state == CircuitState.HALF_OPEN:
                # Failed during test, reopen
                self.circuit_state = CircuitState.OPEN
                self.circuit_opened_at = datetime.now()
                print(f"[SmartRetry] Circuit REOPENED")
    
    def execute(
        self,
        func: Callable,
        *args,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        on_retry: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with smart retry.
        
        Args:
            func: Function to execute
            *args: Function arguments
            severity: Error severity for retry adjustment
            on_retry: Optional callback on retry
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
                
            except Exception as e:
                last_exception = e
                self.record_failure()
                
                if attempt < self.max_retries:
                    if self.should_retry(attempt, e, severity):
                        delay = self.calculate_delay(attempt)
                        
                        print(f"[SmartRetry] Attempt {attempt + 1} failed: {e}")
                        print(f"[SmartRetry] Retrying in {delay:.2f}s...")
                        
                        if on_retry:
                            on_retry(attempt, e, delay)
                        
                        time.sleep(delay)
                    else:
                        # Circuit open or non-retryable
                        break
        
        # All retries exhausted
        raise last_exception
    
    def get_success_rate(self) -> float:
        """Get overall success rate."""
        if self.total_attempts == 0:
            return 0.0
        return self.total_successes / self.total_attempts
    
    def get_stats(self) -> Dict:
        """Get retry statistics."""
        return {
            'total_attempts': self.total_attempts,
            'total_successes': self.total_successes,
            'total_failures': self.total_failures,
            'success_rate': self.get_success_rate(),
            'circuit_state': self.circuit_state.value,
            'consecutive_failures': self.failure_count,
            'consecutive_successes': self.success_count
        }
    
    def reset(self):
        """Reset all counters and circuit state."""
        self.circuit_state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.circuit_opened_at = None
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0


class RetryBudget:
    """
    Manages a retry budget to prevent excessive retries.
    
    Useful for rate-limited APIs or expensive operations.
    """
    
    def __init__(self, budget: int, period_seconds: float = 60.0):
        """
        Initialize retry budget.
        
        Args:
            budget: Number of retries allowed per period
            period_seconds: Time period for budget reset
        """
        self.budget = budget
        self.period_seconds = period_seconds
        self.remaining = budget
        self.period_start = datetime.now()
    
    def can_retry(self) -> bool:
        """Check if retry budget available."""
        self._check_reset()
        return self.remaining > 0
    
    def consume(self, count: int = 1):
        """Consume retry budget."""
        self._check_reset()
        self.remaining = max(0, self.remaining - count)
    
    def _check_reset(self):
        """Check if period elapsed and reset budget."""
        elapsed = (datetime.now() - self.period_start).total_seconds()
        if elapsed >= self.period_seconds:
            self.remaining = self.budget
            self.period_start = datetime.now()
    
    def get_status(self) -> Dict:
        """Get budget status."""
        self._check_reset()
        return {
            'budget': self.budget,
            'remaining': self.remaining,
            'period_seconds': self.period_seconds,
            'time_until_reset': max(0, self.period_seconds - (datetime.now() - self.period_start).total_seconds())
        }


# Convenience decorator
def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
):
    """
    Decorator for automatic retry.
    
    Example:
        @with_retry(max_retries=5, base_delay=2.0)
        def my_function():
            # ... code that might fail
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            retry = SmartRetry(
                max_retries=max_retries,
                base_delay=base_delay,
                strategy=strategy
            )
            return retry.execute(func, *args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test smart retry
    print("🔄 Smart Retry Test")
    print("=" * 60)
    
    # Test 1: Exponential backoff
    print("\n📈 Test 1: Exponential Backoff")
    retry = SmartRetry(
        max_retries=4,
        base_delay=0.1,
        strategy=RetryStrategy.EXPONENTIAL
    )
    
    for i in range(5):
        delay = retry.calculate_delay(i)
        print(f"  Attempt {i}: {delay:.3f}s delay")
    
    # Test 2: Successful execution
    print("\n✅ Test 2: Successful Execution")
    retry = SmartRetry(max_retries=3, base_delay=0.1)
    
    call_count = [0]
    
    def successful_function():
        call_count[0] += 1
        return "Success!"
    
    result = retry.execute(successful_function)
    print(f"  Result: {result}")
    print(f"  Calls: {call_count[0]}")
    print(f"  Stats: {retry.get_stats()}")
    
    # Test 3: Retry on failure
    print("\n🔄 Test 3: Retry on Failure")
    retry = SmartRetry(max_retries=3, base_delay=0.1)
    
    attempt_count = [0]
    
    def failing_function():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ConnectionError(f"Attempt {attempt_count[0]} failed")
        return "Success after retries!"
    
    result = retry.execute(failing_function)
    print(f"  Result: {result}")
    print(f"  Total attempts: {attempt_count[0]}")
    print(f"  Stats: {retry.get_stats()}")
    
    # Test 4: Circuit breaker
    print("\n⚡ Test 4: Circuit Breaker")
    retry = SmartRetry(
        max_retries=2,
        base_delay=0.1,
        circuit_threshold=3,
        circuit_timeout=2.0
    )
    
    def always_fails():
        raise ConnectionError("Always fails")
    
    # Trigger circuit breaker
    for i in range(4):
        try:
            retry.execute(always_fails)
        except:
            pass
        print(f"  After attempt {i+1}: Circuit = {retry.circuit_state.value}")
    
    # Test 5: Retry budget
    print("\n💰 Test 5: Retry Budget")
    budget = RetryBudget(budget=5, period_seconds=10.0)
    
    print(f"  Initial: {budget.get_status()}")
    
    for i in range(7):
        if budget.can_retry():
            budget.consume()
            print(f"  Retry {i+1}: Remaining = {budget.remaining}")
        else:
            print(f"  Retry {i+1}: Budget exhausted!")
    
    # Test 6: Decorator
    print("\n🎯 Test 6: Retry Decorator")
    
    decorator_attempts = [0]
    
    @with_retry(max_retries=3, base_delay=0.1)
    def decorated_function():
        decorator_attempts[0] += 1
        if decorator_attempts[0] < 2:
            raise ConnectionError("Decorator test")
        return "Decorator success!"
    
    result = decorated_function()
    print(f"  Result: {result}")
    print(f"  Attempts: {decorator_attempts[0]}")
    
    print("\n✅ All tests complete!")
