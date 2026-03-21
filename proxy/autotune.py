"""
Auto-Tuning Module for TG WS Proxy.

Provides automatic performance tuning:
- Adaptive connection pool sizing
- Dynamic timeout adjustment
- Smart retry logic
- Performance-based configuration

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

log = logging.getLogger('tg-ws-autotune')


class TuningMode(Enum):
    """Auto-tuning modes."""
    CONSERVATIVE = auto()  # Minimal changes, stable performance
    BALANCED = auto()      # Moderate adjustments
    AGGRESSIVE = auto()    # Maximum performance optimization


@dataclass
class PerformanceSample:
    """Single performance measurement."""
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0
    success: bool = True
    bytes_transferred: int = 0
    connection_reused: bool = False


@dataclass
class TuningConfig:
    """Auto-tuner configuration."""
    mode: TuningMode = TuningMode.BALANCED
    sample_window_seconds: float = 60.0  # Analysis window
    min_samples: int = 10  # Minimum samples before tuning
    adjustment_cooldown_seconds: float = 30.0  # Between adjustments
    enable_pool_tuning: bool = True
    enable_timeout_tuning: bool = True
    enable_retry_tuning: bool = True

    # Thresholds
    high_latency_threshold_ms: float = 200.0
    critical_latency_threshold_ms: float = 500.0
    success_rate_target: float = 0.95  # 95% success rate target
    pool_utilization_target: float = 0.7  # 70% pool usage target


class AutoTuner:
    """Automatic performance tuner."""

    def __init__(
        self,
        config: TuningConfig | None = None,
        on_tuning_applied: Callable[[str], None] | None = None,
    ):
        self.config = config or TuningConfig()
        self._on_tuning_applied = on_tuning_applied

        # Performance samples
        self._samples: list[PerformanceSample] = []
        self._samples_lock = asyncio.Lock()

        # Current tuned values
        self._current_pool_size = 4
        self._current_timeout_ms = 10000.0
        self._current_max_retries = 3

        # Tuning state
        self._last_adjustment_time: float = 0.0
        self._tuning_applied_count = 0
        self._running = False
        self._tuning_task: asyncio.Task | None = None

        # Baseline metrics
        self._baseline_latency: float | None = None
        self._baseline_success_rate: float = 1.0

    async def start(self) -> None:
        """Start auto-tuner."""
        self._running = True
        self._tuning_task = asyncio.create_task(self._tuning_loop())
        log.info("Auto-tuner started (mode: %s)", self.config.mode.name)

    async def stop(self) -> None:
        """Stop auto-tuner."""
        self._running = False
        if self._tuning_task:
            self._tuning_task.cancel()
            try:
                await self._tuning_task
            except asyncio.CancelledError:
                pass
        log.info("Auto-tuner stopped")

    async def _tuning_loop(self) -> None:
        """Main tuning loop."""
        while self._running:
            try:
                await asyncio.sleep(10.0)  # Check every 10 seconds
                await self._analyze_and_tune()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Auto-tuner error: %s", e)

    async def _analyze_and_tune(self) -> None:
        """Analyze performance and apply tuning if needed."""
        now = time.time()

        # Check cooldown
        if now - self._last_adjustment_time < self.config.adjustment_cooldown_seconds:
            return

        async with self._samples_lock:
            # Check minimum samples
            if len(self._samples) < self.config.min_samples:
                return

            # Filter recent samples
            cutoff = now - self.config.sample_window_seconds
            recent_samples = [s for s in self._samples if s.timestamp > cutoff]

            if len(recent_samples) < self.config.min_samples:
                return

            # Calculate metrics
            avg_latency = sum(s.latency_ms for s in recent_samples) / len(recent_samples)
            success_rate = sum(1 for s in recent_samples if s.success) / len(recent_samples)
            pool_reuse_rate = sum(1 for s in recent_samples if s.connection_reused) / len(recent_samples)

            # Store baseline if not set
            if self._baseline_latency is None:
                self._baseline_latency = avg_latency
                self._baseline_success_rate = success_rate

            # Apply tuning based on mode
            await self._apply_tuning(avg_latency, success_rate, pool_reuse_rate)

    async def _apply_tuning(
        self,
        avg_latency: float,
        success_rate: float,
        pool_reuse_rate: float,
    ) -> None:
        """Apply tuning adjustments based on metrics."""
        adjustments = []

        # Pool size tuning
        if self.config.enable_pool_tuning:
            pool_adjustment = self._tune_pool_size(pool_reuse_rate, success_rate)
            if pool_adjustment:
                adjustments.append(pool_adjustment)

        # Timeout tuning
        if self.config.enable_timeout_tuning:
            timeout_adjustment = self._tune_timeout(avg_latency)
            if timeout_adjustment:
                adjustments.append(timeout_adjustment)

        # Retry tuning
        if self.config.enable_retry_tuning:
            retry_adjustment = self._tune_retries(success_rate)
            if retry_adjustment:
                adjustments.append(retry_adjustment)

        # Apply adjustments
        if adjustments:
            self._last_adjustment_time = time.time()
            self._tuning_applied_count += 1

            for adjustment in adjustments:
                log.info("Auto-tuning applied: %s", adjustment)
                if self._on_tuning_applied:
                    self._on_tuning_applied(adjustment)

    def _tune_pool_size(self, pool_reuse_rate: float, success_rate: float) -> str | None:
        """Adjust connection pool size."""
        target = self.config.pool_utilization_target

        if pool_reuse_rate > target + 0.2 and self._current_pool_size < 16:
            # High reuse - increase pool
            old_size = self._current_pool_size
            self._current_pool_size = min(self._current_pool_size + 2, 16)
            return f"Pool size increased: {old_size} → {self._current_pool_size}"

        elif pool_reuse_rate < target - 0.2 and self._current_pool_size > 2:
            # Low reuse - decrease pool
            old_size = self._current_pool_size
            self._current_pool_size = max(self._current_pool_size - 1, 2)
            return f"Pool size decreased: {old_size} → {self._current_pool_size}"

        return None

    def _tune_timeout(self, avg_latency: float) -> str | None:
        """Adjust connection timeout."""
        # Set timeout based on latency with safety margin
        if avg_latency > self.config.critical_latency_threshold_ms:
            # Very high latency - increase timeout
            new_timeout = min(avg_latency * 3, 30000.0)
            if abs(new_timeout - self._current_timeout_ms) > 1000:
                old_timeout = self._current_timeout_ms
                self._current_timeout_ms = new_timeout
                return f"Timeout increased: {old_timeout/1000:.1f}s → {new_timeout/1000:.1f}s"

        elif avg_latency < self.config.high_latency_threshold_ms * 0.5:
            # Low latency - decrease timeout for faster failover
            new_timeout = max(avg_latency * 5, 3000.0)
            if abs(self._current_timeout_ms - new_timeout) > 1000:
                old_timeout = self._current_timeout_ms
                self._current_timeout_ms = new_timeout
                return f"Timeout decreased: {old_timeout/1000:.1f}s → {new_timeout/1000:.1f}s"

        return None

    def _tune_retries(self, success_rate: float) -> str | None:
        """Adjust max retries based on success rate."""
        target = self.config.success_rate_target

        if success_rate < target - 0.1 and self._current_max_retries < 5:
            # Low success rate - increase retries
            old_retries = self._current_max_retries
            self._current_max_retries = min(self._current_max_retries + 1, 5)
            return f"Max retries increased: {old_retries} → {self._current_max_retries}"

        elif success_rate > target and self._current_max_retries > 2:
            # High success rate - decrease retries
            old_retries = self._current_max_retries
            self._current_max_retries = max(self._current_max_retries - 1, 2)
            return f"Max retries decreased: {old_retries} → {self._current_max_retries}"

        return None

    async def record_sample(
        self,
        latency_ms: float,
        success: bool,
        bytes_transferred: int = 0,
        connection_reused: bool = False,
    ) -> None:
        """Record a performance sample."""
        sample = PerformanceSample(
            latency_ms=latency_ms,
            success=success,
            bytes_transferred=bytes_transferred,
            connection_reused=connection_reused,
        )

        async with self._samples_lock:
            self._samples.append(sample)

            # Keep only recent samples
            cutoff = time.time() - self.config.sample_window_seconds * 2
            self._samples = [s for s in self._samples if s.timestamp > cutoff]

    def get_current_pool_size(self) -> int:
        """Get current tuned pool size."""
        return self._current_pool_size

    def get_current_timeout(self) -> float:
        """Get current tuned timeout in milliseconds."""
        return self._current_timeout_ms

    def get_current_max_retries(self) -> int:
        """Get current tuned max retries."""
        return self._current_max_retries

    def get_statistics(self) -> dict:
        """Get auto-tuner statistics."""
        return {
            'tuning_mode': self.config.mode.name,
            'tuning_applied_count': self._tuning_applied_count,
            'current_pool_size': self._current_pool_size,
            'current_timeout_ms': self._current_timeout_ms,
            'current_max_retries': self._current_max_retries,
            'samples_collected': len(self._samples),
            'baseline_latency_ms': self._baseline_latency,
            'baseline_success_rate': self._baseline_success_rate,
        }


# Global auto-tuner instance
_autotuner: AutoTuner | None = None


def get_autotuner() -> AutoTuner:
    """Get or create global auto-tuner."""
    global _autotuner
    if _autotuner is None:
        _autotuner = AutoTuner()
    return _autotuner


def start_autotuner(config: TuningConfig | None = None) -> None:
    """Start the global auto-tuner."""
    global _autotuner
    _autotuner = AutoTuner(config)
    asyncio.create_task(_autotuner.start())


async def stop_autotuner() -> None:
    """Stop the global auto-tuner."""
    if _autotuner:
        await _autotuner.stop()


__all__ = [
    'AutoTuner',
    'TuningConfig',
    'TuningMode',
    'PerformanceSample',
    'get_autotuner',
    'start_autotuner',
    'stop_autotuner',
]
