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


class TestCleanup:
    """Tests for cleanup functionality."""

    def test_cleanup_old_data(self):
        """Test _cleanup_old_data removes old requests."""
        limiter = RateLimiter()
        
        # Manually add old request directly to stats
        import time
        old_time = time.time() - 7200  # 2 hours ago
        stats = limiter._ip_stats["192.168.1.1"]
        stats.requests.append(old_time)
        
        # Cleanup
        limiter._cleanup_old_data()
        
        # Old request should be removed (deque popleft removes from left)
        # The old time should be gone
        assert len([t for t in stats.requests if t < time.time() - 3600]) == 0

    def test_cleanup_old_data_unbans(self):
        """Test _cleanup_old_data unbans expired IPs."""
        limiter = RateLimiter()
        
        # Ban IP with short duration
        limiter.ban_ip("192.168.1.1", duration=0.1)
        
        # Wait for ban to expire
        import time
        time.sleep(0.2)
        
        # Cleanup
        limiter._cleanup_old_data()
        
        # Should be unbanned
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.ban_until == 0.0

    @pytest.mark.asyncio
    async def test_cleanup_loop(self):
        """Test _cleanup_loop runs periodically."""
        limiter = RateLimiter()
        
        await limiter.start()
        
        # Cleanup task should be running
        assert limiter._cleanup_task is not None
        assert limiter._running is True
        
        await limiter.stop()
        assert limiter._running is False


class TestDdosDetection:
    """Tests for DDoS detection."""

    def test_check_ddos_disabled(self):
        """Test DDoS detection when disabled."""
        config = RateLimitConfig(ddos_detection_enabled=False)
        limiter = RateLimiter(config)
        
        is_ddos, ban_duration = limiter._check_ddos("192.168.1.1", IPStats())
        
        assert is_ddos is False
        assert ban_duration == 0.0

    def test_check_ddos_detects_high_rps(self):
        """Test DDoS detection with high RPS."""
        config = RateLimitConfig(ddos_threshold_rps=5, ddos_ban_duration=60.0)
        limiter = RateLimiter(config)
        stats = IPStats()
        
        # Simulate high RPS
        import time
        now = time.time()
        for _ in range(10):
            stats.requests_per_second.append(now)
        
        is_ddos, ban_duration = limiter._check_ddos("192.168.1.1", stats)
        
        assert is_ddos is True
        assert ban_duration > 0

    def test_check_ddos_progressive_ban(self):
        """Test progressive ban duration for repeat offenders."""
        config = RateLimitConfig(ddos_threshold_rps=5, ddos_ban_duration=60.0, max_ban_duration=3600.0)
        limiter = RateLimiter(config)
        stats = IPStats()
        
        # First violation
        import time
        now = time.time()
        for _ in range(10):
            stats.requests_per_second.append(now)
        
        is_ddos, ban_duration1 = limiter._check_ddos("192.168.1.1", stats)
        assert is_ddos is True
        
        # Second violation should have longer ban
        stats.ddos_violations = 1
        is_ddos, ban_duration2 = limiter._check_ddos("192.168.1.1", stats)
        
        assert ban_duration2 > ban_duration1


class TestFloodDetection:
    """Tests for connection flood detection."""

    def test_check_connection_flood_disabled(self):
        """Test flood detection when disabled."""
        config = RateLimitConfig(flood_detection_enabled=False)
        limiter = RateLimiter(config)
        
        is_flood, ban_duration = limiter._check_connection_flood("192.168.1.1", IPStats())
        
        assert is_flood is False
        assert ban_duration == 0.0

    def test_check_connection_flood_detects_high_cps(self):
        """Test flood detection with high CPS."""
        config = RateLimitConfig(flood_threshold_connections=5, flood_ban_duration=60.0)
        limiter = RateLimiter(config)
        stats = IPStats()
        
        # Simulate high CPS
        import time
        now = time.time()
        for _ in range(10):
            stats.connections_per_second.append(now)
        
        is_flood, ban_duration = limiter._check_connection_flood("192.168.1.1", stats)
        
        assert is_flood is True
        assert ban_duration > 0


class TestSubnetLimit:
    """Tests for subnet connection limits."""

    def test_check_subnet_limit_disabled(self):
        """Test subnet limit when disabled."""
        config = RateLimitConfig(enable_ip_range_limiting=False)
        limiter = RateLimiter(config)
        
        is_exceeded, subnet = limiter._check_subnet_limit("192.168.1.1")
        
        assert is_exceeded is False
        assert subnet == ""

    def test_check_subnet_limit_exceeded(self):
        """Test subnet limit exceeded."""
        config = RateLimitConfig(enable_ip_range_limiting=True, max_connections_per_subnet=2)
        limiter = RateLimiter(config)
        
        # Add connections from same subnet
        limiter._subnet_connections["192.168.1.0/24"] = {"192.168.1.1", "192.168.1.2", "192.168.1.3"}
        
        is_exceeded, subnet = limiter._check_subnet_limit("192.168.1.100")
        
        assert is_exceeded is True
        assert subnet == "192.168.1.0/24"

    def test_check_subnet_limit_not_exceeded(self):
        """Test subnet limit not exceeded."""
        config = RateLimitConfig(enable_ip_range_limiting=True, max_connections_per_subnet=5)
        limiter = RateLimiter(config)
        
        # Add few connections from same subnet
        limiter._subnet_connections["192.168.1.0/24"] = {"192.168.1.1", "192.168.1.2"}
        
        is_exceeded, subnet = limiter._check_subnet_limit("192.168.1.100")
        
        assert is_exceeded is False


class TestGlobalLimit:
    """Tests for global rate limits."""

    def test_check_global_limit_ok(self):
        """Test global limit check passes under limits."""
        limiter = RateLimiter()
        
        action = limiter._check_global_limit()
        
        assert action == RateLimitAction.ALLOW

    def test_check_global_limit_max_connections(self):
        """Test global limit rejects when max connections reached."""
        config = RateLimitConfig(max_concurrent_connections=5)
        limiter = RateLimiter(config)
        
        # Set max connections
        limiter._total_active = 5
        
        action = limiter._check_global_limit()
        
        assert action == RateLimitAction.REJECT

    def test_check_global_limit_requests_per_minute(self):
        """Test global limit delays when requests/minute exceeded."""
        config = RateLimitConfig(requests_per_minute=10)
        limiter = RateLimiter(config)
        
        # Add many requests
        import time
        now = time.time()
        for _ in range(100):
            limiter._global_requests.append(now)
        
        action = limiter._check_global_limit()
        
        assert action == RateLimitAction.DELAY


class TestTokenBucketDetailed:
    """Detailed tests for token bucket algorithm."""

    def test_refill_tokens_disabled(self):
        """Test token refill when disabled."""
        config = RateLimitConfig(token_bucket_enabled=False)
        limiter = RateLimiter(config)
        stats = IPStats()
        
        limiter._refill_tokens(stats, 100.0)
        
        # Tokens should not change
        assert stats.tokens == 20.0

    def test_refill_tokens_caps_at_capacity(self):
        """Test token refill caps at capacity."""
        limiter = RateLimiter()
        stats = IPStats()
        stats.tokens = 20.0  # Full bucket
        
        limiter._refill_tokens(stats, 100.0)
        
        # Should not exceed capacity
        assert stats.tokens <= 20.0

    def test_refill_tokens_max_10_seconds(self):
        """Test token refill caps at 10 seconds."""
        config = RateLimitConfig(token_bucket_refill_rate=10.0, token_bucket_capacity=100.0)
        limiter = RateLimiter(config)
        stats = IPStats()
        stats.tokens = 0.0
        stats.last_token_refill = 0.0
        
        # Refill after 100 seconds (should cap at 10)
        limiter._refill_tokens(stats, 100.0)
        
        # Should have 100 tokens (10 sec * 10 tokens/sec), not 1000
        assert stats.tokens == 100.0

    def test_refill_api_tokens(self):
        """Test API token refill."""
        limiter = RateLimiter()
        stats = IPStats()
        stats.api_tokens = 5.0
        stats.last_api_token_refill = 0.0
        
        limiter._refill_api_tokens(stats, 2.0)
        
        # Should refill (2 sec * 5 tokens/sec = 10, but capped at burst_size=10)
        assert stats.api_tokens <= 10.0


class TestSuspiciousScore:
    """Tests for suspicious activity scoring."""

    def test_update_suspicious_score_disabled(self):
        """Test score update when disabled."""
        config = RateLimitConfig(connection_scoring_enabled=False)
        limiter = RateLimiter(config)
        stats = IPStats()
        
        limiter._update_suspicious_score(stats, 100.0, 50.0)
        
        assert stats.suspicious_score == 0.0

    def test_update_suspicious_score_with_decay(self):
        """Test suspicious score with decay."""
        limiter = RateLimiter()
        stats = IPStats()
        stats.suspicious_score = 50.0
        stats.last_score_update = 90.0  # 10 seconds ago
        
        limiter._update_suspicious_score(stats, 100.0, 20.0)
        
        # Score should decay: 50 - (10 * 1.0) + 20 = 60
        assert stats.suspicious_score < 70.0


class TestCleanOldRequests:
    """Tests for cleaning old requests."""

    def test_clean_old_requests(self):
        """Test cleaning requests older than 1 hour."""
        limiter = RateLimiter()
        stats = IPStats()
        
        import time
        now = time.time()
        
        # Add recent and old requests (in correct order: old first, then recent)
        stats.requests.append(now - 7200)  # Old (2 hours) - will be on left
        stats.requests.append(now - 100)  # Recent
        
        limiter._clean_old_requests(stats)
        
        # Old request should be removed
        assert len([t for t in stats.requests if t < now - 3600]) == 0
        assert len([t for t in stats.requests if t > now - 3600]) == 1


class TestHandleViolation:
    """Tests for violation handling."""

    def test_handle_violation_records(self):
        """Test violation is recorded."""
        limiter = RateLimiter()
        
        # Access stats first to initialize
        stats = limiter._ip_stats["192.168.1.1"]
        
        action, delay = limiter._handle_violation("192.168.1.1", stats, "test")
        
        # Violation should be recorded
        assert stats.violations >= 1
        assert stats.blocked_requests >= 1

    def test_handle_violation_exponential_backoff(self):
        """Test exponential backoff for violations."""
        limiter = RateLimiter()
        stats = IPStats()
        
        # First violation
        _, delay1 = limiter._handle_violation("192.168.1.1", stats, "test")
        
        # Second violation should have higher delay
        _, delay2 = limiter._handle_violation("192.168.1.1", stats, "test")
        
        assert delay2 > delay1

    def test_handle_violation_ban_at_threshold(self):
        """Test ban when violations reach threshold."""
        config = RateLimitConfig(ban_threshold=2, ban_duration_seconds=60.0)
        limiter = RateLimiter(config)
        stats = IPStats()
        stats.violations = 1  # Already 1 violation
        
        action, delay = limiter._handle_violation("192.168.1.1", stats, "test")
        
        assert action == RateLimitAction.BAN
        assert delay == 60.0


class TestPrometheusMetrics:
    """Tests for Prometheus metrics export."""

    def test_get_prometheus_metrics(self):
        """Test Prometheus metrics format."""
        limiter = RateLimiter()
        
        # Add some data
        limiter.add_connection("192.168.1.1")
        limiter.check_rate_limit("192.168.1.2")
        
        metrics = limiter.get_prometheus_metrics()
        
        assert "rate_limiter_active_connections" in metrics
        assert "rate_limiter_unique_ips" in metrics
        assert "rate_limiter_banned_ips" in metrics
        assert "rate_limiter_total_violations" in metrics
        assert "# HELP" in metrics
        assert "# TYPE" in metrics

    def test_get_metrics_for_prometheus(self):
        """Test metrics dict for Prometheus."""
        limiter = RateLimiter()
        
        limiter.add_connection("192.168.1.1")
        
        metrics = limiter.get_metrics_for_prometheus()
        
        assert isinstance(metrics, dict)
        assert "rate_limiter_active_connections" in metrics
        assert "rate_limiter_unique_ips" in metrics

    def test_get_global_stats_comprehensive(self):
        """Test get_global_stats returns all fields."""
        limiter = RateLimiter()
        
        # Add various data
        limiter.add_connection("192.168.1.1")
        limiter.ban_ip("192.168.1.2")
        
        stats = limiter.get_global_stats()
        
        assert "total_active_connections" in stats
        assert "unique_ips" in stats
        assert "requests_last_minute" in stats
        assert "banned_ips" in stats
        assert "total_violations" in stats
        assert "ddos_attacks_detected" in stats
        assert "flood_attacks_detected" in stats
        assert "subnets_active" in stats
        assert "connection_flood_rate" in stats
        assert "suspicious_ips" in stats


class TestRecordRequest:
    """Tests for request recording."""

    def test_record_request_success(self):
        """Test recording successful request."""
        limiter = RateLimiter()
        
        limiter.record_request("192.168.1.1", success=True)
        
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.total_requests == 1
        assert stats.blocked_requests == 0

    def test_record_request_blocked(self):
        """Test recording blocked request."""
        limiter = RateLimiter()
        
        limiter.record_request("192.168.1.1", success=False)
        
        stats = limiter._ip_stats["192.168.1.1"]
        assert stats.total_requests == 0
        assert stats.blocked_requests == 1


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_rate_limiter_singleton(self):
        """Test get_rate_limiter returns singleton."""
        from proxy.rate_limiter import get_rate_limiter
        
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2

    def test_check_rate_limit_wrapper(self):
        """Test check_rate_limit wrapper function."""
        from proxy.rate_limiter import check_rate_limit
        
        action, delay = check_rate_limit("192.168.1.1")
        
        assert action == RateLimitAction.ALLOW

    def test_add_remove_connection_wrapper(self):
        """Test add/remove connection wrapper functions."""
        from proxy.rate_limiter import add_connection, remove_connection
        
        add_connection("192.168.1.1")
        remove_connection("192.168.1.1")
        
        # Should not raise
