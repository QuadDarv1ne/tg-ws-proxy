"""
SOCKS5 Protocol Handler.

Implements SOCKS5 protocol negotiation and request parsing.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from enum import IntEnum
from typing import NamedTuple

log = logging.getLogger('tg-ws-socks5')


class Socks5Method(IntEnum):
    """SOCKS5 authentication methods."""
    NO_AUTH = 0x00
    GSSAPI = 0x01
    USERNAME_PASSWORD = 0x02
    NO_ACCEPTABLE = 0xFF


class Socks5Command(IntEnum):
    """SOCKS5 commands."""
    CONNECT = 0x01
    BIND = 0x02
    UDP_ASSOCIATE = 0x03


class Socks5AddressType(IntEnum):
    """SOCKS5 address types."""
    IPV4 = 0x01
    DOMAIN = 0x03
    IPV6 = 0x04


class Socks5Reply(IntEnum):
    """SOCKS5 reply codes."""
    SUCCESS = 0x00
    GENERAL_FAILURE = 0x01
    CONNECTION_NOT_ALLOWED = 0x02
    NETWORK_UNREACHABLE = 0x03
    HOST_UNREACHABLE = 0x04
    CONNECTION_REFUSED = 0x05
    TTL_EXPIRED = 0x06
    COMMAND_NOT_SUPPORTED = 0x07
    ADDRESS_TYPE_NOT_SUPPORTED = 0x08


class Socks5Request(NamedTuple):
    """Parsed SOCKS5 request."""
    command: int
    address_type: int
    destination: str
    port: int


class Socks5Handler:
    """SOCKS5 protocol handler."""

    SOCKS5_VERSION = 0x05

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        timeout: float = 10.0,
    ):
        """
        Initialize SOCKS5 handler.

        Args:
            reader: Stream reader for client connection
            writer: Stream writer for client connection
            timeout: Timeout for SOCKS5 operations in seconds
        """
        self.reader = reader
        self.writer = writer
        self.timeout = timeout

    async def negotiate(self) -> bool:
        """
        Perform SOCKS5 authentication negotiation.

        Returns:
            True if negotiation successful, False otherwise
        """
        try:
            # Read greeting: VER | NMETHODS | METHODS
            data = await asyncio.wait_for(
                self.reader.readexactly(2),
                timeout=self.timeout
            )

            version, nmethods = data[0], data[1]

            if version != self.SOCKS5_VERSION:
                log.warning("Invalid SOCKS5 version: %d", version)
                return False

            if nmethods == 0:
                log.warning("No authentication methods provided")
                return False

            # Read methods
            methods = await asyncio.wait_for(
                self.reader.readexactly(nmethods),
                timeout=self.timeout
            )

            # We only support NO_AUTH (0x00)
            if Socks5Method.NO_AUTH not in methods:
                # Send NO_ACCEPTABLE
                self.writer.write(bytes([
                    self.SOCKS5_VERSION,
                    Socks5Method.NO_ACCEPTABLE
                ]))
                await self.writer.drain()
                log.warning("No acceptable authentication method")
                return False

            # Send selected method: NO_AUTH
            self.writer.write(bytes([
                self.SOCKS5_VERSION,
                Socks5Method.NO_AUTH
            ]))
            await self.writer.drain()

            log.debug("SOCKS5 negotiation successful")
            return True

        except asyncio.TimeoutError:
            log.warning("SOCKS5 negotiation timeout")
            return False
        except asyncio.IncompleteReadError:
            log.warning("SOCKS5 negotiation incomplete read")
            return False
        except Exception as e:
            log.error("SOCKS5 negotiation error: %s", e)
            return False

    async def read_request(self) -> Socks5Request | None:
        """
        Read and parse SOCKS5 request.

        Returns:
            Parsed request or None on error
        """
        try:
            # Read request header: VER | CMD | RSV | ATYP
            header = await asyncio.wait_for(
                self.reader.readexactly(4),
                timeout=self.timeout
            )

            version, cmd, _rsv, atyp = header

            if version != self.SOCKS5_VERSION:
                log.warning("Invalid SOCKS5 version in request: %d", version)
                await self.send_reply(Socks5Reply.GENERAL_FAILURE)
                return None

            if cmd not in (Socks5Command.CONNECT, Socks5Command.BIND, Socks5Command.UDP_ASSOCIATE):
                log.warning("Unsupported SOCKS5 command: %d", cmd)
                await self.send_reply(Socks5Reply.COMMAND_NOT_SUPPORTED)
                return None

            # Parse destination address
            destination: str
            port: int

            if atyp == Socks5AddressType.IPV4:
                # IPv4: 4 bytes
                addr_bytes = await asyncio.wait_for(
                    self.reader.readexactly(4),
                    timeout=self.timeout
                )
                destination = '.'.join(str(b) for b in addr_bytes)

            elif atyp == Socks5AddressType.DOMAIN:
                # Domain: 1 byte length + domain
                length_byte = await asyncio.wait_for(
                    self.reader.readexactly(1),
                    timeout=self.timeout
                )
                length = length_byte[0]
                domain_bytes = await asyncio.wait_for(
                    self.reader.readexactly(length),
                    timeout=self.timeout
                )
                destination = domain_bytes.decode('utf-8', errors='replace')

            elif atyp == Socks5AddressType.IPV6:
                # IPv6: 16 bytes
                addr_bytes = await asyncio.wait_for(
                    self.reader.readexactly(16),
                    timeout=self.timeout
                )
                # Format as IPv6 address
                parts = [addr_bytes[i:i+2].hex() for i in range(0, 16, 2)]
                destination = ':'.join(parts)

            else:
                log.warning("Unsupported address type: %d", atyp)
                await self.send_reply(Socks5Reply.ADDRESS_TYPE_NOT_SUPPORTED)
                return None

            # Read port (2 bytes, big-endian)
            port_bytes = await asyncio.wait_for(
                self.reader.readexactly(2),
                timeout=self.timeout
            )
            port = struct.unpack('!H', port_bytes)[0]

            log.debug("SOCKS5 request: cmd=%d, atyp=%d, dst=%s:%d", cmd, atyp, destination, port)

            return Socks5Request(
                command=cmd,
                address_type=atyp,
                destination=destination,
                port=port
            )

        except asyncio.TimeoutError:
            log.warning("SOCKS5 request timeout")
            await self.send_reply(Socks5Reply.GENERAL_FAILURE)
            return None
        except asyncio.IncompleteReadError:
            log.warning("SOCKS5 request incomplete read")
            return None
        except Exception as e:
            log.error("SOCKS5 request error: %s", e)
            await self.send_reply(Socks5Reply.GENERAL_FAILURE)
            return None

    async def send_reply(
        self,
        reply: Socks5Reply,
        bind_addr: str = '0.0.0.0',
        bind_port: int = 0
    ) -> None:
        """
        Send SOCKS5 reply to client.

        Args:
            reply: Reply code
            bind_addr: Bind address (for BIND/UDP_ASSOCIATE)
            bind_port: Bind port (for BIND/UDP_ASSOCIATE)
        """
        try:
            # Build reply: VER | REP | RSV | ATYP | BND.ADDR | BND.PORT
            response = bytearray([
                self.SOCKS5_VERSION,
                reply,
                0x00,  # Reserved
                Socks5AddressType.IPV4  # Always use IPv4 for bind address
            ])

            # Add bind address (4 bytes for IPv4)
            addr_parts = bind_addr.split('.')
            if len(addr_parts) == 4:
                response.extend(int(p) for p in addr_parts)
            else:
                response.extend([0, 0, 0, 0])

            # Add bind port (2 bytes, big-endian)
            response.extend(struct.pack('!H', bind_port))

            self.writer.write(bytes(response))
            await self.writer.drain()

            log.debug("SOCKS5 reply sent: %s", reply.name)

        except Exception as e:
            log.error("Failed to send SOCKS5 reply: %s", e)

    async def send_success(self) -> None:
        """Send SOCKS5 success reply."""
        await self.send_reply(Socks5Reply.SUCCESS)

    async def send_failure(self, reply: Socks5Reply = Socks5Reply.GENERAL_FAILURE) -> None:
        """Send SOCKS5 failure reply."""
        await self.send_reply(reply)


def build_socks5_reply(status: int) -> bytes:
    """
    Build SOCKS5 reply packet (legacy function for compatibility).

    Args:
        status: Reply status code

    Returns:
        SOCKS5 reply packet bytes
    """
    return bytes([
        0x05,  # SOCKS5 version
        status,
        0x00,  # Reserved
        0x01,  # IPv4
        0, 0, 0, 0,  # Bind address
        0, 0  # Bind port
    ])
