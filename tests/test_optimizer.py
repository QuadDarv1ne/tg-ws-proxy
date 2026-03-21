"""Tests for optimizer.py module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from proxy.optimizer import (
    OptimizationConfig,
    OptimizationLevel,
    PerformanceMetrics,
    PerformanceOptimizer,
    get_optimizer,
)


class TestOptimizationLevel:
    """Tests for OptimizationLevel enum."""

    def test_optimization_level_values(self):
        """Test optimization level values."""
        assert OptimizationLevel.MINIMAL.value == 1
        assert OptimizationLevel.BALANCED.value == 2
        assert OptimizationLevel.AGGRESSIVE.value == 3


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_performance_metrics_default(self):
        """Test default performance metrics."""
        metrics = PerformanceMetrics()

        assert metrics.cpu_percent == 0.0
        assert metrics.memory_mb == 0.0
        assert metrics.active_connections == 0
        assert metrics.connections_per_second == 0.0
        assert metrics.avg_latency_ms == 0.0
        assert metrics.pool_utilization == 0.0
        assert metrics.timestamp > 0

    def test_performance_metrics_custom(self):
        """Test custom performance metrics."""
        metrics = PerformanceMetrics(
            cpu_percent=45.5,
            memory_mb=256.0,
            active_connections=10,
            connections_per_second=5.0,
            avg_latency_ms=25.0,
            pool_utilization=0.6,
        )

        assert metrics.cpu_percent == 45.5
        assert metrics.memory_mb == 256.0
        assert metrics.active_connections == 10


class TestOptimizationConfig:
    """Tests for OptimizationConfig dataclass."""

    def test_optimization_config_default(self):
        """Test default optimization config."""
        config = OptimizationConfig()

        assert config.level == OptimizationLevel.BALANCED
        assert config.check_interval_seconds == 30.0
        assert config.cpu_threshold_high == 80.0
        assert config.cpu_threshold_critical == 95.0
        assert config.memory_threshold_high == 80.0
        assert config.memory_threshold_critical == 95.0
        assert config.max_pool_size == 64
        assert config.min_pool_size == 4
        assert config.enable_auto_scaling is True
        assert config.enable_memory_optimization is True

    def test_optimization_config_custom(self):
        """Test custom optimization config."""
        config = OptimizationConfig(
            level=OptimizationLevel.AGGRESSIVE,
            check_interval_seconds=10.0,
            max_pool_size=128,
            enable_auto_scaling=False,
        )

        assert config.level == OptimizationLevel.AGGRESSIVE
        assert config.check_interval_seconds == 10.0
        assert config.max_pool_size == 128
        assert config.enable_auto_scaling is False


class TestPerformanceOptimizer:
    """Tests for PerformanceOptimizer class."""

    def test_optimizer_init_default(self):
        """Test optimizer initialization with default config."""
        optimizer = PerformanceOptimizer()

        assert optimizer.config.level == OptimizationLevel.BALANCED
        assert optimizer._running is False
        assert optimizer.optimizations_applied == 0

    def test_optimizer_init_custom_config(self):
        """Test optimizer initialization with custom config."""
        config = OptimizationConfig(level=OptimizationLevel.AGGRESSIVE)
        optimizer = PerformanceOptimizer(config)

        assert optimizer.config.level == OptimizationLevel.AGGRESSIVE

    def test_optimizer_init_with_callback(self):
        """Test optimizer initialization with callback."""
        callback = MagicMock()
        optimizer = PerformanceOptimizer(on_optimization=callback)

        assert optimizer._on_optimization == callback

    def test_optimizer_get_current_pool_size(self):
        """Test getting current pool size."""
        optimizer = PerformanceOptimizer()

        pool_size = optimizer.get_current_pool_size()

        assert pool_size == optimizer.config.min_pool_size

    def test_optimizer_get_current_max_connections(self):
        """Test getting current max connections."""
        optimizer = PerformanceOptimizer()

        max_conns = optimizer.get_current_max_connections()

        assert max_conns == 100

    def test_optimizer_get_optimization_history_empty(self):
        """Test getting empty optimization history."""
        optimizer = PerformanceOptimizer()

        history = optimizer.get_optimization_history()

        assert history == []

    def test_optimizer_get_statistics(self):
        """Test getting optimizer statistics."""
        optimizer = PerformanceOptimizer()

        stats = optimizer.get_statistics()

        assert isinstance(stats, dict)
        assert 'optimizations_applied' in stats
        assert 'current_pool_size' in stats
        assert 'current_max_connections' in stats
        assert 'optimization_level' in stats

    def test_optimizer_update_metrics(self):
        """Test updating metrics."""
        optimizer = PerformanceOptimizer()

        # Start optimizer to initialize metrics history
        optimizer._metrics_history.append(PerformanceMetrics())

        optimizer.update_metrics(
            active_connections=10,
            connections_per_second=5.0,
            avg_latency_ms=25.0,
            pool_utilization=0.6,
        )

        if optimizer._metrics_history:
            metrics = optimizer._metrics_history[-1]
            assert metrics.active_connections == 10
            assert metrics.connections_per_second == 5.0
            assert metrics.avg_latency_ms == 25.0
            assert metrics.pool_utilization == 0.6

    def test_optimizer_log_optimization(self):
        """Test logging optimization."""
        optimizer = PerformanceOptimizer()

        optimizer._log_optimization("Test optimization")

        assert optimizer.optimizations_applied == 1
        assert optimizer.last_optimization_time is not None
        assert "Test optimization" in optimizer.get_optimization_history()

    @pytest.mark.asyncio
    async def test_optimizer_start_stop(self):
        """Test optimizer start and stop."""
        optimizer = PerformanceOptimizer(
            OptimizationConfig(check_interval_seconds=0.1)
        )

        await optimizer.start()
        assert optimizer._running is True

        # Let it run for a bit
        import asyncio
        await asyncio.sleep(0.2)

        await optimizer.stop()
        assert optimizer._running is False


class TestGetOptimizer:
    """Tests for get_optimizer function."""

    def test_get_optimizer_singleton(self):
        """Test get_optimizer returns singleton."""
        optimizer1 = get_optimizer()
        optimizer2 = get_optimizer()

        assert optimizer1 is optimizer2

    def test_get_optimizer_default_config(self):
        """Test get_optimizer creates optimizer with default config."""
        optimizer = get_optimizer()

        assert optimizer.config.level == OptimizationLevel.BALANCED
