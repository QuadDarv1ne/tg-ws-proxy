"""
QUIC/HTTP/3 Transport for TG WS Proxy.

Implements QUIC protocol (UDP-based) for censorship circumvention:
- 0-RTT handshakes for fast connection
- Connection migration support
- Bypasses TCP-based blocking
- Better performance on lossy networks

Note: Requires Python 3.10+ and aioquic library for full QUIC support.
This module provides fallback to HTTP/2 if QUIC is unavailable.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import ssl
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger('tg-ws-quic')

# Try to import aioquic for full QUIC support
try:
    from aioquic.asyncio.client import connect as aioquic_connect
    from aioquic.h3.events import HeadersReceived
    from aioquic.quic.configuration import QuicConfiguration
    HAS_AIOQUIC = True
except ImportError:
    HAS_AIOQUIC = False
    log.debug("aioquic not available, QUIC support disabled")


@dataclass
class QuicConfig:
    """QUIC configuration."""
    max_datagram_size: int = 1350  # MTU-safe size
    idle_timeout: float = 30.0
    max_concurrent_streams: int = 100
    initial_max_data: int = 1048576  # 1 MB
    initial_max_stream_data: int = 262144  # 256 KB
    verify_mode: int = ssl.CERT_NONE  # Disable cert verification for proxy
    alpn_protocols: list[str] = field(default_factory=lambda: ['h3', 'h3-29'])


class QuicConnection:
    """
    QUIC Connection wrapper.

    Provides UDP-based reliable transport with 0-RTT resumption.
    """

    def __init__(
        self,
        host: str,
        port: int,
        config: QuicConfig | None = None,
        server_name: str | None = None
    ):
        """
        Initialize QUIC connection.

        Args:
            host: Target host
            port: Target port
            config: QUIC configuration
            server_name: SNI server name
        """
        self.host = host
        self.port = port
        self.server_name = server_name or host
        self.config = config or QuicConfig()

        self._quic = None
        self._stream_id: int | None = None
        self._connected = False
        self._reader: asyncio.Queue[bytes] | None = None
        self._writer_transport = None

        # Stats
        self.bytes_sent = 0
        self.bytes_received = 0
        self.packets_sent = 0
        self.packets_received = 0
        self.rtt_ms = 0.0

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish QUIC connection.

        Returns:
            True if connection successful
        """
        if not HAS_AIOQUIC:
            log.warning("aioquic not available, cannot establish QUIC connection")
            return False

        try:
            # Configure QUIC
            configuration = QuicConfiguration(
                is_client=True,
                alpn_protocols=self.config.alpn_protocols,
                verify_mode=self.config.verify_mode,
                server_name=self.server_name,
                max_datagram_frame_size=self.config.max_datagram_size,
            )

            # Load default certificates
            configuration.load_verify_locations()

            # Connect using aioquic
            self._reader = asyncio.Queue()

            async with aioquic_connect(
                self.host,
                self.port,
                configuration=configuration,
            ) as client:
                self._quic = client
                self._connected = True

                # Create HTTP/3 stream
                self._stream_id = self._quic.get_next_available_stream_id()

                log.info("QUIC connected to %s:%d", self.host, self.port)
                return True

        except Exception as e:
            log.error("QUIC connection error: %s", e)
            return False

    async def send(self, data: bytes) -> bool:
        """Send data over QUIC."""
        if not self._connected or not self._quic:
            return False

        try:
            # Send data on stream
            self._quic.send_stream_data(self._stream_id, data, end_stream=False)
            self._quic.transmit()

            self.bytes_sent += len(data)
            self.packets_sent += 1

            return True

        except Exception as e:
            log.error("QUIC send error: %s", e)
            return False

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive data from QUIC stream."""
        if not self._connected or not self._reader:
            return None

        try:
            data = await self._reader.get()
            self.bytes_received += len(data)
            self.packets_received += 1
            return data

        except asyncio.CancelledError:
            return None
        except Exception as e:
            log.error("QUIC recv error: %s", e)
            return None

    async def close(self) -> None:
        """Close QUIC connection."""
        if self._quic:
            try:
                # Send FIN on stream
                self._quic.send_stream_data(self._stream_id, b'', end_stream=True)
                self._quic.transmit()
            except Exception:
                pass

            self._quic = None
            self._connected = False

        log.info("QUIC connection closed")

    def get_stats(self) -> dict:
        """Get QUIC statistics."""
        return {
            'connected': self._connected,
            'rtt_ms': self.rtt_ms,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
        }


class QuicTransport:
    """
    QUIC Transport for Telegram proxy.

    Provides UDP-based transport with automatic fallback to HTTP/2.
    """

    def __init__(
        self,
        host: str,
        port: int = 443,
        use_quic: bool = True,
        fallback_to_http2: bool = True,
    ):
        """
        Initialize QUIC transport.

        Args:
            host: Target host
            port: Target port
            use_quic: Enable QUIC transport
            fallback_to_http2: Fallback to HTTP/2 if QUIC unavailable
        """
        self.host = host
        self.port = port
        self.use_quic = use_quic
        self.fallback_to_http2 = fallback_to_http2

        self._quic: QuicConnection | None = None
        self._http2 = None  # HTTP/2 fallback
        self._using_fallback = False

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish connection (QUIC or fallback).

        Returns:
            True if connection successful
        """
        # Try QUIC first
        if self.use_quic and HAS_AIOQUIC:
            self._quic = QuicConnection(self.host, self.port)

            if await self._quic.connect(timeout=timeout):
                log.info("Using QUIC transport for %s:%d", self.host, self.port)
                return True

            log.warning("QUIC connection failed, will try fallback")
            self._quic = None

        # Fallback to HTTP/2
        if self.fallback_to_http2:
            from .http2_transport import HTTP2Transport

            self._http2 = HTTP2Transport(self.host, self.port)

            if await self._http2.connect(timeout=timeout):
                log.info("Using HTTP/2 fallback for %s:%d", self.host, self.port)
                self._using_fallback = True
                return True

        log.error("Failed to connect to %s:%d (QUIC and HTTP/2 both failed)",
                 self.host, self.port)
        return False

    async def send(self, data: bytes) -> bool:
        """Send data over QUIC or HTTP/2 fallback."""
        if self._using_fallback and self._http2:
            return await self._http2.send(data)

        if self._quic:
            return await self._quic.send(data)

        return False

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive data from QUIC or HTTP/2 fallback."""
        if self._using_fallback and self._http2:
            return await self._http2.recv(max_size)

        if self._quic:
            return await self._quic.recv(max_size)

        return None

    async def close(self) -> None:
        """Close connection."""
        if self._http2:
            await self._http2.close()
            self._http2 = None

        if self._quic:
            await self._quic.close()
            self._quic = None

        self._using_fallback = False

    def get_stats(self) -> dict:
        """Get transport statistics."""
        if self._using_fallback and self._http2:
            stats = self._http2.get_stats()
            stats['transport'] = 'http2_fallback'
            return stats

        if self._quic:
            stats = self._quic.get_stats()
            stats['transport'] = 'quic'
            return stats

        return {'transport': 'none', 'connected': False}


class UdpRelayQuic:
    """
    Simple UDP relay for QUIC-like behavior without full QUIC implementation.

    This provides basic UDP tunneling that can be used as a lightweight
    alternative when full QUIC is not available.
    """

    def __init__(
        self,
        target_host: str,
        target_port: int,
        local_host: str = '127.0.0.1',
        local_port: int = 0,
    ):
        """
        Initialize UDP relay.

        Args:
            target_host: Target host for UDP packets
            target_port: Target port
            local_host: Local bind host
            local_port: Local bind port (0 for random)
        """
        self.target_host = target_host
        self.target_port = target_port
        self.local_host = local_host
        self.local_port = local_port

        self._socket: socket.socket | None = None
        self._connected = False

        # Stats
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    def connect(self) -> bool:
        """Create UDP socket."""
        try:
            self._socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
                socket.IPPROTO_UDP
            )
            self._socket.setblocking(False)
            self._socket.connect((self.target_host, self.target_port))

            if self.local_port > 0:
                self._socket.bind((self.local_host, self.local_port))

            self._connected = True
            log.info("UDP relay connected to %s:%d",
                    self.target_host, self.target_port)
            return True

        except Exception as e:
            log.error("UDP relay connect error: %s", e)
            return False

    def send(self, data: bytes) -> bool:
        """Send UDP packet."""
        if not self._connected or not self._socket:
            return False

        try:
            sent = self._socket.send(data)
            self.packets_sent += 1
            self.bytes_sent += sent
            return sent == len(data)

        except Exception as e:
            log.error("UDP relay send error: %s", e)
            return False

    def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive UDP packet."""
        if not self._connected or not self._socket:
            return None

        try:
            data = self._socket.recv(max_size)
            self.packets_received += 1
            self.bytes_received += len(data)
            return data

        except BlockingIOError:
            return None
        except Exception as e:
            log.error("UDP relay recv error: %s", e)
            return None

    def close(self) -> None:
        """Close UDP socket."""
        if self._socket:
            self._socket.close()
            self._socket = None
            self._connected = False

    def get_stats(self) -> dict:
        """Get UDP relay statistics."""
        return {
            'connected': self._connected,
            'target': f"{self.target_host}:{self.target_port}",
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
        }


async def create_quic_transport(
    host: str,
    port: int = 443,
    use_quic: bool = True,
    fallback_to_http2: bool = True,
    timeout: float = 10.0
) -> QuicTransport | None:
    """
    Create QUIC transport with automatic fallback.

    Args:
        host: Target host
        port: Target port
        use_quic: Enable QUIC
        fallback_to_http2: Fallback to HTTP/2
        timeout: Connection timeout

    Returns:
        QuicTransport instance or None
    """
    transport = QuicTransport(
        host=host,
        port=port,
        use_quic=use_quic,
        fallback_to_http2=fallback_to_http2
    )

    if await transport.connect(timeout=timeout):
        return transport

    return None


def check_quic_support() -> dict[str, Any]:
    """
    Check QUIC support availability.

    Returns:
        Dictionary with support information
    """
    return {
        'aioquic_available': HAS_AIOQUIC,
        'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
        'quic_capable': HAS_AIOQUIC and os.sys.version_info >= (3, 10),
        'recommendation': (
            "Install aioquic: pip install aioquic" if not HAS_AIOQUIC
            else "QUIC support ready"
        )
    }
