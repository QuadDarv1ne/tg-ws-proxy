"""Tests for dc_monitor.py module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from proxy.dc_monitor import (
    DCConfig,
    DCHealthMonitor,
    DCMetrics,
    DCStatus,
    get_dc_monitor,
)


class TestDCStatus:
    """Tests for DCStatus enum."""

    def test_dc_status_values(self):
        """Test DC status values."""
        assert DCStatus.HEALTHY.value == 1
        assert DCStatus.DEGRADED.value == 2
        assert DCStatus.UNHEALTHY.value == 3
        assert DCStatus.OFFLINE.value == 4


class TestDCMetrics:
    """Tests for DCMetrics dataclass."""

    def test_dc_metrics_default(self):
        """Test default DC metrics."""
        metrics = DCMetrics(dc_id=2)

        assert metrics.dc_id == 2
        assert metrics.latency_ms == 0.0
        assert metrics.error_count == 0
        assert metrics.success_count == 0
        assert metrics.consecutive_failures == 0
        assert metrics.status == DCStatus.HEALTHY

    def test_dc_metrics_custom(self):
        """Test custom DC metrics."""
        metrics = DCMetrics(
            dc_id=4,
            latency_ms=150.5,
            error_count=5,
            success_count=95,
            consecutive_failures=2,
        )

        assert metrics.dc_id == 4
        assert metrics.latency_ms == 150.5
        assert metrics.error_count == 5
        assert metrics.success_count == 95

    def test_dc_metrics_error_rate(self):
        """Test error rate calculation."""
        metrics = DCMetrics(
            dc_id=2,
            error_count=10,
            success_count=90,
        )

        assert metrics.error_rate == 10.0

    def test_dc_metrics_error_rate_zero(self):
        """Test error rate with zero total."""
        metrics = DCMetrics(dc_id=2)
        assert metrics.error_rate == 0.0

    def test_dc_metrics_health_score_good(self):
        """Test health score for good DC."""
        metrics = DCMetrics(
            dc_id=2,
            latency_ms=50.0,
            error_count=1,
            success_count=99,
            consecutive_failures=0,
        )

        # High score for good metrics
        assert metrics.health_score > 80

    def test_dc_metrics_health_score_bad(self):
        """Test health score for bad DC."""
        metrics = DCMetrics(
            dc_id=2,
            latency_ms=600.0,
            error_count=50,
            success_count=50,
            consecutive_failures=5,
        )

        # Low score for bad metrics
        assert metrics.health_score < 50


class TestDCConfig:
    """Tests for DCConfig dataclass."""

    def test_dc_config_default(self):
        """Test default DC config."""
        config = DCConfig()

        assert config.check_interval_seconds == 30.0
        assert config.latency_threshold_ms == 500.0
        assert config.error_rate_threshold == 20.0
        assert config.failure_threshold == 5
        assert config.enable_auto_failover is True

    def test_dc_config_custom(self):
        """Test custom DC config."""
        config = DCConfig(
            check_interval_seconds=10.0,
            latency_threshold_ms=200.0,
            enable_auto_failover=False,
        )

        assert config.check_interval_seconds == 10.0
        assert config.latency_threshold_ms == 200.0
        assert config.enable_auto_failover is False


class TestDCHealthMonitor:
    """Tests for DCHealthMonitor class."""

    def test_dc_monitor_init(self):
        """Test DC monitor initialization."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        assert monitor.dc_ips == dc_ips
        assert len(monitor._metrics) == 2
        assert 2 in monitor._metrics
        assert 4 in monitor._metrics

    def test_dc_monitor_init_with_config(self):
        """Test DC monitor with custom config."""
        dc_ips = {2: '149.154.167.220'}
        config = DCConfig(check_interval_seconds=60.0)
        monitor = DCHealthMonitor(dc_ips, config)

        assert monitor.config.check_interval_seconds == 60.0

    def test_dc_monitor_get_metrics(self):
        """Test getting DC metrics."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = monitor.get_metrics(2)

        assert metrics is not None
        assert metrics.dc_id == 2

    def test_dc_monitor_get_metrics_not_found(self):
        """Test getting non-existent DC metrics."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = monitor.get_metrics(99)

        assert metrics is None

    def test_dc_monitor_get_all_metrics(self):
        """Test getting all DC metrics."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        all_metrics = monitor.get_all_metrics()

        assert len(all_metrics) == 2
        assert 2 in all_metrics
        assert 4 in all_metrics

    def test_dc_monitor_get_healthy_dcs_empty(self):
        """Test getting healthy DCs when all unhealthy."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)
        monitor._metrics[2].status = DCStatus.OFFLINE

        healthy = monitor.get_healthy_dcs()

        assert healthy == []

    def test_dc_monitor_get_healthy_dcs(self):
        """Test getting healthy DCs."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        healthy = monitor.get_healthy_dcs()

        assert 2 in healthy
        assert 4 in healthy

    def test_dc_monitor_get_best_dc(self):
        """Test getting best DC."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        # Set different latencies
        monitor._metrics[2].latency_ms = 100.0
        monitor._metrics[4].latency_ms = 200.0

        best_dc = monitor.get_best_dc()

        assert best_dc == 2

    def test_dc_monitor_get_best_dc_none(self):
        """Test getting best DC when all offline."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)
        monitor._metrics[2].status = DCStatus.OFFLINE

        best_dc = monitor.get_best_dc()

        assert best_dc is None

    def test_dc_monitor_get_status_summary(self):
        """Test getting status summary."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        summary = monitor.get_status_summary()

        assert 2 in summary
        assert 'status' in summary[2]
        assert 'latency_ms' in summary[2]
        assert 'health_score' in summary[2]

    def test_dc_monitor_record_error(self):
        """Test recording DC error."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        monitor.record_error(2)

        metrics = monitor.get_metrics(2)
        assert metrics.error_count == 1
        assert metrics.consecutive_failures == 1

    def test_dc_monitor_record_success(self):
        """Test recording DC success."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        monitor.record_success(2)

        metrics = monitor.get_metrics(2)
        assert metrics.success_count == 1
        assert metrics.consecutive_failures == 0

    def test_dc_monitor_get_statistics(self):
        """Test getting monitor statistics."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        stats = monitor.get_statistics()

        assert stats['total_dcs'] == 2
        assert 'healthy_dcs' in stats
        assert 'average_latency_ms' in stats
        assert 'average_health_score' in stats

    @pytest.mark.asyncio
    async def test_dc_monitor_start_stop(self):
        """Test monitor start and stop."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips, DCConfig(check_interval_seconds=0.1))

        await monitor.start()
        assert monitor._running is True

        import asyncio
        await asyncio.sleep(0.2)

        await monitor.stop()
        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_dc_monitor_status_change_callback(self):
        """Test DC status change callback."""
        dc_ips = {2: '149.154.167.220'}
        callback = MagicMock()
        monitor = DCHealthMonitor(dc_ips, on_dc_status_change=callback)

        # Manually trigger status change
        monitor._metrics[2].status = DCStatus.DEGRADED
        monitor._on_status_change(2, DCStatus.DEGRADED)

        callback.assert_called_once_with(2, DCStatus.DEGRADED)

    def test_dc_monitor_calculate_status_healthy(self):
        """Test status calculation for healthy DC."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = DCMetrics(
            dc_id=2,
            latency_ms=50.0,
            error_count=1,
            success_count=99,
            consecutive_failures=0,
        )

        status = monitor._calculate_status(metrics)
        assert status == DCStatus.HEALTHY

    def test_dc_monitor_calculate_status_degraded(self):
        """Test status calculation for degraded DC."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = DCMetrics(
            dc_id=2,
            latency_ms=600.0,  # Above threshold
            error_count=5,
            success_count=95,
            consecutive_failures=0,
        )

        status = monitor._calculate_status(metrics)
        assert status == DCStatus.DEGRADED

    def test_dc_monitor_calculate_status_unhealthy(self):
        """Test status calculation for unhealthy DC."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = DCMetrics(
            dc_id=2,
            latency_ms=100.0,
            error_count=50,
            success_count=50,  # 50% error rate
            consecutive_failures=0,
        )

        status = monitor._calculate_status(metrics)
        assert status == DCStatus.UNHEALTHY

    def test_dc_monitor_calculate_status_offline(self):
        """Test status calculation for offline DC."""
        dc_ips = {2: '149.154.167.220'}
        monitor = DCHealthMonitor(dc_ips)

        metrics = DCMetrics(
            dc_id=2,
            latency_ms=0.0,
            error_count=10,
            success_count=0,
            consecutive_failures=10,  # Above threshold * 2
        )

        status = monitor._calculate_status(metrics)
        assert status == DCStatus.OFFLINE


class TestGetDcMonitor:
    """Tests for get_dc_monitor function."""

    def test_get_dc_monitor_singleton(self):
        """Test get_dc_monitor returns singleton."""
        dc_ips = {2: '149.154.167.220'}

        monitor1 = get_dc_monitor(dc_ips)
        monitor2 = get_dc_monitor()

        assert monitor1 is monitor2

    def test_get_dc_monitor_with_dc_ips(self):
        """Test get_dc_monitor creates with DC IPs."""
        dc_ips = {2: '149.154.167.220', 4: '149.154.167.220'}

        # Reset global
        import proxy.dc_monitor as dc_mod
        dc_mod._monitor = None

        monitor = get_dc_monitor(dc_ips)

        assert len(monitor.dc_ips) == 2
