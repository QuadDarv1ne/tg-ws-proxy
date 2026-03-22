"""Unit tests for circuit breaker module."""

from __future__ import annotations

import asyncio

import pytest

from proxy.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    get_all_circuit_breakers_info,
    get_circuit_breaker,
    get_circuit_breaker_sync,
    reset_all_circuit_breakers,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    @pytest.mark.asyncio
    async def test_success_does_not_change_state(self):
        """Test successful calls keep circuit closed."""
        breaker = CircuitBreaker("test")

        async def success_func():
            return "ok"

        result = await breaker.call(success_func)
        assert result == "ok"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        """Test consecutive failures open the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open
        assert breaker.stats.failed_calls == 3
        assert breaker.stats.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls with CircuitBreakerError."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=10.0)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        # Try to call - should be rejected
        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(failing_func)

        assert exc_info.value.service == "test"
        assert exc_info.value.retry_after > 0
        assert breaker.stats.rejected_calls == 1

    @pytest.mark.asyncio
    async def test_timeout_transitions_to_half_open(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN
        async def success_func():
            return "ok"

        result = await breaker.call(success_func)
        assert result == "ok"
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Test successful calls in HALF_OPEN close the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        async def success_func():
            return "ok"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        # Wait for timeout
        await asyncio.sleep(0.15)

        # First success in HALF_OPEN
        await breaker.call(success_func)
        assert breaker.state == CircuitState.HALF_OPEN

        # Second success should close circuit
        await breaker.call(success_func)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.consecutive_successes == 2

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Test failure in HALF_OPEN reopens the circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        async def success_then_fail():
            return "ok"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        # Wait for timeout
        await asyncio.sleep(0.15)

        # First call succeeds
        await breaker.call(success_then_fail)
        assert breaker.state == CircuitState.HALF_OPEN

        # Second call fails - should reopen
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_excluded_exceptions_dont_count(self):
        """Test excluded exceptions don't count as failures."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            excluded_exceptions=(asyncio.CancelledError,),
        )
        breaker = CircuitBreaker("test", config)

        async def cancelled_func():
            raise asyncio.CancelledError()

        # Should raise but not count as failure
        with pytest.raises(asyncio.CancelledError):
            await breaker.call(cancelled_func)

        with pytest.raises(asyncio.CancelledError):
            await breaker.call(cancelled_func)

        # Circuit should still be closed
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test manual reset of circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.total_calls == 0
        assert breaker.stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test statistics are properly tracked."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def success_func():
            return "ok"

        async def failing_func():
            raise ValueError("error")

        await breaker.call(success_func)
        await breaker.call(success_func)

        with pytest.raises(ValueError):
            await breaker.call(failing_func)

        stats = breaker.stats
        assert stats.total_calls == 3
        assert stats.successful_calls == 2
        assert stats.failed_calls == 1
        assert stats.consecutive_successes == 0
        assert stats.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_get_info(self):
        """Test getting circuit breaker info."""
        config = CircuitBreakerConfig(failure_threshold=5, timeout=30.0)
        breaker = CircuitBreaker("test_service", config)

        info = breaker.get_info()

        assert info['name'] == "test_service"
        assert info['state'] == "closed"
        assert info['config']['failure_threshold'] == 5
        assert info['config']['timeout'] == 30.0


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    @pytest.mark.asyncio
    async def test_get_or_create(self):
        """Test getting or creating circuit breaker."""
        registry = CircuitBreakerRegistry()

        breaker1 = await registry.get_or_create("test")
        breaker2 = await registry.get_or_create("test")

        assert breaker1 is breaker2

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting nonexistent breaker returns None."""
        registry = CircuitBreakerRegistry()

        breaker = registry.get("nonexistent")
        assert breaker is None

    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test resetting all breakers."""
        registry = CircuitBreakerRegistry()

        breaker1 = await registry.get_or_create("test1")
        breaker2 = await registry.get_or_create("test2")

        # Manually set state to OPEN
        breaker1._state = CircuitState.OPEN
        breaker2._state = CircuitState.OPEN

        registry.reset_all()

        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_all_info(self):
        """Test getting info for all breakers."""
        registry = CircuitBreakerRegistry()

        await registry.get_or_create("test1")
        await registry.get_or_create("test2")

        infos = registry.get_all_info()

        assert len(infos) == 2
        names = {info['name'] for info in infos}
        assert names == {"test1", "test2"}


class TestGlobalFunctions:
    """Tests for global helper functions."""

    @pytest.mark.asyncio
    async def test_get_circuit_breaker(self):
        """Test getting circuit breaker from global registry."""
        # Reset first
        reset_all_circuit_breakers()

        breaker1 = await get_circuit_breaker("global_test")
        breaker2 = get_circuit_breaker_sync("global_test")

        assert breaker1 is breaker2

    @pytest.mark.asyncio
    async def test_reset_all_global(self):
        """Test resetting all global breakers."""
        reset_all_circuit_breakers()

        breaker = await get_circuit_breaker("reset_test")
        breaker._state = CircuitState.OPEN

        reset_all_circuit_breakers()

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_get_all_info_global(self):
        """Test getting info from global registry."""
        reset_all_circuit_breakers()

        await get_circuit_breaker("info_test")

        infos = get_all_circuit_breakers_info()
        assert len(infos) >= 1
