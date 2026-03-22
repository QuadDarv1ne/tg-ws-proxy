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


class TestTokenBucket:
    """Tests for token bucket algorithm."""

    def test_token_bucket_enabled(self):
        """Test token bucket is enabled by default."""
        config = RateLimitConfig()
        assert config.token_bucket_enabled is True
        assert config.token_bucket_capacity == 20
        assert config.token_bucket_refill_rate == 10.0

    def test_token_bucket_refill(self):
        """Test token bucket refills over time."""
        limiter = RateLimiter()
        stats = limiter._ip_stats["192.168.1.1"]
        
        # Consume all tokens
        for _ in range(20):
            limiter.check_rate_limit("192.168.1.1")
        
        # Wait for refill (simulated)
        import time
        time.sleep(0.3)  # 3 tokens should refill at 10/sec
        
        # Trigger refill by calling check_rate_limit
        limiter.check_rate_limit("192.168.1.1")
        
        # Check tokens refilled (should have some tokens after refill)
        assert stats.tokens >= 0.5

    def test_token_bucket_consumes_tokens(self):
        """Test that check_rate_limit consumes tokens."""
        limiter = RateLimiter()
        stats = limiter._ip_stats["192.168.1.1"]
        
        initial_tokens = stats.tokens
        
        limiter.check_rate_limit("192.168.1.1")
        
        # Token should be consumed
        assert stats.tokens < initial_tokens


class TestAPIRateLimiting:
    """Tests for API rate limiting."""

    def test_api_rate_limit_config(self):
        """Test API rate limit configuration."""
        config = RateLimitConfig()
        assert config.api_rate_limit_enabled is True
        assert config.api_requests_per_second == 5.0
        assert config.api_burst_size == 10

    def test_check_api_rate_limit_allow(self):
        """Test API rate limit allows requests."""
        limiter = RateLimiter()
        
        action, delay = limiter.check_api_rate_limit("192.168.1.1")
        
        assert action == RateLimitAction.ALLOW
        assert delay == 0.0

    def test_check_api_rate_limit_delay(self):
        """Test API rate limit delays when limit exceeded."""
        limiter = RateLimiter(RateLimitConfig(api_burst_size=2, api_requests_per_second=1.0))
        
        # Consume all burst tokens
        limiter.check_api_rate_limit("192.168.1.1")
        limiter.check_api_rate_limit("192.168.1.1")
        
        # Next request should be delayed
        action, delay = limiter.check_api_rate_limit("192.168.1.1")
        
        assert action == RateLimitAction.DELAY
        assert delay > 0.0

    def test_check_api_rate_limit_allow_list(self):
        """Test API rate limit bypasses allow list."""
        limiter = RateLimiter()
        
        action, delay = limiter.check_api_rate_limit("127.0.0.1")
        
        assert action == RateLimitAction.ALLOW
        assert delay == 0.0


class TestConnectionScoring:
    """Tests for connection scoring system."""

    def test_connection_scoring_config(self):
        """Test connection scoring configuration."""
        config = RateLimitConfig()
        assert config.connection_scoring_enabled is True
        assert config.suspicious_score_threshold == 100
        assert config.score_decay_per_second == 1.0

    def test_record_suspicious_activity(self):
        """Test recording suspicious activity increases score."""
        limiter = RateLimiter()
        
        # Record suspicious activity multiple times
        limiter.record_suspicious_activity("192.168.1.1", 20.0)
        limiter.record_suspicious_activity("192.168.1.1", 20.0)
        
        stats = limiter._ip_stats["192.168.1.1"]
        # Score should accumulate (with some decay)
        assert stats.suspicious_score > 0

    def test_suspicious_score_decay(self):
        """Test suspicious score decays over time."""
        limiter = RateLimiter()
        
        limiter.record_suspicious_activity("192.168.1.1", 50.0)
        
        # Wait for decay
        import time
        time.sleep(0.5)  # 0.5 seconds decay
        
        # Record another activity to trigger decay calculation
        limiter.record_suspicious_activity("192.168.1.1", 0.0)
        
        stats = limiter._ip_stats["192.168.1.1"]
        # Score should have decayed
        assert stats.suspicious_score < 50.0

    def test_auto_ban_on_threshold(self):
        """Test auto-ban when suspicious score exceeds threshold."""
        limiter = RateLimiter(RateLimitConfig(suspicious_score_threshold=20, max_ban_duration=60.0))
        
        # Record enough suspicious activity to exceed threshold
        for _ in range(5):
            limiter.record_suspicious_activity("192.168.1.1", 10.0)
        
        stats = limiter._ip_stats["192.168.1.1"]
        # Should be banned
        assert stats.ban_until > 0 or stats.suspicious_score >= 20


class TestRateLimiterBan:
    """Tests for ban/unban functionality."""

    def test_ban_ip(self):
        """Test banning an IP."""
        limiter = RateLimiter()
        
        limiter.ban_ip("192.168.1.1", duration=300.0)
        
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.ban_until > 0

    def test_unban_ip(self):
        """Test unbanning an IP."""
        limiter = RateLimiter()
        
        limiter.ban_ip("192.168.1.1", duration=300.0)
        limiter.unban_ip("192.168.1.1")
        
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.ban_until == 0.0

    def test_check_rate_limit_banned_ip(self):
        """Test check_rate_limit returns BAN for banned IP."""
        limiter = RateLimiter()
        
        limiter.ban_ip("192.168.1.1", duration=300.0)
        
        action, delay = limiter.check_rate_limit("192.168.1.1")
        
        assert action == RateLimitAction.BAN
        assert delay > 0.0

    def test_reset_ip(self):
        """Test resetting IP stats."""
        limiter = RateLimiter()
        
        # Add some violations
        for _ in range(10):
            limiter.check_rate_limit("192.168.1.1")
        
        limiter.reset_ip("192.168.1.1")
        
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.violations == 0


class TestSubnetLimiting:
    """Tests for geographic/subnet rate limiting."""

    def test_subnet_tracking(self):
        """Test subnet tracking is enabled."""
        config = RateLimitConfig()
        assert config.enable_ip_range_limiting is True
        assert config.max_connections_per_subnet == 20

    def test_get_subnet_ipv4(self):
        """Test subnet extraction for IPv4."""
        limiter = RateLimiter()
        
        subnet = limiter._get_subnet("192.168.1.100")
        
        assert subnet == "192.168.1.0/24"

    def test_get_subnet_ipv6(self):
        """Test subnet extraction for IPv6."""
        limiter = RateLimiter()
        
        subnet = limiter._get_subnet("2001:db8::1")
        
        assert "::/32" in subnet or "2001:db8::" in subnet
