"""
Proxy statistics tracking module.

Provides Stats class for tracking proxy connections, traffic, and performance metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time

import psutil

# Import alerts module
try:
    from . import alerts as alerts_module  # type: ignore[attr-defined]
    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False
    alerts_module = None

log = logging.getLogger('tg-ws-stats')


def _human_bytes(n: float) -> str:
    """Convert bytes to human-readable format."""
    if n < 0:
        return f"-{_human_bytes(-n)}"
    if n < 1024:
        return f"{int(n)}B"
    units = ('KB', 'MB', 'GB', 'TB')
    unit_idx = 0
    while n >= 1024 and unit_idx < len(units) - 1:
        n /= 1024
        unit_idx += 1
    return f"{n:.1f}{units[unit_idx]}"


def _human_time(seconds: float) -> str:
    """Convert seconds to human-readable format."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m"
    else:
        return f"{seconds/3600:.1f}h"


class Stats:
    """Proxy statistics tracker."""

    def __init__(self, history_size: int = 50, enable_alerts: bool = True, optimize_memory: bool = True) -> None:
        self.connections_total = 0
        self.connections_ws = 0
        self.connections_tcp_fallback = 0
        self.connections_http_rejected = 0
        self.connections_passthrough = 0
        self.ws_errors = 0
        self.bytes_up = 0
        self.bytes_down = 0
        self.pool_hits = 0
        self.pool_misses = 0

        # DC statistics
        self.dc_stats: dict[int, dict[str, int]] = {}  # dc_id -> {connections, errors}
        self._current_dc: int | None = None

        # Latency tracking (last ping per DC)
        self.latency_ms: dict[int, float] = {}  # dc_id -> latency in ms
        self._latency_history: dict[int, list[float]] = {}  # dc_id -> [latencies]

        # Session tracking
        self.session_start = time.monotonic()
        self.last_connection_time: float | None = None
        self.peak_connections_per_minute: float = 0

        # Performance monitoring
        self._process = psutil.Process(os.getpid())
        self.cpu_percent = 0.0
        self.memory_bytes = 0
        self._last_cpu_update = 0.0
        self._cpu_history: list[float] = []
        self._memory_history: list[int] = []

        # History tracking (last N events)
        self._history_size = history_size if not optimize_memory else 30
        self._optimize_memory = optimize_memory
        self.connection_history: list[dict] = []
        self.traffic_history: list[dict] = []
        self._last_traffic_snapshot = (0, 0)
        self._traffic_snapshot_time = time.monotonic()

        # Real-time monitoring
        self.enable_alerts = enable_alerts and ALERTS_AVAILABLE
        self._alert_manager = alerts_module.get_alert_manager() if self.enable_alerts else None
        self._last_error_count = 0
        self._error_rate_window: list[tuple[float, int]] = []  # (timestamp, errors)
        self._monitoring_enabled = False
        self._monitor_task: asyncio.Task | None = None

        # Memory optimization
        if self._optimize_memory:
            self._error_rate_window_max = 30  # Limit error window size
            self._latency_history_max = 20  # Limit latency history per DC
        else:
            self._error_rate_window_max = 60
            self._latency_history_max = 60

    def add_connection(self, conn_type: str, dc: int | None = None) -> None:
        """Record a new connection in history."""
        self.connections_total += 1
        self.last_connection_time = time.monotonic()
        self._current_dc = dc

        if conn_type == 'ws':
            self.connections_ws += 1
        elif conn_type == 'tcp_fallback':
            self.connections_tcp_fallback += 1
        elif conn_type == 'http_rejected':
            self.connections_http_rejected += 1
        elif conn_type == 'passthrough':
            self.connections_passthrough += 1

        if dc is not None:
            if dc not in self.dc_stats:
                self.dc_stats[dc] = {'connections': 0, 'errors': 0}
            self.dc_stats[dc]['connections'] += 1

        self.connection_history.append({
            'time': time.monotonic(),
            'type': conn_type,
            'dc': dc
        })
        if len(self.connection_history) > self._history_size:
            self.connection_history.pop(0)

        cpm = self.get_connections_per_minute()
        if cpm > self.peak_connections_per_minute:
            self.peak_connections_per_minute = cpm

    def add_bytes(self, up: int = 0, down: int = 0) -> None:
        """Record traffic update."""
        self.bytes_up += up
        self.bytes_down += down

        now = time.monotonic()
        if now - self._traffic_snapshot_time >= 1.0:
            self.traffic_history.append({
                'time': now,
                'bytes_up': self.bytes_up,
                'bytes_down': self.bytes_down
            })
            if len(self.traffic_history) > self._history_size:
                self.traffic_history.pop(0)
            self._traffic_snapshot_time = now

    def add_ws_error(self, dc: int | None = None) -> None:
        """Record a WebSocket error."""
        self.ws_errors += 1
        if dc is not None and dc in self.dc_stats:
            self.dc_stats[dc]['errors'] += 1

        # Track error rate for monitoring
        if self.enable_alerts:
            now = time.monotonic()
            self._error_rate_window.append((now, 1))
            # Keep only last minute with optimized limit
            cutoff = now - 60
            max_window = self._error_rate_window_max if self._optimize_memory else 60
            self._error_rate_window = [
                (t, e) for t, e in self._error_rate_window
                if t > cutoff
            ][-max_window:]

            # Check error rate threshold
            errors_per_minute = sum(e for t, e in self._error_rate_window)
            if errors_per_minute >= 10:
                alerts_module.alert_ws_errors(errors_per_minute)

    def record_latency(self, dc: int, latency_ms: float) -> None:
        """Record latency measurement for a DC."""
        self.latency_ms[dc] = latency_ms
        if dc not in self._latency_history:
            self._latency_history[dc] = []
        self._latency_history[dc].append(latency_ms)
        # Use optimized limit if enabled
        max_history = self._latency_history_max if self._optimize_memory else 60
        if len(self._latency_history[dc]) > max_history:
            self._latency_history[dc].pop(0)

    def update_performance_metrics(self) -> None:
        """Update CPU and memory usage metrics."""
        now = time.monotonic()
        # Update CPU every 1 second to avoid excessive overhead
        if now - self._last_cpu_update >= 1.0:
            try:
                self.cpu_percent = self._process.cpu_percent(interval=None)
                self.memory_bytes = self._process.memory_info().rss

                self._cpu_history.append(self.cpu_percent)
                self._memory_history.append(self.memory_bytes)

                # Keep last 60 measurements (1 minute)
                if len(self._cpu_history) > 60:
                    self._cpu_history.pop(0)
                if len(self._memory_history) > 60:
                    self._memory_history.pop(0)

                self._last_cpu_update = now
            except Exception:
                pass

    def get_average_cpu(self) -> float | None:
        """Get average CPU usage over the last minute."""
        if not self._cpu_history:
            return None
        return sum(self._cpu_history) / len(self._cpu_history)

    def get_average_memory(self) -> int | None:
        """Get average memory usage over the last minute."""
        if not self._memory_history:
            return None
        return int(sum(self._memory_history) / len(self._memory_history))

    def get_performance_stats(self) -> dict:
        """Get current performance statistics."""
        self.update_performance_metrics()
        return {
            "cpu_percent": self.cpu_percent,
            "memory_bytes": self.memory_bytes,
            "memory_mb": self.memory_bytes / (1024 * 1024),
            "avg_cpu_percent": self.get_average_cpu(),
            "avg_memory_bytes": self.get_average_memory(),
            "avg_memory_mb": (self.get_average_memory() or 0) / (1024 * 1024),
        }

    def get_average_latency(self, dc: int) -> float | None:
        """Get average latency for a DC."""
        if dc not in self._latency_history or not self._latency_history[dc]:
            return None
        return sum(self._latency_history[dc]) / len(self._latency_history[dc])

    def get_connections_per_minute(self) -> float:
        """Calculate connections per minute from history."""
        if not self.connection_history:
            return 0.0
        now = time.monotonic()
        minute_ago = now - 60
        recent = [c for c in self.connection_history if c['time'] > minute_ago]
        return len(recent)

    def get_traffic_per_minute(self) -> tuple[int, int]:
        """Calculate bytes per minute (up, down) from history."""
        if not self.traffic_history:
            return (0, 0)
        now = time.monotonic()
        minute_ago = now - 60
        recent = [t for t in self.traffic_history if t['time'] > minute_ago]
        if not recent:
            return (0, 0)
        up = sum(t['bytes_up'] for t in recent)
        down = sum(t['bytes_down'] for t in recent)
        return (up, down)

    def get_traffic_history(self, limit: int = 60) -> list[dict]:
        """Get traffic history for chart rendering."""
        if not self.traffic_history:
            return []
        return self.traffic_history[-limit:]

    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return time.monotonic() - self.session_start

    def get_best_dc(self) -> int | None:
        """Get DC with lowest average latency."""
        if not self.latency_ms:
            return None
        return min(self.latency_ms, key=lambda x: self.latency_ms[x])

    def get_dc_stats(self) -> dict[int, dict]:
        """Get statistics per DC."""
        result = {}
        for dc, stats in self.dc_stats.items():
            result[dc] = {
                'connections': stats['connections'],
                'errors': stats['errors'],
                'latency_ms': self.latency_ms.get(dc),
                'avg_latency_ms': self.get_average_latency(dc)
            }
        return result

    def export_to_json(self, include_history: bool = False) -> str:
        """Export statistics to JSON format."""
        data = self.to_dict()
        data['session_duration_seconds'] = self.get_session_duration()
        data['peak_connections_per_minute'] = self.peak_connections_per_minute
        data['dc_stats'] = self.get_dc_stats()
        if include_history:
            data['connection_history'] = self.connection_history[-100:]
            data['traffic_history'] = self.traffic_history[-100:]
        return json.dumps(data, indent=2, default=str)

    def export_to_csv(self) -> str:
        """Export statistics to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'metric', 'value', 'unit'
        ])

        # Basic stats
        data = self.to_dict()
        for key, value in data.items():
            if isinstance(value, (int, float)):
                writer.writerow([key, value, ''])

        # DC stats
        for dc_id, dc_data in self.get_dc_stats().items():
            writer.writerow([f'dc_{dc_id}_connections', dc_data['connections'], ''])
            writer.writerow([f'dc_{dc_id}_errors', dc_data['errors'], ''])
            if dc_data.get('latency_ms'):
                writer.writerow([f'dc_{dc_id}_latency', dc_data['latency_ms'], 'ms'])

        return output.getvalue()

    def get_pool_efficiency(self) -> float:
        """Calculate WebSocket pool efficiency (0.0-1.0)."""
        total = self.pool_hits + self.pool_misses
        if total == 0:
            return 1.0
        return self.pool_hits / total

    def get_error_rate(self) -> float:
        """Calculate error rate (errors per 100 connections)."""
        if self.connections_total == 0:
            return 0.0
        return (self.ws_errors / self.connections_total) * 100

    def get_health_status(self) -> tuple[str, str, str]:
        """
        Get system health status.

        Returns:
            Tuple of (status, message, color)
            - status: 'healthy', 'degraded', 'critical'
            - message: Human-readable status
            - color: 'green', 'yellow', 'red'
        """
        error_rate = self.get_error_rate()
        pool_efficiency = self.get_pool_efficiency()

        # Critical: High error rate or low pool efficiency
        if error_rate > 15 or pool_efficiency < 0.5:
            return (
                'critical',
                f'Проблемы с подключением (ошибки: {error_rate:.1f}%, пул: {pool_efficiency:.0%})',
                'red'
            )

        # Degraded: Moderate issues
        if error_rate > 5 or pool_efficiency < 0.7:
            return (
                'degraded',
                f'Работает с проблемами (ошибки: {error_rate:.1f}%, пул: {pool_efficiency:.0%})',
                'yellow'
            )

        # Healthy
        return (
            'healthy',
            'Работает нормально',
            'green'
        )

    def summary(self) -> str:
        """Return human-readable stats summary."""
        uptime = _human_time(self.get_session_duration())
        return (f"total={self.connections_total} ws={self.connections_ws} "
                f"tcp_fb={self.connections_tcp_fallback} "
                f"http_skip={self.connections_http_rejected} "
                f"pass={self.connections_passthrough} "
                f"err={self.ws_errors} "
                f"pool={self.pool_hits}/{self.pool_hits+self.pool_misses} "
                f"up={_human_bytes(self.bytes_up)} "
                f"down={_human_bytes(self.bytes_down)} "
                f"uptime={uptime}")

    def to_dict(self) -> dict:
        """Return stats as a dictionary."""
        conn_per_min = self.get_connections_per_minute()
        traffic_per_min = self.get_traffic_per_minute()
        perf_stats = self.get_performance_stats()
        return {
            "connections_total": self.connections_total,
            "connections_ws": self.connections_ws,
            "connections_tcp_fallback": self.connections_tcp_fallback,
            "connections_http_rejected": self.connections_http_rejected,
            "connections_passthrough": self.connections_passthrough,
            "ws_errors": self.ws_errors,
            "bytes_up": self.bytes_up,
            "bytes_down": self.bytes_down,
            "pool_hits": self.pool_hits,
            "pool_misses": self.pool_misses,
            "connections_per_minute": round(conn_per_min, 1),
            "peak_connections_per_minute": self.peak_connections_per_minute,
            "traffic_up_per_minute": traffic_per_min[0],
            "traffic_down_per_minute": traffic_per_min[1],
            "connection_history": self.connection_history[-10:],  # Last 10
            "traffic_history": self.get_traffic_history(60),  # Last 60 snapshots
            "dc_stats": self.get_dc_stats(),
            "latency_ms": self.latency_ms,
            "session_duration_seconds": self.get_session_duration(),
            "best_dc": self.get_best_dc(),
            "performance": perf_stats,
            "health": self.get_health_status(),
            "alerts_enabled": self.enable_alerts,
        }

    def start_realtime_monitoring(self, check_interval: float = 10.0, auto_export: bool = False, export_dir: str | None = None) -> None:
        """
        Start real-time monitoring with automatic threshold checks.

        Args:
            check_interval: How often to check thresholds (seconds)
            auto_export: Enable automatic stats export
            export_dir: Directory for exported stats files
        """
        if not self.enable_alerts:
            log.debug("Alerts disabled, skipping monitoring")
            return

        async def monitor_loop() -> None:
            """Monitor metrics and generate alerts."""
            log.info("Real-time monitoring started (interval: %.1fs)", check_interval)
            self._monitoring_enabled = True

            # Auto-export tracking
            last_export_time = time.monotonic()
            export_interval = 3600  # Export every hour

            # Memory cleanup tracking
            last_cleanup_time = time.monotonic()
            cleanup_interval = 600  # Cleanup every 10 minutes

            while self._monitoring_enabled:
                try:
                    await asyncio.sleep(check_interval)
                    self._check_all_thresholds()

                    # Auto-export stats
                    if auto_export and export_dir:
                        now = time.monotonic()
                        if now - last_export_time >= export_interval:
                            self._export_stats_to_file(export_dir)
                            last_export_time = now

                    # Memory cleanup
                    if self._optimize_memory:
                        now = time.monotonic()
                        if now - last_cleanup_time >= cleanup_interval:
                            self.cleanup()
                            last_cleanup_time = now

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error("Monitoring error: %s", e)

            log.info("Real-time monitoring stopped")

        # Start monitoring task
        try:
            self._monitor_task = asyncio.create_task(monitor_loop())
        except Exception as e:
            log.warning("Failed to start monitoring task: %s", e)

    def _export_stats_to_file(self, export_dir: str) -> None:
        """Export current statistics to JSON file."""
        import json
        from datetime import datetime

        try:
            os.makedirs(export_dir, exist_ok=True)
            stats = self.to_dict()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(export_dir, f"stats_{timestamp}.json")

            with open(filename, 'w') as f:
                json.dump(stats, f, indent=2, default=str)

            log.debug("Stats exported to %s", filename)

            # Keep only last 24 exports
            self._cleanup_old_exports(export_dir, max_files=24)

        except Exception as e:
            log.error("Failed to export stats: %s", e)

    def _cleanup_old_exports(self, export_dir: str, max_files: int = 24) -> None:
        """Remove old export files, keeping only recent ones."""
        try:
            files = sorted(
                [f for f in os.listdir(export_dir) if f.startswith("stats_") and f.endswith(".json")],
                reverse=True
            )
            for old_file in files[max_files:]:
                os.remove(os.path.join(export_dir, old_file))
        except Exception as e:
            log.debug("Failed to cleanup old exports: %s", e)

    def stop_realtime_monitoring(self) -> None:
        """Stop real-time monitoring."""
        self._monitoring_enabled = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    def _check_all_thresholds(self) -> None:
        """Check all metric thresholds and generate alerts."""
        if not self._alert_manager:
            return

        # Get current metrics
        conn_per_min = self.get_connections_per_minute()
        error_rate = self._calculate_error_rate()
        cpu = self.cpu_percent
        memory_percent = (self.memory_bytes / (psutil.virtual_memory().total * 1024 * 1024)) * 100 if self.memory_bytes else 0
        traffic_gb_hour = self._calculate_traffic_per_hour() / (1024 ** 3)

        # Check thresholds
        self._alert_manager.check_threshold("connections_per_minute", conn_per_min)
        self._alert_manager.check_threshold("error_rate_percent", error_rate)
        self._alert_manager.check_threshold("cpu_percent", cpu)
        self._alert_manager.check_threshold("memory_percent", memory_percent)
        self._alert_manager.check_threshold("traffic_gb_per_hour", traffic_gb_hour)

        # Check for connection spikes
        if conn_per_min > 100 and conn_per_min > self.peak_connections_per_minute * 1.5:
            alerts_module.alert_connection_spike(int(conn_per_min))

        # Check for high traffic
        if traffic_gb_hour > 50:
            alerts_module.alert_traffic_limit(traffic_gb_hour)

    def _calculate_error_rate(self) -> float:
        """Calculate current error rate percentage."""
        total = self.connections_total
        if total == 0:
            return 0.0
        return (self.ws_errors / total) * 100

    def _calculate_traffic_per_hour(self) -> int:
        """Calculate traffic per hour in bytes."""
        if not self.traffic_history:
            return 0

        now = time.monotonic()
        hour_ago = now - 3600

        # Find traffic from an hour ago
        for entry in self.traffic_history:
            if entry['time'] < hour_ago:
                continue
            current_total: int = entry['bytes_up'] + entry['bytes_down']
            return current_total

        # If no history from an hour ago, return current total
        return int(self.bytes_up + self.bytes_down)

    def get_monitoring_status(self) -> dict:
        """Get current monitoring status."""
        return {
            "enabled": self._monitoring_enabled,
            "alerts_enabled": self.enable_alerts,
            "alert_manager": self._alert_manager is not None,
            "monitor_task": self._monitor_task is not None,
            "error_rate_window": len(self._error_rate_window),
        }

    def cleanup(self) -> None:
        """Clean up old data and free memory."""
        import gc

        # Clear old connection history
        if len(self.connection_history) > self._history_size:
            self.connection_history = self.connection_history[-self._history_size:]

        # Clear old traffic history
        if len(self.traffic_history) > self._history_size:
            self.traffic_history = self.traffic_history[-self._history_size:]

        # Clear old CPU/memory history
        max_perf_history = 30 if self._optimize_memory else 60
        if len(self._cpu_history) > max_perf_history:
            self._cpu_history = self._cpu_history[-max_perf_history:]
        if len(self._memory_history) > max_perf_history:
            self._memory_history = self._memory_history[-max_perf_history:]

        # Clear old latency history
        for dc in self._latency_history:
            max_lat = self._latency_history_max if self._optimize_memory else 60
            if len(self._latency_history[dc]) > max_lat:
                self._latency_history[dc] = self._latency_history[dc][-max_lat:]

        # Force garbage collection
        gc.collect()
