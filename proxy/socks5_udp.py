"""
SOCKS5 UDP Relay for Telegram Calls.

Implements UDP ASSOCIATE command for SOCKS5 proxy, enabling:
- Telegram voice/video calls
- UDP-based media streaming
- DNS-over-UDP queries

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Callable

from .socks5_handler import Socks5AddressType, Socks5Reply

log = logging.getLogger('tg-ws-udp')


@dataclass
class UdpSession:
    """UDP session state."""
    client_addr: tuple[str, int]
    bind_addr: tuple[str, int]
    socket: socket.socket | None = None
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    packets_forwarded: int = 0
    bytes_forwarded: int = 0


class UdpRelay:
    """
    SOCKS5 UDP Relay server.

    Handles UDP ASSOCIATE command and forwards UDP packets to Telegram servers.
    """

    # UDP session timeout (seconds)
    SESSION_TIMEOUT = 120.0

    # Maximum UDP packet size
    MAX_PACKET_SIZE = 65535

    # Maximum concurrent UDP sessions
    MAX_SESSIONS = 100

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 1080,
        on_packet: Callable[[bytes, tuple], None] | None = None,
    ):
        """
        Initialize UDP relay.

        Args:
            host: Bind host
            port: Bind port
            on_packet: Optional callback for each packet (for stats/logging)
        """
        self.host = host
        self.port = port
        self.on_packet = on_packet

        self._sessions: dict[tuple, UdpSession] = {}
        self._sockets: dict[socket.socket, UdpSession] = {}
        self._running = False
        self._udp_socket: socket.socket | None = None
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: asyncio.DatagramProtocol | None = None

        # Stats
        self.total_sessions = 0
        self.total_packets = 0
        self.total_bytes = 0
        self.active_sessions = 0

    async def start(self) -> tuple[str, int]:
        """
        Start UDP relay server.

        Returns:
            (bind_host, bind_port) tuple
        """
        log.info("Starting UDP relay on %s:%d", self.host, self.port)

        loop = asyncio.get_event_loop()

        # Create UDP socket
        self._udp_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP
        )
        self._udp_socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        self._udp_socket.bind((self.host, self.port))
        self._udp_socket.setblocking(False)

        # Get actual bound port (in case port 0 was used)
        bind_host, bind_port = self._udp_socket.getsockname()

        # Start async UDP handler
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: UdpRelayProtocol(self),
            sock=self._udp_socket
        )

        self._running = True

        # Start session cleanup task
        asyncio.create_task(self._cleanup_sessions())

        log.info("UDP relay started on %s:%d", bind_host, bind_port)
        return (bind_host, bind_port)

    def stop(self) -> None:
        """Stop UDP relay server."""
        log.info("Stopping UDP relay...")
        self._running = False

        # Close all sessions
        for session in list(self._sessions.values()):
            self._close_session(session)

        # Close main socket
        if self._transport:
            self._transport.close()
        if self._udp_socket:
            self._udp_socket.close()

        log.info("UDP relay stopped")

    def create_session(
        self,
        client_addr: tuple[str, int],
        bind_addr: tuple[str, int] | None = None
    ) -> UdpSession:
        """
        Create new UDP session.

        Args:
            client_addr: Client address (ip, port)
            bind_addr: Optional bind address (defaults to 0.0.0.0:0)

        Returns:
            New UdpSession
        """
        if len(self._sessions) >= self.MAX_SESSIONS:
            raise RuntimeError(f"Maximum UDP sessions ({self.MAX_SESSIONS}) reached")

        # Create UDP socket for this session
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)

        # Bind to specific address if provided
        if bind_addr:
            sock.bind(bind_addr)

        session = UdpSession(
            client_addr=client_addr,
            bind_addr=sock.getsockname(),
            socket=sock
        )

        self._sessions[session.bind_addr] = session
        self._sockets[sock] = session
        self.total_sessions += 1
        self.active_sessions += 1

        log.debug("UDP session created: %s -> %s", client_addr, session.bind_addr)
        return session

    def get_session(self, bind_addr: tuple[str, int]) -> UdpSession | None:
        """Get session by bind address."""
        return self._sessions.get(bind_addr)

    def _close_session(self, session: UdpSession) -> None:
        """Close UDP session."""
        try:
            if session.socket in self._sockets:
                del self._sockets[session.socket]
            if session.bind_addr in self._sessions:
                del self._sessions[session.bind_addr]
            if session.socket:
                session.socket.close()
            self.active_sessions -= 1
            log.debug("UDP session closed: %s", session.client_addr)
        except Exception as e:
            log.error("Error closing UDP session: %s", e)

    async def _cleanup_sessions(self) -> None:
        """Periodically clean up expired sessions."""
        while self._running:
            await asyncio.sleep(30.0)

            now = time.monotonic()
            expired = []

            for session in list(self._sessions.values()):
                if now - session.last_activity > self.SESSION_TIMEOUT:
                    expired.append(session)

            for session in expired:
                log.debug("UDP session expired: %s", session.client_addr)
                self._close_session(session)

    def forward_packet(
        self,
        session: UdpSession,
        data: bytes,
        target_addr: tuple[str, int]
    ) -> bool:
        """
        Forward UDP packet to target.

        Args:
            session: UDP session
            data: Packet data
            target_addr: Target address (ip, port)

        Returns:
            True if packet sent successfully
        """
        if not session.socket:
            return False

        try:
            session.socket.sendto(data, target_addr)
            session.last_activity = time.monotonic()
            session.packets_forwarded += 1
            session.bytes_forwarded += len(data)

            self.total_packets += 1
            self.total_bytes += len(data)

            if self.on_packet:
                self.on_packet(data, target_addr)

            log.debug("UDP packet forwarded: %d bytes to %s:%d",
                     len(data), target_addr[0], target_addr[1])
            return True

        except Exception as e:
            log.error("UDP forward error: %s", e)
            return False

    def get_stats(self) -> dict:
        """Get UDP relay statistics."""
        return {
            'total_sessions': self.total_sessions,
            'active_sessions': self.active_sessions,
            'total_packets': self.total_packets,
            'total_bytes': self.total_bytes,
            'sessions': [
                {
                    'client': s.client_addr,
                    'bind_addr': s.bind_addr,
                    'packets': s.packets_forwarded,
                    'bytes': s.bytes_forwarded,
                    'age': time.monotonic() - s.created_at,
                }
                for s in self._sessions.values()
            ]
        }


class UdpRelayProtocol(asyncio.DatagramProtocol):
    """
    Asyncio UDP protocol handler.

    Handles incoming UDP packets from clients and forwards them to targets.
    """

    def __init__(self, relay: UdpRelay):
        """
        Initialize protocol.

        Args:
            relay: Parent UdpRelay instance
        """
        self.relay = relay
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Called when connection is established."""
        self.transport = transport
        log.debug("UDP protocol connection established")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """
        Handle incoming UDP datagram.

        Args:
            data: Received data
            addr: Sender address
        """
        # Parse SOCKS5 UDP header
        if len(data) < 4:
            log.warning("UDP packet too short from %s", addr)
            return

        # SOCKS5 UDP header format:
        # RSV (2 bytes) | FRAG (1 byte) | ATYP (1 byte) | DST.ADDR | DST.PORT | DATA
        frag = data[2]
        atyp = data[3]

        # Check fragmentation (we don't support it)
        if frag != 0:
            log.warning("Fragmented UDP packet from %s (frag=%d)", addr, frag)
            return

        # Parse address
        offset = 4
        try:
            if atyp == Socks5AddressType.IPV4:
                dst_ip = socket.inet_ntoa(data[offset:offset+4])
                offset += 4
            elif atyp == Socks5AddressType.DOMAIN:
                domain_len = data[offset]
                offset += 1
                dst_ip = data[offset:offset+domain_len].decode('utf-8')
                offset += domain_len
            elif atyp == Socks5AddressType.IPV6:
                dst_ip = socket.inet_ntop(socket.AF_INET6, data[offset:offset+16])
                offset += 16
            else:
                log.warning("Unknown UDP address type: %d", atyp)
                return

            dst_port = struct.unpack('!H', data[offset:offset+2])[0]
            offset += 2

        except Exception as e:
            log.error("UDP header parse error: %s", e)
            return

        # Extract payload
        payload = data[offset:]

        if not payload:
            log.debug("Empty UDP payload from %s", addr)
            return

        # Find or create session
        session = self.relay.get_session(addr)
        if not session:
            # Create new session for this client
            session = self.relay.create_session(addr)

        # Forward packet
        target = (dst_ip, dst_port)
        self.relay.forward_packet(session, payload, target)

    def error_received(self, exc: Exception) -> None:
        """Handle error."""
        log.error("UDP protocol error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection loss."""
        log.debug("UDP protocol connection lost: %s", exc)


async def handle_udp_associate(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    udp_relay: UdpRelay
) -> None:
    """
    Handle SOCKS5 UDP ASSOCIATE command.

    Args:
        reader: Client stream reader
        writer: Client stream writer
        udp_relay: UDP relay server
    """
    peer = writer.get_extra_info('peername')
    client_addr = peer if peer else ('unknown', 0)

    log.info("[%s] UDP ASSOCIATE request", client_addr[0])

    try:
        # Create UDP session for this client
        session = udp_relay.create_session(client_addr)
        bind_addr = session.bind_addr

        # Send UDP ASSOCIATE reply
        # Format: VER | REP | RSV | ATYP | BND.ADDR | BND.PORT
        reply = bytearray()
        reply.append(0x05)  # SOCKS5 version
        reply.append(Socks5Reply.SUCCESS)  # Success
        reply.append(0x00)  # Reserved

        # Bind address (IPv4)
        reply.append(Socks5AddressType.IPV4)
        reply.extend(socket.inet_aton(bind_addr[0]))
        reply.extend(struct.pack('!H', bind_addr[1]))

        writer.write(reply)
        await writer.drain()

        log.info("[%s] UDP ASSOCIATE bound to %s:%d",
                client_addr[0], bind_addr[0], bind_addr[1])

        # Keep connection open until client closes it
        # UDP packets will be handled separately
        while True:
            data = await reader.read(1)
            if not data:
                break
            await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        log.debug("[%s] UDP ASSOCIATE cancelled", client_addr[0])
    except ConnectionResetError:
        log.debug("[%s] UDP ASSOCIATE reset", client_addr[0])
    except Exception as e:
        log.error("[%s] UDP ASSOCIATE error: %s", client_addr[0], e)
    finally:
        # Clean up session
        session = udp_relay.get_session(client_addr)
        if session:
            udp_relay._close_session(session)
        await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


class UdpOverTcpRelay:
    """
    UDP-over-TCP relay for environments where UDP is blocked.

    Encapsulates UDP packets in TCP stream for reliable delivery.
    Useful for:
    - Networks blocking UDP
    - High-latency connections
    - Environments with strict firewalls
    """

    # UDP packet header for TCP encapsulation
    HEADER_SIZE = 6  # 2 bytes RSV + 4 bytes length
    MAX_PACKET_SIZE = 65535

    def __init__(self, target_host: str, target_port: int):
        """
        Initialize UDP-over-TCP relay.

        Args:
            target_host: Target host for UDP packets
            target_port: Target port for UDP packets
        """
        self.target_host = target_host
        self.target_port = target_port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect to target over TCP."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.target_host, self.target_port),
                timeout=timeout
            )
            log.info("UDP-over-TCP connected to %s:%d",
                    self.target_host, self.target_port)
            return True
        except Exception as e:
            log.error("UDP-over-TCP connect error: %s", e)
            return False

    async def send(self, data: bytes) -> bool:
        """
        Send UDP packet over TCP.

        Packet format: [RSV 2 bytes][Length 4 bytes][Data]
        """
        if not self._writer:
            return False

        try:
            # Build packet
            header = struct.pack('!HI', 0, len(data))
            packet = header + data

            self._writer.write(packet)
            await self._writer.drain()
            return True

        except Exception as e:
            log.error("UDP-over-TCP send error: %s", e)
            return False

    async def recv(self, max_size: int = 65535) -> bytes | None:
        """Receive UDP packet from TCP stream."""
        if not self._reader:
            return None

        try:
            # Read header
            header = await self._reader.readexactly(self.HEADER_SIZE)
            _, length = struct.unpack('!HI', header)

            if length > max_size:
                log.warning("UDP packet too large: %d bytes", length)
                return None

            # Read data
            data = await self._reader.readexactly(length)
            return data

        except asyncio.IncompleteReadError:
            log.debug("UDP-over-TCP connection closed")
            return None
        except Exception as e:
            log.error("UDP-over-TCP recv error: %s", e)
            return None

    async def close(self) -> None:
        """Close connection."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    async def forward_bidirectional(
        self,
        udp_socket: socket.socket,
        on_packet: Callable[[bytes], None] | None = None
    ) -> None:
        """
        Forward data bidirectionally between UDP socket and TCP stream.

        Args:
            udp_socket: Local UDP socket
            on_packet: Optional callback for each packet
        """
        async def udp_to_tcp():
            """Forward UDP -> TCP."""
            while True:
                try:
                    data, addr = udp_socket.recvfrom(self.MAX_PACKET_SIZE)
                    if not await self.send(data):
                        break
                    if on_packet:
                        on_packet(data)
                except Exception as e:
                    log.error("UDP->TCP error: %s", e)
                    break

        async def tcp_to_udp():
            """Forward TCP -> UDP."""
            while True:
                try:
                    data = await self.recv()
                    if data is None:
                        break
                    udp_socket.sendto(data, (self.target_host, self.target_port))
                except Exception as e:
                    log.error("TCP->UDP error: %s", e)
                    break

        # Run both directions concurrently
        await asyncio.gather(
            udp_to_tcp(),
            tcp_to_udp(),
            return_exceptions=True
        )
