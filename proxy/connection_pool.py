"""
Connection Pooling for TG WS Proxy.

Provides connection pooling for WebSocket and TCP connections:
- _WsPool — WebSocket connection pooling with health checks
- _TcpPool — TCP connection pooling with expiry
- Dynamic pool sizing based on hit/miss ratio
- Automatic connection cleanup and refill

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .stats import Stats
from .websocket_client import RawWebSocket, WsHandshakeError

# Import constants from main module
WS_POOL_SIZE = 4
WS_POOL_MAX_SIZE = 8
WS_POOL_MAX_AGE = 120.0
TCP_POOL_SIZE = 2
TCP_POOL_MAX_AGE = 60.0

log = logging.getLogger('tg-ws-pool')


class _WsPool:
    """WebSocket connection pool with health checks and dynamic sizing."""

    def __init__(self, stats: Stats):
        self.stats = stats
        self._idle: dict[tuple[int, bool], list] = {}
        self._refilling: set[tuple[int, bool]] = set()

        # Dynamic pool sizing
        self._pool_size = WS_POOL_SIZE  # Current dynamic pool size
        self._pool_max_size = WS_POOL_MAX_SIZE
        self._last_hit_count = 0
        self._last_miss_count = 0
        self._optimization_interval = 30  # Check every 30 seconds
        self._last_optimization = 0.0

        # Health check configuration
        self._heartbeat_interval = 45.0  # Send PING every 45 seconds
        self._heartbeat_timeout = 10.0   # Timeout for PONG response
        self._last_heartbeat = 0.0
        self._health_check_task: asyncio.Task | None = None

        # Memory profiling
        try:
            from .profiler import get_profiler
            profiler = get_profiler()
            self._profiler = profiler.register_component('WsPool')
        except Exception:
            self._profiler = None  # type: ignore[assignment]

    async def start_health_checker(self) -> None:
        """Start background health check task."""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Periodically send PING to all pooled connections."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._send_heartbeats()

    async def _send_heartbeats(self) -> None:
        """Send PING frames to all pooled connections and remove unresponsive ones."""
        checked_count = 0
        failed_count = 0

        for key, bucket in list(self._idle.items()):
            valid_ws: list[tuple[RawWebSocket, float]] = []
            for ws, created in bucket:
                if ws._closed:
                    continue
                try:
                    # Send PING frame
                    await ws.send(b'', opcode=RawWebSocket.OP_PING)
                    valid_ws.append((ws, created))
                    checked_count += 1
                except asyncio.TimeoutError:
                    log.debug("Health check timeout for DC%d%s", key[0], 'm' if key[1] else '')
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
                except Exception as e:
                    log.debug("Health check failed for DC%d%s: %s", key[0], 'm' if key[1] else '', e)
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
            self._idle[key] = valid_ws

        if failed_count > 0:
            log.info("Health check: %d checked, %d failed", checked_count, failed_count)
        else:
            log.debug("Health check completed: %d connections checked", checked_count)

    async def get(self, dc: int, is_media: bool,
                  target_ip: str, domains: list[str]
                  ) -> RawWebSocket | None:
        """Get WebSocket from pool or None if empty."""
        key = (dc, is_media)
        now = time.monotonic()

        bucket: list[tuple[RawWebSocket, float]] = self._idle.get(key, [])
        while bucket:
            ws, created = bucket.pop(0)
            age = now - created
            if age > WS_POOL_MAX_AGE or ws._closed:
                asyncio.create_task(self._quiet_close(ws))
                continue
            self.stats.pool_hits += 1
            log.debug("WS pool hit for DC%d%s (age=%.1fs, left=%d)",
                      dc, 'm' if is_media else '', age, len(bucket))
            self._schedule_refill(key, target_ip, domains)
            return ws

        self.stats.pool_misses += 1
        self._schedule_refill(key, target_ip, domains)
        return None

    def _can_add_to_pool(self, key: tuple[int, bool]) -> bool:
        """Check if pool can accept more connections."""
        bucket = self._idle.get(key, [])
        return len(bucket) < self._pool_max_size

    def _schedule_refill(self, key: tuple[int, bool], target_ip: str, domains: list[str]) -> None:
        """Schedule pool refill if needed."""
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key, target_ip, domains))

    async def _refill(self, key: tuple[int, bool], target_ip: str, domains: list[str]) -> None:
        """Refill pool with new connections."""
        dc, is_media = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = self._pool_size - len(bucket)
            if needed <= 0:
                return
            tasks = []
            for _ in range(needed):
                tasks.append(asyncio.create_task(
                    self._connect_one(target_ip, domains)))
            for t in tasks:
                try:
                    ws = await t
                    if ws and self._can_add_to_pool(key):
                        bucket.append((ws, time.monotonic()))
                    elif ws:
                        await self._quiet_close(ws)
                except Exception:
                    pass
            log.debug("WS pool refilled DC%d%s: %d ready",
                      dc, 'm' if is_media else '', len(bucket))
        finally:
            self._refilling.discard(key)

    def _optimize_pool_size(self, avg_latency_ms: float = 0.0) -> None:
        """
        Dynamically adjust pool size based on hit/miss ratio and latency.

        Strategy:
        - If miss rate > 30%: increase pool size (up to max)
        - If miss rate < 5%: decrease pool size (min 2)
        - If avg latency > 100ms: increase pool to reduce connection overhead
        - If latency < 30ms and low miss rate: decrease to save resources

        Args:
            avg_latency_ms: Average latency to Telegram DCs in milliseconds
        """
        now = time.monotonic()
        if now - self._last_optimization < self._optimization_interval:
            return

        total = self.stats.pool_hits + self.stats.pool_misses
        if total == 0:
            return

        # Calculate change in hits/misses since last check
        delta_hits = self.stats.pool_hits - self._last_hit_count
        delta_misses = self.stats.pool_misses - self._last_miss_count
        delta_total = delta_hits + delta_misses

        if delta_total > 0:
            current_miss_rate = delta_misses / delta_total
            old_size = self._pool_size

            # Decision logic based on miss rate and latency
            if current_miss_rate > 0.3 and self._pool_size < self._pool_max_size:
                # High miss rate - increase pool
                self._pool_size = min(self._pool_size + 1, self._pool_max_size)
                log.info("Pool optimization: miss rate %.1f%% > 30%%, increased size %d→%d",
                        current_miss_rate * 100, old_size, self._pool_size)

            elif current_miss_rate < 0.05 and self._pool_size > 2:
                # Low miss rate - decrease pool to save resources
                self._pool_size = max(self._pool_size - 1, 2)
                log.info("Pool optimization: miss rate %.1f%% < 5%%, decreased size %d→%d",
                        current_miss_rate * 100, old_size, self._pool_size)

            elif avg_latency_ms > 100 and self._pool_size < self._pool_max_size:
                # High latency - increase pool to reduce connection establishment overhead
                self._pool_size = min(self._pool_size + 1, self._pool_max_size)
                log.info("Pool optimization: high latency %.0fms > 100ms, increased size %d→%d",
                        avg_latency_ms, old_size, self._pool_size)

            elif avg_latency_ms < 30 and self._pool_size > 2 and current_miss_rate < 0.1:
                # Low latency and low miss rate - optimize resources
                self._pool_size = max(self._pool_size - 1, 2)
                log.info("Pool optimization: low latency %.0fms < 30ms, decreased size %d→%d",
                        avg_latency_ms, old_size, self._pool_size)

        # Reset counters
        self._last_hit_count = self.stats.pool_hits
        self._last_miss_count = self.stats.pool_misses
        self._last_optimization = now

    async def _connect_one(self, target_ip: str, domains: list[str]) -> RawWebSocket | None:
        """Connect to one WebSocket endpoint."""
        for domain in domains:
            try:
                ws = await RawWebSocket.connect(target_ip, domain, timeout=8)
                return ws
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    # 302 redirect - this DC doesn't support WS
                    log.debug("DC returned 302 redirect for %s", domain)
                    break
                log.debug("WS connect error for %s: %s", domain, exc)
            except Exception as e:
                log.debug("WS connect failed for %s: %s", domain, e)
        return None

    async def _quiet_close(self, ws: RawWebSocket | None) -> None:
        """Quietly close a WebSocket connection."""
        if ws:
            try:
                await ws.close()
            except Exception:
                pass

    def put(self, dc: int, is_media: bool, ws: RawWebSocket) -> None:
        """Return WebSocket to pool."""
        key = (dc, is_media)
        bucket = self._idle.setdefault(key, [])
        if len(bucket) < self._pool_max_size:
            bucket.append((ws, time.monotonic()))
        else:
            asyncio.create_task(self._quiet_close(ws))

    async def close_all(self) -> None:
        """Close all pooled connections."""
        for _key, bucket in list(self._idle.items()):
            for ws, _ in bucket:
                await self._quiet_close(ws)
        self._idle.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        total = sum(len(b) for b in self._idle.values())
        return {
            'total_connections': total,
            'pool_size': self._pool_size,
            'pool_max_size': self._pool_max_size,
            'buckets': len(self._idle),
            'hits': self.stats.pool_hits,
            'misses': self.stats.pool_misses,
        }

    def warmup(self, dc_opt: dict[int, str | None]) -> None:
        """Pre-fill pool for all configured DCs on startup."""
        from . import tg_ws_proxy

        for dc, target_ip in dc_opt.items():
            if target_ip is None:
                continue
            for is_media in (False, True):
                domains = tg_ws_proxy._ws_domains(dc, is_media)
                key = (dc, is_media)
                self._schedule_refill(key, target_ip, domains)
        log.info("WS pool warmup started for %d DC(s)", len(dc_opt))


class _TcpPool:
    """TCP connection pool with expiry."""

    def __init__(self) -> None:
        self._idle: dict[tuple[str, int], list] = {}
        self._max_size = TCP_POOL_SIZE
        self._max_age = TCP_POOL_MAX_AGE

    def get(self, host: str, port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        """Get TCP connection from pool or None if empty."""
        key = (host, port)
        bucket: list[tuple[asyncio.StreamReader, asyncio.StreamWriter, float]] = (
            self._idle.get(key, [])
        )
        now = time.monotonic()

        while bucket:
            reader, writer, created = bucket.pop(0)
            age = now - created
            if age > self._max_age:
                try:
                    writer.close()
                except Exception:
                    pass
                continue
            return reader, writer

        return None

    def put(self, host: str, port: int,
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Return TCP connection to pool."""
        key = (host, port)
        bucket = self._idle.setdefault(key, [])
        if len(bucket) < self._max_size:
            bucket.append((reader, writer, time.monotonic()))
        else:
            try:
                writer.close()
            except Exception:
                pass

    async def close_all(self) -> None:
        """Close all pooled connections."""
        for _key, bucket in list(self._idle.items()):
            for _reader, writer, _ in bucket:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
        self._idle.clear()

    def clear(self) -> None:
        """Clear all pooled connections."""
        self._idle.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get TCP pool statistics."""
        total = sum(len(b) for b in self._idle.values())
        return {
            'total_connections': total,
            'buckets': len(self._idle),
        }


# Global TCP pool instance
_tcp_pool: _TcpPool | None = None


def get_tcp_pool() -> _TcpPool:
    """Get or create global TCP pool."""
    global _tcp_pool
    if _tcp_pool is None:
        _tcp_pool = _TcpPool()
    return _tcp_pool
