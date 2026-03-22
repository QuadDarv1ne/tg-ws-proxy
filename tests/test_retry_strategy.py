"""Unit tests for retry strategy module."""

from __future__ import annotations

import asyncio
import time

import pytest

from proxy.retry_strategy import (
    RetryConfig,
    RetryResult,
    RetryStrategy,
    RetryStrategyType,
    get_dns_retry_strategy,
    get_http_retry_strategy,
    get_tcp_retry_strategy,
    get_websocket_retry_strategy,
)


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_was_retried_single_attempt(self):
        """Test was_retried with single attempt."""
        result = RetryResult(success=True, attempts=1)
        assert not result.was_retried

    def test_was_retried_multiple_attempts(self):
        """Test was_retried with multiple attempts."""
        result = RetryResult(success=True, attempts=3)
        assert result.was_retried


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = RetryConfig()
        assert config.max_attempts == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.strategy == RetryStrategyType.EXPONENTIAL

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=10.0,
            strategy=RetryStrategyType.LINEAR,
            jitter=False,
        )
        assert config.max_attempts == 3
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.strategy == RetryStrategyType.LINEAR
        assert config.jitter is False


class TestRetryStrategy:
    """Tests for RetryStrategy class."""

    def test_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        strategy = RetryStrategy()

        def success_func():
            return "success"

        result = strategy.execute(success_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert result.error is None
        assert not result.was_retried

    def test_success_after_failures(self):
        """Test successful execution after failures."""
        strategy = RetryStrategy(RetryConfig(max_attempts=3, base_delay=0.01))

        attempt_count = [0]

        def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Temporary error")
            return "success"

        result = strategy.execute(flaky_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert result.was_retried

    def test_failure_all_attempts_exhausted(self):
        """Test failure after all attempts exhausted."""
        strategy = RetryStrategy(RetryConfig(max_attempts=3, base_delay=0.01))

        def always_fail():
            raise ValueError("Always fails")

        result = strategy.execute(always_fail)

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.error, ValueError)
        assert len(result.delays) == 2  # 2 delays between 3 attempts

    def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.01,
            non_retryable_exceptions=(ValueError,),
        )
        strategy = RetryStrategy(config)

        def raise_non_retryable():
            raise ValueError("Non-retryable")

        result = strategy.execute(raise_non_retryable)

        assert result.success is False
        assert result.attempts == 1  # Should not retry
        assert len(result.delays) == 0

    def test_retryable_exception(self):
        """Test that retryable exceptions trigger retry."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        strategy = RetryStrategy(config)

        call_count = [0]

        def raise_retryable():
            call_count[0] += 1
            raise ValueError("Retryable")

        result = strategy.execute(raise_retryable)

        assert result.success is False
        assert result.attempts == 3  # Should retry max attempts
        assert call_count[0] == 3

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
        strategy = RetryStrategy(config)

        # Test delay calculation
        assert strategy._calculate_delay(0) == 1.0
        assert strategy._calculate_delay(1) == 2.0
        assert strategy._calculate_delay(2) == 4.0
        assert strategy._calculate_delay(3) == 8.0

    def test_linear_backoff(self):
        """Test linear backoff calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            strategy=RetryStrategyType.LINEAR,
            jitter=False,
        )
        strategy = RetryStrategy(config)

        assert strategy._calculate_delay(0) == 1.0
        assert strategy._calculate_delay(1) == 2.0
        assert strategy._calculate_delay(2) == 3.0

    def test_fixed_backoff(self):
        """Test fixed backoff calculation."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            strategy=RetryStrategyType.FIXED,
            jitter=False,
        )
        strategy = RetryStrategy(config)

        assert strategy._calculate_delay(0) == 2.0
        assert strategy._calculate_delay(1) == 2.0
        assert strategy._calculate_delay(2) == 2.0

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            max_attempts=10,
            base_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )
        strategy = RetryStrategy(config)

        # Even with exponential growth, should not exceed max_delay
        for attempt in range(10):
            delay = strategy._calculate_delay(attempt)
            assert delay <= 5.0

    def test_jitter_applied(self):
        """Test that jitter is applied to delay."""
        config = RetryConfig(
            base_delay=1.0,
            jitter=True,
        )
        strategy = RetryStrategy(config)

        # Run multiple times to check jitter variation
        delays = [strategy._calculate_delay(0) for _ in range(10)]
        # With jitter, delays should vary (not all equal)
        assert len(set(delays)) > 1

    def test_jitter_not_applied(self):
        """Test that jitter is not applied when disabled."""
        config = RetryConfig(
            base_delay=1.0,
            jitter=False,
        )
        strategy = RetryStrategy(config)

        # All delays should be identical
        delays = [strategy._calculate_delay(0) for _ in range(10)]
        assert len(set(delays)) == 1
        assert all(d == 1.0 for d in delays)

    def test_total_time_tracking(self):
        """Test that total time is tracked correctly."""
        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=False)
        strategy = RetryStrategy(config)

        def always_fail():
            raise ValueError("Fail")

        result = strategy.execute(always_fail)

        # Should have at least 0.2s of delays (0.1 + 0.2)
        assert result.total_time >= 0.2
        assert len(result.delays) == 2


class TestRetryStrategyAsync:
    """Tests for async retry strategy."""

    @pytest.mark.asyncio
    async def test_async_success_on_first_attempt(self):
        """Test async successful execution on first attempt."""
        strategy = RetryStrategy()

        async def success_func():
            return "async success"

        result = await strategy.execute_async(success_func)

        assert result.success is True
        assert result.result == "async success"
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_async_success_after_failures(self):
        """Test async successful execution after failures."""
        strategy = RetryStrategy(RetryConfig(max_attempts=3, base_delay=0.01))

        attempt_count = [0]

        async def flaky_func():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise ValueError("Temporary error")
            return "async success"

        result = await strategy.execute_async(flaky_func)

        assert result.success is True
        assert result.result == "async success"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_async_failure_all_attempts_exhausted(self):
        """Test async failure after all attempts exhausted."""
        strategy = RetryStrategy(RetryConfig(max_attempts=3, base_delay=0.01))

        async def always_fail():
            raise ValueError("Always fails")

        result = await strategy.execute_async(always_fail)

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.error, ValueError)

    @pytest.mark.asyncio
    async def test_async_with_actual_delay(self):
        """Test async execution with actual delay."""
        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=False)
        strategy = RetryStrategy(config)

        async def always_fail():
            raise ValueError("Fail")

        start = time.monotonic()
        result = await strategy.execute_async(always_fail)
        elapsed = time.monotonic() - start

        # Should have at least 0.3s of delays (0.1 + 0.2)
        assert elapsed >= 0.3
        assert result.total_time >= 0.3


class TestPreconfiguredStrategies:
    """Tests for pre-configured retry strategies."""

    def test_dns_retry_strategy(self):
        """Test DNS retry strategy configuration."""
        strategy = get_dns_retry_strategy()

        assert strategy.config.max_attempts == 3
        assert strategy.config.base_delay == 0.5
        assert strategy.config.max_delay == 5.0
        assert asyncio.TimeoutError in strategy.config.retryable_exceptions

    def test_websocket_retry_strategy(self):
        """Test WebSocket retry strategy configuration."""
        strategy = get_websocket_retry_strategy()

        assert strategy.config.max_attempts == 5
        assert strategy.config.base_delay == 1.0
        assert strategy.config.max_delay == 30.0
        assert ConnectionError in strategy.config.retryable_exceptions

    def test_tcp_retry_strategy(self):
        """Test TCP retry strategy configuration."""
        strategy = get_tcp_retry_strategy()

        assert strategy.config.max_attempts == 3
        assert strategy.config.base_delay == 0.5
        assert strategy.config.max_delay == 10.0

    def test_http_retry_strategy(self):
        """Test HTTP retry strategy configuration."""
        strategy = get_http_retry_strategy()

        assert strategy.config.max_attempts == 5
        assert strategy.config.base_delay == 1.0
        assert strategy.config.max_delay == 60.0
        assert ValueError in strategy.config.non_retryable_exceptions
