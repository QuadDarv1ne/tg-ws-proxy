"""
Proxy statistics tracking module.

Provides Stats class for tracking proxy connections, traffic, and performance metrics.
"""

from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional, Tuple

import psutil


def _human_bytes(n: int) -> str:
    """Convert bytes to human-readable format."""
    if n < 0:
        return f"-{_human_bytes(-n)}"
    if n < 1024:
        return f"{n}B"
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

    def __init__(self, history_size: int = 100) -> None:
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
        self.dc_stats: Dict[int, Dict[str, int]] = {}  # dc_id -> {connections, errors}
        self._current_dc: Optional[int] = None

        # Latency tracking (last ping per DC)
        self.latency_ms: Dict[int, float] = {}  # dc_id -> latency in ms
        self._latency_history: Dict[int, List[float]] = {}  # dc_id -> [latencies]

        # Session tracking
        self.session_start = time.monotonic()
        self.last_connection_time: Optional[float] = None
        self.peak_connections_per_minute = 0

        # Performance monitoring
        self._process = psutil.Process(os.getpid())
        self.cpu_percent = 0.0
        self.memory_bytes = 0
        self._last_cpu_update = 0.0
        self._cpu_history: List[float] = []
        self._memory_history: List[int] = []

        # History tracking (last N events)
        self._history_size = history_size
        self.connection_history: List[dict] = []
        self.traffic_history: List[dict] = []
        self._last_traffic_snapshot = (0, 0)
        self._traffic_snapshot_time = time.monotonic()

    def add_connection(self, conn_type: str, dc: Optional[int] = None) -> None:
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

    def add_ws_error(self, dc: Optional[int] = None) -> None:
        """Record a WebSocket error."""
        self.ws_errors += 1
        if dc is not None and dc in self.dc_stats:
            self.dc_stats[dc]['errors'] += 1

    def record_latency(self, dc: int, latency_ms: float) -> None:
        """Record latency measurement for a DC."""
        self.latency_ms[dc] = latency_ms
        if dc not in self._latency_history:
            self._latency_history[dc] = []
        self._latency_history[dc].append(latency_ms)
        if len(self._latency_history[dc]) > 60:  # Keep last 60 measurements
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

    def get_average_cpu(self) -> Optional[float]:
        """Get average CPU usage over the last minute."""
        if not self._cpu_history:
            return None
        return sum(self._cpu_history) / len(self._cpu_history)

    def get_average_memory(self) -> Optional[int]:
        """Get average memory usage over the last minute."""
        if not self._memory_history:
            return None
        return int(sum(self._memory_history) / len(self._memory_history))

    def get_performance_stats(self) -> Dict:
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

    def get_average_latency(self, dc: int) -> Optional[float]:
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

    def get_traffic_per_minute(self) -> Tuple[int, int]:
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

    def get_traffic_history(self, limit: int = 60) -> List[Dict]:
        """Get traffic history for chart rendering."""
        if not self.traffic_history:
            return []
        return self.traffic_history[-limit:]

    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return time.monotonic() - self.session_start

    def get_best_dc(self) -> Optional[int]:
        """Get DC with lowest average latency."""
        if not self.latency_ms:
            return None
        return min(self.latency_ms, key=self.latency_ms.get)

    def get_dc_stats(self) -> Dict[int, Dict]:
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

    def export_to_json(self) -> str:
        """Export statistics to JSON format."""
        data = self.to_dict()
        data['session_duration_seconds'] = self.get_session_duration()
        data['peak_connections_per_minute'] = self.peak_connections_per_minute
        data['dc_stats'] = self.get_dc_stats()
        return json.dumps(data, indent=2, default=str)

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
        }
