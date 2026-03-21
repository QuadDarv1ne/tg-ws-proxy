"""Tests for rate_limiter.py module."""

from __future__ import annotations

import pytest

from proxy.rate_limiter import (
    IPStats,
    RateLimitAction,
    RateLimitConfig,
    RateLimiter,
)


class TestRateLimitAction:
    """Tests for RateLimitAction enum."""

    def test_rate_limit_action_values(self):
        """Test RateLimitAction enum values."""
        assert RateLimitAction.ALLOW.value == 1
        assert RateLimitAction.DELAY.value == 2
        assert RateLimitAction.REJECT.value == 3
        assert RateLimitAction.BAN.value == 4


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_rate_limit_config_default(self):
        """Test default RateLimitConfig."""
        config = RateLimitConfig()

        assert config.requests_per_second == 10.0
        assert config.requests_per_minute == 100
        assert config.requests_per_hour == 1000
        assert config.max_concurrent_connections == 500
        assert config.max_connections_per_ip == 10
        assert config.ban_threshold == 5
        assert config.ban_duration_seconds == 300.0
        assert config.initial_delay_ms == 100
        assert config.max_delay_ms == 5000
        assert config.backoff_multiplier == 2.0
        assert "127.0.0.1" in config.allow_list

    def test_rate_limit_config_custom(self):
        """Test custom RateLimitConfig."""
        config = RateLimitConfig(
            requests_per_second=5.0,
            max_concurrent_connections=100,
        )

        assert config.requests_per_second == 5.0
        assert config.max_concurrent_connections == 100


class TestIPStats:
    """Tests for IPStats dataclass."""

    def test_ip_stats_default(self):
        """Test default IPStats."""
        stats = IPStats()

        assert len(stats.requests) == 0
        assert stats.violations == 0
        assert stats.ban_until == 0.0
        assert stats.total_requests == 0
        assert stats.blocked_requests == 0


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_rate_limiter_init(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter()

        assert limiter._running is False
        assert limiter._cleanup_task is None
        assert len(limiter._ip_stats) == 0

    def test_rate_limiter_custom_config(self):
        """Test RateLimiter with custom config."""
        config = RateLimitConfig(requests_per_second=5.0)
        limiter = RateLimiter(config)

        assert limiter.config.requests_per_second == 5.0

    @pytest.mark.asyncio
    async def test_rate_limiter_start_stop(self):
        """Test RateLimiter start and stop."""
        limiter = RateLimiter()

        await limiter.start()
        assert limiter._running is True
        assert limiter._cleanup_task is not None

        await limiter.stop()
        assert limiter._running is False

    def test_rate_limiter_check_rate_limit(self):
        """Test check_rate_limit method."""
        limiter = RateLimiter()

        action, delay = limiter.check_rate_limit("192.168.1.1")

        assert action == RateLimitAction.ALLOW
        assert delay == 0

    def test_rate_limiter_check_rate_limit_allow_list(self):
        """Test check_rate_limit for allow-listed IP."""
        limiter = RateLimiter()

        action, delay = limiter.check_rate_limit("127.0.0.1")

        assert action == RateLimitAction.ALLOW
        assert delay == 0

    def test_rate_limiter_check_rate_limit_records(self):
        """Test check_rate_limit records requests."""
        limiter = RateLimiter()

        limiter.check_rate_limit("192.168.1.1")

        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.total_requests >= 1

    def test_rate_limiter_get_ip_stats(self):
        """Test get_ip_stats method."""
        limiter = RateLimiter()

        limiter.check_rate_limit("192.168.1.1")

        stats = limiter.get_ip_stats("192.168.1.1")

        assert isinstance(stats, dict)
        assert 'total_requests' in stats

    def test_rate_limiter_get_ip_stats_missing(self):
        """Test get_ip_stats for missing IP."""
        limiter = RateLimiter()

        stats = limiter.get_ip_stats("192.168.1.1")

        assert isinstance(stats, dict)

    def test_rate_limiter_get_global_stats(self):
        """Test get_global_stats method."""
        limiter = RateLimiter()

        stats = limiter.get_global_stats()

        assert 'total_active_connections' in stats
        assert 'unique_ips' in stats

    def test_rate_limiter_add_connection(self):
        """Test add_connection method."""
        limiter = RateLimiter()

        limiter.add_connection("192.168.1.1")

        assert limiter._active_connections["192.168.1.1"] == 1
        assert limiter._total_active == 1

    def test_rate_limiter_remove_connection(self):
        """Test remove_connection method."""
        limiter = RateLimiter()

        limiter.add_connection("192.168.1.1")
        limiter.remove_connection("192.168.1.1")

        assert limiter._active_connections["192.168.1.1"] == 0
        assert limiter._total_active == 0
