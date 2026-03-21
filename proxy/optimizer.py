"""
Performance Auto-Optimizer Module for TG WS Proxy.

Provides automatic performance optimization:
- Dynamic pool sizing based on load
- Memory usage optimization
- Connection pooling adjustments
- CPU-aware throttling
- Smart DC selection based on latency and error history
- Adaptive connection caching

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import psutil

log = logging.getLogger('tg-ws-optimizer')


class OptimizationLevel(Enum):
    """Performance optimization levels."""
    MINIMAL = auto()      # Low resource usage
    BALANCED = auto()     # Balanced performance
    AGGRESSIVE = auto()   # Maximum performance


@dataclass
class PerformanceMetrics:
    """Current performance metrics."""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    active_connections: int = 0
    connections_per_second: float = 0.0
    avg_latency_ms: float = 0.0
    pool_utilization: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class DCStats:
    """Statistics for a single datacenter."""
    dc_id: int
    total_connections: int = 0
    failed_connections: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float | None = None
    last_error_time: float | None = None
    consecutive_errors: int = 0
    is_blacklisted: bool = False
    blacklisted_until: float | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_connections == 0:
            return 100.0
        return ((self.total_connections - self.failed_connections) / self.total_connections) * 100

    @property
    def avg_latency(self) -> float:
        """Calculate average latency."""
        if self.total_connections == 0:
            return 0.0
        return self.total_latency_ms / self.total_connections

    def record_success(self, latency_ms: float) -> None:
        """Record a successful connection."""
        self.total_connections += 1
        self.total_latency_ms += latency_ms
        self.last_latency_ms = latency_ms
        self.consecutive_errors = 0

    def record_failure(self) -> None:
        """Record a failed connection."""
        self.total_connections += 1
        self.failed_connections += 1
        self.last_error_time = time.time()
        self.consecutive_errors += 1

    def get_score(self) -> float:
        """
        Calculate DC quality score (higher is better).
        Combines success rate, latency, and recent errors.
        """
        # Base score from success rate (0-100)
        score = self.success_rate

        # Latency penalty (reduce score for high latency)
        if self.last_latency_ms:
            latency_penalty = min(self.last_latency_ms / 10, 50)  # Max 50 point penalty
            score -= latency_penalty

        # Consecutive error penalty
        score -= self.consecutive_errors * 10

        # Blacklist penalty
        if self.is_blacklisted:
            score -= 100

        return max(0, score)


@dataclass
class OptimizationConfig:
    """Optimizer configuration."""
    level: OptimizationLevel = OptimizationLevel.BALANCED
    check_interval_seconds: float = 30.0
    cpu_threshold_high: float = 80.0
    cpu_threshold_critical: float = 95.0
    memory_threshold_high: float = 80.0
    memory_threshold_critical: float = 95.0
    max_pool_size: int = 64
    min_pool_size: int = 4
    connection_timeout_seconds: float = 10.0
    enable_auto_scaling: bool = True
    enable_memory_optimization: bool = True
    enable_smart_dc_selection: bool = True
    dc_blacklist_duration: float = 300.0  # 5 minutes
    dc_error_threshold: int = 3  # Errors before blacklist consideration
    min_dc_success_rate: float = 50.0  # Minimum success rate to use DC


class PerformanceOptimizer:
    """Automatic performance optimizer."""

    def __init__(
        self,
        config: OptimizationConfig | None = None,
        on_optimization: Callable[[str], None] | None = None,
    ):
        self.config = config or OptimizationConfig()
        self._on_optimization = on_optimization
        self._metrics_history: list[PerformanceMetrics] = []
        self._running = False
        self._optimization_task: asyncio.Task | None = None
        self._process = psutil.Process(os.getpid())

        # Dynamic pool settings
        self._current_pool_size = self.config.min_pool_size
        self._current_max_connections = 100

        # Optimization statistics
        self.optimizations_applied = 0
        self.last_optimization_time: float | None = None
        self._optimization_reasons: list[str] = []
        
        # Smart DC selection
        self._dc_stats: dict[int, DCStats] = {}
        self._dc_stats_lock = asyncio.Lock()
        
        # Connection cache with LRU eviction
        self._connection_cache: dict[str, tuple[any, float, int]] = {}  # key -> (connection, timestamp, hits)
        self._cache_max_size = 100
        self._cache_ttl = 120.0  # 2 minutes

    async def start(self) -> None:
        """Start the optimizer."""
        self._running = True
        self._optimization_task = asyncio.create_task(self._optimization_loop())
        log.info(
            "Performance optimizer started (level: %s, interval: %.1fs)",
            self.config.level.name,
            self.config.check_interval_seconds
        )

    async def stop(self) -> None:
        """Stop the optimizer."""
        self._running = False
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
        log.info("Performance optimizer stopped")

    async def _optimization_loop(self) -> None:
        """Main optimization loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                await self._check_and_optimize()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Optimizer error: %s", e)

    async def _check_and_optimize(self) -> None:
        """Check metrics and apply optimizations."""
        metrics = await self._collect_metrics()
        self._metrics_history.append(metrics)

        # Keep only recent history
        max_history = int(300 / self.config.check_interval_seconds)  # 5 minutes
        if len(self._metrics_history) > max_history:
            self._metrics_history = self._metrics_history[-max_history:]

        # Apply optimizations based on level
        if self.config.enable_auto_scaling:
            await self._optimize_pool_size(metrics)
            await self._optimize_connection_limits(metrics)

        if self.config.enable_memory_optimization:
            await self._optimize_memory_usage(metrics)

        # Check thresholds
        await self._check_thresholds(metrics)

    async def _collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        cpu = self._process.cpu_percent(interval=0.1)
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)

        return PerformanceMetrics(
            cpu_percent=cpu,
            memory_mb=memory_mb,
            active_connections=0,  # Will be set by proxy
            connections_per_second=0.0,  # Will be set by proxy
            avg_latency_ms=0.0,  # Will be set by proxy
            pool_utilization=0.0,  # Will be set by proxy
        )

    async def _optimize_pool_size(self, metrics: PerformanceMetrics) -> None:
        """Dynamically adjust pool size based on load."""
        if metrics.pool_utilization > 0.8:  # High utilization
            if self._current_pool_size < self.config.max_pool_size:
                old_size = self._current_pool_size
                self._current_pool_size = min(
                    self._current_pool_size + 4,
                    self.config.max_pool_size
                )
                self._log_optimization(
                    f"Pool size increased: {old_size} → {self._current_pool_size}"
                )
        elif metrics.pool_utilization < 0.3:  # Low utilization
            if self._current_pool_size > self.config.min_pool_size:
                old_size = self._current_pool_size
                self._current_pool_size = max(
                    self._current_pool_size - 2,
                    self.config.min_pool_size
                )
                self._log_optimization(
                    f"Pool size decreased: {old_size} → {self._current_pool_size}"
                )

    async def _optimize_connection_limits(self, metrics: PerformanceMetrics) -> None:
        """Adjust connection limits based on CPU/memory."""
        if metrics.cpu_percent > self.config.cpu_threshold_high:
            # Reduce connections to lower CPU usage
            new_limit = max(50, int(self._current_max_connections * 0.8))
            if new_limit != self._current_max_connections:
                old_limit = self._current_max_connections
                self._current_max_connections = new_limit
                self._log_optimization(
                    f"Connection limit reduced (high CPU): {old_limit} → {new_limit}"
                )
        elif metrics.cpu_percent < 50 and self._current_max_connections < 500:
            # Can handle more connections
            new_limit = min(500, int(self._current_max_connections * 1.2))
            if new_limit != self._current_max_connections:
                old_limit = self._current_max_connections
                self._current_max_connections = new_limit
                self._log_optimization(
                    f"Connection limit increased: {old_limit} → {new_limit}"
                )

    async def _optimize_memory_usage(self, metrics: PerformanceMetrics) -> None:
        """Optimize memory usage."""
        memory_percent = (metrics.memory_mb / (psutil.virtual_memory().total / (1024 * 1024))) * 100

        if memory_percent > self.config.memory_threshold_critical:
            self._log_optimization(
                f"⚠️ Critical memory usage: {memory_percent:.1f}% - consider restarting"
            )
        elif memory_percent > self.config.memory_threshold_high:
            self._log_optimization(
                f"High memory usage: {memory_percent:.1f}% - reducing pool sizes"
            )
            # Reduce pool sizes to free memory
            self._current_pool_size = max(
                self._current_pool_size - 4,
                self.config.min_pool_size
            )

    async def _check_thresholds(self, metrics: PerformanceMetrics) -> None:
        """Check performance thresholds and trigger alerts."""
        if not self._on_optimization:
            return

        # CPU alerts
        if metrics.cpu_percent > self.config.cpu_threshold_critical:
            self._on_optimization(f"🔴 CRITICAL: CPU usage {metrics.cpu_percent:.1f}%")
        elif metrics.cpu_percent > self.config.cpu_threshold_high:
            self._on_optimization(f"🟡 WARNING: CPU usage {metrics.cpu_percent:.1f}%")

        # Memory alerts
        memory_percent = (metrics.memory_mb / (psutil.virtual_memory().total / (1024 * 1024))) * 100
        if memory_percent > self.config.memory_threshold_critical:
            self._on_optimization(f"🔴 CRITICAL: Memory usage {memory_percent:.1f}%")
        elif memory_percent > self.config.memory_threshold_high:
            self._on_optimization(f"🟡 WARNING: Memory usage {memory_percent:.1f}%")

    def _log_optimization(self, reason: str) -> None:
        """Log optimization action."""
        self.optimizations_applied += 1
        self.last_optimization_time = time.time()
        self._optimization_reasons.append(reason)

        # Keep only recent reasons
        if len(self._optimization_reasons) > 20:
            self._optimization_reasons = self._optimization_reasons[-20:]

        log.info("Optimization applied: %s", reason)

        if self._on_optimization:
            self._on_optimization(reason)

    def update_metrics(
        self,
        active_connections: int | None = None,
        connections_per_second: float | None = None,
        avg_latency_ms: float | None = None,
        pool_utilization: float | None = None,
    ) -> None:
        """Update metrics from external sources."""
        if self._metrics_history:
            metrics = self._metrics_history[-1]
            if active_connections is not None:
                metrics.active_connections = active_connections
            if connections_per_second is not None:
                metrics.connections_per_second = connections_per_second
            if avg_latency_ms is not None:
                metrics.avg_latency_ms = avg_latency_ms
            if pool_utilization is not None:
                metrics.pool_utilization = pool_utilization

    def get_current_pool_size(self) -> int:
        """Get current dynamic pool size."""
        return self._current_pool_size

    def get_current_max_connections(self) -> int:
        """Get current max connections limit."""
        return self._current_max_connections

    def get_optimization_history(self, limit: int = 10) -> list[str]:
        """Get recent optimization actions."""
        return self._optimization_reasons[-limit:]

    # =========================================================================
    # Smart DC Selection
    # =========================================================================

    async def record_dc_success(self, dc_id: int, latency_ms: float) -> None:
        """Record successful DC connection."""
        async with self._dc_stats_lock:
            if dc_id not in self._dc_stats:
                self._dc_stats[dc_id] = DCStats(dc_id=dc_id)
            self._dc_stats[dc_id].record_success(latency_ms)

            # Clear blacklist on success
            if self._dc_stats[dc_id].is_blacklisted:
                self._dc_stats[dc_id].is_blacklisted = False
                self._dc_stats[dc_id].blacklisted_until = None
                self._log_optimization(f"DC{dc_id} removed from blacklist after successful connection")

    async def record_dc_failure(self, dc_id: int, error: str = "") -> None:
        """Record failed DC connection."""
        async with self._dc_stats_lock:
            if dc_id not in self._dc_stats:
                self._dc_stats[dc_id] = DCStats(dc_id=dc_id)

            self._dc_stats[dc_id].record_failure()

            # Check if should be blacklisted
            stats = self._dc_stats[dc_id]
            if (stats.consecutive_errors >= self.config.dc_error_threshold and
                stats.success_rate < self.config.min_dc_success_rate):
                stats.is_blacklisted = True
                stats.blacklisted_until = time.time() + self.config.dc_blacklist_duration
                self._log_optimization(
                    f"DC{dc_id} blacklisted for {self.config.dc_blacklist_duration:.0f}s "
                    f"(errors: {stats.consecutive_errors}, success rate: {stats.success_rate:.1f}%)"
                )

    async def get_best_dc(self, available_dcs: list[int]) -> int | None:
        """
        Select best DC based on score (success rate, latency, recent errors).
        
        Args:
            available_dcs: List of available DC IDs to choose from
            
        Returns:
            Best DC ID or None if all are blacklisted
        """
        async with self._dc_stats_lock:
            now = time.time()
            candidates = []

            for dc_id in available_dcs:
                stats = self._dc_stats.get(dc_id, DCStats(dc_id=dc_id))

                # Check if blacklist expired
                if stats.is_blacklisted:
                    if stats.blacklisted_until and now > stats.blacklisted_until:
                        stats.is_blacklisted = False
                        stats.blacklisted_until = None
                        self._log_optimization(f"DC{dc_id} blacklist expired")
                    else:
                        continue  # Skip blacklisted DC

                score = stats.get_score()
                candidates.append((dc_id, score))

            if not candidates:
                # All DCs blacklisted - return first available as fallback
                log.warning("All DCs blacklisted - using fallback")
                return available_dcs[0] if available_dcs else None

            # Select DC with highest score
            best_dc, best_score = max(candidates, key=lambda x: x[1])
            log.debug("DC selection: %s", ", ".join(f"DC{dc}={score:.1f}" for dc, score in candidates))
            log.info("Selected best DC: DC%d (score: %.1f)", best_dc, best_score)
            return best_dc

    def get_dc_stats(self, dc_id: int) -> DCStats | None:
        """Get statistics for a specific DC."""
        return self._dc_stats.get(dc_id)

    def get_all_dc_stats(self) -> dict[int, dict]:
        """Get all DC statistics as dictionary."""
        return {
            dc_id: {
                "dc_id": stats.dc_id,
                "total_connections": stats.total_connections,
                "failed_connections": stats.failed_connections,
                "success_rate": stats.success_rate,
                "avg_latency": stats.avg_latency,
                "last_latency": stats.last_latency_ms,
                "consecutive_errors": stats.consecutive_errors,
                "is_blacklisted": stats.is_blacklisted,
                "score": stats.get_score(),
            }
            for dc_id, stats in self._dc_stats.items()
        }

    # =========================================================================
    # Connection Cache (LRU)
    # =========================================================================

    async def cache_get(self, key: str) -> any | None:
        """Get connection from cache with LRU support."""
        now = time.time()
        if key in self._connection_cache:
            conn, timestamp, hits = self._connection_cache[key]
            # Check TTL
            if now - timestamp < self._cache_ttl:
                # Update hits for LRU
                self._connection_cache[key] = (conn, timestamp, hits + 1)
                log.debug("Cache hit for %s (hits: %d)", key, hits + 1)
                return conn
            else:
                # Expired - remove
                del self._connection_cache[key]
                log.debug("Cache expired for %s", key)
        return None

    async def cache_put(self, key: str, connection: any) -> None:
        """Put connection to cache with LRU eviction."""
        now = time.time()

        # Evict if cache is full
        if len(self._connection_cache) >= self._cache_max_size:
            # Find least recently used (lowest hits, oldest)
            lru_key = min(
                self._connection_cache.keys(),
                key=lambda k: (self._connection_cache[k][2], self._connection_cache[k][1])
            )
            del self._connection_cache[lru_key]
            log.debug("Cache evicted LRU: %s", lru_key)

        # Clean expired entries periodically
        if len(self._connection_cache) % 10 == 0:
            expired = [k for k, (_, ts, _) in self._connection_cache.items()
                      if now - ts > self._cache_ttl]
            for k in expired:
                del self._connection_cache[k]

        self._connection_cache[key] = (connection, now, 0)
        log.debug("Cache put: %s", key)

    async def cache_remove(self, key: str) -> None:
        """Remove connection from cache."""
        self._connection_cache.pop(key, None)
        log.debug("Cache remove: %s", key)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        valid_entries = sum(1 for _, (__, ts, ___) in self._connection_cache.items()
                           if now - ts < self._cache_ttl)
        return {
            "total_entries": len(self._connection_cache),
            "valid_entries": valid_entries,
            "expired_entries": len(self._connection_cache) - valid_entries,
            "max_size": self._cache_max_size,
            "ttl_seconds": self._cache_ttl,
        }

    def get_statistics(self) -> dict:
        """Get optimizer statistics."""
        return {
            "optimizations_applied": self.optimizations_applied,
            "last_optimization": self.last_optimization_time,
            "current_pool_size": self._current_pool_size,
            "current_max_connections": self._current_max_connections,
            "optimization_level": self.config.level.name,
            "recent_optimizations": self.get_optimization_history(5),
            "dc_stats": self.get_all_dc_stats(),
            "cache_stats": self.get_cache_stats(),
        }


# Global optimizer instance
_optimizer: PerformanceOptimizer | None = None


def get_optimizer() -> PerformanceOptimizer:
    """Get or create global optimizer instance."""
    global _optimizer
    if _optimizer is None:
        _optimizer = PerformanceOptimizer()
    return _optimizer


def start_optimizer(config: OptimizationConfig | None = None) -> None:
    """Start the global optimizer."""
    global _optimizer
    _optimizer = PerformanceOptimizer(config)
    asyncio.create_task(_optimizer.start())


async def stop_optimizer() -> None:
    """Stop the global optimizer."""
    if _optimizer:
        await _optimizer.stop()


__all__ = [
    'PerformanceOptimizer',
    'OptimizationConfig',
    'OptimizationLevel',
    'PerformanceMetrics',
    'DCStats',
    'get_optimizer',
    'start_optimizer',
    'stop_optimizer',
]
