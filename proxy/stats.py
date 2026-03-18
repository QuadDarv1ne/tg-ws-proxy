"""
Proxy statistics tracking module.

Provides Stats class for tracking proxy connections, traffic, and performance metrics.
"""

from __future__ import annotations

import time
from typing import Dict, List, Tuple


def _human_bytes(n: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


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

        # History tracking (last N events)
        self._history_size = history_size
        self.connection_history: List[dict] = []  # [{time, type, dc}, ...]
        self.traffic_history: List[dict] = []  # [{time, bytes_up, bytes_down}, ...]
        self._last_traffic_snapshot = (0, 0)

    def add_connection(self, conn_type: str, dc: int = None) -> None:
        """Record a new connection in history."""
        self.connections_total += 1
        if conn_type == 'ws':
            self.connections_ws += 1
        elif conn_type == 'tcp_fallback':
            self.connections_tcp_fallback += 1
        elif conn_type == 'http_rejected':
            self.connections_http_rejected += 1
        elif conn_type == 'passthrough':
            self.connections_passthrough += 1

        self.connection_history.append({
            'time': time.time(),
            'type': conn_type,
            'dc': dc
        })
        if len(self.connection_history) > self._history_size:
            self.connection_history.pop(0)

    def add_bytes(self, up: int = 0, down: int = 0) -> None:
        """Record traffic update."""
        self.bytes_up += up
        self.bytes_down += down

    def add_ws_error(self) -> None:
        """Record a WebSocket error."""
        self.ws_errors += 1

    def get_connections_per_minute(self) -> float:
        """Calculate connections per minute from history."""
        if not self.connection_history:
            return 0.0
        now = time.time()
        minute_ago = now - 60
        recent = [c for c in self.connection_history if c['time'] > minute_ago]
        return len(recent)

    def get_traffic_per_minute(self) -> Tuple[int, int]:
        """Calculate bytes per minute (up, down) from history."""
        if not self.traffic_history:
            return (0, 0)
        now = time.time()
        minute_ago = now - 60
        recent = [t for t in self.traffic_history if t['time'] > minute_ago]
        if not recent:
            return (0, 0)
        up = sum(t['bytes_up'] for t in recent)
        down = sum(t['bytes_down'] for t in recent)
        return (up, down)

    def summary(self) -> str:
        """Return human-readable stats summary."""
        return (f"total={self.connections_total} ws={self.connections_ws} "
                f"tcp_fb={self.connections_tcp_fallback} "
                f"http_skip={self.connections_http_rejected} "
                f"pass={self.connections_passthrough} "
                f"err={self.ws_errors} "
                f"pool={self.pool_hits}/{self.pool_hits+self.pool_misses} "
                f"up={_human_bytes(self.bytes_up)} "
                f"down={_human_bytes(self.bytes_down)}")

    def to_dict(self) -> dict:
        """Return stats as a dictionary."""
        conn_per_min = self.get_connections_per_minute()
        traffic_per_min = self.get_traffic_per_minute()
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
            "traffic_up_per_minute": traffic_per_min[0],
            "traffic_down_per_minute": traffic_per_min[1],
            "connection_history": self.connection_history[-10:],  # Last 10
        }
