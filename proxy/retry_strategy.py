"""
Retry Strategy with Exponential Backoff.

Provides intelligent retry logic for network operations:
- Exponential backoff with jitter
- Maximum retry attempts
- Exception filtering
- Async support

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

log = logging.getLogger('tg-ws-retry')


class RetryStrategyType(Enum):
    """Retry strategy types."""
    EXPONENTIAL = "exponential"  # Exponential backoff
    LINEAR = "linear"  # Linear backoff
    FIXED = "fixed"  # Fixed delay


T = TypeVar('T')


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 5
    base_delay: float = 1.0  # Base delay in seconds
    max_delay: float = 60.0  # Maximum delay between retries
    exponential_base: float = 2.0  # Base for exponential backoff
    jitter: bool = True  # Add random jitter to delay
    strategy: RetryStrategyType = RetryStrategyType.EXPONENTIAL
    retryable_exceptions: tuple = (Exception,)  # Exceptions that trigger retry
    non_retryable_exceptions: tuple = ()  # Exceptions that should not be retried


@dataclass
class RetryResult:
    """Result of retry operation."""
    success: bool
    result: Any = None
    error: Exception | None = None
    attempts: int = 0
    total_time: float = 0.0
    delays: list[float] = field(default_factory=list)

    @property
    def was_retried(self) -> bool:
        """Check if operation was retried."""
        return self.attempts > 1


class RetryStrategy:
    """
    Retry strategy with exponential backoff and jitter.

    Usage:
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        strategy = RetryStrategy(config)

        # Sync usage
        result = strategy.execute(my_function, arg1, arg2)

        # Async usage
        result = await strategy.execute_async(my_async_function, arg1, arg2)
    """

    def __init__(self, config: RetryConfig | None = None):
        """
        Initialize retry strategy.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for current attempt.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategyType.FIXED:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategyType.LINEAR:
            delay = self.config.base_delay * (attempt + 1)
        else:  # EXPONENTIAL
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)

        # Apply jitter (±25% randomization)
        if self.config.jitter:
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)

        # Cap at max_delay
        return min(delay, self.config.max_delay)

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Check if operation should be retried.

        Args:
            exception: Exception that was raised
            attempt: Current attempt number

        Returns:
            True if should retry, False otherwise
        """
        # Check if we've exhausted attempts
        if attempt >= self.config.max_attempts:
            return False

        # Check non-retryable exceptions
        if self.config.non_retryable_exceptions:
            if isinstance(exception, self.config.non_retryable_exceptions):
                return False

        # Check retryable exceptions
        if isinstance(exception, self.config.retryable_exceptions):
            return True

        return False

    def execute(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with success status and result
        """
        import time

        start_time = time.monotonic()
        delays: list[float] = []
        last_error: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=time.monotonic() - start_time,
                    delays=delays,
                )
            except Exception as e:
                last_error = e

                if not self._should_retry(e, attempt):
                    log.debug("Non-retryable error or max attempts: %s", e)
                    break

                # Calculate and apply delay
                delay = self._calculate_delay(attempt)
                delays.append(delay)

                log.debug(
                    "Attempt %d failed: %s. Retrying in %.2fs...",
                    attempt + 1, e, delay
                )
                time.sleep(delay)

        # All attempts failed
        return RetryResult(
            success=False,
            error=last_error,
            attempts=self.config.max_attempts,
            total_time=time.monotonic() - start_time,
            delays=delays,
        )

    async def execute_async(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """
        Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            RetryResult with success status and result
        """
        import time

        start_time = time.monotonic()
        delays: list[float] = []
        last_error: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_time=time.monotonic() - start_time,
                    delays=delays,
                )
            except Exception as e:
                last_error = e

                if not self._should_retry(e, attempt):
                    log.debug("Non-retryable error or max attempts: %s", e)
                    break

                # Calculate and apply delay
                delay = self._calculate_delay(attempt)
                delays.append(delay)

                log.debug(
                    "Attempt %d failed: %s. Retrying in %.2fs...",
                    attempt + 1, e, delay
                )
                await asyncio.sleep(delay)

        # All attempts failed
        return RetryResult(
            success=False,
            error=last_error,
            attempts=self.config.max_attempts,
            total_time=time.monotonic() - start_time,
            delays=delays,
        )


# Pre-configured retry strategies for common use cases

def get_dns_retry_strategy() -> RetryStrategy:
    """Get retry strategy for DNS resolution."""
    return RetryStrategy(RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=5.0,
        strategy=RetryStrategyType.EXPONENTIAL,
        retryable_exceptions=(asyncio.TimeoutError, ConnectionError),
    ))


def get_websocket_retry_strategy() -> RetryStrategy:
    """Get retry strategy for WebSocket connections."""
    return RetryStrategy(RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategyType.EXPONENTIAL,
        retryable_exceptions=(
            asyncio.TimeoutError,
            ConnectionError,
            ConnectionRefusedError,
            OSError,
        ),
    ))


def get_tcp_retry_strategy() -> RetryStrategy:
    """Get retry strategy for TCP connections."""
    return RetryStrategy(RetryConfig(
        max_attempts=3,
        base_delay=0.5,
        max_delay=10.0,
        strategy=RetryStrategyType.EXPONENTIAL,
        retryable_exceptions=(
            asyncio.TimeoutError,
            ConnectionRefusedError,
            OSError,
        ),
    ))


def get_http_retry_strategy() -> RetryStrategy:
    """Get retry strategy for HTTP requests."""
    return RetryStrategy(RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
        strategy=RetryStrategyType.EXPONENTIAL,
        retryable_exceptions=(
            asyncio.TimeoutError,
            ConnectionError,
            OSError,
        ),
        non_retryable_exceptions=(
            # Don't retry on HTTP 4xx errors
            ValueError,  # Used for HTTP 4xx in our code
        ),
    ))
