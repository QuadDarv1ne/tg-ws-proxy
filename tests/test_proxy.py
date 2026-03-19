"""Unit tests for tg_ws_proxy module."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.stats import Stats
from proxy.tg_ws_proxy import (
    ProxyServer,
    _clear_dns_cache,
    _dns_cache,
    _get_tcp_pool,
    _resolve_domain_cached,
    _TcpPool,
    _WsPool,
)


class TestDnsCache:
    """Tests for DNS caching functionality."""

    def teardown_method(self):
        """Clear DNS cache after each test."""
        _dns_cache.clear()

    @pytest.mark.asyncio
    async def test_resolve_domain_cached_first_miss(self):
        """Test DNS resolution on cache miss."""
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_resolver = AsyncMock(return_value=[
                (2, 1, 6, '', ('8.8.8.8', 443)),
                (2, 1, 6, '', ('8.8.4.4', 443)),
            ])
            mock_loop.return_value.getaddrinfo = mock_resolver

            result = await _resolve_domain_cached("example.com", port=443)

            assert len(result) == 2
            assert ("8.8.8.8", 443) in result
            assert ("8.8.4.4", 443) in result

    @pytest.mark.asyncio
    async def test_resolve_domain_cached_hit(self):
        """Test DNS resolution on cache hit."""
        now = time.monotonic()
        _dns_cache["test.com"] = [("1.2.3.4", now + 300)]

        result = await _resolve_domain_cached("test.com", port=443)

        assert result == [("1.2.3.4", 443)]

    @pytest.mark.asyncio
    async def test_resolve_domain_cached_expired(self):
        """Test DNS resolution with expired cache."""
        now = time.monotonic()
        _dns_cache["expired.com"] = [("1.2.3.4", now - 100)]  # Expired

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_resolver = AsyncMock(return_value=[
                (2, 1, 6, '', ('5.6.7.8', 443)),
            ])
            mock_loop.return_value.getaddrinfo = mock_resolver

            result = await _resolve_domain_cached("expired.com", port=443)

            assert result == [("5.6.7.8", 443)]
            assert "expired.com" in _dns_cache  # New cache entry

    def test_clear_dns_cache(self):
        """Test DNS cache clearing."""
        _dns_cache["test1.com"] = [("1.2.3.4", time.monotonic() + 300)]
        _dns_cache["test2.com"] = [("5.6.7.8", time.monotonic() + 300)]

        _clear_dns_cache()

        assert len(_dns_cache) == 0


class TestTcpPool:
    """Tests for TCP connection pool."""

    @pytest.mark.asyncio
    async def test_tcp_pool_get_empty(self):
        """Test getting connection from empty pool."""
        pool = _TcpPool(Stats(), max_size=4, max_age=60.0)

        result = await pool.get("127.0.0.1", 443)

        assert result is None

    @pytest.mark.asyncio
    async def test_tcp_pool_put_and_get(self):
        """Test putting and getting connection."""
        pool = _TcpPool(Stats(), max_size=4, max_age=60.0)
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.transport.is_closing.return_value = False

        pool.put("127.0.0.1", 443, mock_reader, mock_writer)
        result = await pool.get("127.0.0.1", 443)

        assert result == (mock_reader, mock_writer)

    @pytest.mark.asyncio
    async def test_tcp_pool_expired_connection(self):
        """Test that expired connections are not returned."""
        pool = _TcpPool(Stats(), max_size=4, max_age=0.1)  # 100ms max age
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.transport.is_closing.return_value = False

        pool.put("127.0.0.1", 443, mock_reader, mock_writer)
        await asyncio.sleep(0.2)  # Wait for expiration
        result = await pool.get("127.0.0.1", 443)

        assert result is None

    @pytest.mark.asyncio
    async def test_tcp_pool_max_size(self):
        """Test pool respects max size."""
        pool = _TcpPool(Stats(), max_size=2, max_age=60.0)
        mock_writer_closing = MagicMock()
        mock_writer_closing.is_closing.return_value = True
        mock_writer_closing.close = MagicMock()

        # Add 3 connections (exceeds max_size=2)
        for _ in range(3):
            pool.put("127.0.0.1", 443, MagicMock(), mock_writer_closing)

        # Pool should only keep 2
        assert len(pool._idle.get("127.0.0.1:443", [])) <= 2

    @pytest.mark.asyncio
    async def test_tcp_pool_clear(self):
        """Test clearing the pool."""
        pool = _TcpPool(Stats(), max_size=4, max_age=60.0)
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.transport.is_closing.return_value = False

        pool.put("127.0.0.1", 443, mock_reader, mock_writer)
        pool.clear()

        assert len(pool._idle) == 0


class TestGetTcpPool:
    """Tests for lazy TCP pool initialization."""

    def teardown_module(self):
        """Reset global pool after tests."""
        from proxy import tg_ws_proxy
        tg_ws_proxy._tcp_pool = None

    def test_get_tcp_pool_lazy_init(self):
        """Test lazy initialization of TCP pool."""
        from proxy import tg_ws_proxy
        tg_ws_proxy._tcp_pool = None  # Reset

        pool = _get_tcp_pool()

        assert pool is not None
        assert isinstance(pool, _TcpPool)
        assert tg_ws_proxy._tcp_pool is pool

    def test_get_tcp_pool_singleton(self):
        """Test that pool is singleton."""
        pool1 = _get_tcp_pool()
        pool2 = _get_tcp_pool()

        assert pool1 is pool2


class TestProxyServer:
    """Tests for ProxyServer class."""

    def test_proxy_server_init(self):
        """Test ProxyServer initialization."""
        dc_opt = {2: "149.154.167.220"}
        server = ProxyServer(
            dc_opt=dc_opt,
            host="127.0.0.1",
            port=8080,
        )

        assert server.dc_opt == dc_opt
        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server._ws_pool is None  # Lazy init

    def test_proxy_server_ws_pool_lazy(self):
        """Test lazy initialization of ws_pool."""
        dc_opt = {2: "149.154.167.220"}
        server = ProxyServer(dc_opt=dc_opt)

        # Pool should be None initially
        assert server._ws_pool is None

        # Access property to trigger lazy init
        pool = server.ws_pool

        assert pool is not None
        assert isinstance(pool, _WsPool)
        assert server._ws_pool is pool

    def test_proxy_server_get_stats(self):
        """Test get_stats method."""
        dc_opt = {2: "149.154.167.220"}
        server = ProxyServer(dc_opt=dc_opt)

        stats = server.get_stats()

        assert isinstance(stats, dict)
        assert "connections_total" in stats
        assert "bytes_up" in stats  # Stats uses bytes_up/bytes_down

    def test_proxy_server_get_stats_summary(self):
        """Test get_stats_summary method."""
        dc_opt = {2: "149.154.167.220"}
        server = ProxyServer(dc_opt=dc_opt)

        summary = server.get_stats_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestWsPool:
    """Tests for WebSocket pool."""

    def test_ws_pool_init(self):
        """Test WebSocket pool initialization."""
        stats = Stats()
        pool = _WsPool(stats)

        assert pool._pool_size == 4  # Default WS_POOL_SIZE
        assert pool._pool_max_size == 8  # Default WS_POOL_MAX_SIZE
        assert pool.stats is stats

    def test_ws_pool_can_add(self):
        """Test _can_add_to_pool method."""
        stats = Stats()
        pool = _WsPool(stats)
        key = (2, False)

        # Empty bucket - can add
        assert pool._can_add_to_pool(key) is True

        # Fill bucket to max
        for _ in range(pool._pool_max_size):
            pool._idle.setdefault(key, []).append(MagicMock())

        # Full bucket - cannot add
        assert pool._can_add_to_pool(key) is False


class TestProxyServerAuth:
    """Tests for ProxyServer with authentication."""

    def test_proxy_server_with_auth(self):
        """Test ProxyServer with auth enabled."""
        dc_opt = {2: "149.154.167.220"}
        auth_credentials = {"username": "test", "password": "pass"}

        server = ProxyServer(
            dc_opt=dc_opt,
            auth_required=True,
            auth_credentials=auth_credentials,
        )

        assert server.auth_required is True
        assert server.auth_credentials == auth_credentials

    def test_proxy_server_with_ip_whitelist(self):
        """Test ProxyServer with IP whitelist."""
        dc_opt = {2: "149.154.167.220"}
        ip_whitelist = ["192.168.1.1", "10.0.0.1"]

        server = ProxyServer(
            dc_opt=dc_opt,
            ip_whitelist=ip_whitelist,
        )

        # ip_whitelist is converted to set
        assert server.ip_whitelist == {"192.168.1.1", "10.0.0.1"}
