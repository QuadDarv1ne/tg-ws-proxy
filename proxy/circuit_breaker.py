"""
Circuit Breaker Pattern Implementation.

Provides protection against cascade failures by tracking failures
and temporarily blocking operations when failure threshold is exceeded.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

log = logging.getLogger('tg-ws-circuit-breaker')


class CircuitState(Enum):
    """Circuit breaker state."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking operations
    HALF_OPEN = "half_open"  # Testing if service recovered


T = TypeVar('T')


@dataclass
class CircuitStats:
    """Circuit breaker statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Calls rejected when circuit was open
    state_changes: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 3  # Successes in half-open before closing
    timeout: float = 30.0  # Seconds to wait before trying half-open
    half_open_max_calls: int = 3  # Max calls allowed in half-open state
    excluded_exceptions: tuple = (asyncio.CancelledError,)  # Exceptions that don't count as failures


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker OPEN for {service}, retry after {retry_after:.1f}s")


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation.

    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Blocking all operations, waiting for timeout
    - HALF_OPEN: Allowing limited calls to test recovery
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Service name for identification
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._opened_at: float = 0.0
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self._state == CircuitState.HALF_OPEN

    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on state."""
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.config.timeout:
                log.info("Circuit %s: timeout elapsed, transitioning to HALF_OPEN", self.name)
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._stats.state_changes += 1
                return True
            return False

        # HALF_OPEN state
        if self._half_open_calls < self.config.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    def _on_success(self) -> None:
        """Handle successful call."""
        self._stats.successful_calls += 1
        self._stats.last_success_time = time.monotonic()
        self._stats.consecutive_failures = 0
        self._stats.consecutive_successes += 1

        if self._state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.config.success_threshold:
                log.info("Circuit %s: recovered, transitioning to CLOSED", self.name)
                self._state = CircuitState.CLOSED
                self._stats.state_changes += 1

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._stats.failed_calls += 1
        self._stats.last_failure_time = time.monotonic()
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0

        if self._state == CircuitState.HALF_OPEN:
            log.warning("Circuit %s: failure in HALF_OPEN, transitioning to OPEN", self.name)
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._stats.state_changes += 1
        elif self._state == CircuitState.CLOSED:
            if self._stats.consecutive_failures >= self.config.failure_threshold:
                log.warning("Circuit %s: failure threshold exceeded, transitioning to OPEN", self.name)
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._stats.state_changes += 1

    async def call(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit is open
        """
        async with self._lock:
            self._stats.total_calls += 1

            if not self._should_allow_request():
                self._stats.rejected_calls += 1
                retry_after = self.config.timeout - (time.monotonic() - self._opened_at)
                raise CircuitBreakerError(self.name, max(0, retry_after))

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result  # type: ignore[no-any-return]
        except self.config.excluded_exceptions:
            # Don't count these as failures
            raise
        except Exception as e:
            self._on_failure()
            log.debug("Circuit %s: call failed: %s", self.name, e)
            raise

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._opened_at = 0.0
        self._half_open_calls = 0
        log.info("Circuit %s: manually reset", self.name)

    def get_info(self) -> dict[str, Any]:
        """Get circuit breaker info for monitoring."""
        return {
            'name': self.name,
            'state': self._state.value,
            'stats': {
                'total_calls': self._stats.total_calls,
                'successful_calls': self._stats.successful_calls,
                'failed_calls': self._stats.failed_calls,
                'rejected_calls': self._stats.rejected_calls,
                'consecutive_failures': self._stats.consecutive_failures,
                'consecutive_successes': self._stats.consecutive_successes,
            },
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'success_threshold': self.config.success_threshold,
                'timeout': self.config.timeout,
            },
        }


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self) -> None:
        """Initialize registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """Get or create circuit breaker by name."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
                log.info("Circuit breaker created: %s", name)
            return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_info(self) -> list[dict[str, Any]]:
        """Get info for all circuit breakers."""
        return [b.get_info() for b in self._breakers.values()]


# Global registry instance
_registry = CircuitBreakerRegistry()


async def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create circuit breaker from global registry."""
    return await _registry.get_or_create(name, config)


def get_circuit_breaker_sync(name: str) -> CircuitBreaker | None:
    """Get circuit breaker from global registry (sync)."""
    return _registry.get(name)


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers."""
    _registry.reset_all()


def get_all_circuit_breakers_info() -> list[dict[str, Any]]:
    """Get info for all circuit breakers."""
    return _registry.get_all_info()
