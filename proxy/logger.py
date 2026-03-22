"""
Enhanced Logging Module for TG WS Proxy.

Provides advanced logging features:
- Structured JSON logging
- Log rotation
- Multiple log levels
- Log export to file
- Performance logging

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'stack_info', 'exc_info', 'thread', 'threadName'):
                try:
                    json.dumps(value)  # Check if serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter."""

    COLORS = {
        logging.DEBUG: '\033[36m',     # Cyan
        logging.INFO: '\033[32m',      # Green
        logging.WARNING: '\033[33m',   # Yellow
        logging.ERROR: '\033[31m',     # Red
        logging.CRITICAL: '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class PerformanceLogger:
    """Logger for performance metrics."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._timers: dict[str, float] = {}
        self._metrics: list[dict[str, Any]] = []

    def start_timer(self, name: str) -> None:
        """Start a performance timer."""
        self._timers[name] = time.perf_counter()

    def stop_timer(self, name: str, log_level: int = logging.DEBUG) -> float | None:
        """Stop timer and log elapsed time."""
        if name not in self._timers:
            return None

        elapsed = time.perf_counter() - self._timers.pop(name)
        self._logger.log(
            log_level,
            "Performance: %s took %.3fs",
            name,
            elapsed
        )
        self._metrics.append({
            'operation': name,
            'duration_ms': elapsed * 1000,
            'timestamp': time.time()
        })
        return elapsed

    def get_average_duration(self, operation: str) -> float | None:
        """Get average duration for an operation."""
        matching = [m for m in self._metrics if m['operation'] == operation]
        if not matching:
            return None
        return sum(m['duration_ms'] for m in matching) / len(matching)

    def get_metrics(self) -> list[dict[str, Any]]:
        """Get all performance metrics."""
        return self._metrics.copy()


class EnhancedLogger:
    """Enhanced logger with advanced features."""

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        log_dir: str | None = None,
        enable_json: bool = False,
        enable_rotation: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        console_output: bool = True,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers.clear()

        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)

            if enable_json:
                console_handler.setFormatter(JsonFormatter())
            else:
                console_handler.setFormatter(ColoredFormatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))

            self.logger.addHandler(console_handler)

        # File handler
        if log_dir:
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)

            log_file = log_path / f"{name}.log"

            if enable_rotation:
                file_handler: RotatingFileHandler | logging.FileHandler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
            else:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')

            file_handler.setLevel(level)
            file_handler.setFormatter(
                JsonFormatter() if enable_json else logging.Formatter(
                    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
            self.logger.addHandler(file_handler)

        self.perf = PerformanceLogger(self.logger)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, extra=kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg, extra=kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self.logger.critical(msg, extra=kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        self.logger.exception(msg, extra=kwargs)

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        details: dict[str, Any] | None = None
    ) -> None:
        """Log performance metric."""
        msg = f"Performance: {operation} - {duration_ms:.2f}ms"
        if details:
            self.info(msg, **details)
        else:
            self.info(msg)

    def export_logs(
        self,
        output_path: str,
        level: int | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> int:
        """Export logs to a file.

        Returns number of exported log entries.
        """
        # This would require reading from file handlers
        # For now, export performance metrics
        metrics = self.perf.get_metrics()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'exported_at': datetime.utcnow().isoformat() + 'Z',
                'logger': self.logger.name,
                'metrics': metrics,
            }, f, indent=2, ensure_ascii=False)

        return len(metrics)


# Global loggers registry
_loggers: dict[str, EnhancedLogger] = {}


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_dir: str | None = None,
    enable_json: bool = False,
) -> EnhancedLogger:
    """Get or create enhanced logger."""
    if name not in _loggers:
        _loggers[name] = EnhancedLogger(
            name,
            level=level,
            log_dir=log_dir,
            enable_json=enable_json,
        )
    return _loggers[name]


def setup_logging(
    level: int = logging.INFO,
    log_dir: str | None = None,
    enable_json: bool = False,
    enable_file_logging: bool = True,
) -> None:
    """Setup global logging configuration."""
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(console_handler)

    # File handler
    if log_dir and enable_file_logging:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Daily rotation
        file_handler = TimedRotatingFileHandler(
            log_path / 'tg-ws-proxy.log',
            when='D',
            interval=1,
            backupCount=7,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(
            JsonFormatter() if enable_json else logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
        root_logger.addHandler(file_handler)


__all__ = [
    'EnhancedLogger',
    'JsonFormatter',
    'ColoredFormatter',
    'PerformanceLogger',
    'get_logger',
    'setup_logging',
]
