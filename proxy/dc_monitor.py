"""
DC Health Monitor for TG WS Proxy.

Provides real-time monitoring of Telegram Data Centers:
- Latency tracking
- Error rate monitoring
- Automatic DC failover
- Health scoring

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitState,
)

log = logging.getLogger('tg-dc-monitor')


class DCStatus(Enum):
    """DC health status."""
    HEALTHY = auto()
    DEGRADED = auto()
    UNHEALTHY = auto()
    OFFLINE = auto()


@dataclass
class DCMetrics:
    """DC metrics data."""
    dc_id: int
    latency_ms: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_check: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    status: DCStatus = DCStatus.HEALTHY

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        total = self.error_count + self.success_count
        if total == 0:
            return 0.0
        return (self.error_count / total) * 100

    @property
    def health_score(self) -> float:
        """Calculate health score (0-100)."""
        # Base score
        score = 100.0

        # Latency penalty (lower is better)
        if self.latency_ms > 500:
            score -= 40
        elif self.latency_ms > 200:
            score -= 20
        elif self.latency_ms > 100:
            score -= 10

        # Error rate penalty
        score -= min(self.error_rate, 50)

        # Consecutive failures penalty
        score -= min(self.consecutive_failures * 5, 30)

        return max(0.0, min(100.0, score))


@dataclass
class DCConfig:
    """DC monitor configuration."""
    check_interval_seconds: float = 30.0
    latency_threshold_ms: float = 500.0
    error_rate_threshold: float = 20.0
    failure_threshold: int = 5
    recovery_threshold: int = 3
    enable_auto_failover: bool = True
    min_healthy_dcs: int = 2


class DCHealthMonitor:
    """Monitor health of Telegram Data Centers with Circuit Breaker protection."""

    def __init__(
        self,
        dc_ips: dict[int, str],
        config: DCConfig | None = None,
        on_dc_status_change: Callable[[int, DCStatus], None] | None = None,
    ):
        self.dc_ips = dc_ips
        self.config = config or DCConfig()
        self._on_status_change = on_dc_status_change

        self._metrics: dict[int, DCMetrics] = {}
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._status_history: dict[int, list[DCStatus]] = {}

        # Circuit Breaker integration - one per DC
        self._circuit_breakers: dict[int, CircuitBreaker] = {}
        self._cb_registry = CircuitBreakerRegistry()

        # Initialize metrics and circuit breakers for each DC
        for dc_id in dc_ips.keys():
            self._metrics[dc_id] = DCMetrics(dc_id=dc_id)
            self._status_history[dc_id] = []
            # Create circuit breaker for each DC
            cb_config = CircuitBreakerConfig(
                failure_threshold=self.config.failure_threshold,
                success_threshold=self.config.recovery_threshold,
                timeout=60.0,  # 1 minute timeout before trying again
                half_open_max_calls=3,
            )
            self._circuit_breakers[dc_id] = CircuitBreaker(
                name=f"DC{dc_id}",
                config=cb_config
            )

    def get_circuit_breaker(self, dc_id: int) -> CircuitBreaker | None:
        """Get circuit breaker for a specific DC."""
        return self._circuit_breakers.get(dc_id)

    def is_dc_available(self, dc_id: int) -> bool:
        """Check if DC is available (circuit breaker not open)."""
        cb = self._circuit_breakers.get(dc_id)
        if cb is None:
            return True
        return cb.state != CircuitState.OPEN

    async def record_dc_success(self, dc_id: int, latency_ms: float = 0.0) -> None:
        """Record successful DC operation."""
        if dc_id in self._metrics:
            self._metrics[dc_id].success_count += 1
            self._metrics[dc_id].consecutive_failures = 0
            if latency_ms > 0:
                self._metrics[dc_id].latency_ms = latency_ms

    async def record_dc_error(self, dc_id: int, error: Exception | None = None) -> None:
        """Record failed DC operation."""
        if dc_id in self._metrics:
            self._metrics[dc_id].error_count += 1
            self._metrics[dc_id].consecutive_failures += 1

    async def start(self) -> None:
        """Start the DC health monitor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info(
            "DC Health Monitor started (interval: %.1fs, auto-failover: %s)",
            self.config.check_interval_seconds,
            self.config.enable_auto_failover
        )

    async def stop(self) -> None:
        """Stop the DC health monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        log.info("DC Health Monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                await self._check_all_dcs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("DC monitor error: %s", e)

    async def _check_all_dcs(self) -> None:
        """Check health of all DCs."""

        tasks = []
        for dc_id, ip in self.dc_ips.items():
            tasks.append(self._check_dc(dc_id, ip))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_dc(self, dc_id: int, ip: str) -> None:
        """Check health of a single DC with Circuit Breaker integration."""
        metrics = self._metrics[dc_id]
        cb = self._circuit_breakers.get(dc_id)

        # Skip check if circuit breaker is open
        if cb and cb.state == CircuitState.OPEN:
            retry_after = cb.config.timeout - (time.monotonic() - cb._opened_at)
            if retry_after > 0:
                log.debug("DC%d circuit breaker OPEN, skipping check (retry in %.1fs)",
                         dc_id, retry_after)
                # Still update status based on existing metrics
                old_status = metrics.status
                new_status = self._calculate_status(metrics)
                if old_status != new_status:
                    metrics.status = new_status
                    self._status_history[dc_id].append(new_status)
                    if self._on_status_change:
                        self._on_status_change(dc_id, new_status)
                return

        try:
            # Measure latency using asyncio
            start_time = time.perf_counter()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, 443, ssl=True),
                    timeout=5.0
                )
                latency = (time.perf_counter() - start_time) * 1000
                writer.close()
                await writer.wait_closed()

                # Record success in metrics
                metrics.success_count += 1
                metrics.consecutive_failures = 0
                metrics.latency_ms = latency

                # Record success in circuit breaker
                if cb:
                    cb._on_success()

            except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
                # Record failure in metrics
                metrics.error_count += 1
                metrics.consecutive_failures += 1

                # Record failure in circuit breaker
                if cb:
                    cb._on_failure()

                log.debug("DC%d connection failed: %s (circuit state: %s)",
                         dc_id, e, cb.state.value if cb else "N/A")

        except Exception as e:
            log.debug("DC%d check failed: %s", dc_id, e)
            metrics.error_count += 1
            metrics.consecutive_failures += 1

            if cb:
                cb._on_failure()

        metrics.last_check = time.time()

        # Update status
        old_status = metrics.status
        new_status = self._calculate_status(metrics)

        if old_status != new_status:
            metrics.status = new_status
            self._status_history[dc_id].append(new_status)

            # Keep only recent history
            if len(self._status_history[dc_id]) > 100:
                self._status_history[dc_id] = self._status_history[dc_id][-100:]

            log.info(
                "DC%d status changed: %s → %s (latency: %.1fms, errors: %d)",
                dc_id, old_status.name, new_status.name,
                metrics.latency_ms, metrics.error_count
            )

            if self._on_status_change:
                self._on_status_change(dc_id, new_status)

    def _calculate_status(self, metrics: DCMetrics) -> DCStatus:
        """Calculate DC status based on metrics."""
        # Check for offline
        if metrics.consecutive_failures >= self.config.failure_threshold * 2:
            return DCStatus.OFFLINE

        # Check for unhealthy
        if (metrics.consecutive_failures >= self.config.failure_threshold or
            metrics.error_rate >= self.config.error_rate_threshold * 2):
            return DCStatus.UNHEALTHY

        # Check for degraded
        if (metrics.latency_ms > self.config.latency_threshold_ms or
            metrics.error_rate >= self.config.error_rate_threshold or
            metrics.consecutive_failures >= 2):
            return DCStatus.DEGRADED

        return DCStatus.HEALTHY

    def get_metrics(self, dc_id: int) -> DCMetrics | None:
        """Get metrics for a specific DC."""
        return self._metrics.get(dc_id)

    def get_all_metrics(self) -> dict[int, DCMetrics]:
        """Get metrics for all DCs."""
        return self._metrics.copy()

    def get_healthy_dcs(self) -> list[int]:
        """Get list of healthy DC IDs."""
        return [
            dc_id for dc_id, metrics in self._metrics.items()
            if metrics.status in (DCStatus.HEALTHY, DCStatus.DEGRADED)
        ]

    def get_best_dc(self) -> int | None:
        """Get the best DC based on health score."""
        healthy = self.get_healthy_dcs()
        if not healthy:
            return None

        return min(
            healthy,
            key=lambda dc_id: self._metrics[dc_id].latency_ms
        )

    def get_status_summary(self) -> dict:
        """Get summary of all DC statuses."""
        return {
            dc_id: {
                'status': metrics.status.name,
                'latency_ms': round(metrics.latency_ms, 2),
                'error_rate': round(metrics.error_rate, 2),
                'health_score': round(metrics.health_score, 2),
                'consecutive_failures': metrics.consecutive_failures,
                'circuit_breaker_state': self._circuit_breakers.get(dc_id).state.value
                    if self._circuit_breakers.get(dc_id) else 'N/A',
            }
            for dc_id, metrics in self._metrics.items()
        }

    async def execute_with_circuit_breaker(
        self,
        dc_id: int,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute function through DC circuit breaker.

        Args:
            dc_id: Data Center ID
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function call

        Raises:
            CircuitBreakerError: If circuit breaker is open
        """
        cb = self._circuit_breakers.get(dc_id)
        if cb is None:
            # No circuit breaker, execute directly
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

        return await cb.call(func, *args, **kwargs)

    def record_error(self, dc_id: int) -> None:
        """Manually record an error for a DC."""
        if dc_id in self._metrics:
            self._metrics[dc_id].error_count += 1
            self._metrics[dc_id].consecutive_failures += 1

    def record_success(self, dc_id: int) -> None:
        """Manually record a success for a DC."""
        if dc_id in self._metrics:
            self._metrics[dc_id].success_count += 1
            self._metrics[dc_id].consecutive_failures = 0

    def get_statistics(self) -> dict:
        """Get monitor statistics with Circuit Breaker info."""
        healthy_count = sum(
            1 for m in self._metrics.values()
            if m.status == DCStatus.HEALTHY
        )

        # Circuit breaker stats
        cb_stats = {
            dc_id: cb.get_info()
            for dc_id, cb in self._circuit_breakers.items()
        }

        return {
            'total_dcs': len(self._metrics),
            'healthy_dcs': healthy_count,
            'degraded_dcs': sum(1 for m in self._metrics.values() if m.status == DCStatus.DEGRADED),
            'unhealthy_dcs': sum(1 for m in self._metrics.values() if m.status == DCStatus.UNHEALTHY),
            'offline_dcs': sum(1 for m in self._metrics.values() if m.status == DCStatus.OFFLINE),
            'average_latency_ms': sum(m.latency_ms for m in self._metrics.values()) / len(self._metrics) if self._metrics else 0,
            'average_health_score': sum(m.health_score for m in self._metrics.values()) / len(self._metrics) if self._metrics else 0,
            'circuit_breakers': cb_stats,
            'dcs_with_open_circuit': sum(1 for cb in self._circuit_breakers.values() if cb.is_open),
            'dcs_with_half_open_circuit': sum(1 for cb in self._circuit_breakers.values() if cb.is_half_open),
        }


# Global monitor instance
_monitor: DCHealthMonitor | None = None


def get_dc_monitor(dc_ips: dict[int, str] | None = None) -> DCHealthMonitor:
    """Get or create global DC monitor instance."""
    global _monitor

    if dc_ips is not None:
        _monitor = DCHealthMonitor(dc_ips)

    if _monitor is None:
        from proxy.constants import DC_IP_MAP
        _monitor = DCHealthMonitor(DC_IP_MAP)

    return _monitor


async def start_dc_monitor(dc_ips: dict[int, str] | None = None) -> None:
    """Start the global DC monitor."""
    monitor = get_dc_monitor(dc_ips)
    await monitor.start()


async def stop_dc_monitor() -> None:
    """Stop the global DC monitor."""
    if _monitor:
        await _monitor.stop()


__all__ = [
    'DCHealthMonitor',
    'DCStatus',
    'DCMetrics',
    'DCConfig',
    'get_dc_monitor',
    'start_dc_monitor',
    'stop_dc_monitor',
]
