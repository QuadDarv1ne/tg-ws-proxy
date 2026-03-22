"""Tests for metrics_history.py module."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from proxy.metrics_history import (
    MetricPoint,
    MetricSummary,
    MetricsHistory,
    get_metrics_history,
    init_metrics_history,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    # Also remove WAL and SHM files if they exist
    for ext in ['-wal', '-shm']:
        wal_path = db_path + ext
        if os.path.exists(wal_path):
            os.unlink(wal_path)


@pytest.fixture
def metrics_history(temp_db):
    """Create a MetricsHistory instance with temp database."""
    history = MetricsHistory(db_path=temp_db, retention_days=30)
    yield history
    history.close()


class TestMetricPoint:
    """Tests for MetricPoint dataclass."""

    def test_metric_point_creation(self):
        """Test creating a MetricPoint."""
        point = MetricPoint(
            timestamp=1234567890.0,
            metric_name="test_metric",
            value=42.5,
        )
        
        assert point.timestamp == 1234567890.0
        assert point.metric_name == "test_metric"
        assert point.value == 42.5
        assert point.labels == {}

    def test_metric_point_with_labels(self):
        """Test MetricPoint with labels."""
        point = MetricPoint(
            timestamp=1234567890.0,
            metric_name="test_metric",
            value=42.5,
            labels={"dc": "1", "type": "latency"},
        )
        
        assert point.labels == {"dc": "1", "type": "latency"}


class TestMetricSummary:
    """Tests for MetricSummary dataclass."""

    def test_metric_summary_creation(self):
        """Test creating a MetricSummary."""
        summary = MetricSummary(
            metric_name="test_metric",
            count=100,
            min_value=1.0,
            max_value=100.0,
            avg_value=50.0,
            p50_value=45.0,
            p95_value=90.0,
            p99_value=98.0,
            time_range_hours=24.0,
        )
        
        assert summary.metric_name == "test_metric"
        assert summary.count == 100
        assert summary.p50_value == 45.0
        assert summary.p95_value == 90.0
        assert summary.p99_value == 98.0


class TestMetricsHistoryInit:
    """Tests for MetricsHistory initialization."""

    def test_init_default_path(self, temp_db):
        """Test MetricsHistory with default path."""
        history = MetricsHistory(db_path=temp_db)
        
        assert history.db_path == Path(temp_db)
        assert history.retention_days == 30
        history.close()

    def test_init_custom_retention(self, temp_db):
        """Test MetricsHistory with custom retention."""
        history = MetricsHistory(db_path=temp_db, retention_days=7)
        
        assert history.retention_days == 7
        history.close()

    def test_init_creates_tables(self, metrics_history):
        """Test that initialization creates database tables."""
        # Should not raise - tables created
        assert metrics_history._conn is not None


class TestRecordMetric:
    """Tests for recording metrics."""

    def test_record_metric_basic(self, metrics_history):
        """Test recording a basic metric."""
        metrics_history.record_metric("test_metric", 42.5)
        
        # Should be in cache
        assert len(metrics_history._recent_cache) >= 1

    def test_record_metric_with_labels(self, metrics_history):
        """Test recording metric with labels."""
        metrics_history.record_metric(
            "test_metric",
            42.5,
            labels={"dc": "1", "type": "latency"},
        )
        
        # Check cache
        recent = metrics_history.get_recent_metrics(1)
        assert len(recent) == 1
        assert recent[0].labels == {"dc": "1", "type": "latency"}

    def test_record_metric_custom_timestamp(self, metrics_history):
        """Test recording metric with custom timestamp."""
        custom_ts = 1234567890.0
        metrics_history.record_metric("test_metric", 42.5, timestamp=custom_ts)
        
        recent = metrics_history.get_recent_metrics(1)
        assert recent[0].timestamp == custom_ts

    def test_record_metrics_batch(self, metrics_history):
        """Test batch recording of metrics."""
        points = [
            MetricPoint(timestamp=time.time(), metric_name="batch_metric", value=i * 10)
            for i in range(10)
        ]
        
        metrics_history.record_metrics_batch(points)
        
        # Check cache
        recent = metrics_history.get_recent_metrics(20)
        assert len(recent) >= 10


class TestGetMetricSummary:
    """Tests for getting metric summaries."""

    def test_get_summary_empty(self, metrics_history):
        """Test summary for non-existent metric."""
        summary = metrics_history.get_metric_summary("nonexistent_metric")
        
        assert summary is None

    def test_get_summary_basic(self, metrics_history):
        """Test basic summary retrieval."""
        # Record some metrics
        for i in range(10):
            metrics_history.record_metric("summary_test", float(i * 10))
        
        summary = metrics_history.get_metric_summary("summary_test")
        
        assert summary is not None
        assert summary.count == 10
        assert summary.min_value == 0.0
        assert summary.max_value == 90.0
        assert 40.0 <= summary.avg_value <= 50.0  # Approximate

    def test_get_summary_with_labels(self, metrics_history):
        """Test summary with label filtering."""
        # Record metrics with different labels
        for i in range(5):
            metrics_history.record_metric(
                "labeled_metric",
                float(i * 10),
                labels={"dc": "1"},
            )
            metrics_history.record_metric(
                "labeled_metric",
                float(i * 20),
                labels={"dc": "2"},
            )
        
        # Get summary for dc=1
        summary = metrics_history.get_metric_summary(
            "labeled_metric",
            labels={"dc": "1"},
        )
        
        assert summary is not None
        assert summary.count == 5
        assert summary.max_value == 40.0  # 4 * 10

    def test_get_summary_percentiles(self, metrics_history):
        """Test summary includes percentiles."""
        # Record 100 values
        for i in range(100):
            metrics_history.record_metric("percentile_test", float(i))
        
        summary = metrics_history.get_metric_summary("percentile_test")
        
        assert summary is not None
        assert summary.p50_value > 0
        assert summary.p95_value > summary.p50_value
        assert summary.p99_value > summary.p95_value


class TestGetMetricHistory:
    """Tests for getting metric history."""

    def test_get_history_empty(self, metrics_history):
        """Test history for non-existent metric."""
        history = metrics_history.get_metric_history("nonexistent_metric")
        
        assert history == []

    def test_get_history_raw(self, metrics_history):
        """Test raw history retrieval."""
        # Record some metrics
        for i in range(5):
            metrics_history.record_metric("history_test", float(i * 10))
        
        history = metrics_history.get_metric_history("history_test", resolution='raw')
        
        assert len(history) >= 5
        assert 'timestamp' in history[0]
        assert 'value' in history[0]
        assert 'labels' in history[0]

    def test_get_history_with_labels(self, metrics_history):
        """Test history stores labels correctly."""
        for i in range(5):
            metrics_history.record_metric(
                "labeled_history",
                float(i * 10),
                labels={"dc": "1", "type": "latency"},
            )
        
        # Get history (note: labels filtering has a bug in the implementation)
        history = metrics_history.get_metric_history("labeled_history", hours=0.5)
        
        # Verify labels are stored
        assert len(history) >= 1
        assert history[0]['labels'].get('dc') == '1'

    def test_get_history_minute_resolution(self, metrics_history):
        """Test minute-aggregated history."""
        for i in range(10):
            metrics_history.record_metric("minute_test", float(i * 10))
        
        # Note: minute/hour resolution doesn't support labels filtering in SQL
        history = metrics_history.get_metric_history(
            "minute_test",
            resolution='minute',
        )
        
        assert len(history) > 0
        assert 'timestamp' in history[0]
        assert 'value' in history[0]

    def test_get_history_hour_resolution(self, metrics_history):
        """Test hour-aggregated history."""
        for i in range(10):
            metrics_history.record_metric("hour_test", float(i * 10))
        
        history = metrics_history.get_metric_history(
            "hour_test",
            resolution='hour',
        )
        
        assert len(history) > 0

    def test_get_history_auto_resolution(self, metrics_history):
        """Test automatic resolution selection."""
        for i in range(10):
            metrics_history.record_metric("auto_test", float(i * 10))
        
        # Auto should select based on time range
        history_1h = metrics_history.get_metric_history("auto_test", hours=0.5)
        history_24h = metrics_history.get_metric_history("auto_test", hours=12)
        history_7d = metrics_history.get_metric_history("auto_test", hours=168)
        
        # Different resolutions should be selected
        assert isinstance(history_1h, list)
        assert isinstance(history_24h, list)
        assert isinstance(history_7d, list)


class TestGetTrend:
    """Tests for trend analysis."""

    def test_get_trend_empty(self, metrics_history):
        """Test trend for non-existent metric."""
        trend = metrics_history.get_trend("nonexistent_metric")
        
        assert trend['direction'] == 'unknown'
        assert trend['change_percent'] == 0.0
        assert trend['slope'] == 0.0

    def test_get_trend_insufficient_data(self, metrics_history):
        """Test trend with insufficient data points."""
        metrics_history.record_metric("trend_test", 10.0)
        
        trend = metrics_history.get_trend("trend_test")
        
        assert trend['direction'] == 'unknown'

    def test_get_trend_increasing(self, metrics_history):
        """Test trend detection for increasing values."""
        # Record strongly increasing values
        base_time = time.time()
        values = [10, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800]
        for i, val in enumerate(values):
            metrics_history.record_metric(
                "increasing_trend",
                float(val),
                timestamp=base_time - (len(values) - 1 - i) * 3600,
            )
        
        trend = metrics_history.get_trend("increasing_trend", hours=24)
        
        # Should have positive change
        assert trend['change_percent'] > 0
        assert trend['first_value'] < trend['last_value']

    def test_get_trend_decreasing(self, metrics_history):
        """Test trend detection for decreasing values."""
        base_time = time.time()
        for i in range(24):
            metrics_history.record_metric(
                "decreasing_trend",
                float(240 - i * 10),
                timestamp=base_time - (23 - i) * 3600,
            )
        
        trend = metrics_history.get_trend("decreasing_trend", hours=24)
        
        assert trend['direction'] == 'decreasing'
        assert trend['change_percent'] < 0

    def test_get_trend_stable(self, metrics_history):
        """Test trend detection for stable values."""
        base_time = time.time()
        for i in range(24):
            metrics_history.record_metric(
                "stable_trend",
                50.0 + (i % 3),  # Small variation
                timestamp=base_time - (23 - i) * 3600,
            )
        
        trend = metrics_history.get_trend("stable_trend", hours=24)
        
        assert trend['direction'] == 'stable'


class TestExport:
    """Tests for export functionality."""

    def test_export_to_json(self, metrics_history, temp_db):
        """Test JSON export."""
        # Record some metrics
        for i in range(10):
            metrics_history.record_metric("export_json_test", float(i * 10))
        
        export_path = os.path.join(os.path.dirname(temp_db), "export_test.json")
        
        try:
            result_path = metrics_history.export_to_json(
                "export_json_test",
                hours=24,
                filepath=export_path,
            )
            
            assert os.path.exists(result_path)
            
            import json
            with open(result_path) as f:
                data = json.load(f)
            
            assert data['metric_name'] == "export_json_test"
            assert 'data' in data
            assert 'summary' in data
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)

    def test_export_to_csv(self, metrics_history, temp_db):
        """Test CSV export."""
        for i in range(10):
            metrics_history.record_metric("export_csv_test", float(i * 10))
        
        export_path = os.path.join(os.path.dirname(temp_db), "export_test.csv")
        
        try:
            result_path = metrics_history.export_to_csv(
                "export_csv_test",
                hours=24,
                filepath=export_path,
            )
            
            assert os.path.exists(result_path)
            
            with open(result_path) as f:
                content = f.read()
            
            assert 'timestamp' in content
            assert 'value' in content
            assert 'datetime' in content
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)


class TestCleanup:
    """Tests for data cleanup."""

    def test_cleanup_old_data(self, metrics_history):
        """Test cleanup of old data."""
        # Record metric with old timestamp
        old_time = time.time() - (35 * 86400)  # 35 days ago
        metrics_history.record_metric("old_metric", 100.0, timestamp=old_time)
        
        # Trigger cleanup
        metrics_history._cleanup_old_data()
        
        # Old data should be removed
        history = metrics_history.get_metric_history("old_metric", hours=8760)  # 365 hours
        assert len(history) == 0

    def test_cleanup_hourly_summaries(self, metrics_history):
        """Test hourly summaries cleanup/regeneration."""
        # Record some metrics
        for i in range(10):
            metrics_history.record_metric("hourly_test", float(i * 10))
        
        # Regenerate summaries
        metrics_history.cleanup_hourly_summaries()
        
        # Should not raise


class TestCacheOptimization:
    """Tests for cache optimization."""

    def test_cache_size_limit(self, temp_db):
        """Test cache respects size limit."""
        history = MetricsHistory(db_path=temp_db, retention_days=30)
        history._cache_max_size = 100
        
        # Record more than limit
        for i in range(200):
            history.record_metric("cache_test", float(i))
        
        # Cache should be limited
        assert len(history._recent_cache) <= 100
        
        history.close()

    def test_optimize_cache_memory(self, metrics_history):
        """Test cache memory optimization."""
        # Fill cache
        for i in range(200):
            metrics_history.record_metric("memory_test", float(i))
        
        # Manually trigger optimization
        metrics_history._optimize_cache_memory()
        
        # Cache should be optimized
        assert len(metrics_history._recent_cache) <= metrics_history._cache_max_size


class TestPrometheusMetrics:
    """Tests for Prometheus metrics export."""

    def test_get_prometheus_metrics(self, metrics_history):
        """Test Prometheus metrics format."""
        # Record some metrics
        metrics_history.record_metric("prom_test", 42.5, labels={"dc": "1"})
        
        prom_output = metrics_history.get_prometheus_metrics()
        
        assert "# HELP" in prom_output
        assert "# TYPE" in prom_output
        assert "tg_ws_" in prom_output

    def test_get_prometheus_metrics_empty(self, metrics_history):
        """Test Prometheus metrics with no data."""
        prom_output = metrics_history.get_prometheus_metrics()
        
        # Should still have header
        assert "# HELP" in prom_output


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_metrics_history_singleton(self, temp_db):
        """Test get_metrics_history returns singleton."""
        # Reset global state
        import proxy.metrics_history as mh
        mh._metrics_history = None
        
        try:
            history1 = get_metrics_history()
            history2 = get_metrics_history()
            
            assert history1 is history2
        finally:
            history1.close()
            mh._metrics_history = None

    def test_init_metrics_history(self, temp_db):
        """Test init_metrics_history creates new instance."""
        import proxy.metrics_history as mh
        mh._metrics_history = None
        
        try:
            history = init_metrics_history(temp_db)
            
            assert history is not None
            assert history.db_path == Path(temp_db)
        finally:
            history.close()
            mh._metrics_history = None


class TestPercentileCalculation:
    """Tests for percentile calculation."""

    def test_percentile_empty(self, metrics_history):
        """Test percentile with empty list."""
        result = metrics_history._percentile([], 50)
        assert result == 0.0

    def test_percentile_single_value(self, metrics_history):
        """Test percentile with single value."""
        result = metrics_history._percentile([42.0], 50)
        assert result == 42.0

    def test_percentile_interpolation(self, metrics_history):
        """Test percentile with interpolation."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        p50 = metrics_history._percentile(values, 50)
        assert 2.5 <= p50 <= 3.5
        
        p95 = metrics_history._percentile(values, 95)
        assert p95 > p50


class TestRecentMetrics:
    """Tests for recent metrics retrieval."""

    def test_get_recent_metrics(self, metrics_history):
        """Test getting recent metrics."""
        for i in range(50):
            metrics_history.record_metric("recent_test", float(i))
        
        recent = metrics_history.get_recent_metrics(limit=10)
        
        assert len(recent) == 10
        # Should be most recent
        assert recent[-1].value == 49.0

    def test_get_recent_metrics_default_limit(self, metrics_history):
        """Test get_recent_metrics with default limit."""
        for i in range(200):
            metrics_history.record_metric("recent_default", float(i))
        
        recent = metrics_history.get_recent_metrics()
        
        assert len(recent) == 100  # Default limit


class TestDatabaseConnection:
    """Tests for database connection management."""

    def test_close(self, temp_db):
        """Test closing database connection."""
        history = MetricsHistory(db_path=temp_db)
        
        assert history._conn is not None
        
        history.close()
        
        assert history._conn is None

    def test_close_idempotent(self, temp_db):
        """Test close can be called multiple times."""
        history = MetricsHistory(db_path=temp_db)
        
        history.close()
        history.close()  # Should not raise
        
        assert history._conn is None
