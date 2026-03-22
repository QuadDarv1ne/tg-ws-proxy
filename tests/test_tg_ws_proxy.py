"""Tests for tg_ws_proxy.py module."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.tg_ws_proxy import (
    ProxyServer,
    RawWebSocket,
    WsHandshakeError,
    _clear_dns_cache,
    _dns_cache,
    _socks5_reply,
    _ws_domains,
    _xor_mask,
    clear_dns_cache,
    get_adaptive_timeout,
    get_adaptive_timeout_stats,
    get_dns_cache_info,
    get_optimization_config,
    get_stats,
    get_stats_summary,
    parse_dc_ip_list,
    update_optimization_config,
)


class TestOptimizationConfig:
    """Tests for optimization configuration."""

    def test_get_optimization_config(self):
        """Test getting optimization config."""
        config = get_optimization_config()
        
        assert isinstance(config, dict)
        assert 'enable_dns_cache' in config
        assert 'enable_connection_pooling' in config

    def test_update_optimization_config(self):
        """Test updating optimization config."""
        update_optimization_config({'enable_dns_cache': False})
        
        config = get_optimization_config()
        assert config['enable_dns_cache'] is False
        
        # Reset
        update_optimization_config({'enable_dns_cache': True})

    def test_update_optimization_config_multiple_values(self):
        """Test updating multiple config values."""
        update_optimization_config({
            'enable_dns_cache': False,
            'pool_max_size': 10,
        })
        
        config = get_optimization_config()
        assert config['enable_dns_cache'] is False
        assert config['pool_max_size'] == 10


class TestDnsCache:
    """Tests for DNS cache functionality."""

    def test_get_dns_cache_info_empty(self):
        """Test DNS cache info when empty."""
        info = get_dns_cache_info()
        
        assert isinstance(info, dict)

    def test_clear_dns_cache(self):
        """Test clearing DNS cache."""
        # Add entry to cache
        _dns_cache['test.com'] = [('1.2.3.4', time.monotonic() + 100)]
        
        clear_dns_cache()
        
        assert 'test.com' not in _dns_cache

    def test_clear_dns_cache_function(self):
        """Test _clear_dns_cache function."""
        _dns_cache['test2.com'] = [('1.2.3.4', time.monotonic() + 100)]
        
        _clear_dns_cache()
        
        assert 'test2.com' not in _dns_cache


class TestAdaptiveTimeout:
    """Tests for adaptive timeout functionality."""

    def test_get_adaptive_timeout(self):
        """Test getting adaptive timeout."""
        timeout = get_adaptive_timeout()
        
        assert isinstance(timeout, float)
        assert timeout > 0

    def test_get_adaptive_timeout_stats(self):
        """Test getting adaptive timeout stats."""
        stats = get_adaptive_timeout_stats()
        
        assert isinstance(stats, dict)
        assert 'avg_latency_ms' in stats
        assert 'current_timeout' in stats


class TestXorMask:
    """Tests for XOR mask utility."""

    def test_xor_mask_basic(self):
        """Test basic XOR masking."""
        data = b'hello'
        mask = b'1234'
        
        masked = _xor_mask(data, mask)
        unmasked = _xor_mask(masked, mask)
        
        assert unmasked == data

    def test_xor_mask_empty(self):
        """Test XOR masking with empty data."""
        result = _xor_mask(b'', b'1234')
        assert result == b''

    def test_xor_mask_longer_data(self):
        """Test XOR masking with data longer than mask."""
        data = b'hello world test'
        mask = b'abcd'
        
        masked = _xor_mask(data, mask)
        unmasked = _xor_mask(masked, mask)
        
        assert unmasked == data


class TestWsDomains:
    """Tests for WebSocket domain selection."""

    def test_ws_domains_dc2(self):
        """Test WebSocket domains for DC2."""
        domains = _ws_domains(2, is_media=False)
        
        assert isinstance(domains, list)
        assert len(domains) > 0

    def test_ws_domains_dc4(self):
        """Test WebSocket domains for DC4."""
        domains = _ws_domains(4, is_media=False)
        
        assert isinstance(domains, list)
        assert len(domains) > 0

    def test_ws_domains_media(self):
        """Test WebSocket domains for media."""
        domains = _ws_domains(2, is_media=True)
        
        assert isinstance(domains, list)
        # Media domains might be different
        assert len(domains) > 0


class TestSocks5Reply:
    """Tests for SOCKS5 reply generation."""

    def test_socks5_reply_success(self):
        """Test SOCKS5 success reply."""
        reply = _socks5_reply(0)
        
        assert isinstance(reply, bytes)
        assert len(reply) >= 2

    def test_socks5_reply_failure(self):
        """Test SOCKS5 failure reply."""
        reply = _socks5_reply(1)
        
        assert isinstance(reply, bytes)
        assert len(reply) >= 2


class TestStats:
    """Tests for statistics functions."""

    def test_get_stats(self):
        """Test getting stats."""
        stats = get_stats()
        
        assert isinstance(stats, dict)

    def test_get_stats_summary(self):
        """Test getting stats summary."""
        summary = get_stats_summary()
        
        assert isinstance(summary, str)


class TestParseDcIpList:
    """Tests for DC IP list parsing."""

    def test_parse_dc_ip_list_basic(self):
        """Test basic DC IP list parsing."""
        dc_ips = ['2:149.154.167.220', '4:149.154.167.50']
        
        result = parse_dc_ip_list(dc_ips)
        
        assert isinstance(result, dict)
        assert 2 in result
        assert 4 in result
        assert result[2] == '149.154.167.220'
        assert result[4] == '149.154.167.50'

    def test_parse_dc_ip_list_empty(self):
        """Test empty DC IP list."""
        result = parse_dc_ip_list([])
        
        assert result == {}


class TestProxyServerInit:
    """Tests for ProxyServer initialization."""

    def test_proxy_server_init(self):
        """Test ProxyServer initialization."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            host='127.0.0.1',
            port=1080,
        )
        
        assert server.host == '127.0.0.1'
        assert server.port == 1080
        assert server.dc_opt == {2: '149.154.167.220'}

    def test_proxy_server_init_default_host(self):
        """Test ProxyServer with default host."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            port=1080,
        )
        
        assert server.host == '127.0.0.1'
        assert server.port == 1080

    def test_proxy_server_init_with_auth(self):
        """Test ProxyServer with authentication."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            auth_required=True,
            auth_credentials={'user': 'pass'},
        )
        
        assert server.auth_required is True
        assert server.auth_credentials == {'user': 'pass'}

    def test_proxy_server_init_with_whitelist(self):
        """Test ProxyServer with IP whitelist."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            ip_whitelist=['192.168.1.1', '10.0.0.1'],
        )
        
        assert server.ip_whitelist == {'192.168.1.1', '10.0.0.1'}


class TestProxyServerCallbacks:
    """Tests for ProxyServer callbacks."""

    def test_set_on_client_connect_callback(self):
        """Test setting on_client_connect callback."""
        callback = MagicMock()
        
        from proxy.tg_ws_proxy import set_on_client_connect_callback
        set_on_client_connect_callback(callback)

    def test_set_on_client_error_callback(self):
        """Test setting on_client_error callback."""
        callback = MagicMock()
        
        from proxy.tg_ws_proxy import set_on_client_error_callback
        set_on_client_error_callback(callback)

    def test_set_on_high_latency_callback(self):
        """Test setting on_high_latency callback."""
        callback = MagicMock()
        
        from proxy.tg_ws_proxy import set_on_high_latency_callback
        set_on_high_latency_callback(callback)


class TestRawWebSocketInit:
    """Tests for RawWebSocket initialization."""

    def test_raw_websocket_op_ping(self):
        """Test RawWebSocket OP_PING constant."""
        assert hasattr(RawWebSocket, 'OP_PING')

    def test_raw_websocket_op_pong(self):
        """Test RawWebSocket OP_PONG constant."""
        assert hasattr(RawWebSocket, 'OP_PONG')


class TestRawWebSocketConnect:
    """Tests for RawWebSocket connection."""

    @pytest.mark.asyncio
    async def test_raw_websocket_connect_timeout(self):
        """Test RawWebSocket connect timeout."""
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_open.side_effect=asyncio.TimeoutError()
            
            with pytest.raises(asyncio.TimeoutError):
                await RawWebSocket.connect('1.2.3.4', 'example.com', timeout=0.1)

    @pytest.mark.asyncio
    async def test_raw_websocket_connect_refused(self):
        """Test RawWebSocket connect refused."""
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_open.side_effect=ConnectionRefusedError()
            
            with pytest.raises((ConnectionRefusedError, OSError)):
                await RawWebSocket.connect('1.2.3.4', 'example.com', timeout=0.1)


class TestWsHandshakeError:
    """Tests for WsHandshakeError exception."""

    def test_ws_handshake_error_basic(self):
        """Test basic WsHandshakeError."""
        error = WsHandshakeError(status_code=500, status_line="Internal Server Error")
        
        assert error.status_code == 500
        assert error.status_line == "Internal Server Error"

    def test_ws_handshake_error_with_code(self):
        """Test WsHandshakeError with status code."""
        error = WsHandshakeError(status_code=302, status_line="Found", location="/new")
        
        assert error.status_code == 302
        assert error.is_redirect is True
        assert error.location == "/new"

    def test_ws_handshake_error_not_redirect(self):
        """Test WsHandshakeError without redirect."""
        error = WsHandshakeError(status_code=404, status_line="Not Found")
        
        assert error.status_code == 404
        assert error.is_redirect is False


class TestProxyServerEncryption:
    """Tests for ProxyServer encryption features."""

    def test_proxy_server_encryption_setup(self):
        """Test encryption setup."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            encryption_config={
                'encryption_enabled': True,
                'encryption_type': 'aes-256-gcm',
            },
        )
        
        # Encryption should be configured
        assert server.encryption_enabled is True
        assert server.crypto_manager is not None

    def test_proxy_server_encryption_disabled(self):
        """Test encryption disabled by default."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        assert server.encryption_enabled is False
        assert server.crypto_manager is None


class TestProxyServerRateLimiter:
    """Tests for ProxyServer rate limiter features."""

    def test_proxy_server_rate_limiter_setup(self):
        """Test rate limiter setup."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            rate_limit_config={
                'requests_per_second': 10.0,
                'max_concurrent_connections': 100,
            },
        )
        
        # Rate limiter should be configured
        assert server.rate_limiter is not None

    def test_proxy_server_rate_limiter_disabled(self):
        """Test rate limiter disabled by default."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        assert server.rate_limiter is None


class TestProxyServerCircuitBreaker:
    """Tests for ProxyServer circuit breaker integration."""

    def test_proxy_server_circuit_breakers_initialized(self):
        """Test circuit breakers are initialized."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        # Circuit breakers should be initialized
        assert len(server._circuit_breakers) > 0

    def test_proxy_server_ws_blacklist(self):
        """Test WebSocket blacklist."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        assert hasattr(server, 'ws_blacklist')
        assert isinstance(server.ws_blacklist, set)


class TestProxyServerStats:
    """Tests for ProxyServer statistics."""

    def test_proxy_server_get_stats(self):
        """Test getting server stats."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        stats = server.get_stats()
        
        assert isinstance(stats, dict)

    def test_proxy_server_get_optimization_metrics(self):
        """Test getting optimization metrics."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        metrics = server.get_optimization_metrics()
        
        assert isinstance(metrics, dict)
        assert 'config' in metrics

    def test_proxy_server_update_optimization_metrics(self):
        """Test updating optimization metrics."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        server.update_optimization_metrics(total_dns_resolutions=100)
        
        metrics = server.get_optimization_metrics()
        assert metrics['total_dns_resolutions'] == 100

    def test_proxy_server_record_dns_cache_hit(self):
        """Test recording DNS cache hit."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        server.record_dns_cache_hit()
        
        metrics = server.get_optimization_metrics()
        assert metrics['dns_cache_hits'] >= 1

    def test_proxy_server_record_dns_cache_miss(self):
        """Test recording DNS cache miss."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        server.record_dns_cache_miss()
        
        metrics = server.get_optimization_metrics()
        assert metrics['dns_cache_misses'] >= 1


class TestProxyServerKeyRotation:
    """Tests for ProxyServer key rotation."""

    @pytest.mark.asyncio
    async def test_proxy_server_start_key_rotation(self):
        """Test starting key rotation."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            encryption_config={
                'encryption_enabled': True,
                'encryption_type': 'aes-256-gcm',
            },
        )
        
        await server._start_key_rotation()
        
        assert server._key_rotation_task is not None
        
        # Cleanup
        server._stop_key_rotation()

    @pytest.mark.asyncio
    async def test_proxy_server_stop_key_rotation(self):
        """Test stopping key rotation."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            encryption_config={
                'encryption_enabled': True,
                'encryption_type': 'aes-256-gcm',
            },
        )
        
        await server._start_key_rotation()
        server._stop_key_rotation()
        
        assert server._key_rotation_task is None


class TestProxyServerDcFailures:
    """Tests for ProxyServer DC failure tracking."""

    def test_proxy_server_dc_error_count(self):
        """Test DC error count tracking."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        key = (2, False)
        server.dc_error_count[key] = 5
        
        assert server.dc_error_count[key] == 5

    def test_proxy_server_dc_fail_until(self):
        """Test DC fail_until tracking."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        key = (2, False)
        server.dc_fail_until[key] = time.monotonic() + 60
        
        assert server.dc_fail_until[key] > time.monotonic()


class TestProxyServerOptimization:
    """Tests for ProxyServer optimization features."""

    def test_proxy_server_ws_pool_lazy_initialized(self):
        """Test WebSocket pool is lazy initialized."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        # Pool should be None until accessed
        assert server._ws_pool is None


class TestProxyServerMemory:
    """Tests for ProxyServer memory management."""

    def test_proxy_server_stats_optimized(self):
        """Test stats are optimized for memory."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
        )
        
        # Stats should be created with memory optimization
        assert server.stats is not None


class TestProxyServerRun:
    """Tests for ProxyServer run functionality."""

    def test_proxy_server_get_stats_method(self):
        """Test ProxyServer has get_stats method."""
        server = ProxyServer(
            dc_opt={2: '149.154.167.220'},
            port=0,
        )
        
        # Server should have get_stats method
        assert hasattr(server, 'get_stats')
        assert callable(server.get_stats)
