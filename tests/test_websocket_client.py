"""
Tests for WebSocket client.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import asyncio
import struct
from io import BytesIO

import pytest

from proxy.websocket_client import (
    RawWebSocket,
    WsHandshakeError,
    _xor_mask,
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

    async def readline(self) -> bytes:
        """Read a line."""
        line = b''
        while True:
            char = self.data.read(1)
            if not char:
                break
            line += char
            if char == b'\n':
                break
        return line


class MockStreamWriter:
    """Mock StreamWriter for testing."""

    def __init__(self):
        self.data = BytesIO()
        self.closed = False

    def write(self, data: bytes) -> None:
        """Write data."""
        if not self.closed:
            self.data.write(data)

    async def drain(self) -> None:
        """Drain (no-op for mock)."""
        pass

    def close(self) -> None:
        """Close writer."""
        self.closed = True

    async def wait_closed(self) -> None:
        """Wait for close (no-op for mock)."""
        pass

    def get_written_data(self) -> bytes:
        """Get all written data."""
        return self.data.getvalue()


def test_xor_mask():
    """Test XOR masking function."""
    data = b'Hello, World!'
    mask = b'\x12\x34\x56\x78'

    masked = _xor_mask(data, mask)
    assert masked != data

    # Masking twice should return original
    unmasked = _xor_mask(masked, mask)
    assert unmasked == data


def test_xor_mask_empty():
    """Test XOR masking with empty data."""
    result = _xor_mask(b'', b'\x00\x00\x00\x00')
    assert result == b''


@pytest.mark.asyncio
async def test_websocket_send():
    """Test sending WebSocket frame."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    await ws.send(b'test data')

    written = writer.get_written_data()
    assert len(written) > 0

    # Check frame structure
    assert written[0] == 0x82  # FIN=1, OPCODE=BINARY
    assert written[1] & 0x80 == 0x80  # MASK=1


@pytest.mark.asyncio
async def test_websocket_send_batch():
    """Test sending multiple WebSocket frames."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    parts = [b'part1', b'part2', b'part3']
    await ws.send_batch(parts)

    written = writer.get_written_data()
    assert len(written) > 0

    # Should contain multiple frames
    # Each frame starts with 0x82 (FIN=1, OPCODE=BINARY)
    assert written.count(b'\x82') == 3


@pytest.mark.asyncio
async def test_websocket_recv_binary():
    """Test receiving binary WebSocket frame."""
    # Build a binary frame: FIN=1, OPCODE=BINARY, no mask, payload="test"
    payload = b'test'
    frame = bytes([
        0x82,  # FIN=1, OPCODE=BINARY
        len(payload)  # Length
    ]) + payload

    reader = MockStreamReader(frame)
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    data = await ws.recv()
    assert data == payload


@pytest.mark.asyncio
async def test_websocket_recv_close():
    """Test receiving close frame."""
    # Build a close frame
    frame = bytes([
        0x88,  # FIN=1, OPCODE=CLOSE
        0x00   # Length=0
    ])

    reader = MockStreamReader(frame)
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    data = await ws.recv()
    assert data is None
    assert ws._closed


@pytest.mark.asyncio
async def test_websocket_recv_ping():
    """Test receiving ping frame (should auto-respond with pong)."""
    # Build ping frame followed by binary frame
    ping_frame = bytes([
        0x89,  # FIN=1, OPCODE=PING
        0x04   # Length=4
    ]) + b'ping'

    binary_frame = bytes([
        0x82,  # FIN=1, OPCODE=BINARY
        0x04   # Length=4
    ]) + b'data'

    reader = MockStreamReader(ping_frame + binary_frame)
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    # Should skip ping and return binary data
    data = await ws.recv()
    assert data == b'data'

    # Check that pong was sent
    written = writer.get_written_data()
    assert len(written) > 0
    assert written[0] == 0x8A  # FIN=1, OPCODE=PONG


@pytest.mark.asyncio
async def test_websocket_close():
    """Test closing WebSocket."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    await ws.close()

    assert ws._closed
    assert writer.closed

    # Check that close frame was sent
    written = writer.get_written_data()
    assert len(written) > 0
    assert written[0] == 0x88  # FIN=1, OPCODE=CLOSE


@pytest.mark.asyncio
async def test_websocket_send_after_close():
    """Test sending after close raises error."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    await ws.close()

    with pytest.raises(ConnectionError, match="WebSocket closed"):
        await ws.send(b'test')


@pytest.mark.asyncio
async def test_websocket_recv_incomplete():
    """Test receiving incomplete frame."""
    # Incomplete frame (missing payload)
    frame = bytes([
        0x82,  # FIN=1, OPCODE=BINARY
        0x04   # Length=4 (but no payload)
    ])

    reader = MockStreamReader(frame)
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    data = await ws.recv()
    assert data is None
    assert ws._closed


@pytest.mark.asyncio
async def test_websocket_build_frame_small():
    """Test building small frame (<126 bytes)."""
    payload = b'small'
    frame = RawWebSocket._build_frame(RawWebSocket.OP_BINARY, payload, mask=False)

    assert frame[0] == 0x82  # FIN=1, OPCODE=BINARY
    assert frame[1] == len(payload)
    assert frame[2:] == payload


@pytest.mark.asyncio
async def test_websocket_build_frame_medium():
    """Test building medium frame (126-65535 bytes)."""
    payload = b'x' * 200
    frame = RawWebSocket._build_frame(RawWebSocket.OP_BINARY, payload, mask=False)

    assert frame[0] == 0x82  # FIN=1, OPCODE=BINARY
    assert frame[1] == 126   # Extended length indicator
    length = struct.unpack('>H', frame[2:4])[0]
    assert length == 200


@pytest.mark.asyncio
async def test_websocket_build_frame_large():
    """Test building large frame (>65535 bytes)."""
    payload = b'x' * 70000
    frame = RawWebSocket._build_frame(RawWebSocket.OP_BINARY, payload, mask=False)

    assert frame[0] == 0x82  # FIN=1, OPCODE=BINARY
    assert frame[1] == 127   # Extended length indicator
    length = struct.unpack('>Q', frame[2:10])[0]
    assert length == 70000


def test_ws_handshake_error():
    """Test WsHandshakeError exception."""
    error = WsHandshakeError(404, "Not Found", {"location": "/new"}, "/new")

    assert error.status_code == 404
    assert error.status_line == "Not Found"
    assert error.location == "/new"
    assert not error.is_redirect


def test_ws_handshake_error_redirect():
    """Test WsHandshakeError with redirect."""
    error = WsHandshakeError(302, "Found", {"location": "/redirect"}, "/redirect")

    assert error.is_redirect
    assert error.location == "/redirect"


@pytest.mark.asyncio
async def test_websocket_recv_pong():
    """Test receiving pong frame (should be ignored)."""
    # Build pong frame followed by binary frame
    pong_frame = bytes([
        0x8A,  # FIN=1, OPCODE=PONG
        0x00   # Length=0
    ])

    binary_frame = bytes([
        0x82,  # FIN=1, OPCODE=BINARY
        0x04   # Length=4
    ]) + b'data'

    reader = MockStreamReader(pong_frame + binary_frame)
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer)

    # Should skip pong and return binary data
    data = await ws.recv()
    assert data == b'data'
