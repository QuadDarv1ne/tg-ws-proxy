"""
Tests for Alerting System - DC Latency Alerts.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import pytest

from proxy.alerts import (
    Alert,
    AlertManager,
    AlertSeverity,
    AlertType,
    alert_dc_latency,
    get_alert_manager,
)


class TestDCLatencyAlerts:
    """Tests for DC latency alerting."""

    def test_dc_latency_threshold_configured(self):
        """Test DC latency threshold is configured in AlertManager."""
        manager = AlertManager()
        assert "dc_latency_ms" in manager.thresholds
        threshold = manager.thresholds["dc_latency_ms"]
        assert threshold.warning_value == 150.0
        assert threshold.critical_value == 200.0
        assert threshold.enabled is True
        assert threshold.cooldown_seconds == 120  # 2 minutes cooldown

    def test_dc_latency_alert_type_exists(self):
        """Test DC_HIGH_LATENCY alert type exists."""
        assert hasattr(AlertType, 'DC_HIGH_LATENCY')
        assert AlertType.DC_HIGH_LATENCY is not None

    @pytest.mark.asyncio
    async def test_alert_dc_latency_warning_level(self):
        """Test DC latency warning alert (150-200ms)."""
        # Reset alert manager
        import proxy.alerts
        proxy.alerts._alert_manager = None

        alert_dc_latency(2, 175.0)
        manager = get_alert_manager()
        alerts = manager.get_recent_alerts(1)

        assert len(alerts) > 0
        alert = alerts[-1]
        assert alert.alert_type == AlertType.DC_HIGH_LATENCY
        assert alert.severity == AlertSeverity.WARNING
        assert "DC2" in alert.title
        assert "175" in alert.message
        assert alert.metadata["dc_id"] == 2
        assert alert.metadata["latency_ms"] == 175.0

    @pytest.mark.asyncio
    async def test_alert_dc_latency_critical_level(self):
        """Test DC latency critical alert (>200ms)."""
        # Reset alert manager
        import proxy.alerts
        proxy.alerts._alert_manager = None

        alert_dc_latency(4, 250.0)
        manager = get_alert_manager()
        alerts = manager.get_recent_alerts(1)

        assert len(alerts) > 0
        alert = alerts[-1]
        assert alert.alert_type == AlertType.DC_HIGH_LATENCY
        assert alert.severity == AlertSeverity.CRITICAL
        assert "DC4" in alert.title
        assert "250" in alert.message
        assert alert.metadata["dc_id"] == 4
        assert alert.metadata["latency_ms"] == 250.0

    @pytest.mark.asyncio
    async def test_alert_dc_latency_boundary_warning(self):
        """Test DC latency at warning boundary (150ms)."""
        import proxy.alerts
        proxy.alerts._alert_manager = None

        alert_dc_latency(1, 150.0)
        manager = get_alert_manager()
        alerts = manager.get_recent_alerts(1)

        assert len(alerts) > 0
        alert = alerts[-1]
        assert alert.severity == AlertSeverity.WARNING
        assert "DC1" in alert.title

    @pytest.mark.asyncio
    async def test_alert_dc_latency_boundary_critical(self):
        """Test DC latency at critical boundary (200ms)."""
        import proxy.alerts
        proxy.alerts._alert_manager = None

        alert_dc_latency(3, 200.0)
        manager = get_alert_manager()
        alerts = manager.get_recent_alerts(1)

        assert len(alerts) > 0
        alert = alerts[-1]
        assert alert.severity == AlertSeverity.CRITICAL
        assert "DC3" in alert.title

    def test_alert_serialization(self):
        """Test DC latency alert serialization."""
        alert = Alert(
            alert_type=AlertType.DC_HIGH_LATENCY,
            severity=AlertSeverity.WARNING,
            title="DC2 high latency: 175ms",
            message="Telegram DC2 latency is 175ms",
            metadata={"dc_id": 2, "latency_ms": 175.0}
        )
        data = alert.to_dict()

        assert data["type"] == "DC_HIGH_LATENCY"
        assert data["severity"] == "WARNING"
        assert data["title"] == "DC2 high latency: 175ms"
        assert data["message"] == "Telegram DC2 latency is 175ms"
        assert data["metadata"]["dc_id"] == 2
        assert data["metadata"]["latency_ms"] == 175.0
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_alert_manager_statistics(self):
        """Test alert statistics after DC latency alerts."""
        import proxy.alerts
        proxy.alerts._alert_manager = None

        # Generate some alerts
        alert_dc_latency(1, 175.0)
        alert_dc_latency(2, 250.0)

        manager = get_alert_manager()
        stats = manager.get_statistics()

        assert "total_alerts" in stats
        assert "alerts_last_hour" in stats
        assert "alerts_last_day" in stats
        assert stats["total_alerts"] >= 2
        assert stats["alerts_sent"] >= 2
