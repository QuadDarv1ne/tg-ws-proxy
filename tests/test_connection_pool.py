"""Tests for connection_pool.py module."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.connection_pool import (
    TCP_POOL_MAX_AGE,
    TCP_POOL_SIZE,
    WS_POOL_MAX_AGE,
    WS_POOL_SIZE,
    _TcpPool,
    _WsPool,
    get_tcp_pool,
)


class MockStats:
    """Mock stats object for testing."""
    
    def __init__(self):
        self.pool_hits = 0
        self.pool_misses = 0
        self.tcp_pool_hits = 0
        self.tcp_pool_misses = 0


@pytest.fixture
def mock_stats():
    """Create mock stats."""
    return MockStats()


@pytest.fixture
def mock_ws():
    """Create mock WebSocket connection."""
    ws = MagicMock()
    ws._closed = False
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestWsPoolInit:
    """Tests for _WsPool initialization."""

    def test_ws_pool_init(self, mock_stats):
        """Test _WsPool initialization."""
        pool = _WsPool(mock_stats)
        
        assert pool.stats is mock_stats
        assert pool._idle == {}
        assert pool._refilling == set()
        assert pool._pool_size == WS_POOL_SIZE

    def test_ws_pool_with_different_stats(self):
        """Test _WsPool with different stats instance."""
        stats1 = MockStats()
        stats2 = MockStats()
        
        pool1 = _WsPool(stats1)
        pool2 = _WsPool(stats2)
        
        assert pool1.stats is stats1
        assert pool2.stats is stats2


class TestTcpPoolInit:
    """Tests for _TcpPool initialization."""

    def test_tcp_pool_init(self):
        """Test _TcpPool initialization."""
        pool = _TcpPool()
        
        assert pool._idle == {}
        assert pool._max_size == TCP_POOL_SIZE

    def test_tcp_pool_multiple_instances(self):
        """Test multiple _TcpPool instances."""
        pool1 = _TcpPool()
        pool2 = _TcpPool()
        
        assert pool1 is not pool2


class TestWsPoolGet:
    """Tests for _WsPool.get method."""

    @pytest.mark.asyncio
    async def test_ws_pool_get_empty_pool(self, mock_stats):
        """Test getting from empty pool returns None."""
        pool = _WsPool(mock_stats)
        
        result = await pool.get(dc=2, is_media=False, target_ip="1.2.3.4", domains=["example.com"])
        
        assert result is None
        assert mock_stats.pool_misses == 1

    @pytest.mark.asyncio
    async def test_ws_pool_get_with_connection(self, mock_stats, mock_ws):
        """Test getting connection from pool."""
        pool = _WsPool(mock_stats)
        
        # Add connection to pool
        key = (2, False)
        pool._idle[key] = [(mock_ws, time.monotonic())]
        pool._latency_history[id(mock_ws)] = [50.0]
        
        result = await pool.get(dc=2, is_media=False, target_ip="1.2.3.4", domains=["example.com"])
        
        assert result is mock_ws
        assert mock_stats.pool_hits == 1

    @pytest.mark.asyncio
    async def test_ws_pool_get_removes_from_bucket(self, mock_stats, mock_ws):
        """Test that get removes connection from bucket."""
        pool = _WsPool(mock_stats)
        
        key = (2, False)
        pool._idle[key] = [(mock_ws, time.monotonic())]
        pool._latency_history[id(mock_ws)] = [50.0]
        
        await pool.get(dc=2, is_media=False, target_ip="1.2.3.4", domains=["example.com"])
        
        # Connection should be removed from bucket
        assert len(pool._idle.get(key, [])) == 0

    @pytest.mark.asyncio
    async def test_ws_pool_get_removes_stale(self, mock_stats, mock_ws):
        """Test that stale connections are removed."""
        pool = _WsPool(mock_stats)
        
        key = (2, False)
        # Add stale connection (older than MAX_AGE)
        pool._idle[key] = [(mock_ws, time.monotonic() - WS_POOL_MAX_AGE - 10)]
        
        result = await pool.get(dc=2, is_media=False, target_ip="1.2.3.4", domains=["example.com"])
        
        assert result is None


class TestWsPoolHealthCheck:
    """Tests for _WsPool health checking."""

    @pytest.mark.asyncio
    async def test_send_heartbeats(self, mock_stats, mock_ws):
        """Test sending heartbeats to pooled connections."""
        pool = _WsPool(mock_stats)
        
        key = (2, False)
        pool._idle[key] = [(mock_ws, time.monotonic())]
        pool._last_activity[id(mock_ws)] = time.monotonic()
        
        await pool._send_heartbeats()
        
        # PING should be sent
        mock_ws.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_heartbeats_removes_closed(self, mock_stats):
        """Test that closed connections are removed during heartbeat."""
        pool = _WsPool(mock_stats)
        
        closed_ws = MagicMock()
        closed_ws._closed = True
        
        key = (2, False)
        pool._idle[key] = [(closed_ws, time.monotonic())]
        
        await pool._send_heartbeats()
        
        # Closed connection should be removed
        assert len(pool._idle.get(key, [])) == 0

    @pytest.mark.asyncio
    async def test_send_heartbeats_handles_timeout(self, mock_stats):
        """Test heartbeat handles timeout."""
        pool = _WsPool(mock_stats)
        
        timeout_ws = MagicMock()
        timeout_ws._closed = False
        timeout_ws.send = AsyncMock(side_effect=asyncio.TimeoutError())
        
        key = (2, False)
        pool._idle[key] = [(timeout_ws, time.monotonic())]
        pool._last_activity[id(timeout_ws)] = time.monotonic()
        
        await pool._send_heartbeats()
        
        # Timed out connection should be removed
        assert len(pool._idle.get(key, [])) == 0

    @pytest.mark.asyncio
    async def test_aggressive_mode_on_failures(self, mock_stats):
        """Test aggressive mode is enabled on failures."""
        pool = _WsPool(mock_stats)
        
        # Simulate multiple failures
        pool._consecutive_failures = {1: 2, 2: 2, 3: 2}
        
        await pool._send_heartbeats()
        
        assert pool._aggressive_mode is True


class TestWsPoolRefill:
    """Tests for _WsPool refill functionality."""

    @pytest.mark.asyncio
    async def test_refill_respects_max_size(self, mock_stats):
        """Test pool refill respects max size."""
        pool = _WsPool(mock_stats)
        
        key = (2, False)
        # Fill pool to max
        pool._idle[key] = [(MagicMock(), time.monotonic()) for _ in range(pool._pool_max_size)]
        pool._refilling.add(key)
        
        # Mock _connect_one to return None (connection failure)
        with patch.object(pool, '_connect_one', new_callable=AsyncMock, return_value=None):
            await pool._refill(key, "1.2.3.4", ["example.com"])
        
        # Should not exceed max size
        assert len(pool._idle[key]) <= pool._pool_max_size

    @pytest.mark.asyncio
    async def test_schedule_refill_prevents_duplicate(self, mock_stats):
        """Test schedule_refill prevents duplicate refills."""
        pool = _WsPool(mock_stats)
        
        key = (2, False)
        pool._schedule_refill(key, "1.2.3.4", ["example.com"])
        
        # Key should be in refilling set
        assert key in pool._refilling


class TestWsPoolOptimization:
    """Tests for _WsPool dynamic optimization."""

    def test_optimize_pool_size_high_miss_rate(self, mock_stats):
        """Test pool optimization with high miss rate."""
        pool = _WsPool(mock_stats)
        pool._last_optimization = 0  # Force optimization
        
        # Simulate high miss rate
        pool.stats.pool_hits = 10
        pool.stats.pool_misses = 50
        pool._last_hit_count = 0
        pool._last_miss_count = 0
        
        pool._optimize_pool_size()
        
        # Pool size should increase
        assert pool._pool_size > WS_POOL_SIZE

    def test_optimize_pool_size_low_miss_rate(self, mock_stats):
        """Test pool optimization with low miss rate."""
        pool = _WsPool(mock_stats)
        pool._pool_size = 6  # Start with larger pool
        pool._last_optimization = 0
        
        # Simulate low miss rate
        pool.stats.pool_hits = 100
        pool.stats.pool_misses = 2
        pool._last_hit_count = 0
        pool._last_miss_count = 0
        
        pool._optimize_pool_size()
        
        # Pool size should decrease
        assert pool._pool_size < 6

    def test_optimize_pool_size_no_changes_if_recent(self, mock_stats):
        """Test optimization skips if recently optimized."""
        pool = _WsPool(mock_stats)
        pool._last_optimization = time.monotonic()
        
        old_size = pool._pool_size
        
        pool._optimize_pool_size()
        
        # Size should not change
        assert pool._pool_size == old_size


class TestTcpPool:
    """Tests for _TcpPool."""

    def test_tcp_pool_get_empty(self):
        """Test TCP pool get from empty pool."""
        pool = _TcpPool()
        
        result = pool.get("127.0.0.1", 8080)
        
        assert result is None

    def test_tcp_pool_get_with_connection(self):
        """Test TCP pool get with available connection."""
        pool = _TcpPool()
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        key = ("127.0.0.1", 8080)
        pool._idle[key] = [(mock_reader, mock_writer, time.monotonic())]
        
        result = pool.get("127.0.0.1", 8080)
        
        assert result is not None
        assert result[0] is mock_reader
        assert result[1] is mock_writer

    def test_tcp_pool_put(self):
        """Test TCP pool put connection."""
        pool = _TcpPool()
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        pool.put("127.0.0.1", 8080, mock_reader, mock_writer)
        
        key = ("127.0.0.1", 8080)
        assert len(pool._idle[key]) == 1

    @pytest.mark.asyncio
    async def test_tcp_pool_close_all(self):
        """Test TCP pool close all connections."""
        pool = _TcpPool()
        
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        
        pool.put("127.0.0.1", 8080, MagicMock(), mock_writer)
        
        await pool.close_all()
        
        # Connection should be closed
        mock_writer.close.assert_called()

    def test_tcp_pool_removes_expired(self):
        """Test TCP pool removes expired connections."""
        pool = _TcpPool()
        
        mock_reader = MagicMock()
        mock_writer = MagicMock()
        key = ("127.0.0.1", 8080)
        # Add expired connection
        pool._idle[key] = [(mock_reader, mock_writer, time.monotonic() - TCP_POOL_MAX_AGE - 10)]
        
        result = pool.get("127.0.0.1", 8080)
        
        assert result is None

    def test_tcp_pool_clear(self):
        """Test TCP pool clear."""
        pool = _TcpPool()
        
        pool.put("127.0.0.1", 8080, MagicMock(), MagicMock())
        pool.clear()
        
        assert len(pool._idle) == 0

    def test_tcp_pool_get_stats(self):
        """Test TCP pool stats."""
        pool = _TcpPool()
        
        pool.put("127.0.0.1", 8080, MagicMock(), MagicMock())
        pool.put("127.0.0.1", 8081, MagicMock(), MagicMock())
        
        stats = pool.get_stats()
        
        assert 'total_connections' in stats
        assert 'buckets' in stats
        assert stats['total_connections'] == 2


class TestConnectionScoring:
    """Tests for connection scoring functionality."""

    def test_calculate_connection_score(self, mock_stats):
        """Test connection score calculation."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        latency_ms = 50.0
        error_count = 0
        age = 10.0
        
        score = pool._calculate_connection_score(ws_id, latency_ms, error_count, age)
        
        # Score should be positive
        assert score > 0

    def test_calculate_connection_score_with_errors(self, mock_stats):
        """Test connection score with errors."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        latency_ms = 50.0
        error_count = 10
        age = 10.0
        
        score = pool._calculate_connection_score(ws_id, latency_ms, error_count, age)
        
        # Score should be lower with errors
        assert score >= 0

    def test_record_connection_error(self, mock_stats):
        """Test recording connection error."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        pool._connection_scores[ws_id] = {'error_count': 0}
        
        pool._record_connection_error(ws_id)
        
        assert pool._connection_scores[ws_id]['error_count'] == 1

    def test_record_connection_latency(self, mock_stats):
        """Test recording latency sample."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        
        pool._record_connection_latency(ws_id, 50.0)
        
        assert ws_id in pool._latency_history
        assert 50.0 in pool._latency_history[ws_id]

    def test_get_average_latency(self, mock_stats):
        """Test getting average latency."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        pool._latency_history[ws_id] = [40.0, 50.0, 60.0]
        
        avg = pool._get_average_latency(ws_id)
        
        assert avg == 50.0

    def test_cleanup_connection_tracking(self, mock_stats):
        """Test cleaning up connection tracking."""
        pool = _WsPool(mock_stats)
        
        ws_id = 12345
        pool._connection_scores[ws_id] = {'score': 80}
        pool._latency_history[ws_id] = [50.0]
        
        pool._cleanup_connection_tracking(ws_id)
        
        assert ws_id not in pool._connection_scores
        assert ws_id not in pool._latency_history


class TestQuietClose:
    """Tests for _quiet_close method."""

    @pytest.mark.asyncio
    async def test_quiet_close(self, mock_stats, mock_ws):
        """Test quiet close of WebSocket."""
        pool = _WsPool(mock_stats)
        
        await pool._quiet_close(mock_ws)
        
        # close should be called
        mock_ws.close.assert_called()

    @pytest.mark.asyncio
    async def test_quiet_close_handles_exception(self, mock_stats):
        """Test quiet close handles exceptions."""
        pool = _WsPool(mock_stats)
        
        error_ws = MagicMock()
        error_ws.close = AsyncMock(side_effect=Exception("test"))
        
        # Should not raise
        await pool._quiet_close(error_ws)


class TestWsPoolPut:
    """Tests for _WsPool.put method."""

    def test_ws_pool_put(self, mock_stats, mock_ws):
        """Test returning WebSocket to pool."""
        pool = _WsPool(mock_stats)
        
        pool.put(dc=2, is_media=False, ws=mock_ws)
        
        key = (2, False)
        assert len(pool._idle[key]) == 1

    def test_ws_pool_put_updates_tracking(self, mock_stats, mock_ws):
        """Test put updates connection tracking."""
        pool = _WsPool(mock_stats)
        
        ws_id = id(mock_ws)
        pool._latency_history[ws_id] = [50.0]
        
        pool.put(dc=2, is_media=False, ws=mock_ws)
        
        # Last activity should be updated
        assert ws_id in pool._last_activity


class TestWsPoolStats:
    """Tests for _WsPool statistics."""

    def test_get_stats(self, mock_stats):
        """Test getting pool stats."""
        pool = _WsPool(mock_stats)
        
        # Add some data
        mock_ws = MagicMock()
        mock_ws._closed = False
        pool._idle[(2, False)] = [(mock_ws, time.monotonic())]
        
        stats = pool.get_stats()
        
        assert 'total_connections' in stats
        assert 'pool_size' in stats
        assert 'hits' in stats
        assert 'misses' in stats

    def test_get_prometheus_metrics(self, mock_stats):
        """Test Prometheus metrics export."""
        pool = _WsPool(mock_stats)
        
        metrics = pool.get_prometheus_metrics()
        
        assert 'tg_ws_pool_connections' in metrics
        assert 'tg_ws_pool_hits_total' in metrics
        assert 'tg_ws_pool_misses_total' in metrics


class TestGetTcpPool:
    """Tests for get_tcp_pool function."""

    def test_get_tcp_pool_singleton(self):
        """Test get_tcp_pool returns singleton."""
        import proxy.connection_pool as cp
        cp._tcp_pool = None  # Reset
        
        try:
            pool1 = get_tcp_pool()
            pool2 = get_tcp_pool()
            
            assert pool1 is pool2
        finally:
            cp._tcp_pool = None  # Reset


class TestDomainTracking:
    """Tests for domain failure/success tracking."""

    def test_domain_failure_tracking(self, mock_stats):
        """Test domain failure is tracked."""
        pool = _WsPool(mock_stats)
        
        domain = "example.com"
        now = time.monotonic()
        
        pool._domain_failures[domain] = [now - 100, now - 50, now]
        
        # Should have 3 failures
        assert len(pool._domain_failures[domain]) == 3

    def test_domain_success_rate_update(self, mock_stats):
        """Test domain success rate is updated."""
        pool = _WsPool(mock_stats)
        
        domain = "good.com"
        pool._domain_success_rate[domain] = 0.5
        
        # Simulate success
        pool._domain_success_rate[domain] = min(
            pool._domain_success_rate.get(domain, 0.5) + 0.1,
            1.0
        )
        
        assert pool._domain_success_rate[domain] == 0.6

    def test_get_stats_includes_domains(self, mock_stats):
        """Test get_stats includes domain statistics."""
        pool = _WsPool(mock_stats)
        
        pool._domain_success_rate["example.com"] = 0.8
        pool._domain_failures["example.com"] = [time.monotonic() - 100]
        
        stats = pool.get_stats()
        
        assert 'domain_stats' in stats
        assert 'example.com' in stats['domain_stats']
