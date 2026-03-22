"""Tests for circuit_breaker.py module."""

from __future__ import annotations

import asyncio
import time

import pytest

from proxy.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
    CircuitStats,
    get_all_circuit_breakers_info,
    get_circuit_breaker,
    get_circuit_breaker_sync,
    reset_all_circuit_breakers,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_values(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitStats:
    """Tests for CircuitStats dataclass."""

    def test_circuit_stats_default(self):
        """Test default CircuitStats."""
        stats = CircuitStats()
        
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0
        assert stats.state_changes == 0
        assert stats.last_failure_time == 0.0
        assert stats.last_success_time == 0.0
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 0


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_circuit_breaker_config_default(self):
        """Test default CircuitBreakerConfig."""
        config = CircuitBreakerConfig()
        
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout == 30.0
        assert config.half_open_max_calls == 3
        assert config.excluded_exceptions == (asyncio.CancelledError,)

    def test_circuit_breaker_config_custom(self):
        """Test custom CircuitBreakerConfig."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout=60.0,
            half_open_max_calls=5,
        )
        
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.timeout == 60.0
        assert config.half_open_max_calls == 5


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_circuit_breaker_error_basic(self):
        """Test basic CircuitBreakerError."""
        error = CircuitBreakerError("test-service", 30.0)
        
        assert error.service == "test-service"
        assert error.retry_after == 30.0
        assert "test-service" in str(error)
        assert "30.0" in str(error)


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_circuit_breaker_init(self):
        """Test CircuitBreaker initialization."""
        cb = CircuitBreaker("test")
        
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False

    def test_circuit_breaker_init_with_config(self):
        """Test CircuitBreaker with custom config."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config)
        
        assert cb.config.failure_threshold == 10


class TestCircuitBreakerBasic:
    """Basic tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_success(self):
        """Test successful call through circuit breaker."""
        cb = CircuitBreaker("test")
        
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        
        assert result == "success"
        assert cb.stats.successful_calls == 1
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_failure(self):
        """Test failed call through circuit breaker."""
        cb = CircuitBreaker("test")
        
        async def fail_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        
        assert cb.stats.failed_calls == 1
        assert cb.stats.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_sync_function(self):
        """Test sync function through circuit breaker."""
        cb = CircuitBreaker("test")
        
        def sync_func():
            return "sync_result"
        
        result = await cb.call(sync_func)
        
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_with_args(self):
        """Test call with arguments."""
        cb = CircuitBreaker("test")
        
        async def add_func(a, b):
            return a + b
        
        result = await cb.call(add_func, 2, 3)
        
        assert result == 5

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_with_kwargs(self):
        """Test call with keyword arguments."""
        cb = CircuitBreaker("test")
        
        async def greet_func(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        result = await cb.call(greet_func, "World", greeting="Hi")
        
        assert result == "Hi, World!"


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=1.0)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        # Cause 3 failures
        for _ in range(3):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        assert cb.is_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self):
        """Test circuit rejects calls when open."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=10.0)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Should reject calls
        with pytest.raises(CircuitBreakerError):
            await cb.call(success_func)
        
        assert cb.stats.rejected_calls >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.5, success_threshold=2)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        assert cb.is_open is True
        
        # Wait for timeout
        await asyncio.sleep(0.6)
        
        # Next call should be allowed (half-open)
        result = await cb.call(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_successes(self):
        """Test circuit closes after success threshold in half-open."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1, success_threshold=2)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Succeed twice to close
        await cb.call(success_func)
        await cb.call(success_func)
        
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in half-open state."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1, success_threshold=2)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Fail in half-open state
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        
        assert cb.is_open is True


class TestCircuitBreakerExcludedExceptions:
    """Tests for excluded exceptions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_excluded_exception(self):
        """Test excluded exceptions don't count as failures."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=10.0)
        cb = CircuitBreaker("test", config)
        
        async def cancel_func():
            raise asyncio.CancelledError()
        
        # Should raise but not count as failure
        with pytest.raises(asyncio.CancelledError):
            await cb.call(cancel_func)
        
        # Should still be closed (no failures counted)
        assert cb.is_closed is True
        assert cb.stats.failed_calls == 0


class TestCircuitBreakerReset:
    """Tests for circuit breaker reset."""

    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset."""
        cb = CircuitBreaker("test")
        cb._state = CircuitState.OPEN
        cb._stats.total_calls = 10
        
        cb.reset()
        
        assert cb.is_closed is True
        assert cb.stats.total_calls == 0


class TestCircuitBreakerGetInfo:
    """Tests for get_info method."""

    def test_circuit_breaker_get_info(self):
        """Test get_info returns correct structure."""
        cb = CircuitBreaker("test")
        
        info = cb.get_info()
        
        assert info['name'] == "test"
        assert info['state'] == "closed"
        assert 'stats' in info
        assert 'config' in info
        assert info['config']['failure_threshold'] == 5


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    @pytest.mark.asyncio
    async def test_registry_get_or_create(self):
        """Test get_or_create in registry."""
        registry = CircuitBreakerRegistry()
        
        cb1 = await registry.get_or_create("test")
        cb2 = await registry.get_or_create("test")
        
        assert cb1 is cb2

    @pytest.mark.asyncio
    async def test_registry_get(self):
        """Test get in registry."""
        registry = CircuitBreakerRegistry()
        
        await registry.get_or_create("test")
        
        cb = registry.get("test")
        
        assert cb is not None
        assert cb.name == "test"

    @pytest.mark.asyncio
    async def test_registry_get_missing(self):
        """Test get missing circuit breaker."""
        registry = CircuitBreakerRegistry()
        
        cb = registry.get("nonexistent")
        
        assert cb is None

    def test_registry_reset_all(self):
        """Test reset_all in registry."""
        registry = CircuitBreakerRegistry()
        
        cb = CircuitBreaker("test")
        cb._state = CircuitState.OPEN
        registry._breakers["test"] = cb
        
        registry.reset_all()
        
        assert cb.is_closed is True

    def test_registry_get_all_info(self):
        """Test get_all_info in registry."""
        registry = CircuitBreakerRegistry()
        
        cb = CircuitBreaker("test")
        registry._breakers["test"] = cb
        
        info_list = registry.get_all_info()
        
        assert len(info_list) == 1
        assert info_list[0]['name'] == "test"


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    @pytest.mark.asyncio
    async def test_get_circuit_breaker(self):
        """Test get_circuit_breaker global function."""
        cb = await get_circuit_breaker("test-global")
        
        assert cb is not None
        assert cb.name == "test-global"

    def test_get_circuit_breaker_sync(self):
        """Test get_circuit_breaker_sync global function."""
        # First create via async
        asyncio.run(get_circuit_breaker("test-sync"))
        
        cb = get_circuit_breaker_sync("test-sync")
        
        assert cb is not None

    def test_get_circuit_breaker_sync_missing(self):
        """Test get_circuit_breaker_sync for missing breaker."""
        cb = get_circuit_breaker_sync("nonexistent")
        
        assert cb is None

    def test_reset_all_circuit_breakers(self):
        """Test reset_all_circuit_breakers global function."""
        reset_all_circuit_breakers()
        # Should not raise

    def test_get_all_circuit_breakers_info(self):
        """Test get_all_circuit_breakers_info global function."""
        info = get_all_circuit_breakers_info()
        
        assert isinstance(info, list)


class TestCircuitBreakerConcurrentAccess:
    """Tests for concurrent access to circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_concurrent_calls(self):
        """Test concurrent calls through circuit breaker."""
        cb = CircuitBreaker("test")
        
        async def slow_func():
            await asyncio.sleep(0.1)
            return "done"
        
        # Make concurrent calls
        tasks = [cb.call(slow_func) for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert all(r == "done" for r in results)

    @pytest.mark.asyncio
    async def test_circuit_breaker_concurrent_failures(self):
        """Test concurrent failures."""
        config = CircuitBreakerConfig(failure_threshold=10)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        # Make concurrent failing calls
        tasks = [cb.call(fail_func) for _ in range(10)]
        
        for task in tasks:
            with pytest.raises(ValueError):
                await task
        
        # Should have tracked all failures
        assert cb.stats.failed_calls == 10


class TestCircuitBreakerEdgeCases:
    """Edge case tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_zero_timeout(self):
        """Test circuit breaker with zero timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.01)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        async def success_func():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Wait for very short timeout
        await asyncio.sleep(0.02)
        
        # Should be allowed
        result = await cb.call(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_circuit_breaker_high_failure_threshold(self):
        """Test circuit breaker with high failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=100)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        # Cause many failures but below threshold
        for _ in range(50):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Should still be closed
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_single_call(self):
        """Test half-open with single allowed call."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1, half_open_max_calls=1)
        cb = CircuitBreaker("test", config)
        
        async def fail_func():
            raise ValueError("test error")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # First call allowed in half-open
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        
        # Second call should be rejected (still half-open, max calls reached)
        with pytest.raises(CircuitBreakerError):
            await cb.call(fail_func)
