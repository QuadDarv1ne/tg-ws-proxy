"""Tests for logger.py module."""

from __future__ import annotations

import json
import logging
import os
import time

import pytest

from proxy.logger import (
    ColoredFormatter,
    EnhancedLogger,
    JsonFormatter,
    PerformanceLogger,
    get_logger,
)


def close_logger_handlers(logger: logging.Logger):
    """Explicitly close all handlers to avoid Windows PermissionError."""
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


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
        logger = logging.getLogger('test_perf_1')
        perf_logger = PerformanceLogger(logger)

        perf_logger.start_timer('operation1')

        assert 'operation1' in perf_logger._timers

    def test_performance_logger_stop_timer(self):
        """Test stop_timer method."""
        logger = logging.getLogger('test_perf_2')
        perf_logger = PerformanceLogger(logger)

        perf_logger.start_timer('operation1')
        time.sleep(0.01)
        elapsed = perf_logger.stop_timer('operation1')

        assert elapsed is not None
        assert elapsed >= 0.01
        assert len(perf_logger._metrics) == 1

    def test_performance_logger_stop_timer_missing(self):
        """Test stop_timer for missing timer."""
        logger = logging.getLogger('test_perf_3')
        perf_logger = PerformanceLogger(logger)

        elapsed = perf_logger.stop_timer('nonexistent')

        assert elapsed is None

    def test_performance_logger_get_average_duration(self):
        """Test get_average_duration method."""
        logger = logging.getLogger('test_perf_4')
        perf_logger = PerformanceLogger(logger)

        perf_logger._metrics = [
            {'operation': 'op1', 'duration_ms': 10.0},
            {'operation': 'op1', 'duration_ms': 20.0},
        ]

        avg = perf_logger.get_average_duration('op1')

        assert avg == 15.0

    def test_performance_logger_get_average_duration_missing(self):
        """Test get_average_duration for missing operation."""
        logger = logging.getLogger('test_perf_5')
        perf_logger = PerformanceLogger(logger)

        avg = perf_logger.get_average_duration('nonexistent')

        assert avg is None

    def test_performance_logger_get_metrics(self):
        """Test get_metrics method."""
        logger = logging.getLogger('test_perf_6')
        perf_logger = PerformanceLogger(logger)

        perf_logger._metrics = [{'operation': 'op1', 'duration_ms': 10.0}]

        metrics = perf_logger.get_metrics()

        assert len(metrics) == 1


class TestEnhancedLogger:
    """Tests for EnhancedLogger class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Cleanup loggers after each test to free file handles."""
        yield
        # Logic to clear loggers created during tests
        from proxy.logger import _loggers
        for name in list(_loggers.keys()):
            enhanced = _loggers.pop(name)
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_init(self, tmp_path):
        """Test EnhancedLogger initialization."""
        log_dir = tmp_path / "logs"
        logger_name = f"test_init_{time.time()}"
        enhanced = EnhancedLogger(logger_name, log_dir=str(log_dir))

        try:
            assert enhanced.logger.name == logger_name
            assert len(enhanced.logger.handlers) >= 1
            log_file = log_dir / f"{logger_name}.log"
            assert log_file.exists()
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_debug(self, tmp_path):
        """Test debug method."""
        enhanced = EnhancedLogger('test_debug', log_dir=str(tmp_path))
        try:
            enhanced.debug('Debug message')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_info(self, tmp_path):
        """Test info method."""
        enhanced = EnhancedLogger('test_info', log_dir=str(tmp_path))
        try:
            enhanced.info('Info message')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_warning(self, tmp_path):
        """Test warning method."""
        enhanced = EnhancedLogger('test_warning', log_dir=str(tmp_path))
        try:
            enhanced.warning('Warning message')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_error(self, tmp_path):
        """Test error method."""
        enhanced = EnhancedLogger('test_error', log_dir=str(tmp_path))
        try:
            enhanced.error('Error message')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_critical(self, tmp_path):
        """Test critical method."""
        enhanced = EnhancedLogger('test_critical', log_dir=str(tmp_path))
        try:
            enhanced.critical('Critical message')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_exception(self, tmp_path):
        """Test exception method."""
        enhanced = EnhancedLogger('test_exception', log_dir=str(tmp_path))
        try:
            try:
                raise ValueError('Test error')
            except ValueError:
                enhanced.exception('Exception occurred')
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_log_performance(self, tmp_path):
        """Test log_performance method."""
        enhanced = EnhancedLogger('test_perf_log', log_dir=str(tmp_path))
        try:
            enhanced.log_performance('operation', 100.5)
        finally:
            close_logger_handlers(enhanced.logger)

    def test_enhanced_logger_export_logs(self, tmp_path):
        """Test export_logs method."""
        enhanced = EnhancedLogger('test_export', log_dir=str(tmp_path))
        try:
            output_path = str(tmp_path / 'metrics.json')
            count = enhanced.export_logs(output_path)
            assert count >= 0
            assert os.path.exists(output_path)
        finally:
            close_logger_handlers(enhanced.logger)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_singleton(self, tmp_path):
        """Test get_logger returns singleton."""
        name = f"singleton_{time.time()}"
        logger1 = get_logger(name, log_dir=str(tmp_path))
        logger2 = get_logger(name, log_dir=str(tmp_path))

        assert logger1 is logger2
        # Cleanup is handled by setup_teardown fixture

    def test_get_logger_creates_new(self, tmp_path):
        """Test get_logger creates new instance for different names."""
        logger1 = get_logger('test1', log_dir=str(tmp_path))
        logger2 = get_logger('test2', log_dir=str(tmp_path))

        assert logger1 is not logger2
        # Cleanup is handled by setup_teardown fixture
