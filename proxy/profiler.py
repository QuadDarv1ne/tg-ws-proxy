"""
Memory Profiling Module for TG WS Proxy.

Provides memory usage tracking and leak detection:
- Per-component memory tracking
- Object count monitoring
- Memory leak detection
- Periodic snapshots and reporting

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import tracemalloc
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

log = logging.getLogger('tg-ws-profiler')


@dataclass
class MemorySnapshot:
    """Memory snapshot at a point in time."""
    timestamp: float
    total_bytes: int
    total_count: int
    top_allocations: list[tuple[str, int, int]]  # (traceback, size, count)
    component_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    def diff(self, other: MemorySnapshot) -> MemoryDiff:
        """Calculate difference between two snapshots."""
        return MemoryDiff(
            timestamp_delta=other.timestamp - self.timestamp,
            bytes_delta=other.total_bytes - self.total_bytes,
            count_delta=other.total_count - self.total_count,
            top_grows=other.top_allocations[:10],
        )


@dataclass
class MemoryDiff:
    """Difference between two memory snapshots."""
    timestamp_delta: float
    bytes_delta: int
    count_delta: int
    top_grows: list[tuple[str, int, int]]

    @property
    def bytes_per_second(self) -> float:
        if self.timestamp_delta <= 0:
            return 0.0
        return self.bytes_delta / self.timestamp_delta

    def is_leak_suspected(self, threshold_bytes_per_sec: float = 1024) -> bool:
        """Check if memory leak is suspected (>1KB/s growth)."""
        return self.bytes_per_second > threshold_bytes_per_sec


class ComponentTracker:
    """Track memory usage per component."""

    def __init__(self, name: str):
        self.name = name
        self._objects: weakref.WeakSet = weakref.WeakSet()
        self._created_count = 0
        self._destroyed_count = 0

    def track(self, obj: Any) -> None:
        """Track an object."""
        self._objects.add(obj)
        self._created_count += 1

    def untrack(self, obj: Any) -> None:
        """Untrack an object."""
        self._destroyed_count += 1

    @property
    def live_count(self) -> int:
        """Get count of live objects."""
        return len(self._objects)

    @property
    def stats(self) -> dict[str, Any]:
        """Get component statistics."""
        return {
            'name': self.name,
            'live_objects': self.live_count,
            'created_total': self._created_count,
            'destroyed_total': self._destroyed_count,
            'leak_suspected': self._created_count - self._destroyed_count > self.live_count + 10,
        }


class MemoryProfiler:
    """Memory profiler with leak detection."""

    def __init__(self, check_interval: float = 60.0):
        self.check_interval = check_interval
        self._snapshots: list[MemorySnapshot] = []
        self._component_trackers: dict[str, ComponentTracker] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._max_snapshots = 100
        self._leak_alerts: list[dict[str, Any]] = []
        self._baseline_snapshot: MemorySnapshot | None = None

    def register_component(self, name: str) -> ComponentTracker:
        """Register a component for tracking."""
        if name not in self._component_trackers:
            self._component_trackers[name] = ComponentTracker(name)
        return self._component_trackers[name]

    def start(self) -> None:
        """Start memory profiling."""
        if not tracemalloc.is_tracing():
            tracemalloc.start(25)  # Store 25 frames
            log.info("Tracemalloc started (25 frames)")

        self._running = True
        self._task = asyncio.create_task(self._profiling_loop())
        self._baseline_snapshot = self.take_snapshot()
        log.info("Memory profiler started (interval: %.1fs)", self.check_interval)

    def stop(self) -> None:
        """Stop memory profiling."""
        self._running = False
        if self._task:
            self._task.cancel()
            # Don't use run_until_complete - task will be awaited by caller if needed
            self._task = None
        tracemalloc.stop()
        log.info("Memory profiler stopped")

    async def _profiling_loop(self) -> None:
        """Background profiling loop."""
        while self._running:
            await asyncio.sleep(self.check_interval)
            try:
                await self._check_memory()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("Memory check error: %s", e)

    async def _check_memory(self) -> None:
        """Check memory usage and detect leaks."""
        snapshot = self.take_snapshot()

        # Store snapshot
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

        # Check for leaks if we have baseline
        if self._baseline_snapshot and len(self._snapshots) >= 2:
            diff = self._snapshots[-2].diff(snapshot)

            if diff.is_leak_suspected():
                alert = {
                    'timestamp': datetime.now().isoformat(),
                    'bytes_per_second': diff.bytes_per_second,
                    'total_growth': diff.bytes_delta,
                    'top_allocations': diff.top_grows[:5],
                }
                self._leak_alerts.append(alert)
                log.warning(
                    "MEMORY LEAK SUSPECTED: %.1f KB/s growth (%.1f KB total) | Top: %s",
                    diff.bytes_per_second / 1024,
                    diff.bytes_delta / 1024,
                    diff.top_grows[0][0] if diff.top_grows else "unknown"
                )

        # Log component stats
        for name, tracker in self._component_trackers.items():
            stats = tracker.stats
            if stats['leak_suspected']:
                log.warning(
                    "Component '%s' leak suspected: created=%d, destroyed=%d, live=%d",
                    name, stats['created_total'], stats['destroyed_total'], stats['live_objects']
                )

        # Log summary
        current, peak = tracemalloc.get_traced_memory()
        log.debug(
            "Memory: current=%.1f MB, peak=%.1f MB, snapshots=%d",
            current / 1024 / 1024,
            peak / 1024 / 1024,
            len(self._snapshots)
        )

    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory snapshot."""
        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics('lineno')

        top_allocations = [
            (str(entry.traceback), entry.size, entry.count)
            for entry in stats[:20]
        ]

        # Force garbage collection
        gc.collect()

        return MemorySnapshot(
            timestamp=asyncio.get_event_loop().time(),
            total_bytes=tracemalloc.get_traced_memory()[0],
            total_count=len(gc.get_objects()),
            top_allocations=top_allocations,
            component_stats={
                name: tracker.stats
                for name, tracker in self._component_trackers.items()
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get current memory statistics."""
        current, peak = tracemalloc.get_traced_memory()

        return {
            'current_bytes': current,
            'peak_bytes': peak,
            'current_mb': current / 1024 / 1024,
            'peak_mb': peak / 1024 / 1024,
            'object_count': len(gc.get_objects()),
            'snapshot_count': len(self._snapshots),
            'leak_alerts': len(self._leak_alerts),
            'components': {
                name: tracker.stats
                for name, tracker in self._component_trackers.items()
            },
            'last_leak_alert': self._leak_alerts[-1] if self._leak_alerts else None,
        }

    def force_gc(self) -> int:
        """Force garbage collection and return freed objects count."""
        before = len(gc.get_objects())
        gc.collect()
        gc.collect()
        gc.collect()
        after = len(gc.get_objects())
        freed = before - after
        if freed > 0:
            log.debug("GC freed %d objects", freed)
        return freed

    def get_leak_report(self) -> str:
        """Generate leak report."""
        if not self._leak_alerts:
            return "No memory leaks detected"

        lines = ["Memory Leak Report", "=" * 50]
        for alert in self._leak_alerts[-10:]:  # Last 10 alerts
            lines.append(f"Time: {alert['timestamp']}")
            lines.append(f"  Growth: {alert['bytes_per_second']:.1f} KB/s")
            lines.append(f"  Total: {alert['total_growth'] / 1024:.1f} KB")
            if alert['top_allocations']:
                lines.append(f"  Top: {alert['top_allocations'][0][0][:100]}")
            lines.append("")

        return "\n".join(lines)


# Global profiler instance
_profiler: MemoryProfiler | None = None


def get_profiler(check_interval: float = 60.0) -> MemoryProfiler:
    """Get or create global memory profiler."""
    global _profiler
    if _profiler is None:
        _profiler = MemoryProfiler(check_interval=check_interval)
    return _profiler


def start_profiling(check_interval: float = 60.0) -> MemoryProfiler:
    """Start memory profiling."""
    profiler = get_profiler(check_interval)
    profiler.start()
    return profiler


def stop_profiling() -> None:
    """Stop memory profiling."""
    if _profiler:
        _profiler.stop()


def get_memory_stats() -> dict[str, Any]:
    """Get current memory statistics."""
    return get_profiler().get_stats() if _profiler else {}


def force_gc() -> int:
    """Force garbage collection."""
    return get_profiler().force_gc() if _profiler else 0


__all__ = [
    'MemoryProfiler',
    'MemorySnapshot',
    'MemoryDiff',
    'ComponentTracker',
    'get_profiler',
    'start_profiling',
    'stop_profiling',
    'get_memory_stats',
    'force_gc',
]
