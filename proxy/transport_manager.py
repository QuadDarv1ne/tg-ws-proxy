"""
Unified Transport Manager for TG WS Proxy.

Provides a single interface for managing multiple transport protocols:
- WebSocket (default)
- HTTP/2
- QUIC/HTTP/3
- Meek (domain fronting)
- Shadowsocks 2022
- Tuic
- Reality

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Protocol

log = logging.getLogger('tg-ws-transport-manager')


class TransportType(Enum):
    """Available transport types."""
    WEBSOCKET = auto()
    HTTP2 = auto()
    QUIC = auto()
    MEEK = auto()
    SHADOWSOCKS = auto()
    TUIC = auto()
    REALITY = auto()
    DIRECT_TCP = auto()


class TransportStatus(Enum):
    """Transport connection status."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    FAILED = auto()
    DEGRADED = auto()


class Transport(Protocol):
    """Transport protocol interface."""

    async def connect(self, timeout: float = 10.0) -> bool:
        """Establish connection."""
        ...

    async def send(self, data: bytes) -> bool:
        """Send data."""
        ...

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive data."""
        ...

    async def close(self) -> None:
        """Close connection."""
        ...

    def get_stats(self) -> dict:
        """Get transport statistics."""
        ...


@dataclass
class TransportConfig:
    """Transport configuration."""
    transport_type: TransportType = TransportType.WEBSOCKET

    # Common settings
    host: str = 'kws2.web.telegram.org'
    port: int = 443
    path: str = '/api'

    # HTTP/2 settings
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    use_tls: bool = True

    # QUIC settings
    use_quic: bool = True
    fallback_to_http2: bool = True

    # Meek settings
    meek_cdn: str = 'cloudflare'
    bridge_host: str = ''
    bridge_port: int = 443

    # Shadowsocks settings
    ss_method: str = 'chacha20-ietf-poly1305'
    ss_password: str = ''

    # Tuic settings
    tuic_token: str = ''
    tuic_uuid: str = ''

    # Reality settings
    reality_public_key: str = ''
    reality_short_id: str = ''
    reality_server_name: str = 'www.microsoft.com'

    # Auto-selection
    auto_select: bool = True
    health_check_interval: float = 30.0

    # Timeouts
    connect_timeout: float = 10.0
    read_timeout: float = 30.0


@dataclass
class TransportHealth:
    """Transport health metrics."""
    latency_ms: float = 0.0
    packet_loss: float = 0.0
    last_check: float = field(default_factory=time.monotonic)
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def is_healthy(self) -> bool:
        return (
            self.consecutive_failures < 3 and
            self.success_rate > 0.8 and
            self.latency_ms < 500
        )


class TransportManager:
    """
    Unified Transport Manager.

    Features:
    - Multiple transport support
    - Automatic health checking
    - Failover and fallback
    - Performance metrics
    - Auto-selection based on latency
    """

    def __init__(self, config: TransportConfig | None = None):
        """
        Initialize transport manager.

        Args:
            config: Transport configuration
        """
        self.config = config or TransportConfig()

        # Active transport
        self._transport: Transport | None = None
        self._transport_type: TransportType = self.config.transport_type
        self._status: TransportStatus = TransportStatus.DISCONNECTED

        # Health tracking
        self._health: dict[TransportType, TransportHealth] = {
            t: TransportHealth() for t in TransportType
        }

        # Fallback chain
        self._fallback_chain = self._build_fallback_chain()

        # Background tasks
        self._health_check_task: asyncio.Task | None = None
        self._running = False

        # Stats
        self.connections_created = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.transports_switched = 0

    def _build_fallback_chain(self) -> list[TransportType]:
        """Build fallback chain based on primary transport."""
        # Default fallback order
        chain = [
            TransportType.QUIC,
            TransportType.HTTP2,
            TransportType.WEBSOCKET,
            TransportType.DIRECT_TCP,
        ]

        # Add Meek for strict censorship
        if self.config.meek_cdn:
            chain.append(TransportType.MEEK)

        return chain

    async def start(self) -> bool:
        """
        Start transport manager and connect.

        Returns:
            True if connection successful
        """
        log.info("Starting transport manager...")
        self._running = True

        # Auto-select best transport
        if self.config.auto_select:
            success = await self._auto_select_and_connect()
        else:
            success = await self._connect_with_fallback()

        if success:
            # Start health monitoring
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )

        return success

    async def stop(self) -> None:
        """Stop transport manager."""
        log.info("Stopping transport manager...")
        self._running = False

        # Cancel health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close active transport
        if self._transport:
            await self._transport.close()
            self._transport = None

        self._status = TransportStatus.DISCONNECTED

    async def _auto_select_and_connect(self) -> bool:
        """
        Auto-select best transport based on latency.

        Returns:
            True if connection successful
        """
        log.info("Auto-selecting best transport...")

        # Measure latency for each transport
        latencies = {}
        for transport_type in self._fallback_chain:
            latency = await self._measure_transport_latency(transport_type)
            if latency > 0:
                latencies[transport_type] = latency
                log.debug("%s latency: %.1fms", transport_type.name, latency)

        if not latencies:
            log.error("No transports available")
            return False

        # Select fastest
        best_transport = min(latencies, key=latencies.get)
        log.info("Selected %s (%.1fms)", best_transport.name, latencies[best_transport])

        # Connect with selected transport
        return await self._connect_transport(best_transport)

    async def _measure_transport_latency(
        self,
        transport_type: TransportType,
        timeout: float = 5.0
    ) -> float:
        """
        Measure latency for a transport type.

        Returns:
            Latency in ms, or -1 if failed
        """
        transport = await self._create_transport(transport_type)
        if not transport:
            return -1.0

        try:
            start = time.monotonic()

            if await transport.connect(timeout=timeout):
                # Send ping
                if hasattr(transport, 'ping'):
                    latency = await transport.ping()
                else:
                    # Simple RTT measurement
                    await transport.send(b'\x00')
                    latency = (time.monotonic() - start) * 1000

                await transport.close()
                return latency

            await transport.close()
            return -1.0

        except Exception as e:
            log.debug("Failed to measure %s latency: %s", transport_type.name, e)
            return -1.0

    async def _connect_with_fallback(self) -> bool:
        """
        Try to connect with fallback chain.

        Returns:
            True if connection successful
        """
        for transport_type in self._fallback_chain:
            log.info("Trying %s...", transport_type.name)

            if await self._connect_transport(transport_type):
                return True

            log.warning("%s failed, trying next...", transport_type.name)

        log.error("All transports failed")
        return False

    async def _connect_transport(self, transport_type: TransportType) -> bool:
        """
        Connect with specific transport.

        Returns:
            True if successful
        """
        self._status = TransportStatus.CONNECTING

        transport = await self._create_transport(transport_type)
        if not transport:
            self._status = TransportStatus.FAILED
            return False

        try:
            if await transport.connect(timeout=self.config.connect_timeout):
                self._transport = transport
                self._transport_type = transport_type
                self._status = TransportStatus.CONNECTED
                self.connections_created += 1

                log.info("Connected via %s", transport_type.name)
                return True

            await transport.close()

        except Exception as e:
            log.error("Failed to connect %s: %s", transport_type.name, e)

        self._status = TransportStatus.FAILED
        return False

    async def _create_transport(self, transport_type: TransportType) -> Transport | None:
        """
        Create transport instance.

        Returns:
            Transport instance or None
        """
        try:
            if transport_type == TransportType.WEBSOCKET:
                from proxy.websocket_client import RawWebSocket
                # Wrap as Transport interface
                return WebSocketTransport(
                    self.config.host,
                    self.config.port,
                    self.config.path
                )

            elif transport_type == TransportType.HTTP2:
                from proxy.http2_transport import HTTP2Transport
                return HTTP2Transport(
                    self.config.host,
                    self.config.port,
                    self.config.path,
                    self.config.user_agent
                )

            elif transport_type == TransportType.QUIC:
                from proxy.quic_transport import QuicTransport
                return QuicTransport(
                    self.config.host,
                    self.config.port,
                    use_quic=self.config.use_quic,
                    fallback_to_http2=self.config.fallback_to_http2
                )

            elif transport_type == TransportType.MEEK:
                from proxy.meek_transport import MeekTransport
                return MeekTransport(
                    self.config.bridge_host or self.config.host,
                    self.config.bridge_port or self.config.port,
                    use_cdn=self.config.meek_cdn
                )

            elif transport_type == TransportType.SHADOWSOCKS:
                from proxy.shadowsocks_transport import ShadowsocksTransport
                return ShadowsocksTransport(
                    self.config.host,
                    self.config.port,
                    method=self.config.ss_method,
                    password=self.config.ss_password
                )

            elif transport_type == TransportType.TUIC:
                from proxy.tuic_transport import TuicTransport
                return TuicTransport(
                    self.config.host,
                    self.config.port,
                    token=self.config.tuic_token,
                    uuid=self.config.tuic_uuid
                )

            elif transport_type == TransportType.REALITY:
                from proxy.reality_transport import RealityTransport
                return RealityTransport(
                    self.config.host,
                    self.config.port,
                    public_key=self.config.reality_public_key,
                    short_id=self.config.reality_short_id,
                    server_name=self.config.reality_server_name
                )

            elif transport_type == TransportType.DIRECT_TCP:
                from proxy.direct_transport import DirectTcpTransport
                return DirectTcpTransport(
                    self.config.host,
                    self.config.port
                )

        except ImportError as e:
            log.warning("Transport %s not available: %s", transport_type.name, e)
        except Exception as e:
            log.error("Failed to create %s: %s", transport_type.name, e)

        return None

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            await asyncio.sleep(self.config.health_check_interval)

            if self._transport:
                # Check current transport health
                health = self._health[self._transport_type]
                health.last_check = time.monotonic()
                health.total_requests += 1

                try:
                    # Simple health check (ping or small request)
                    if hasattr(self._transport, 'ping'):
                        latency = await self._transport.ping()
                        health.latency_ms = latency
                    else:
                        health.latency_ms = 0

                    health.successful_requests += 1
                    health.consecutive_failures = 0

                    # Update status
                    if health.is_healthy:
                        self._status = TransportStatus.CONNECTED
                    else:
                        self._status = TransportStatus.DEGRADED

                except Exception as e:
                    log.debug("Health check failed: %s", e)
                    health.consecutive_failures += 1

                    # Trigger failover if unhealthy
                    if not health.is_healthy:
                        log.warning("Transport unhealthy, triggering failover")
                        await self._failover()

    async def _failover(self) -> None:
        """Switch to fallback transport."""
        log.info("Initiating failover...")

        # Find next healthy transport
        for transport_type in self._fallback_chain:
            if transport_type == self._transport_type:
                continue

            health = self._health[transport_type]
            if health.is_healthy:
                log.info("Failing over to %s", transport_type.name)

                # Close current
                if self._transport:
                    await self._transport.close()

                # Connect new
                if await self._connect_transport(transport_type):
                    self.transports_switched += 1
                    return

        log.warning("No healthy fallback available")

    # Public API

    async def send(self, data: bytes) -> bool:
        """Send data via active transport."""
        if not self._transport:
            return False

        success = await self._transport.send(data)
        if success:
            self.bytes_sent += len(data)
        return success

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive data from active transport."""
        if not self._transport:
            return None

        data = await self._transport.recv(max_size)
        if data:
            self.bytes_received += len(data)
        return data

    async def reconnect(self) -> bool:
        """Force reconnection."""
        if self._transport:
            await self._transport.close()

        return await self._connect_with_fallback()

    def get_stats(self) -> dict:
        """Get comprehensive statistics."""
        transport_stats = self._transport.get_stats() if self._transport else {}

        return {
            'status': self._status.name,
            'transport_type': self._transport_type.name,
            'connections_created': self.connections_created,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'transports_switched': self.transports_switched,
            'health': {
                t.name: {
                    'latency_ms': h.latency_ms,
                    'success_rate': h.success_rate,
                    'is_healthy': h.is_healthy,
                }
                for t, h in self._health.items()
            },
            'transport': transport_stats,
        }

    @property
    def status(self) -> TransportStatus:
        """Get current status."""
        return self._status

    @property
    def transport_type(self) -> TransportType:
        """Get active transport type."""
        return self._transport_type


# WebSocket wrapper for Transport interface
class WebSocketTransport:
    """WebSocket transport wrapper."""

    def __init__(self, host: str, port: int, path: str = '/'):
        self.host = host
        self.port = port
        self.path = path
        self._ws = None

    async def connect(self, timeout: float = 10.0) -> bool:
        from proxy.websocket_client import RawWebSocket
        self._ws = RawWebSocket(self.host, self.port, path=self.path)
        return await self._ws.connect(timeout=timeout)

    async def send(self, data: bytes) -> bool:
        if not self._ws:
            return False
        return await self._ws.send(data)

    async def recv(self, max_size: int = 65536) -> bytes | None:
        if not self._ws:
            return None
        _, data = await self._ws.recv()
        return data

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()

    def get_stats(self) -> dict:
        if not self._ws:
            return {'connected': False}
        return self._ws.get_stats()

    async def ping(self) -> float:
        if not self._ws:
            return -1.0
        return await self._ws.ping()


# Placeholder transports for future implementation
class DirectTcpTransport:
    """Direct TCP transport."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._reader = None
        self._writer = None

    async def connect(self, timeout: float = 10.0) -> bool:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout
            )
            return True
        except Exception:
            return False

    async def send(self, data: bytes) -> bool:
        if not self._writer:
            return False
        self._writer.write(data)
        await self._writer.drain()
        return True

    async def recv(self, max_size: int = 65536) -> bytes | None:
        if not self._reader:
            return None
        return await self._reader.read(max_size)

    async def close(self) -> None:
        if self._writer:
            self._writer.close()

    def get_stats(self) -> dict:
        return {'connected': self._writer is not None}
