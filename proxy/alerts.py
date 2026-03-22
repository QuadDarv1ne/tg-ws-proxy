"""
Proxy Alerts and Notifications Module.

Provides real-time monitoring and alerting for:
- Connection thresholds
- Error rate spikes
- Traffic limits
- Performance degradation
- Security events

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum, auto
from typing import Callable

log = logging.getLogger('tg-ws-alerts')


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = auto()
    WARNING = auto()
    CRITICAL = auto()
    EMERGENCY = auto()


class AlertType(Enum):
    """Types of alerts."""
    CONNECTION_SPIKE = auto()
    ERROR_RATE_HIGH = auto()
    TRAFFIC_LIMIT = auto()
    CPU_HIGH = auto()
    MEMORY_HIGH = auto()
    WS_ERRORS = auto()
    DC_UNAVAILABLE = auto()
    DC_HIGH_LATENCY = auto()  # New: High DC latency alert
    SECURITY_EVENT = auto()
    KEY_ROTATION = auto()
    RATE_LIMIT = auto()
    POOL_EXHAUSTED = auto()


@dataclass
class Alert:
    """Alert data container."""
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.alert_type.name,
            "severity": self.severity.name,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AlertThreshold:
    """Threshold configuration for alerts."""
    metric: str
    warning_value: float
    critical_value: float
    enabled: bool = True
    cooldown_seconds: int = 300


class AlertManager:
    """Centralized alert management system."""

    def __init__(self) -> None:
        self.alerts: list[Alert] = []
        self.alert_history: list[Alert] = []
        self.max_history = 1000
        self._alert_callbacks: list[Callable[[Alert], None]] = []
        self.thresholds: dict[str, AlertThreshold] = {}
        self._last_alert_time: dict[str, float] = {}
        self._email_config: dict | None = None
        self._webhook_urls: list[str] = []
        self.alerts_sent = 0
        self.alerts_suppressed = 0
        self._setup_default_thresholds()

    def _setup_default_thresholds(self) -> None:
        self.thresholds = {
            "connections_per_minute": AlertThreshold("connections_per_minute", 100, 500, cooldown_seconds=300),
            "error_rate_percent": AlertThreshold("error_rate_percent", 5.0, 15.0, cooldown_seconds=180),
            "cpu_percent": AlertThreshold("cpu_percent", 70.0, 90.0, cooldown_seconds=600),
            "memory_percent": AlertThreshold("memory_percent", 70.0, 90.0, cooldown_seconds=600),
            "ws_errors_per_minute": AlertThreshold("ws_errors_per_minute", 10, 50, cooldown_seconds=180),
            "traffic_gb_per_hour": AlertThreshold("traffic_gb_per_hour", 50, 100, cooldown_seconds=3600),
            "dc_latency_ms": AlertThreshold("dc_latency_ms", 150.0, 200.0, cooldown_seconds=120),  # New: DC latency threshold
        }

    def check_threshold(self, metric: str, value: float) -> Alert | None:
        threshold = self.thresholds.get(metric)
        if not threshold or not threshold.enabled:
            return None

        now = time.time()
        last_alert = self._last_alert_time.get(metric, 0)
        if now - last_alert < threshold.cooldown_seconds:
            self.alerts_suppressed += 1
            return None

        severity = None
        if value >= threshold.critical_value:
            severity = AlertSeverity.CRITICAL
        elif value >= threshold.warning_value:
            severity = AlertSeverity.WARNING

        if not severity:
            return None

        alert = self._create_threshold_alert(metric, value, severity)
        self._send_alert(alert)
        self._last_alert_time[metric] = now
        return alert

    def _create_threshold_alert(self, metric: str, value: float, severity: AlertSeverity) -> Alert:
        # Mapping from metric names to AlertType
        metric_to_alert_type = {
            "connections_per_minute": AlertType.CONNECTION_SPIKE,
            "error_rate_percent": AlertType.ERROR_RATE_HIGH,
            "cpu_percent": AlertType.CPU_HIGH,
            "memory_percent": AlertType.MEMORY_HIGH,
            "ws_errors_per_minute": AlertType.WS_ERRORS,
            "traffic_gb_per_hour": AlertType.TRAFFIC_LIMIT,
            "dc_latency_ms": AlertType.DC_HIGH_LATENCY,
        }

        titles = {
            "connections_per_minute": f"High connection rate: {value:.0f}/min",
            "error_rate_percent": f"High error rate: {value:.1f}%",
            "cpu_percent": f"High CPU usage: {value:.1f}%",
            "memory_percent": f"High memory usage: {value:.1f}%",
            "ws_errors_per_minute": f"WebSocket errors: {value:.0f}/min",
            "traffic_gb_per_hour": f"High traffic: {value:.1f} GB/hour",
            "dc_latency_ms": f"High DC latency: {value:.0f}ms",
        }

        messages = {
            "connections_per_minute": f"Connection rate exceeded threshold. Current: {value:.0f}/min",
            "error_rate_percent": f"Error rate is above acceptable level. Current: {value:.1f}%",
            "cpu_percent": f"CPU usage is critically high. Current: {value:.1f}%",
            "memory_percent": f"Memory usage is critically high. Current: {value:.1f}%",
            "ws_errors_per_minute": f"WebSocket errors detected. Current: {value:.0f}/min",
            "traffic_gb_per_hour": f"Traffic volume exceeded threshold. Current: {value:.1f} GB/hour",
            "dc_latency_ms": f"DC latency is above acceptable level. Current: {value:.0f}ms (threshold: 150ms warning, 200ms critical)",
        }

        alert_type = metric_to_alert_type.get(metric, AlertType.SECURITY_EVENT)

        return Alert(
            alert_type=alert_type,
            severity=severity,
            title=titles.get(metric, f"Threshold exceeded: {metric}"),
            message=messages.get(metric, f"{metric}: {value}"),
            metadata={"value": value, "metric": metric},
        )

    def send_custom_alert(self, alert_type: AlertType, severity: AlertSeverity, title: str, message: str, metadata: dict | None = None) -> None:
        alert = Alert(alert_type=alert_type, severity=severity, title=title, message=message, metadata=metadata or {})
        self._send_alert(alert)

    def _send_alert(self, alert: Alert) -> None:
        self.alerts.append(alert)
        self.alert_history.append(alert)
        self.alerts_sent += 1

        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                log.error("Alert callback error: %s", e)

        log_method = log.warning if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY) else log.info
        log_method("ALERT [%s] %s: %s", alert.severity.name, alert.title, alert.message)

        asyncio.create_task(self._send_notifications(alert))

    async def _send_notifications(self, alert: Alert) -> None:
        if self._email_config:
            await self._send_email_notification(alert)
        if self._webhook_urls:
            await self._send_webhook_notifications(alert)

    async def _send_email_notification(self, alert: Alert) -> None:
        try:
            config = self._email_config
            if not config:
                return
            msg = MIMEMultipart()
            msg['From'] = config['from_email']
            msg['To'] = ', '.join(config['to_emails'])
            msg['Subject'] = f"[{alert.severity.name}] {alert.title}"
            body = f"{alert.title}\n\n{alert.message}\n\nTime: {alert.timestamp}\nSeverity: {alert.severity.name}"
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()
            server.login(config['username'], config['password'])
            server.send_message(msg)
            server.quit()
            log.info("Alert email sent successfully")
        except Exception as e:
            log.error("Failed to send alert email: %s", e)

    async def _send_webhook_notifications(self, alert: Alert) -> None:
        try:
            import aiohttp
            payload = {"alert": alert.to_dict(), "source": "TG WS Proxy"}
            async with aiohttp.ClientSession() as session:
                for url in self._webhook_urls:
                    try:
                        async with session.post(url, json=payload, timeout=10) as response:
                            if response.status == 200:
                                log.debug("Webhook notification sent to %s", url)
                    except Exception:
                        pass
        except ImportError:
            pass
        except Exception as e:
            log.error("Webhook notification error: %s", e)

    def configure_email(self, smtp_server: str, smtp_port: int, username: str, password: str, from_email: str, to_emails: list[str]) -> None:
        self._email_config = {'smtp_server': smtp_server, 'smtp_port': smtp_port, 'username': username, 'password': password, 'from_email': from_email, 'to_emails': to_emails}
        log.info("Email alerts configured for %s", from_email)

    def configure_webhook(self, urls: list[str]) -> None:
        self._webhook_urls = urls
        log.info("Webhook alerts configured for %d URLs", len(urls))

    def get_recent_alerts(self, limit: int = 50) -> list[Alert]:
        return self.alert_history[-limit:]

    def get_statistics(self) -> dict:
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        recent_alerts = [a for a in self.alert_history if a.timestamp > hour_ago]
        day_alerts = [a for a in self.alert_history if a.timestamp > day_ago]

        return {
            "total_alerts": len(self.alert_history),
            "alerts_last_hour": len(recent_alerts),
            "alerts_last_day": len(day_alerts),
            "alerts_sent": self.alerts_sent,
            "alerts_suppressed": self.alerts_suppressed,
        }

    def update_threshold(self, metric: str, warning: float | None = None, critical: float | None = None, enabled: bool | None = None) -> None:
        threshold = self.thresholds.get(metric)
        if not threshold:
            raise ValueError(f"Unknown metric: {metric}")
        if warning is not None:
            threshold.warning_value = warning
        if critical is not None:
            threshold.critical_value = critical
        if enabled is not None:
            threshold.enabled = enabled


_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def check_alert(metric: str, value: float) -> Alert | None:
    return get_alert_manager().check_threshold(metric, value)


def send_alert(alert_type: AlertType, severity: AlertSeverity, title: str, message: str, metadata: dict | None = None) -> None:
    get_alert_manager().send_custom_alert(alert_type, severity, title, message, metadata)


def alert_ws_errors(count: int) -> None:
    send_alert(AlertType.WS_ERRORS, AlertSeverity.WARNING if count < 50 else AlertSeverity.CRITICAL, f"WebSocket errors: {count}/min", f"Multiple WebSocket errors detected: {count} in the last minute", {"error_count": count})


def alert_connection_spike(connections: int) -> None:
    send_alert(AlertType.CONNECTION_SPIKE, AlertSeverity.WARNING if connections < 500 else AlertSeverity.CRITICAL, f"Connection spike detected: {connections}/min", f"Unusual increase in connections: {connections} per minute", {"connections": connections})


def alert_traffic_limit(traffic_gb: float) -> None:
    send_alert(AlertType.TRAFFIC_LIMIT, AlertSeverity.WARNING if traffic_gb < 100 else AlertSeverity.CRITICAL, f"High traffic volume: {traffic_gb:.1f} GB/hour", f"Traffic exceeded threshold: {traffic_gb:.1f} GB in the last hour", {"traffic_gb": traffic_gb})


def alert_key_rotation(algorithm: str) -> None:
    send_alert(AlertType.KEY_ROTATION, AlertSeverity.INFO, f"Encryption keys rotated: {algorithm}", f"Automatic key rotation completed successfully for {algorithm}", {"algorithm": algorithm})


def alert_dc_latency(dc_id: int, latency_ms: float) -> None:
    """Send alert for high DC latency."""
    severity = AlertSeverity.WARNING if latency_ms < 200 else AlertSeverity.CRITICAL
    send_alert(
        AlertType.DC_HIGH_LATENCY,
        severity,
        f"DC{dc_id} high latency: {latency_ms:.0f}ms",
        f"Telegram DC{dc_id} latency is {latency_ms:.0f}ms (threshold: 150ms warning, 200ms critical)",
        {"dc_id": dc_id, "latency_ms": latency_ms}
    )


__all__ = ['AlertManager', 'Alert', 'AlertType', 'AlertSeverity', 'AlertThreshold', 'get_alert_manager', 'check_alert', 'send_alert', 'alert_ws_errors', 'alert_connection_spike', 'alert_traffic_limit', 'alert_key_rotation', 'alert_dc_latency']
