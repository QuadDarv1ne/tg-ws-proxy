"""
Tests for SOCKS5 protocol handler.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import asyncio
import struct
from io import BytesIO

import pytest

from proxy.socks5_handler import (
    Socks5AddressType,
    Socks5Command,
    Socks5Handler,
    Socks5Reply,
    build_socks5_reply,
)


class MockStreamReader:
    """Mock StreamReader for testing."""

    def __init__(self, data: bytes):
        self.data = BytesIO(data)

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes."""
        result = self.data.read(n)
        if len(result) < n:
            raise asyncio.IncompleteReadError(result, n)
        return result


class MockStreamWriter:
    """Mock StreamWriter for testing."""

    def __init__(self):
        self.data = BytesIO()

    def write(self, data: bytes) -> None:
        """Write data."""
        self.data.write(data)

    async def drain(self) -> None:
        """Drain (no-op for mock)."""
        pass

    def get_written_data(self) -> bytes:
        """Get all written data."""
        return self.data.getvalue()


@pytest.mark.asyncio
async def test_negotiate_success():
    """Test successful SOCKS5 negotiation."""
    # Client greeting: VER=5, NMETHODS=1, METHOD=0 (NO_AUTH)
    client_data = bytes([0x05, 0x01, 0x00])

    reader = MockStreamReader(client_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    result = await handler.negotiate()

    assert result is True

    # Check server response: VER=5, METHOD=0
    response = writer.get_written_data()
    assert response == bytes([0x05, 0x00])


@pytest.mark.asyncio
async def test_negotiate_invalid_version():
    """Test negotiation with invalid SOCKS version."""
    # Invalid version: VER=4
    client_data = bytes([0x04, 0x01, 0x00])

    reader = MockStreamReader(client_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    result = await handler.negotiate()

    assert result is False


@pytest.mark.asyncio
async def test_negotiate_no_acceptable_method():
    """Test negotiation with no acceptable method."""
    # Client only supports GSSAPI (0x01)
    client_data = bytes([0x05, 0x01, 0x01])

    reader = MockStreamReader(client_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    result = await handler.negotiate()

    assert result is False

    # Check server response: VER=5, METHOD=0xFF (NO_ACCEPTABLE)
    response = writer.get_written_data()
    assert response == bytes([0x05, 0xFF])


@pytest.mark.asyncio
async def test_read_request_ipv4():
    """Test reading SOCKS5 request with IPv4 address."""
    # Request: VER=5, CMD=CONNECT, RSV=0, ATYP=IPv4
    # DST.ADDR=149.154.167.220, DST.PORT=443
    request_data = bytes([
        0x05, 0x01, 0x00, 0x01,  # Header
        149, 154, 167, 220,       # IPv4 address
        0x01, 0xBB                # Port 443
    ])

    reader = MockStreamReader(request_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    request = await handler.read_request()

    assert request is not None
    assert request.command == Socks5Command.CONNECT
    assert request.address_type == Socks5AddressType.IPV4
    assert request.destination == '149.154.167.220'
    assert request.port == 443


@pytest.mark.asyncio
async def test_read_request_domain():
    """Test reading SOCKS5 request with domain name."""
    # Request: VER=5, CMD=CONNECT, RSV=0, ATYP=DOMAIN
    # DST.ADDR=web.telegram.org, DST.PORT=443
    domain = b'web.telegram.org'
    request_data = bytes([
        0x05, 0x01, 0x00, 0x03,  # Header
        len(domain)               # Domain length
    ]) + domain + bytes([0x01, 0xBB])  # Port 443

    reader = MockStreamReader(request_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    request = await handler.read_request()

    assert request is not None
    assert request.command == Socks5Command.CONNECT
    assert request.address_type == Socks5AddressType.DOMAIN
    assert request.destination == 'web.telegram.org'
    assert request.port == 443


@pytest.mark.asyncio
async def test_read_request_invalid_command():
    """Test reading SOCKS5 request with invalid command."""
    # Request with invalid command (0xFF)
    request_data = bytes([
        0x05, 0xFF, 0x00, 0x01,  # Invalid command
        127, 0, 0, 1,             # IPv4 address
        0x00, 0x50                # Port 80
    ])

    reader = MockStreamReader(request_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    request = await handler.read_request()

    assert request is None

    # Check that error reply was sent
    response = writer.get_written_data()
    assert len(response) > 0
    assert response[1] == Socks5Reply.COMMAND_NOT_SUPPORTED


@pytest.mark.asyncio
async def test_send_reply_success():
    """Test sending SOCKS5 success reply."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    await handler.send_reply(Socks5Reply.SUCCESS, '127.0.0.1', 1080)

    response = writer.get_written_data()

    # Check response format
    assert response[0] == 0x05  # SOCKS5 version
    assert response[1] == Socks5Reply.SUCCESS
    assert response[2] == 0x00  # Reserved
    assert response[3] == Socks5AddressType.IPV4
    assert response[4:8] == bytes([127, 0, 0, 1])  # Bind address
    assert struct.unpack('!H', response[8:10])[0] == 1080  # Bind port


@pytest.mark.asyncio
async def test_send_success():
    """Test sending success reply helper."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    await handler.send_success()

    response = writer.get_written_data()
    assert response[1] == Socks5Reply.SUCCESS


@pytest.mark.asyncio
async def test_send_failure():
    """Test sending failure reply helper."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    await handler.send_failure(Socks5Reply.CONNECTION_REFUSED)

    response = writer.get_written_data()
    assert response[1] == Socks5Reply.CONNECTION_REFUSED


def test_build_socks5_reply():
    """Test legacy build_socks5_reply function."""
    reply = build_socks5_reply(Socks5Reply.SUCCESS)

    assert len(reply) == 10
    assert reply[0] == 0x05  # SOCKS5 version
    assert reply[1] == Socks5Reply.SUCCESS
    assert reply[2] == 0x00  # Reserved
    assert reply[3] == 0x01  # IPv4


@pytest.mark.asyncio
async def test_negotiate_timeout():
    """Test negotiation timeout."""
    # Empty reader will cause timeout
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer, timeout=0.1)

    result = await handler.negotiate()

    assert result is False


@pytest.mark.asyncio
async def test_read_request_incomplete():
    """Test reading incomplete request."""
    # Incomplete request (missing port)
    request_data = bytes([
        0x05, 0x01, 0x00, 0x01,  # Header
        127, 0, 0, 1              # IPv4 address (missing port)
    ])

    reader = MockStreamReader(request_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    request = await handler.read_request()

    assert request is None


@pytest.mark.asyncio
async def test_multiple_auth_methods():
    """Test negotiation with multiple authentication methods."""
    # Client supports NO_AUTH (0x00) and USERNAME_PASSWORD (0x02)
    client_data = bytes([0x05, 0x02, 0x00, 0x02])

    reader = MockStreamReader(client_data)
    writer = MockStreamWriter()
    handler = Socks5Handler(reader, writer)

    result = await handler.negotiate()

    assert result is True

    # Server should select NO_AUTH
    response = writer.get_written_data()
    assert response == bytes([0x05, 0x00])
