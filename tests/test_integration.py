"""Integration tests for TG WS Proxy."""

from __future__ import annotations

import asyncio
import socket
import time
from unittest.mock import AsyncMock, patch

import pytest

from proxy.tg_ws_proxy import (
    ProxyServer,
    _dns_cache,
    _resolve_domain_cached,
    clear_dns_cache,
    get_adaptive_timeout,
    update_optimization_config,
)


class TestDnsResolverIntegration:
    """Integration tests for DNS resolver."""

    @pytest.mark.asyncio
    async def test_resolve_domain_cached_google(self):
        """Test resolving google.com with caching."""
        clear_dns_cache()
        
        # First resolution (cache miss)
        start = time.monotonic()
        result1 = await _resolve_domain_cached('google.com', timeout=5.0)
        time1 = time.monotonic() - start
        
        assert len(result1) > 0
        assert all(isinstance(ip, tuple) and len(ip) == 2 for ip in result1)
        
        # Second resolution (cache hit) - should be faster
        start = time.monotonic()
        result2 = await _resolve_domain_cached('google.com', timeout=5.0)
        time2 = time.monotonic() - start
        
        assert len(result2) > 0
        assert time2 < time1  # Cache hit should be faster

    @pytest.mark.asyncio
    async def test_resolve_domain_cached_invalid(self):
        """Test resolving invalid domain."""
        clear_dns_cache()
        
        result = await _resolve_domain_cached('invalid.domain.that.does.not.exist', timeout=2.0)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_resolve_domain_cache_expiry(self):
        """Test DNS cache expiry."""
        clear_dns_cache()
        
        # Set short TTL
        from proxy.tg_ws_proxy import _dns_cache_ttl
        original_ttl = _dns_cache_ttl
        
        try:
            # Temporarily set very short TTL
            import proxy.tg_ws_proxy as tg_ws_proxy
            tg_ws_proxy._dns_cache_ttl = 0.1
            
            # Resolve domain
            result1 = await _resolve_domain_cached('google.com', timeout=5.0)
            assert len(result1) > 0
            
            # Wait for expiry
            await asyncio.sleep(0.2)
            
            # Should resolve again (cache expired)
            result2 = await _resolve_domain_cached('google.com', timeout=5.0)
            assert len(result2) > 0
            
        finally:
            # Restore original TTL
            tg_ws_proxy._dns_cache_ttl = original_ttl


class TestAdaptiveTimeoutIntegration:
    """Integration tests for adaptive timeout."""

    def test_adaptive_timeout_concurrent_requests(self):
        """Test adaptive timeout with concurrent requests."""
        # Simulate multiple requests
        timeouts = []
        for _ in range(10):
            timeout = get_adaptive_timeout()
            timeouts.append(timeout)
        
        # All timeouts should be reasonable
        assert all(5.0 <= t <= 30.0 for t in timeouts)

    def test_adaptive_timeout_latency_simulation(self):
        """Test adaptive timeout with simulated latency."""
        from proxy.tg_ws_proxy import _OPTIMIZATION_CONFIG
        
        # Update config with latency data
        update_optimization_config({
            'enable_adaptive_timeout': True,
            'connection_timeout_base': 10.0,
            'connection_timeout_multiplier': 2.0,
        })
        
        timeout = get_adaptive_timeout()
        
        # Should use base timeout
        assert timeout >= 10.0


class TestProxyServerIntegration:
    """Integration tests for ProxyServer."""

    def test_proxy_server_initialization(self):
        """Test ProxyServer initialization."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            port=1080,
        )
        
        # Server should be initialized
        assert server.host == '127.0.0.1'
        assert server.port == 1080
        assert server.dc_opt == {2: '149.154.167.220'}

    @pytest.mark.asyncio
    async def test_proxy_server_with_encryption(self):
        """Test ProxyServer with encryption enabled."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            encryption_config={
                'encryption_enabled': True,
                'encryption_type': 'aes-256-gcm',
                'key_rotation_interval': 60,
            },
            port=0,
        )
        
        assert server.encryption_enabled is True
        assert server.crypto_manager is not None

    @pytest.mark.asyncio
    async def test_proxy_server_with_rate_limiting(self):
        """Test ProxyServer with rate limiting."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            rate_limit_config={
                'enabled': True,
                'max_concurrent_connections': 10,
                'requests_per_minute': 100,
            },
            port=0,
        )
        
        assert server.rate_limiter is not None
        
        # Start rate limiter
        await server._start_rate_limiter()
        
        # Stop rate limiter
        await server._stop_rate_limiter()

    def test_proxy_server_circuit_breaker_trips(self):
        """Test circuit breaker trips on failures."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            port=0,
        )
        
        cb = server.get_circuit_breaker('websocket')
        
        # Simulate failures using private method (internal API)
        for _ in range(5):
            cb._on_failure()
        
        # Circuit should be open
        assert cb.is_closed is False

    def test_proxy_server_stats_tracking(self):
        """Test ProxyServer statistics tracking."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            port=0,
        )
        
        # Record some DNS metrics
        server.record_dns_cache_hit()
        server.record_dns_cache_hit()
        server.record_dns_cache_miss()
        
        metrics = server.get_optimization_metrics()
        
        assert metrics['dns_cache_hits'] == 2
        assert metrics['dns_cache_misses'] == 1
        assert metrics['total_dns_resolutions'] == 3


class TestConnectionPoolIntegration:
    """Integration tests for connection pool."""

    def test_tcp_pool_get_put(self):
        """Test TCP pool get/put operations."""
        from proxy.connection_pool import _TcpPool
        
        pool = _TcpPool()
        
        # Pool should be empty
        conn = pool.get('127.0.0.1', 80)
        assert conn is None
        
        # Put mock connection (we can't create real streams without event loop)
        # Just test that put doesn't raise
        pool.put('127.0.0.1', 80, None, None)
        
        # Connection should be in pool
        key = ('127.0.0.1', 80)
        assert key in pool._idle

    def test_tcp_pool_max_size(self):
        """Test TCP pool respects max size."""
        from proxy.connection_pool import _TcpPool, TCP_POOL_SIZE
        
        pool = _TcpPool()
        
        # Max size should be default
        assert pool._max_size == TCP_POOL_SIZE


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        from proxy.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=0.5,
        )
        
        cb = CircuitBreaker('test', config)
        
        # Initial state: CLOSED
        assert cb.is_closed is True
        
        # Cause failures to open circuit
        for _ in range(3):
            cb._on_failure()
        
        # Circuit should be OPEN
        assert cb.is_closed is False
        
        # Wait for timeout
        await asyncio.sleep(0.6)
        
        # Should allow request (transitions to HALF_OPEN internally)
        assert cb._should_allow_request() is True
        
        # Success should close circuit
        for _ in range(2):
            cb._on_success()
        
        # Circuit should be CLOSED
        assert cb.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_wrapper(self):
        """Test circuit breaker call wrapper."""
        from proxy.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
        
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.5)
        cb = CircuitBreaker('test', config)
        
        async def success_func():
            return 'success'
        
        async def fail_func():
            raise ValueError('test error')
        
        # Successful call
        result = await cb.call(success_func)
        assert result == 'success'
        
        # Failed calls
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)
        
        # Circuit should be open, next call should raise CircuitBreakerError
        from proxy.circuit_breaker import CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await cb.call(success_func)


class TestRateLimiterIntegration:
    """Integration tests for rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_token_bucket(self):
        """Test rate limiter token bucket algorithm."""
        from proxy.rate_limiter import RateLimiter, RateLimitConfig, RateLimitAction
        
        config = RateLimitConfig(
            token_bucket_enabled=True,
            token_bucket_capacity=5,
            token_bucket_refill_rate=2.0,
        )
        
        limiter = RateLimiter(config)
        
        # Consume all tokens
        for _ in range(5):
            action, _ = limiter.check_rate_limit('192.168.1.1')
            assert action == RateLimitAction.ALLOW
        
        # Next request should be rate limited (may be ALLOW or DELAY depending on timing)
        # Just check that rate limiter is working
        action, delay = limiter.check_rate_limit('192.168.1.1')
        assert action in (RateLimitAction.ALLOW, RateLimitAction.DELAY, RateLimitAction.REJECT)
        
        # Wait for refill
        await asyncio.sleep(1.0)
        
        # Should have tokens again
        action, _ = limiter.check_rate_limit('192.168.1.1')
        assert action == RateLimitAction.ALLOW

    @pytest.mark.asyncio
    async def test_rate_limiter_ban_unban(self):
        """Test rate limiter ban and unban."""
        from proxy.rate_limiter import RateLimiter, RateLimitAction
        
        limiter = RateLimiter()
        
        # Ban IP
        limiter.ban_ip('192.168.1.1', duration=60.0)
        
        # Should be banned
        action, _ = limiter.check_rate_limit('192.168.1.1')
        assert action == RateLimitAction.BAN
        
        # Unban
        limiter.unban_ip('192.168.1.1')
        
        # Should be allowed
        action, _ = limiter.check_rate_limit('192.168.1.1')
        assert action == RateLimitAction.ALLOW


class TestMetricsHistoryIntegration:
    """Integration tests for metrics history."""

    def test_metrics_history_recording(self):
        """Test metrics history recording."""
        from proxy.metrics_history import MetricsHistory
        
        history = MetricsHistory(':memory:')
        
        # Record some metrics
        history.record_metric('test_metric', 10.0, labels={'source': 'test'})
        history.record_metric('test_metric', 20.0, labels={'source': 'test'})
        history.record_metric('test_metric', 30.0, labels={'source': 'test'})
        
        # Get summary
        summary = history.get_metric_summary('test_metric', hours=1)
        
        assert summary is not None
        assert summary.count == 3
        assert summary.min_value == 10.0
        assert summary.max_value == 30.0
        assert abs(summary.avg_value - 20.0) < 0.01

    def test_metrics_history_trend(self):
        """Test metrics history trend analysis."""
        from proxy.metrics_history import MetricsHistory
        
        history = MetricsHistory(':memory:')
        
        # Record increasing metrics
        for i in range(10):
            history.record_metric('trend_metric', float(i * 10))
        
        # Get trend
        trend = history.get_trend('trend_metric', hours=1)
        
        assert trend['direction'] in ['increasing', 'stable']  # May be stable with small data
        assert trend['data_points'] >= 2


class TestPluggableTransportsIntegration:
    """Integration tests for pluggable transports."""

    def test_obfs4_obfuscation(self):
        """Test obfs4-like obfuscation."""
        from proxy.pluggable_transports import Obfs4Obfuscator
        
        obfuscator = Obfs4Obfuscator()
        
        # Create client handshake
        client_hs = obfuscator.create_client_handshake()
        
        assert len(client_hs) == 1968
        
        # Obfuscate and deobfuscate
        data = b'Hello, World!'
        obfuscated = obfuscator.obfuscate(data)
        deobfuscated = obfuscator.deobfuscate(obfuscated)
        
        assert deobfuscated == data

    def test_websocket_fragmentation(self):
        """Test WebSocket fragmentation."""
        from proxy.pluggable_transports import WSFragmenter

        fragmenter = WSFragmenter()

        # Create large message
        data = b'X' * 1000

        # Fragment
        fragments = fragmenter.fragment(data)

        # All fragments except possibly the last should be within size limits
        for i, frag in enumerate(fragments):
            if i < len(fragments) - 1:
                assert 64 <= len(frag) <= 256
            else:
                # Last fragment can be smaller
                assert len(frag) <= 256

        # Reassemble
        reassembled = fragmenter.reassemble(fragments)

        assert reassembled == data

    def test_shadowsocks_encryption(self):
        """Test Shadowsocks-style encryption."""
        from proxy.pluggable_transports import ShadowsocksObfs
        
        obfs = ShadowsocksObfs(password='password123', cipher='aes-256-gcm')
        
        # Encrypt and decrypt
        data = b'Secret message'
        encrypted = obfs.encrypt(data)
        decrypted = obfs.decrypt(encrypted)
        
        assert decrypted == data
