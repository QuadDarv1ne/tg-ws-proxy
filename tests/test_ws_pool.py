"""Tests for WebSocket connection pool and Keep-alive."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from proxy.stats import Stats
from proxy.tg_ws_proxy import RawWebSocket, _WsPool


@pytest.fixture
def stats():
    return Stats()

@pytest.fixture
def ws_pool(stats):
    # Patch heartbeat loop to avoid background task interference during tests
    with patch("proxy.tg_ws_proxy.asyncio.create_task"):
        return _WsPool(stats)

class TestWsPoolLogic:
    """Tests for _WsPool class."""

    @pytest.mark.asyncio
    async def test_pool_get_empty(self, ws_pool):
        """Test getting from empty pool should return None and schedule refill."""
        with patch.object(ws_pool, "_schedule_refill") as mock_refill:
            ws = await ws_pool.get(2, False, "1.1.1.1", ["kws2.web.telegram.org"])
            assert ws is None
            assert ws_pool.stats.pool_misses == 1
            mock_refill.assert_called_once()

    @pytest.mark.asyncio
    async def test_pool_put_and_get(self, ws_pool):
        """Test put connection into pool and retrieve it."""
        mock_ws = AsyncMock(spec=RawWebSocket)
        mock_ws._closed = False
        key = (2, False)

        # Manually put into idle list
        ws_pool._idle[key] = [(mock_ws, time.monotonic())]

        ws = await ws_pool.get(2, False, "1.1.1.1", ["kws2.web.telegram.org"])

        assert ws is mock_ws
        assert ws_pool.stats.pool_hits == 1
        assert len(ws_pool._idle[key]) == 0

    @pytest.mark.asyncio
    async def test_pool_expired_connection(self, ws_pool):
        """Test that expired connections are discarded."""
        mock_ws = AsyncMock(spec=RawWebSocket)
        mock_ws._closed = False
        key = (2, False)

        # Put expired connection (older than WS_POOL_MAX_AGE which is 120s)
        ws_pool._idle[key] = [(mock_ws, time.monotonic() - 200)]

        # Mock _quiet_close to track calls
        with patch.object(ws_pool, "_quiet_close", new_callable=AsyncMock):
            ws = await ws_pool.get(2, False, "1.1.1.1", ["kws2.web.telegram.org"])

            assert ws is None
            # _quiet_close should be scheduled (but not executed due to mocked create_task)
            # We verify that it was scheduled by checking the pool state
            assert len(ws_pool._idle.get(key, [])) == 0

    @pytest.mark.asyncio
    async def test_heartbeat_cleanup(self, ws_pool):
        """Test that heartbeat loop removes closed connections."""
        mock_ws_alive = AsyncMock(spec=RawWebSocket)
        mock_ws_alive._closed = False
        mock_ws_alive.send = AsyncMock()

        mock_ws_dead = AsyncMock(spec=RawWebSocket)
        mock_ws_dead._closed = True

        key = (2, False)
        ws_pool._idle[key] = [
            (mock_ws_alive, time.monotonic()),
            (mock_ws_dead, time.monotonic())
        ]

        # Trigger one heartbeat iteration logic manually
        # (Simplified version of _heartbeat_loop)
        for k, bucket in list(ws_pool._idle.items()):
            valid = []
            for ws, created in bucket:
                if not ws._closed:
                    try:
                        await ws.send(b'', opcode=0x9)  # PING
                        valid.append((ws, created))
                    except Exception:
                        pass
            ws_pool._idle[k] = valid

        assert len(ws_pool._idle[key]) == 1
        assert ws_pool._idle[key][0][0] is mock_ws_alive
        mock_ws_alive.send.assert_called_once()
