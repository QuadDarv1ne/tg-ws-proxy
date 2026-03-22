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

from .autotune import AutoTuner, get_autotuner
from .retry_strategy import RetryStrategy, get_websocket_retry_strategy
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

        # Health check configuration with adaptive intervals
        self._heartbeat_interval = 30.0  # Send PING every 30 seconds (aggressive)
        self._heartbeat_timeout = 5.0    # Timeout for PONG response (reduced)
        self._last_heartbeat = 0.0
        self._health_check_task: asyncio.Task | None = None

        # Advanced health monitoring
        self._consecutive_failures: dict[int, int] = {}  # Track failures per DC
        self._last_activity: dict[int, float] = {}  # Last activity timestamp per connection
        self._aggressive_mode = False  # Enable aggressive health checking
        self._failed_connections: list[tuple[RawWebSocket, float]] = []  # Recently failed connections

        # Auto-tuner integration for adaptive timeouts
        self._autotuner: AutoTuner = get_autotuner()
        self._use_adaptive_timeout = True  # Enable adaptive timeout based on latency

        # Retry strategy for WebSocket connections
        self._retry_strategy: RetryStrategy = get_websocket_retry_strategy()

        # Connection attempt tracking per domain
        self._domain_failures: dict[str, list[float]] = {}  # domain -> [failure_timestamps]
        self._domain_success_rate: dict[str, float] = {}  # domain -> success_rate (0.0-1.0)

        # Connection scoring for WebSocket quality tracking
        self._connection_scores: dict[int, dict[str, Any]] = {}  # id(ws) -> scoring info
        self._latency_history: dict[int, list[float]] = {}  # id(ws) -> [latencies]

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
        stale_count = 0
        now = time.monotonic()

        # Aggressive mode: check more frequently when failures detected
        if self._aggressive_mode:
            self._heartbeat_interval = 15.0  # Check every 15 seconds in aggressive mode
            base_timeout = 3.0    # Shorter timeout
        else:
            self._heartbeat_interval = 30.0  # Normal mode
            base_timeout = 5.0

        # Adaptive timeout based on current latency (from autotuner)
        if self._use_adaptive_timeout:
            tuned_timeout_ms = self._autotuner.get_current_timeout()
            # Convert to seconds and apply safety margin (2x for health check)
            adaptive_timeout = max(base_timeout, (tuned_timeout_ms / 1000.0) * 0.5)
            self._heartbeat_timeout = min(adaptive_timeout, 10.0)  # Cap at 10s
        else:
            self._heartbeat_timeout = base_timeout

        for key, bucket in list(self._idle.items()):
            dc = key[0]
            valid_ws: list[tuple[RawWebSocket, float]] = []

            for ws, created in bucket:
                last_activity = self._last_activity.get(id(ws), created)
                idle_time = now - last_activity

                # Check for stale connections (no activity for > 2 minutes)
                if idle_time > 120.0:
                    log.debug("Stale connection detected for DC%d%s (idle=%.0fs)",
                             dc, 'm' if key[1] else '', idle_time)
                    asyncio.create_task(self._quiet_close(ws))
                    stale_count += 1
                    continue

                if ws._closed:
                    continue

                try:
                    # Send PING frame with timeout
                    await asyncio.wait_for(
                        ws.send(b'', opcode=RawWebSocket.OP_PING),
                        timeout=self._heartbeat_timeout
                    )
                    valid_ws.append((ws, created))
                    checked_count += 1

                    # Reset failure counter on success
                    self._consecutive_failures[dc] = 0

                except asyncio.TimeoutError:
                    log.debug("Health check timeout for DC%d%s (timeout=%.1fs)",
                             dc, 'm' if key[1] else '', self._heartbeat_timeout)
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
                    self._consecutive_failures[dc] = self._consecutive_failures.get(dc, 0) + 1
                    self._failed_connections.append((ws, now))

                except Exception as e:
                    log.debug("Health check failed for DC%d%s: %s",
                             dc, 'm' if key[1] else '', e)
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
                    self._consecutive_failures[dc] = self._consecutive_failures.get(dc, 0) + 1
                    self._failed_connections.append((ws, now))

            self._idle[key] = valid_ws

        # Clean up old failed connections (older than 5 minutes)
        self._failed_connections = [(ws, t) for ws, t in self._failed_connections if now - t < 300]

        # Adjust mode based on failures
        total_failures = sum(self._consecutive_failures.values())
        if total_failures > 5:
            self._aggressive_mode = True
            log.warning("Aggressive health check mode enabled (%d consecutive failures)", total_failures)
        elif total_failures == 0 and self._aggressive_mode:
            self._aggressive_mode = False
            log.info("Aggressive health check mode disabled (all connections healthy)")

        # Log results
        if failed_count > 0 or stale_count > 0:
            log.warning("Health check: %d checked, %d failed, %d stale (aggressive=%s)",
                       checked_count, failed_count, stale_count, self._aggressive_mode)
        else:
            log.debug("Health check passed: %d connections checked", checked_count)

    async def get(self, dc: int, is_media: bool,
                  target_ip: str, domains: list[str]
                  ) -> RawWebSocket | None:
        """Get WebSocket from pool with connection scoring."""
        key = (dc, is_media)
        now = time.monotonic()

        bucket: list[tuple[RawWebSocket, float]] = self._idle.get(key, [])
        
        # Score all connections in bucket and sort by score (best first)
        scored_connections: list[tuple[float, RawWebSocket, float]] = []
        valid_bucket: list[tuple[RawWebSocket, float]] = []
        
        for ws, created in bucket:
            age = now - created
            if age > WS_POOL_MAX_AGE or ws._closed:
                asyncio.create_task(self._quiet_close(ws))
                continue
            
            ws_id = id(ws)
            latency_ms = self._get_average_latency(ws_id)
            error_count = self._connection_scores.get(ws_id, {}).get('error_count', 0)
            score = self._calculate_connection_score(ws_id, latency_ms, error_count, age)
            scored_connections.append((score, ws, created))
            valid_bucket.append((ws, created))
        
        # Update bucket with valid connections
        self._idle[key] = valid_bucket
        
        # Get best scored connection
        if scored_connections:
            # Sort by score (highest first)
            scored_connections.sort(key=lambda x: x[0], reverse=True)
            best_score, ws, created = scored_connections[0]
            
            # Remove from bucket
            valid_bucket.remove((ws, created))
            self._idle[key] = valid_bucket
            
            # Update last activity time
            self._last_activity[id(ws)] = now
            
            self.stats.pool_hits += 1
            log.debug(
                "WS pool hit for DC%d%s (score=%.0f, latency=%.0fms, age=%.1fs, left=%d)",
                dc, 'm' if is_media else '', best_score,
                self._get_average_latency(id(ws)), now - created, len(valid_bucket)
            )
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

        Also syncs with auto-tuner for coordinated optimization.

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

        # Sync with auto-tuner (record performance sample)
        if avg_latency_ms > 0:
            asyncio.create_task(self._record_autotune_sample(avg_latency_ms, True))

    def _calculate_adaptive_health_check_interval(self) -> float:
        """
        Calculate health check interval based on connection quality.

        Returns:
            Interval in seconds (15-60 seconds)
        """
        # Base interval
        base_interval = 30.0
        
        # Adjust based on consecutive failures
        total_failures = sum(self._consecutive_failures.values())
        
        if total_failures > 10:
            # Many failures - check more frequently
            return 15.0
        elif total_failures > 5:
            # Some failures - moderate frequency
            return 20.0
        elif total_failures == 0:
            # No failures - check less frequently
            return min(60.0, base_interval * 2)
        
        return base_interval

    def _calculate_dc_reliability_score(self, dc: int) -> float:
        """
        Calculate reliability score for a DC (0-100).

        Args:
            dc: Datacenter ID

        Returns:
            Reliability score (higher = more reliable)
        """
        # Base score
        score = 100.0
        
        # Penalty for consecutive failures
        failures = self._consecutive_failures.get(dc, 0)
        score -= failures * 10
        
        # Penalty for recent failed connections
        recent_failed = sum(1 for _, t in self._failed_connections if time.monotonic() - t < 300)
        score -= recent_failed * 5
        
        # Bonus for successful health checks
        if dc in self._last_activity:
            last_activity = self._last_activity[dc]
            if time.monotonic() - last_activity < 60:
                score += 10
        
        return max(0.0, min(100.0, score))

    async def _record_autotune_sample(
        self,
        latency_ms: float,
        success: bool,
        bytes_transferred: int = 0,
    ) -> None:
        """Record a performance sample for auto-tuner."""
        try:
            await self._autotuner.record_sample(
                latency_ms=latency_ms,
                success=success,
                bytes_transferred=bytes_transferred,
                connection_reused=self.stats.pool_hits > 0,
            )
        except Exception as e:
            log.debug("Failed to record autotune sample: %s", e)

    async def _connect_one(self, target_ip: str, domains: list[str]) -> RawWebSocket | None:
        """
        Connect to one WebSocket endpoint with retry logic.

        Uses exponential backoff with jitter for resilience.
        Tracks domain success rates for intelligent domain selection.
        """
        # Sort domains by success rate (prefer domains with higher success rate)
        sorted_domains = sorted(
            domains,
            key=lambda d: self._domain_success_rate.get(d, 0.5),
            reverse=True
        )

        for domain in sorted_domains:
            # Clean up old failure records (older than 5 minutes)
            now = time.monotonic()
            self._domain_failures[domain] = [
                t for t in self._domain_failures.get(domain, [])
                if now - t < 300
            ]

            # Skip domain if it has too many recent failures (>3 in last 5 minutes)
            if len(self._domain_failures.get(domain, [])) >= 3:
                log.debug("Skipping domain %s (too many recent failures)", domain)
                continue

            # Try to connect with retry strategy
            connect_success = False
            ws = None

            async def _connect_attempt() -> RawWebSocket:
                """Inner connect function for retry strategy."""
                return await RawWebSocket.connect(target_ip, domain, timeout=8)

            # Execute with retry logic
            result = await self._retry_strategy.execute_async(_connect_attempt)

            if result.success:
                ws = result.result
                connect_success = True
                # Record success
                self._domain_success_rate[domain] = min(
                    self._domain_success_rate.get(domain, 0.5) + 0.1,
                    1.0
                )
                log.debug(
                    "WS connected to %s after %d attempt(s) "
                    "(latency=%.0fms, success_rate=%.0f%%)",
                    domain,
                    result.attempts,
                    result.total_time * 1000,
                    self._domain_success_rate[domain] * 100
                )
            else:
                # Record failure
                self._domain_failures.setdefault(domain, []).append(now)
                self._domain_success_rate[domain] = max(
                    self._domain_success_rate.get(domain, 0.5) - 0.15,
                    0.0
                )
                log.debug(
                    "WS connect failed to %s after %d attempts: %s "
                    "(success_rate=%.0f%%)",
                    domain,
                    result.attempts,
                    result.error,
                    self._domain_success_rate[domain] * 100
                )

                # Check if it's a redirect (302) - this DC doesn't support WS
                if result.error and isinstance(result.error, WsHandshakeError):
                    if result.error.is_redirect:
                        log.debug("DC returned 302 redirect for %s", domain)
                        break

            if connect_success and ws:
                return ws

        # All domains failed
        return None

    def _calculate_connection_score(
        self,
        ws_id: int,
        latency_ms: float,
        error_count: int,
        age_seconds: float,
    ) -> float:
        """
        Calculate connection quality score (0-100).

        Higher score = better connection.

        Args:
            ws_id: WebSocket object ID
            latency_ms: Connection latency
            error_count: Number of errors
            age_seconds: Connection age

        Returns:
            Score from 0 (bad) to 100 (excellent)
        """
        # Latency score (lower is better, max 100 points)
        if latency_ms < 50:
            latency_score = 100
        elif latency_ms < 100:
            latency_score = 80
        elif latency_ms < 200:
            latency_score = 60
        elif latency_ms < 500:
            latency_score = 40
        else:
            latency_score = max(0, 100 - latency_ms / 10)

        # Error penalty (max 50 points penalty)
        error_penalty = min(error_count * 10, 50)

        # Age penalty (older connections get stale, max 20 points)
        # Prefer connections that are not too old (>5 min = penalty)
        age_penalty = min(max(0, (age_seconds - 300) / 60), 20)

        score = max(0, latency_score - error_penalty - age_penalty)

        # Store scoring info
        self._connection_scores[ws_id] = {
            'score': score,
            'latency_ms': latency_ms,
            'error_count': error_count,
            'age_seconds': age_seconds,
            'calculated_at': time.monotonic(),
        }

        return score

    def _record_connection_latency(self, ws_id: int, latency_ms: float) -> None:
        """Record latency sample for connection."""
        if ws_id not in self._latency_history:
            self._latency_history[ws_id] = []

        self._latency_history[ws_id].append(latency_ms)

        # Keep only last 20 samples
        if len(self._latency_history[ws_id]) > 20:
            self._latency_history[ws_id] = self._latency_history[ws_id][-20:]

    def _get_average_latency(self, ws_id: int) -> float:
        """Get average latency for connection."""
        history = self._latency_history.get(ws_id, [])
        if not history:
            return 0.0
        return sum(history) / len(history)

    def _record_connection_error(self, ws_id: int) -> None:
        """Record error for connection."""
        if ws_id in self._connection_scores:
            self._connection_scores[ws_id]['error_count'] = (
                self._connection_scores[ws_id].get('error_count', 0) + 1
            )

    def _cleanup_connection_tracking(self, ws_id: int) -> None:
        """Clean up tracking data for closed connection."""
        self._connection_scores.pop(ws_id, None)
        self._latency_history.pop(ws_id, None)

    async def _quiet_close(self, ws: RawWebSocket | None) -> None:
        """Quietly close a WebSocket connection."""
        if ws:
            # Clean up tracking data
            ws_id = id(ws)
            self._cleanup_connection_tracking(ws_id)

            try:
                await ws.close()
            except Exception:
                pass

    def put(self, dc: int, is_media: bool, ws: RawWebSocket) -> None:
        """Return WebSocket to pool with connection scoring."""
        key = (dc, is_media)
        bucket = self._idle.setdefault(key, [])
        
        if len(bucket) < self._pool_max_size:
            now = time.monotonic()
            ws_id = id(ws)
            
            # Update last activity time
            self._last_activity[ws_id] = now
            
            # Get or create connection info
            created = now  # Default for new connections
            error_count = 0
            latency_ms = self._get_average_latency(ws_id)
            
            # Find existing connection in bucket to get created time
            for existing_ws, existing_created in bucket:
                if id(existing_ws) == ws_id:
                    created = existing_created
                    break
            
            # Get error count from tracking
            if ws_id in self._connection_scores:
                error_count = self._connection_scores[ws_id].get('error_count', 0)
            
            # Calculate connection score
            age = now - created
            score = self._calculate_connection_score(ws_id, latency_ms, error_count, age)
            
            log.debug(
                "WS returned to pool: DC%d%s, score=%.0f, latency=%.0fms, errors=%d, age=%.0fs",
                dc, 'm' if is_media else '', score, latency_ms, error_count, age
            )
            
            bucket.append((ws, created))
        else:
            asyncio.create_task(self._quiet_close(ws))

    async def close_all(self) -> None:
        """Close all pooled connections."""
        for _key, bucket in list(self._idle.items()):
            for ws, _ in bucket:
                await self._quiet_close(ws)
        self._idle.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics with Prometheus metrics support."""
        total = sum(len(b) for b in self._idle.values())
        autotune_stats = self._autotuner.get_statistics()

        # Calculate domain statistics
        now = time.monotonic()
        domain_stats = {}
        for domain in set(list(self._domain_success_rate.keys()) + list(self._domain_failures.keys())):
            # Clean up old failures
            self._domain_failures[domain] = [
                t for t in self._domain_failures.get(domain, [])
                if now - t < 300
            ]
            domain_stats[domain] = {
                'success_rate': self._domain_success_rate.get(domain, 0.5),
                'recent_failures': len(self._domain_failures.get(domain, [])),
            }

        # Connection scoring stats
        connection_scores = {
            ws_id: info['score']
            for ws_id, info in self._connection_scores.items()
        }
        avg_score = (
            sum(connection_scores.values()) / len(connection_scores)
            if connection_scores else 0
        )

        return {
            'total_connections': total,
            'pool_size': self._pool_size,
            'pool_max_size': self._pool_max_size,
            'buckets': len(self._idle),
            'hits': self.stats.pool_hits,
            'misses': self.stats.pool_misses,
            'aggressive_mode': self._aggressive_mode,
            'consecutive_failures': sum(self._consecutive_failures.values()),
            'failed_connections_recent': len(self._failed_connections),
            'heartbeat_interval': self._heartbeat_interval,
            'heartbeat_timeout': self._heartbeat_timeout,
            'domain_stats': domain_stats,
            'connection_scoring': {
                'tracked_connections': len(self._connection_scores),
                'average_score': avg_score,
                'scores': connection_scores,
            },
            'autotune': {
                'enabled': self._use_adaptive_timeout,
                'current_timeout_ms': autotune_stats['current_timeout_ms'],
                'current_pool_size': autotune_stats['current_pool_size'],
                'tuning_mode': autotune_stats['tuning_mode'],
                'tuning_applied_count': autotune_stats['tuning_applied_count'],
            },
        }

    def get_prometheus_metrics(self) -> str:
        """
        Export pool metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        stats = self.get_stats()

        # Pool connections gauge
        lines.append("# HELP tg_ws_pool_connections Total connections in pool")
        lines.append("# TYPE tg_ws_pool_connections gauge")
        lines.append(f"tg_ws_pool_connections {stats['total_connections']}")
        lines.append("")

        # Pool hits counter
        lines.append("# HELP tg_ws_pool_hits_total Total pool hits")
        lines.append("# TYPE tg_ws_pool_hits_total counter")
        lines.append(f"tg_ws_pool_hits_total {stats['hits']}")
        lines.append("")

        # Pool misses counter
        lines.append("# HELP tg_ws_pool_misses_total Total pool misses")
        lines.append("# TYPE tg_ws_pool_misses_total counter")
        lines.append(f"tg_ws_pool_misses_total {stats['misses']}")
        lines.append("")

        # Average connection score gauge
        lines.append("# HELP tg_ws_pool_avg_connection_score Average connection score")
        lines.append("# TYPE tg_ws_pool_avg_connection_score gauge")
        lines.append(f"tg_ws_pool_avg_connection_score {stats['connection_scoring']['average_score']:.2f}")
        lines.append("")

        # Domain success rate gauge
        lines.append("# HELP tg_ws_domain_success_rate Domain success rate")
        lines.append("# TYPE tg_ws_domain_success_rate gauge")
        for domain, dstats in stats['domain_stats'].items():
            safe_domain = domain.replace('.', '_').replace('-', '_')
            lines.append(f'tg_ws_domain_success_rate{{domain="{safe_domain}"}} {dstats["success_rate"]:.2f}')
        lines.append("")

        return '\n'.join(lines)

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
