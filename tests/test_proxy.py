"""Unit tests for tg_ws_proxy module."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.connection_pool import _TcpPool, _WsPool, get_tcp_pool
from proxy.stats import Stats
from proxy.tg_ws_proxy import (
    ProxyServer,
    _check_ws_domain_available,
    _check_ws_domains_available,
    _clear_dns_cache,
    _dns_cache,
    _measure_all_dc_pings,
    _measure_dc_ping,
    _resolve_domain_cached,
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
        pool = _TcpPool()

        result = pool.get("127.0.0.1", 443)

        assert result is None

    @pytest.mark.asyncio
    async def test_tcp_pool_put_and_get(self):
        """Test putting and getting connection."""
        pool = _TcpPool()
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.transport.is_closing.return_value = False

        pool.put("127.0.0.1", 443, mock_reader, mock_writer)
        result = pool.get("127.0.0.1", 443)

        assert result == (mock_reader, mock_writer)

    @pytest.mark.asyncio
    async def test_tcp_pool_expired_connection(self):
        """Test that expired connections are not returned."""
        pool = _TcpPool()
        pool._max_age = 0.1  # 100ms max age
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.is_closing.return_value = False
        mock_writer.transport.is_closing.return_value = False

        pool.put("127.0.0.1", 443, mock_reader, mock_writer)
        await asyncio.sleep(0.2)  # Wait for expiration
        result = pool.get("127.0.0.1", 443)

        assert result is None

    @pytest.mark.asyncio
    async def test_tcp_pool_max_size(self):
        """Test pool respects max size."""
        pool = _TcpPool()
        pool._max_size = 2
        mock_writer_closing = MagicMock()
        mock_writer_closing.is_closing.return_value = True
        mock_writer_closing.close = MagicMock()

        # Add 3 connections (exceeds max_size=2)
        for _ in range(3):
            pool.put("127.0.0.1", 443, MagicMock(), mock_writer_closing)

        # Pool should only keep 2
        assert len(pool._idle.get(("127.0.0.1", 443), [])) <= 2

    @pytest.mark.asyncio
    async def test_tcp_pool_clear(self):
        """Test clearing the pool."""
        pool = _TcpPool()
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
        # Reset via get_tcp_pool function
        import proxy.connection_pool as cp
        cp._tcp_pool = None

    def test_get_tcp_pool_lazy_init(self):
        """Test lazy initialization of TCP pool."""
        import proxy.connection_pool as cp
        cp._tcp_pool = None  # Reset

        pool = get_tcp_pool()

        assert pool is not None
        assert isinstance(pool, _TcpPool)
        assert cp._tcp_pool is pool

    def test_get_tcp_pool_singleton(self):
        """Test that pool is singleton."""
        pool1 = get_tcp_pool()
        pool2 = get_tcp_pool()

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


class TestCheckWsDomainAvailable:
    """Tests for _check_ws_domain_available function."""

    @pytest.mark.asyncio
    async def test_domain_available(self):
        """Test domain availability check with successful resolution."""
        with patch('proxy.tg_ws_proxy._resolve_domain_cached') as mock_resolve:
            mock_resolve.return_value = [("149.154.167.220", 443)]

            is_available, error = await _check_ws_domain_available(2)

            assert is_available is True
            assert error is None

    @pytest.mark.asyncio
    async def test_domain_not_available(self):
        """Test domain availability check with failed resolution."""
        with patch('proxy.tg_ws_proxy._resolve_domain_cached') as mock_resolve:
            mock_resolve.return_value = []

            is_available, error = await _check_ws_domain_available(2)

            assert is_available is False
            assert error is not None


class TestCheckWsDomainsAvailable:
    """Tests for _check_ws_domains_available function."""

    @pytest.mark.asyncio
    async def test_multiple_dcs(self):
        """Test domain check for multiple DCs."""
        dc_opt = {2: "149.154.167.220", 4: "149.154.167.220"}

        with patch('proxy.tg_ws_proxy._check_ws_domain_available') as mock_check:
            mock_check.return_value = (True, None)

            results = await _check_ws_domains_available(dc_opt)

            assert 2 in results
            assert 4 in results
            assert results[2][0] is True
            assert results[4][0] is True


class TestMeasureDcPing:
    """Tests for _measure_dc_ping function."""

    @pytest.mark.asyncio
    async def test_ping_success(self):
        """Test successful ping measurement."""
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch('asyncio.open_connection') as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)

            latency, error = await _measure_dc_ping(2)

            assert latency is not None
            assert latency > 0
            assert error is None
            mock_writer.close.assert_called()

    @pytest.mark.asyncio
    async def test_ping_timeout(self):
        """Test ping timeout."""
        with patch('asyncio.open_connection') as mock_open:
            mock_open.side_effect = asyncio.TimeoutError()

            latency, error = await _measure_dc_ping(2, timeout=0.1)

            assert latency is None
            assert error is not None


class TestMeasureAllDcPings:
    """Tests for _measure_all_dc_pings function."""

    @pytest.mark.asyncio
    async def test_measure_multiple_dcs(self):
        """Test ping measurement for multiple DCs."""
        dc_opt = {2: "149.154.167.220", 4: "149.154.167.220"}

        with patch('proxy.tg_ws_proxy._measure_dc_ping') as mock_ping:
            mock_ping.return_value = (10.5, None)

            results = await _measure_all_dc_pings(dc_opt)

            assert 2 in results
            assert 4 in results
            assert results[2] == 10.5
            assert results[4] == 10.5


class TestHandleClientAuth:
    """Tests for _handle_client authentication logic."""

    @pytest.mark.asyncio
    async def test_auth_required_client_no_support(self):
        """Test client rejected when auth required but client doesn't support."""
        dc_opt = {2: "149.154.167.220"}
        auth_credentials = {"username": "test", "password": "pass"}
        stats = Stats()
        ws_pool = _WsPool(stats)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_writer.is_closing.return_value = False
        mock_writer.close = MagicMock()
        mock_writer.drain = AsyncMock()

        # SOCKS5 greeting with no auth method (only 0x00)
        mock_reader.readexactly = AsyncMock(side_effect=[
            b'\x05\x01',  # SOCKS5, 1 method
            b'\x00',      # No auth method
        ])

        from proxy.tg_ws_proxy import _handle_client

        await _handle_client(
            reader=mock_reader,
            writer=mock_writer,
            stats=stats,
            dc_opt=dc_opt,
            ws_pool=ws_pool,
            ws_blacklist=set(),
            dc_fail_until={},
            auth_required=True,
            auth_credentials=auth_credentials,
        )

        # Should write \x05\xff (no acceptable methods)
        mock_writer.write.assert_any_call(b'\x05\xff')


class TestHandleClientIpWhitelist:
    """Tests for IP whitelist functionality."""

    @pytest.mark.asyncio
    async def test_ip_not_in_whitelist(self):
        """Test client rejected when IP not in whitelist."""
        dc_opt = {2: "149.154.167.220"}
        ip_whitelist = {"192.168.1.1"}
        stats = Stats()
        ws_pool = _WsPool(stats)

        mock_reader = AsyncMock()
        mock_writer = MagicMock()
        mock_writer.get_extra_info.return_value = ("10.0.0.1", 12345)  # Not in whitelist
        mock_writer.is_closing.return_value = False
        mock_writer.close = MagicMock()

        from proxy.tg_ws_proxy import _handle_client

        await _handle_client(
            reader=mock_reader,
            writer=mock_writer,
            stats=stats,
            dc_opt=dc_opt,
            ws_pool=ws_pool,
            ws_blacklist=set(),
            dc_fail_until={},
            ip_whitelist=ip_whitelist,
        )

        # Writer should be closed
        mock_writer.close.assert_called()

    def test_proxy_server_whitelist_init(self):
        """Test ProxyServer initializes whitelist correctly."""
        dc_opt = {2: "149.154.167.220"}
        whitelist = ["192.168.1.1", "10.0.0.1"]

        from proxy.tg_ws_proxy import ProxyServer
        server = ProxyServer(dc_opt=dc_opt, ip_whitelist=whitelist)

        # Whitelist should be converted to set
        assert isinstance(server.ip_whitelist, set)
        assert server.ip_whitelist == {"192.168.1.1", "10.0.0.1"}

    def test_proxy_server_whitelist_none(self):
        """Test ProxyServer with no whitelist (None)."""
        dc_opt = {2: "149.154.167.220"}

        from proxy.tg_ws_proxy import ProxyServer
        server = ProxyServer(dc_opt=dc_opt)

        # No whitelist means all IPs allowed
        assert server.ip_whitelist is None
