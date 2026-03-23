"""
Metrics History Module for TG WS Proxy.

Provides historical metrics storage and analysis:
- Time-series metrics storage
- 30-day retention policy
- Aggregation functions (avg, min, max, percentiles)
- Trend analysis
- Export to CSV/JSON
- SQLite backend for persistence

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger('tg-ws-metrics-history')


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: float
    metric_name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""
    metric_name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    p50_value: float  # 50th percentile
    p95_value: float  # 95th percentile
    p99_value: float  # 99th percentile
    time_range_hours: float


class MetricsHistory:
    """
    Historical metrics storage and analysis.

    Features:
    - SQLite backend for persistence
    - 30-day automatic retention
    - Efficient time-series queries
    - Aggregation functions
    - Trend analysis
    """

    DEFAULT_RETENTION_DAYS = 30
    BATCH_INSERT_SIZE = 100

    def __init__(
        self,
        db_path: str | Path | None = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        """
        Initialize metrics history.

        Args:
            db_path: Path to SQLite database. Default: ./metrics_history.db
            retention_days: Number of days to retain metrics
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'metrics_history.db'

        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self._conn: sqlite3.Connection | None = None

        # In-memory cache for recent metrics with memory optimization
        self._recent_cache: list[MetricPoint] = []
        self._cache_max_size = 1000
        self._cache_max_memory_mb = 10.0  # Max 10MB for cache
        self._estimated_point_size = 200  # Estimated bytes per point

        # Automatic aggregation thresholds
        self._aggregation_enabled = True
        self._raw_retention_hours = 24  # Keep raw data for 24 hours
        self._hourly_retention_days = 7  # Keep hourly aggregates for 7 days
        self._daily_retention_days = 30  # Keep daily aggregates for 30 days

        self._init_database()
        log.info("Metrics history initialized: %s (retention: %d days, cache: %.1fMB)",
                self.db_path, retention_days, self._cache_max_memory_mb)

    def _init_database(self) -> None:
        """Initialize SQLite database with schema."""
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None  # Auto-commit
        )
        self._conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency

        cursor = self._conn.cursor()

        # Main metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT,
                created_at REAL DEFAULT (strftime('%s', 'now'))
            )
        """)

        # Indexes for efficient queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name_time
            ON metrics(metric_name, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_time
            ON metrics(timestamp DESC)
        """)

        # Summary table for pre-aggregated data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_hourly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hour_timestamp REAL NOT NULL,
                metric_name TEXT NOT NULL,
                min_value REAL,
                max_value REAL,
                avg_value REAL,
                count INTEGER,
                UNIQUE(hour_timestamp, metric_name)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hourly_name_time
            ON metrics_hourly(metric_name, hour_timestamp DESC)
        """)

        self._conn.commit()

        # Cleanup old data on startup
        self._cleanup_old_data()

    def record_metric(
        self,
        metric_name: str,
        value: float,
        labels: dict[str, str] | None = None,
        timestamp: float | None = None,
    ) -> None:
        """
        Record a metric data point.

        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels (e.g., {'dc': '1', 'type': 'latency'})
            timestamp: Unix timestamp. Default: current time
        """
        if timestamp is None:
            timestamp = time.time()

        labels_json = json.dumps(labels) if labels else None

        # Add to cache
        point = MetricPoint(
            timestamp=timestamp,
            metric_name=metric_name,
            value=value,
            labels=labels or {},
        )
        self._recent_cache.append(point)

        # Trim cache if needed
        if len(self._recent_cache) > self._cache_max_size:
            self._recent_cache = self._recent_cache[-self._cache_max_size:]

        # Insert to database
        if self._conn:
            try:
                self._conn.execute(
                    """
                    INSERT INTO metrics (timestamp, metric_name, value, labels)
                    VALUES (?, ?, ?, ?)
                    """,
                    (timestamp, metric_name, value, labels_json)
                )
            except sqlite3.Error as e:
                log.error("Failed to record metric %s: %s", metric_name, e)

    def record_metrics_batch(self, points: list[MetricPoint]) -> None:
        """
        Record multiple metrics in a batch (more efficient).

        Args:
            points: List of MetricPoint objects
        """
        if not points or not self._conn:
            return

        data = [
            (p.timestamp, p.metric_name, p.value, json.dumps(p.labels) if p.labels else None)
            for p in points
        ]

        try:
            self._conn.executemany(
                """
                INSERT INTO metrics (timestamp, metric_name, value, labels)
                VALUES (?, ?, ?, ?)
                """,
                data
            )
            self._conn.commit()
        except sqlite3.Error as e:
            log.error("Failed to record metrics batch: %s", e)

        # Update cache with memory optimization
        self._recent_cache.extend(points)
        self._optimize_cache_memory()

    def _optimize_cache_memory(self) -> None:
        """
        Optimize in-memory cache to stay within memory limits.

        Removes oldest entries when cache exceeds size or memory limit.
        """
        # Check size limit
        if len(self._recent_cache) > self._cache_max_size:
            self._recent_cache = self._recent_cache[-self._cache_max_size:]

        # Check memory limit
        estimated_memory = len(self._recent_cache) * self._estimated_point_size / (1024 * 1024)
        if estimated_memory > self._cache_max_memory_mb:
            # Remove oldest entries to get under limit
            target_size = int((self._cache_max_memory_mb * 0.8) / (self._estimated_point_size / (1024 * 1024)))
            self._recent_cache = self._recent_cache[-target_size:]
            log.debug("Metrics cache optimized: %.2fMB -> %.2fMB",
                     estimated_memory, target_size * self._estimated_point_size / (1024 * 1024))

    def _cleanup_old_data(self) -> None:
        """
        Automatically clean up old data based on retention policies.

        Called periodically to maintain database size.
        """
        if not self._conn:
            return

        now = time.time()

        # Clean up raw data older than raw_retention_hours
        raw_cutoff = now - (self._raw_retention_hours * 3600)
        try:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM metrics WHERE timestamp < ?", (raw_cutoff,))
            deleted = cursor.rowcount
            if deleted > 0:
                log.debug("Cleaned up %d raw metrics older than %d hours",
                         deleted, self._raw_retention_hours)
        except sqlite3.Error as e:
            log.debug("Failed to cleanup raw metrics: %s", e)

    def get_metric_summary(
        self,
        metric_name: str,
        hours: float = 24.0,
        labels: dict[str, str] | None = None,
    ) -> MetricSummary | None:
        """
        Get summary statistics for a metric.

        Args:
            metric_name: Name of the metric
            hours: Time range in hours
            labels: Optional labels to filter by

        Returns:
            MetricSummary or None if no data
        """
        if not self._conn:
            return None

        cutoff = time.time() - (hours * 3600)

        # Build query
        query = """
            SELECT
                COUNT(*) as count,
                MIN(value) as min_value,
                MAX(value) as max_value,
                AVG(value) as avg_value
            FROM metrics
            WHERE metric_name = ? AND timestamp >= ?
        """
        params: list[Any] = [metric_name, cutoff]

        if labels:
            query += " AND labels = ?"
            params.append(json.dumps(labels))

        cursor = self._conn.execute(query, params)
        row = cursor.fetchone()

        if not row or row[0] == 0:
            return None

        count, min_val, max_val, avg_val = row

        # Calculate percentiles
        p50, p95, p99 = self._calculate_percentiles(metric_name, cutoff, labels)

        return MetricSummary(
            metric_name=metric_name,
            count=count,
            min_value=min_val or 0,
            max_value=max_val or 0,
            avg_value=avg_val or 0,
            p50_value=p50,
            p95_value=p95,
            p99_value=p99,
            time_range_hours=hours,
        )

    def _calculate_percentiles(
        self,
        metric_name: str,
        cutoff: float,
        labels: dict[str, str] | None = None,
    ) -> tuple[float, float, float]:
        """Calculate p50, p95, p99 percentiles."""
        if not self._conn:
            return 0.0, 0.0, 0.0

        query = """
            SELECT value FROM metrics
            WHERE metric_name = ? AND timestamp >= ?
            ORDER BY value
        """
        params: list[Any] = [metric_name, cutoff]

        if labels:
            query += " AND labels = ?"
            params.append(json.dumps(labels))

        cursor = self._conn.execute(query, params)
        values = [row[0] for row in cursor.fetchall()]

        if not values:
            return 0.0, 0.0, 0.0

        p50 = self._percentile(values, 50)
        p95 = self._percentile(values, 95)
        p99 = self._percentile(values, 99)

        return p50, p95, p99

    def _percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)

        # Linear interpolation
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = index - lower

        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    def get_metric_history(
        self,
        metric_name: str,
        hours: float = 24.0,
        labels: dict[str, str] | None = None,
        resolution: str = 'auto',
    ) -> list[dict[str, Any]]:
        """
        Get metric history with specified resolution.

        Args:
            metric_name: Name of the metric
            hours: Time range in hours
            labels: Optional labels to filter by
            resolution: 'raw', 'minute', 'hour', 'auto'

        Returns:
            List of {timestamp, value, labels} dicts
        """
        if not self._conn:
            return []

        cutoff = time.time() - (hours * 3600)

        # Determine resolution
        if resolution == 'auto':
            if hours <= 1:
                resolution = 'raw'
            elif hours <= 24:
                resolution = 'minute'
            else:
                resolution = 'hour'

        if resolution == 'raw':
            query = """
                SELECT timestamp, value, labels FROM metrics
                WHERE metric_name = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            """
        elif resolution == 'minute':
            query = """
                SELECT
                    (timestamp / 60) * 60 as minute_ts,
                    AVG(value) as avg_value,
                    labels
                FROM metrics
                WHERE metric_name = ? AND timestamp >= ?
                GROUP BY minute_ts, labels
                ORDER BY minute_ts ASC
            """
        else:  # hour
            query = """
                SELECT
                    (timestamp / 3600) * 3600 as hour_ts,
                    AVG(value) as avg_value,
                    labels
                FROM metrics
                WHERE metric_name = ? AND timestamp >= ?
                GROUP BY hour_ts, labels
                ORDER BY hour_ts ASC
            """

        params: list[Any] = [metric_name, cutoff]

        if labels:
            query += " AND labels = ?"
            params.append(json.dumps(labels))

        cursor = self._conn.execute(query, params)

        results = []
        for row in cursor.fetchall():
            if resolution == 'raw':
                timestamp, value, labels_json = row
            else:
                timestamp, value, labels_json = row

            results.append({
                'timestamp': timestamp,
                'value': value,
                'labels': json.loads(labels_json) if labels_json else {},
            })

        return results

    def get_trend(
        self,
        metric_name: str,
        hours: float = 24.0,
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze metric trend.

        Args:
            metric_name: Name of the metric
            hours: Time range in hours
            labels: Optional labels

        Returns:
            Dict with trend analysis:
            - direction: 'increasing', 'decreasing', 'stable'
            - change_percent: percentage change
            - slope: linear regression slope
        """
        history = self.get_metric_history(metric_name, hours, labels, resolution='hour')

        if len(history) < 2:
            return {
                'direction': 'unknown',
                'change_percent': 0.0,
                'slope': 0.0,
                'data_points': len(history),
            }

        # Calculate change
        first_value = history[0]['value']
        last_value = history[-1]['value']

        if first_value == 0:
            change_percent = 0.0
        else:
            change_percent = ((last_value - first_value) / first_value) * 100

        # Calculate slope (simple linear regression)
        n = len(history)
        sum_x = sum(i for i in range(n))
        sum_y = sum(point['value'] for point in history)
        sum_xy = sum(i * point['value'] for i, point in enumerate(history))
        sum_x2 = sum(i * i for i in range(n))

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            slope = 0.0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / denominator

        # Determine direction
        if abs(change_percent) < 5:
            direction = 'stable'
        elif change_percent > 0:
            direction = 'increasing'
        else:
            direction = 'decreasing'

        return {
            'direction': direction,
            'change_percent': change_percent,
            'slope': slope,
            'data_points': len(history),
            'first_value': first_value,
            'last_value': last_value,
        }

    def _cleanup_old_data(self) -> None:
        """Remove data older than retention period."""
        if not self._conn:
            return

        cutoff = time.time() - (self.retention_days * 86400)

        try:
            cursor = self._conn.execute(
                "DELETE FROM metrics WHERE timestamp < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount

            # Also cleanup hourly summaries
            self._conn.execute(
                "DELETE FROM metrics_hourly WHERE hour_timestamp < ?",
                (cutoff,)
            )

            self._conn.commit()

            if deleted > 0:
                log.info("Cleaned up %d old metric records", deleted)

        except sqlite3.Error as e:
            log.error("Failed to cleanup old metrics: %s", e)

    def cleanup_hourly_summaries(self) -> None:
        """Regenerate hourly summary table."""
        if not self._conn:
            return

        log.info("Regenerating hourly summaries...")

        # Clear existing summaries
        self._conn.execute("DELETE FROM metrics_hourly")

        # Regenerate from raw data
        self._conn.execute("""
            INSERT OR REPLACE INTO metrics_hourly
            (hour_timestamp, metric_name, min_value, max_value, avg_value, count)
            SELECT
                (timestamp / 3600) * 3600 as hour_ts,
                metric_name,
                MIN(value),
                MAX(value),
                AVG(value),
                COUNT(*)
            FROM metrics
            GROUP BY hour_ts, metric_name
        """)  # noqa: B007

        self._conn.commit()
        log.info("Hourly summaries regenerated")

    def export_to_json(
        self,
        metric_name: str,
        hours: float = 24.0,
        filepath: str | Path | None = None,
    ) -> str:
        """
        Export metric history to JSON.

        Args:
            metric_name: Name of the metric
            hours: Time range in hours
            filepath: Output file path. Default: ./{metric_name}_history.json

        Returns:
            Path to exported file
        """
        history = self.get_metric_history(metric_name, hours)
        summary = self.get_metric_summary(metric_name, hours)

        data = {
            'metric_name': metric_name,
            'time_range_hours': hours,
            'exported_at': datetime.now().isoformat(),
            'summary': {
                'count': summary.count if summary else 0,
                'min': summary.min_value if summary else 0,
                'max': summary.max_value if summary else 0,
                'avg': summary.avg_value if summary else 0,
                'p50': summary.p50_value if summary else 0,
                'p95': summary.p95_value if summary else 0,
                'p99': summary.p99_value if summary else 0,
            } if summary else None,
            'data': history,
        }

        if filepath is None:
            filepath = f"{metric_name}_history.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        log.info("Exported %s history to %s", metric_name, filepath)
        return str(filepath)

    def export_to_csv(
        self,
        metric_name: str,
        hours: float = 24.0,
        filepath: str | Path | None = None,
    ) -> str:
        """
        Export metric history to CSV.

        Args:
            metric_name: Name of the metric
            hours: Time range in hours
            filepath: Output file path

        Returns:
            Path to exported file
        """
        import csv

        history = self.get_metric_history(metric_name, hours)

        if filepath is None:
            filepath = f"{metric_name}_history.csv"

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'datetime', 'value', 'labels'])

            for point in history:
                dt = datetime.fromtimestamp(point['timestamp']).isoformat()
                writer.writerow([
                    point['timestamp'],
                    dt,
                    point['value'],
                    json.dumps(point['labels']),
                ])

        log.info("Exported %s history to CSV: %s", metric_name, filepath)
        return str(filepath)

    def get_recent_metrics(self, limit: int = 100) -> list[MetricPoint]:
        """Get most recent metrics from cache."""
        return self._recent_cache[-limit:]

    def get_prometheus_metrics(self) -> str:
        """
        Export recent metrics in Prometheus exposition format.

        Returns:
            Prometheus-formatted metrics string
        """
        output_lines = []

        # Header
        output_lines.append("# HELP tg_ws_proxy_metrics TG WS Proxy metrics")
        output_lines.append("# TYPE tg_ws_proxy_metrics untyped")

        # Get recent metrics from database (last 1000 points)
        now = time.time()
        hour_ago = now - 3600

        try:
            if not self._conn:
                return ""

            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT metric_name, value, labels, timestamp
                FROM metrics
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """, (hour_ago,))

            rows = cursor.fetchall()

            # Group by metric name
            metrics_by_name: dict[str, list] = {}
            for metric_name, value, labels_json, timestamp in rows:
                if metric_name not in metrics_by_name:
                    metrics_by_name[metric_name] = []
                metrics_by_name[metric_name].append({
                    'value': value,
                    'labels': json.loads(labels_json) if labels_json else {},
                    'timestamp': timestamp,
                })

            # Format each metric
            for metric_name, points in metrics_by_name.items():
                # Sanitize metric name for Prometheus
                prom_name = f"tg_ws_{metric_name.replace('rate_limiter_', '')}"
                prom_name = prom_name.replace('-', '_').replace('.', '_')

                # Add HELP
                output_lines.append(f"# HELP {prom_name} {metric_name.replace('_', ' ').title()}")

                # Determine type based on metric name
                if 'count' in metric_name or 'total' in metric_name:
                    output_lines.append(f"# TYPE {prom_name} counter")
                else:
                    output_lines.append(f"# TYPE {prom_name} gauge")

                # Add values with labels
                for point in points[:10]:  # Limit to last 10 values per metric
                    labels = point['labels']
                    value = point['value']

                    # Format labels
                    label_parts = []
                    for key, val in labels.items():
                        # Escape label values
                        escaped_val = str(val).replace('"', '\\"')
                        label_parts.append(f'{key}="{escaped_val}"')

                    labels_str = '{' + ','.join(label_parts) + '}' if label_parts else ''
                    timestamp_ms = int(point['timestamp'] * 1000)

                    output_lines.append(f"{prom_name}{labels_str} {value} {timestamp_ms}")

                output_lines.append("")  # Empty line between metrics

        except Exception as e:
            log.debug("Failed to export Prometheus metrics: %s", e)
            # Return at least header
            output_lines.append(f"# ERROR: {e}")

        return '\n'.join(output_lines)

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
        log.info("Metrics history closed")


# Global metrics history instance
_metrics_history: MetricsHistory | None = None


def get_metrics_history() -> MetricsHistory:
    """Get or create global metrics history instance."""
    global _metrics_history
    if _metrics_history is None:
        _metrics_history = MetricsHistory()
    return _metrics_history


def init_metrics_history(db_path: str | Path | None = None) -> MetricsHistory:
    """Initialize global metrics history."""
    global _metrics_history
    _metrics_history = MetricsHistory(db_path)
    return _metrics_history


__all__ = [
    'MetricsHistory',
    'MetricPoint',
    'MetricSummary',
    'get_metrics_history',
    'init_metrics_history',
]
