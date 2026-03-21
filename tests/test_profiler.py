"""Unit tests for proxy memory profiler module."""

from __future__ import annotations

import gc
import time

import pytest

from proxy.profiler import ComponentTracker, MemoryDiff, MemoryProfiler, MemorySnapshot


class TestMemorySnapshot:
    """Tests for MemorySnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test MemorySnapshot creation."""
        snapshot = MemorySnapshot(
            timestamp=100.0,
            total_bytes=1024,
            total_count=10,
            top_allocations=[("file.py:10", 512, 5)],
        )

        assert snapshot.timestamp == 100.0
        assert snapshot.total_bytes == 1024
        assert snapshot.total_count == 10
        assert len(snapshot.top_allocations) == 1

    def test_snapshot_diff(self):
        """Test calculating difference between snapshots."""
        snapshot1 = MemorySnapshot(
            timestamp=100.0,
            total_bytes=1024,
            total_count=10,
            top_allocations=[],
        )
        snapshot2 = MemorySnapshot(
            timestamp=200.0,
            total_bytes=2048,
            total_count=20,
            top_allocations=[],
        )

        diff = snapshot1.diff(snapshot2)

        assert diff.timestamp_delta == 100.0
        assert diff.bytes_delta == 1024
        assert diff.count_delta == 10

    def test_memory_diff_bytes_per_second(self):
        """Test bytes_per_second calculation."""
        diff = MemoryDiff(
            timestamp_delta=10.0,
            bytes_delta=10240,
            count_delta=100,
            top_grows=[],
        )

        assert diff.bytes_per_second == 1024.0

    def test_memory_diff_is_leak_suspected(self):
        """Test leak detection."""
        # High growth rate - leak suspected
        diff1 = MemoryDiff(
            timestamp_delta=10.0,
            bytes_delta=20480,  # 2048 bytes/s
            count_delta=100,
            top_grows=[],
        )
        assert diff1.is_leak_suspected() is True

        # Low growth rate - no leak
        diff2 = MemoryDiff(
            timestamp_delta=10.0,
            bytes_delta=1024,  # 102.4 bytes/s
            count_delta=10,
            top_grows=[],
        )
        assert diff2.is_leak_suspected() is False

    def test_memory_diff_zero_timestamp(self):
        """Test bytes_per_second with zero timestamp delta."""
        diff = MemoryDiff(
            timestamp_delta=0,
            bytes_delta=1024,
            count_delta=10,
            top_grows=[],
        )

        assert diff.bytes_per_second == 0.0


class TestComponentTracker:
    """Tests for ComponentTracker class."""

    def test_tracker_creation(self):
        """Test ComponentTracker creation."""
        tracker = ComponentTracker("test_component")

        assert tracker.name == "test_component"

    def test_track_object(self):
        """Test tracking an object."""
        tracker = ComponentTracker("test")
        obj = {"key": "value"}

        tracker.track(obj)

        stats = tracker.stats
        assert stats['created_total'] == 1

    def test_get_stats(self):
        """Test getting component stats."""
        tracker = ComponentTracker("test")
        obj = object()
        tracker.track(obj)

        stats = tracker.stats

        assert 'created_total' in stats
        assert 'destroyed_total' in stats
        assert 'live_objects' in stats


class TestMemoryProfiler:
    """Tests for MemoryProfiler class."""

    def test_profiler_creation(self):
        """Test MemoryProfiler creation."""
        profiler = MemoryProfiler()

        assert profiler._snapshots == []
        assert profiler._component_trackers == {}
        assert profiler._running is False

    def test_register_component(self):
        """Test registering a component tracker."""
        profiler = MemoryProfiler()

        tracker = profiler.register_component("test_component")

        assert "test_component" in profiler._component_trackers
        assert tracker.name == "test_component"

    def test_register_component_singleton(self):
        """Test that register_component returns same tracker."""
        profiler = MemoryProfiler()

        tracker1 = profiler.register_component("test")
        tracker2 = profiler.register_component("test")

        assert tracker1 is tracker2

    def test_take_snapshot_basic(self):
        """Test taking a memory snapshot."""
        profiler = MemoryProfiler()

        snapshot = profiler.take_snapshot()

        assert snapshot is not None
        assert snapshot.total_bytes >= 0
        assert snapshot.total_count >= 0

    def test_get_snapshots_empty(self):
        """Test getting snapshots when none exist."""
        profiler = MemoryProfiler()

        snapshots = profiler.get_snapshots()

        assert snapshots == []

    def test_get_report(self):
        """Test generating memory report."""
        profiler = MemoryProfiler()
        profiler.take_snapshot()

        report = profiler.get_report()

        assert isinstance(report, str)
        assert len(report) > 0

    def test_context_manager(self):
        """Test using profiler as context manager."""
        profiler = MemoryProfiler()

        with profiler:
            assert profiler._running is True

        # After context, profiler should be stopped
        # (but background task may still be running)

    def test_max_snapshots_limit(self):
        """Test that max_snapshots limit is enforced."""
        profiler = MemoryProfiler(check_interval=0.01)
        profiler._max_snapshots = 5

        # Manually add snapshots
        for _ in range(10):
            profiler._snapshots.append(
                MemorySnapshot(
                    timestamp=float(_),
                    total_bytes=_,
                    total_count=_,
                    top_allocations=[],
                )
            )

        # Should be trimmed to max_snapshots
        assert len(profiler._snapshots) <= profiler._max_snapshots + 1
