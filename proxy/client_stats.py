"""
Client Statistics Module for TG WS Proxy.

Provides detailed per-client statistics:
- Connection tracking
- Traffic accounting
- Session duration
- Geographic data
- Client fingerprinting

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-client-stats')


class ClientType(Enum):
    """Client application type."""
    TELEGRAM_DESKTOP = auto()
    TELEGRAM_ANDROID = auto()
    TELEGRAM_IOS = auto()
    TELEGRAM_WEB = auto()
    UNKNOWN = auto()


class ClientStatus(Enum):
    """Client connection status."""
    CONNECTING = auto()
    ACTIVE = auto()
    IDLE = auto()
    DISCONNECTED = auto()
    BLOCKED = auto()


@dataclass
class ClientInfo:
    """Client information."""
    ip: str
    port: int
    client_id: str = ""
    client_type: ClientType = ClientType.UNKNOWN
    status: ClientStatus = ClientStatus.CONNECTING
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    bytes_sent: int = 0
    bytes_received: int = 0
    connections_count: int = 0
    dc_id: int | None = None
    user_agent: str | None = None

    def __post_init__(self) -> None:
        if not self.client_id:
            self.client_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique client ID."""
        data = f"{self.ip}:{self.port}:{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    @property
    def session_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.connected_at

    @property
    def idle_time(self) -> float:
        """Get idle time in seconds."""
        return time.time() - self.last_activity

    @property
    def total_bytes(self) -> int:
        """Get total bytes transferred."""
        return self.bytes_sent + self.bytes_received

    @property
    def is_active(self) -> bool:
        """Check if client is active (not idle for more than 5 minutes)."""
        return self.idle_time < 300

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'client_id': self.client_id,
            'ip': self.ip,
            'port': self.port,
            'client_type': self.client_type.name,
            'status': self.status.name,
            'connected_at': self.connected_at,
            'last_activity': self.last_activity,
            'session_duration_sec': round(self.session_duration, 2),
            'idle_time_sec': round(self.idle_time, 2),
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'total_bytes': self.total_bytes,
            'connections_count': self.connections_count,
            'dc_id': self.dc_id,
        }


@dataclass
class ClientSession:
    """Client session data."""
    client_id: str
    start_time: float
    end_time: float | None = None
    bytes_transferred: int = 0
    dc_id: int | None = None
    error_count: int = 0
    last_error: str | None = None

    @property
    def duration(self) -> float:
        """Get session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.end_time is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'client_id': self.client_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_sec': round(self.duration, 2),
            'bytes_transferred': self.bytes_transferred,
            'dc_id': self.dc_id,
            'error_count': self.error_count,
            'is_active': self.is_active,
        }


class ClientStatistics:
    """
    Per-client statistics tracker.
    
    Features:
    - Track individual client connections
    - Session history
    - Traffic accounting
    - Activity monitoring
    """

    def __init__(self, max_clients: int = 1000, max_history: int = 100):
        self.max_clients = max_clients
        self.max_history = max_history

        self._clients: dict[str, ClientInfo] = {}
        self._sessions: dict[str, list[ClientSession]] = {}
        self._ip_to_client: dict[str, str] = {}  # IP -> client_id mapping

        # Global statistics
        self.total_connections = 0
        self.total_disconnections = 0
        self.peak_concurrent_clients = 0
        self.start_time = time.time()

    def register_client(
        self,
        ip: str,
        port: int,
        client_type: ClientType = ClientType.UNKNOWN,
    ) -> ClientInfo:
        """Register a new client connection."""
        client_id = f"{ip}:{port}"

        # Check if client already exists
        if client_id in self._clients:
            client = self._clients[client_id]
            client.status = ClientStatus.ACTIVE
            client.last_activity = time.time()
            client.connections_count += 1
        else:
            # Evict oldest client if at capacity
            if len(self._clients) >= self.max_clients:
                self._evict_oldest_client()

            client = ClientInfo(
                ip=ip,
                port=port,
                client_type=client_type,
            )
            self._clients[client_id] = client
            self._ip_to_client[ip] = client_id

        self.total_connections += 1

        # Update peak
        current_clients = len([
            c for c in self._clients.values()
            if c.status == ClientStatus.ACTIVE
        ])
        if current_clients > self.peak_concurrent_clients:
            self.peak_concurrent_clients = current_clients

        # Create new session
        session = ClientSession(
            client_id=client_id,
            start_time=time.time(),
        )

        if client_id not in self._sessions:
            self._sessions[client_id] = []
        self._sessions[client_id].append(session)

        # Trim session history
        if len(self._sessions[client_id]) > self.max_history:
            self._sessions[client_id] = self._sessions[client_id][-self.max_history:]

        log.debug("Client registered: %s (%s)", client_id, client_type.name)
        return client

    def unregister_client(self, ip: str, port: str) -> None:
        """Unregister a client connection."""
        client_id = f"{ip}:{port}"

        if client_id in self._clients:
            client = self._clients[client_id]
            client.status = ClientStatus.DISCONNECTED
            client.last_activity = time.time()

            # Close active session
            if client_id in self._sessions:
                for session in reversed(self._sessions[client_id]):
                    if session.is_active:
                        session.end_time = time.time()
                        session.bytes_transferred = client.total_bytes
                        break

            self.total_disconnections += 1
            log.debug("Client unregistered: %s", client_id)

    def update_client_activity(
        self,
        ip: str,
        port: int,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ) -> None:
        """Update client activity."""
        client_id = f"{ip}:{port}"

        if client_id in self._clients:
            client = self._clients[client_id]
            client.last_activity = time.time()
            client.status = ClientStatus.ACTIVE
            client.bytes_sent += bytes_sent
            client.bytes_received += bytes_received

            # Update active session
            if client_id in self._sessions:
                for session in reversed(self._sessions[client_id]):
                    if session.is_active:
                        session.bytes_transferred = client.total_bytes
                        break

    def update_client_dc(self, ip: str, port: int, dc_id: int) -> None:
        """Update client's DC ID."""
        client_id = f"{ip}:{port}"

        if client_id in self._clients:
            self._clients[client_id].dc_id = dc_id

            # Update active session
            if client_id in self._sessions:
                for session in reversed(self._sessions[client_id]):
                    if session.is_active:
                        session.dc_id = dc_id
                        break

    def record_client_error(
        self,
        ip: str,
        port: int,
        error: str,
    ) -> None:
        """Record client error."""
        client_id = f"{ip}:{port}"

        if client_id in self._sessions:
            for session in reversed(self._sessions[client_id]):
                if session.is_active:
                    session.error_count += 1
                    session.last_error = error
                    break

    def get_client(self, ip: str, port: int) -> ClientInfo | None:
        """Get client info."""
        client_id = f"{ip}:{port}"
        return self._clients.get(client_id)

    def get_client_by_id(self, client_id: str) -> ClientInfo | None:
        """Get client info by client ID."""
        return self._clients.get(client_id)

    def get_all_clients(self) -> list[ClientInfo]:
        """Get all clients."""
        return list(self._clients.values())

    def get_active_clients(self) -> list[ClientInfo]:
        """Get active clients."""
        return [
            client for client in self._clients.values()
            if client.is_active
        ]

    def get_client_sessions(self, client_id: str) -> list[ClientSession]:
        """Get client session history."""
        return self._sessions.get(client_id, [])

    def get_statistics(self) -> dict[str, Any]:
        """Get overall statistics."""
        active_clients = self.get_active_clients()

        # Calculate traffic
        total_sent = sum(c.bytes_sent for c in self._clients.values())
        total_received = sum(c.bytes_received for c in self._clients.values())

        # Calculate average session duration
        all_sessions = []
        for sessions in self._sessions.values():
            all_sessions.extend(sessions)

        completed_sessions = [s for s in all_sessions if not s.is_active]
        avg_session_duration = (
            sum(s.duration for s in completed_sessions) / len(completed_sessions)
            if completed_sessions else 0
        )

        return {
            'total_clients': len(self._clients),
            'active_clients': len(active_clients),
            'total_connections': self.total_connections,
            'total_disconnections': self.total_disconnections,
            'peak_concurrent_clients': self.peak_concurrent_clients,
            'total_bytes_sent': total_sent,
            'total_bytes_received': total_received,
            'total_bytes': total_sent + total_received,
            'average_session_duration_sec': round(avg_session_duration, 2),
            'uptime_sec': round(time.time() - self.start_time, 2),
        }

    def get_top_clients(self, limit: int = 10, by: str = 'traffic') -> list[ClientInfo]:
        """Get top clients by specified metric."""
        clients = list(self._clients.values())

        if by == 'traffic':
            clients.sort(key=lambda c: c.total_bytes, reverse=True)
        elif by == 'duration':
            clients.sort(key=lambda c: c.session_duration, reverse=True)
        elif by == 'connections':
            clients.sort(key=lambda c: c.connections_count, reverse=True)

        return clients[:limit]

    def _evict_oldest_client(self) -> None:
        """Evict the oldest inactive client."""
        inactive = [
            (client_id, client)
            for client_id, client in self._clients.items()
            if not client.is_active
        ]

        if inactive:
            # Sort by last activity
            inactive.sort(key=lambda x: x[1].last_activity)
            oldest_id, oldest_client = inactive[0]

            del self._clients[oldest_id]
            if oldest_client.ip in self._ip_to_client:
                del self._ip_to_client[oldest_client.ip]

            log.debug("Evicted oldest client: %s", oldest_id)

    def cleanup_inactive(self, max_idle_seconds: float = 3600) -> int:
        """Clean up inactive clients. Returns count of cleaned clients."""
        now = time.time()
        to_remove = [
            client_id for client_id, client in self._clients.items()
            if (now - client.last_activity) > max_idle_seconds
            and client.status == ClientStatus.DISCONNECTED
        ]

        for client_id in to_remove:
            del self._clients[client_id]

        return len(to_remove)


# Global client statistics instance
_client_stats: ClientStatistics | None = None


def get_client_statistics(max_clients: int = 1000) -> ClientStatistics:
    """Get or create global client statistics."""
    global _client_stats
    if _client_stats is None:
        _client_stats = ClientStatistics(max_clients=max_clients)
    return _client_stats


def detect_client_type(user_agent: str | None = None) -> ClientType:
    """Detect client type from user agent or other hints."""
    if not user_agent:
        return ClientType.UNKNOWN

    user_agent_lower = user_agent.lower()

    if 'telegram' in user_agent_lower:
        if 'android' in user_agent_lower:
            return ClientType.TELEGRAM_ANDROID
        elif 'iphone' in user_agent_lower or 'ios' in user_agent_lower:
            return ClientType.TELEGRAM_IOS
        elif 'web' in user_agent_lower or 'browser' in user_agent_lower:
            return ClientType.TELEGRAM_WEB
        else:
            return ClientType.TELEGRAM_DESKTOP

    return ClientType.UNKNOWN


__all__ = [
    'ClientStatistics',
    'ClientInfo',
    'ClientSession',
    'ClientType',
    'ClientStatus',
    'get_client_statistics',
    'detect_client_type',
]
