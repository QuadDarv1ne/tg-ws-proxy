"""
Tests for Alerting System.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import pytest

from proxy.alerts import (
    Alert,
    AlertManager,
    AlertSeverity,
    AlertThreshold,
    AlertType,
    alert_dc_latency,
    get_alert_manager,
)


class TestAlertManager:
    """Tests for AlertManager."""

    def test_alert_manager_creation(self):
        """Test AlertManager initialization."""
        manager = AlertManager()
        assert manager.alerts == []
        assert manager.alert_history == []
        assert manager.thresholds != {}

    def test_alert_manager_singleton(self):
        """Test get_alert_manager returns singleton."""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        assert manager1 is manager2

    def test_check_threshold_warning(self):
        """Test threshold check with warning level."""
        manager = AlertManager()
        # Use existing threshold that maps to AlertType
        alert = manager.check_threshold("ws_errors_per_minute", 15.0)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING

    def test_check_threshold_critical(self):
        """Test threshold check with critical level."""
        manager = AlertManager()
        alert = manager.check_threshold("ws_errors_per_minute", 60.0)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_check_threshold_below_warning(self):
        """Test threshold check below warning level."""
        manager = AlertManager()
        alert = manager.check_threshold("ws_errors_per_minute", 5.0)
        assert alert is None

    def test_check_threshold_cooldown(self):
        """Test threshold cooldown."""
        manager = AlertManager()
        # First alert should trigger
        alert1 = manager.check_threshold("ws_errors_per_minute", 60.0)
        assert alert1 is not None

        # Second alert within cooldown should be suppressed
        alert2 = manager.check_threshold("ws_errors_per_minute", 60.0)
        assert alert2 is None
        assert manager.alerts_suppressed == 1

    def test_dc_latency_threshold_exists(self):
        """Test DC latency threshold is configured."""
        manager = AlertManager()
        assert "dc_latency_ms" in manager.thresholds
        threshold = manager.thresholds["dc_latency_ms"]
        assert threshold.warning_value == 150.0
        assert threshold.critical_value == 200.0
        assert threshold.enabled is True

    def test_dc_latency_alert_warning(self):
        """Test DC latency warning alert."""
        manager = AlertManager()
        alert = manager.check_threshold("dc_latency_ms", 175.0)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert "DC" in alert.title
        assert "latency" in alert.title.lower()

    def test_dc_latency_alert_critical(self):
        """Test DC latency critical alert."""
        manager = AlertManager()
        alert = manager.check_threshold("dc_latency_ms", 250.0)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL
        assert "DC" in alert.title

    def test_update_threshold(self):
        """Test updating threshold values."""
        manager = AlertManager()
        manager.update_threshold("ws_errors_per_minute", warning=60.0, critical=80.0)
        threshold = manager.thresholds["ws_errors_per_minute"]
        assert threshold.warning_value == 60.0
        assert threshold.critical_value == 80.0

    def test_update_threshold_invalid_metric(self):
        """Test updating invalid metric raises error."""
        manager = AlertManager()
        with pytest.raises(ValueError):
            manager.update_threshold("invalid_metric", warning=10.0)

    def test_get_statistics(self):
        """Test getting alert statistics."""
        manager = AlertManager()
        manager.check_threshold("ws_errors_per_minute", 60.0)
        stats = manager.get_statistics()
        assert "total_alerts" in stats
        assert "alerts_last_hour" in stats
        assert "alerts_last_day" in stats
        assert stats["total_alerts"] >= 1


class TestAlertHelpers:
    """Tests for alert helper functions."""

    @pytest.mark.asyncio
    async def test_alert_dc_latency_warning(self):
        """Test DC latency warning alert helper."""
        # Reset alert manager to avoid cooldown from other tests
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

    @pytest.mark.asyncio
    async def test_alert_dc_latency_critical(self):
        """Test DC latency critical alert helper."""
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

    def test_alert_to_dict(self):
        """Test Alert serialization."""
        alert = Alert(
            alert_type=AlertType.DC_HIGH_LATENCY,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            metadata={"dc_id": 2, "latency": 175.0}
        )
        data = alert.to_dict()
        assert data["type"] == "DC_HIGH_LATENCY"
        assert data["severity"] == "WARNING"
        assert data["title"] == "Test Alert"
        assert data["message"] == "Test message"
        assert "dc_id" in data["metadata"]
