"""Tests for logger.py module."""

from __future__ import annotations

import json
import logging

from proxy.logger import (
    ColoredFormatter,
    EnhancedLogger,
    JsonFormatter,
    PerformanceLogger,
    get_logger,
)


class TestJsonFormatter:
    """Tests for JsonFormatter class."""

    def test_json_formatter_format(self):
        """Test JsonFormatter formats as JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should be valid JSON
        data = json.loads(result)
        assert data['level'] == 'INFO'
        assert data['message'] == 'Test message'
        assert data['logger'] == 'test'


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_colored_formatter_format(self):
        """Test ColoredFormatter adds color codes."""
        formatter = ColoredFormatter('%(levelname)s: %(message)s')
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should contain color codes
        assert '\033[' in result


class TestPerformanceLogger:
    """Tests for PerformanceLogger class."""

    def test_performance_logger_start_timer(self):
        """Test start_timer method."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        perf_logger.start_timer('operation1')

        assert 'operation1' in perf_logger._timers

    def test_performance_logger_stop_timer(self):
        """Test stop_timer method."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        perf_logger.start_timer('operation1')
        import time
        time.sleep(0.01)
        elapsed = perf_logger.stop_timer('operation1')

        assert elapsed is not None
        assert elapsed >= 0.01
        assert len(perf_logger._metrics) == 1

    def test_performance_logger_stop_timer_missing(self):
        """Test stop_timer for missing timer."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        elapsed = perf_logger.stop_timer('nonexistent')

        assert elapsed is None

    def test_performance_logger_get_average_duration(self):
        """Test get_average_duration method."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        perf_logger._metrics = [
            {'operation': 'op1', 'duration_ms': 10.0},
            {'operation': 'op1', 'duration_ms': 20.0},
        ]

        avg = perf_logger.get_average_duration('op1')

        assert avg == 15.0

    def test_performance_logger_get_average_duration_missing(self):
        """Test get_average_duration for missing operation."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        avg = perf_logger.get_average_duration('nonexistent')

        assert avg is None

    def test_performance_logger_get_metrics(self):
        """Test get_metrics method."""
        logger = logging.getLogger('test_perf')
        perf_logger = PerformanceLogger(logger)

        perf_logger._metrics = [{'operation': 'op1', 'duration_ms': 10.0}]

        metrics = perf_logger.get_metrics()

        assert len(metrics) == 1


class TestEnhancedLogger:
    """Tests for EnhancedLogger class."""

    def test_enhanced_logger_init(self, tmp_path):
        """Test EnhancedLogger initialization."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        assert logger.logger.name == 'test'
        assert len(logger.logger.handlers) >= 1

    def test_enhanced_logger_debug(self, tmp_path):
        """Test debug method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.debug('Debug message')

    def test_enhanced_logger_info(self, tmp_path):
        """Test info method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.info('Info message')

    def test_enhanced_logger_warning(self, tmp_path):
        """Test warning method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.warning('Warning message')

    def test_enhanced_logger_error(self, tmp_path):
        """Test error method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.error('Error message')

    def test_enhanced_logger_critical(self, tmp_path):
        """Test critical method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.critical('Critical message')

    def test_enhanced_logger_exception(self, tmp_path):
        """Test exception method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        try:
            raise ValueError('Test error')
        except ValueError:
            logger.exception('Exception occurred')

    def test_enhanced_logger_log_performance(self, tmp_path):
        """Test log_performance method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        # Should not raise
        logger.log_performance('operation', 100.5)

    def test_enhanced_logger_export_logs(self, tmp_path):
        """Test export_logs method."""
        logger = EnhancedLogger('test', log_dir=str(tmp_path))

        output_path = str(tmp_path / 'metrics.json')
        count = logger.export_logs(output_path)

        assert count >= 0


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_singleton(self):
        """Test get_logger returns singleton."""
        logger1 = get_logger('test_singleton')
        logger2 = get_logger('test_singleton')

        assert logger1 is logger2

    def test_get_logger_creates_new(self):
        """Test get_logger creates new instance for different names."""
        logger1 = get_logger('test1')
        logger2 = get_logger('test2')

        assert logger1 is not logger2
