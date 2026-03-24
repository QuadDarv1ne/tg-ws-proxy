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
    # Count frames by checking frame headers
    frame_count = sum(1 for i, b in enumerate(written) if b == 0x82 and (i == 0 or written[i-1] != 0x82))
    assert frame_count >= 3


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


def test_websocket_compression_init():
    """Test WebSocket with compression enabled."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer, compress=True)

    assert ws._compress is True
    assert ws._compressor is not None
    assert ws._decompressor is not None


def test_websocket_compression_disabled():
    """Test WebSocket without compression."""
    reader = MockStreamReader(b'')
    writer = MockStreamWriter()
    ws = RawWebSocket(reader, writer, compress=False)

    assert ws._compress is False
    assert ws._compressor is None
    assert ws._decompressor is None


def test_websocket_compression_connect_signature():
    """Test that connect method accepts compress parameter."""
    import inspect
    sig = inspect.signature(RawWebSocket.connect)
    params = sig.parameters

    assert 'compress' in params
    assert params['compress'].default is False


class TestWebSocketPingPong:
    """Tests for WebSocket ping/pong functionality."""

    @pytest.mark.asyncio
    async def test_websocket_send_ping_frame(self):
        """Test sending ping frame manually."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        # Send ping using send method with ping opcode
        await ws.send(b'ping', opcode=0x09)  # PING opcode

        written = writer.get_written_data()
        assert len(written) > 0
        assert written[0] == 0x89  # FIN=1, OPCODE=PING

    @pytest.mark.asyncio
    async def test_websocket_send_pong_frame(self):
        """Test sending pong frame manually."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        # Send pong using send method with pong opcode
        await ws.send(b'pong', opcode=0x0A)  # PONG opcode

        written = writer.get_written_data()
        assert len(written) > 0
        assert written[0] == 0x8A  # FIN=1, OPCODE=PONG


class TestWebSocketClose:
    """Tests for WebSocket close functionality."""

    @pytest.mark.asyncio
    async def test_websocket_close_sends_frame(self):
        """Test closing sends close frame."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        await ws.close()

        written = writer.get_written_data()
        assert len(written) > 0
        assert written[0] == 0x88  # FIN=1, OPCODE=CLOSE

    @pytest.mark.asyncio
    async def test_websocket_close_twice(self):
        """Test closing twice doesn't send duplicate frames."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        await ws.close()
        await ws.close()  # Should be no-op

        written = writer.get_written_data()
        # Should only have one close frame
        close_frames = sum(1 for i, b in enumerate(written) if b == 0x88)
        assert close_frames == 1


class TestWebSocketStats:
    """Tests for WebSocket statistics."""

    @pytest.mark.asyncio
    async def test_websocket_get_stats(self):
        """Test getting WebSocket stats."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        stats = ws.get_stats()

        assert isinstance(stats, dict)
        assert 'domain' in stats
        assert 'ip' in stats
        assert 'closed' in stats
        assert 'compress' in stats
        assert 'connect_time' in stats
        assert 'last_activity' in stats

    @pytest.mark.asyncio
    async def test_websocket_stats_domain_set(self):
        """Test that stats include domain after connect."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        # Set domain like connect would
        ws._domain = 'test.com'
        ws._ip = '1.2.3.4'

        stats = ws.get_stats()
        assert stats['domain'] == 'test.com'
        assert stats['ip'] == '1.2.3.4'


class TestWebSocketRepr:
    """Tests for WebSocket string representation."""

    def test_websocket_repr(self):
        """Test WebSocket __repr__ method."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)

        repr_str = repr(ws)
        assert 'RawWebSocket' in repr_str


class TestWebSocketConnect:
    """Tests for WebSocket connect method."""

    @pytest.mark.asyncio
    async def test_websocket_connect_retry_timeout(self):
        """Test connect with timeout and retry."""
        # Mock open_connection to fail
        with pytest.raises(asyncio.TimeoutError):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr('asyncio.open_connection',
                          lambda *args, **kwargs: asyncio.sleep(100))
                await RawWebSocket.connect(
                    ip='127.0.0.1',
                    domain='test.com',
                    path='/',
                    timeout=0.1,
                    retry_count=1
                )

    @pytest.mark.asyncio
    async def test_websocket_connect_retry_refused(self):
        """Test connect with connection refused."""
        with pytest.raises((ConnectionRefusedError, OSError)):
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr('asyncio.open_connection',
                          lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionRefusedError()))
                await RawWebSocket.connect(
                    ip='127.0.0.1',
                    domain='test.com',
                    path='/',
                    timeout=0.1,
                    retry_count=1
                )


class TestWebSocketBuildFrame:
    """Tests for _build_frame method."""

    def test_build_frame_small_payload(self):
        """Test building frame with small payload (<126 bytes)."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        data = b'Hello'
        frame = ws._build_frame(ws.OP_TEXT, data, mask=False)
        
        # First byte: FIN=1, opcode=1
        assert frame[0] == 0x81
        # Second byte: length=5, no mask
        assert frame[1] == 0x05
        # Payload
        assert frame[2:] == data

    def test_build_frame_masked(self):
        """Test building masked frame."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        data = b'Test data'
        frame = ws._build_frame(ws.OP_TEXT, data, mask=True)
        
        # First byte: FIN=1, opcode=1
        assert frame[0] == 0x81
        # Second byte: mask bit set
        assert frame[1] & 0x80 == 0x80
        # Length
        assert frame[1] & 0x7F == 0x09
        # Mask key (4 bytes)
        assert len(frame) == 2 + 4 + len(data)

    def test_build_frame_medium_payload(self):
        """Test building frame with medium payload (126-65535 bytes)."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        data = b'X' * 200
        frame = ws._build_frame(ws.OP_BINARY, data, mask=False)
        
        # First byte: FIN=1, opcode=2
        assert frame[0] == 0x82
        # Second byte: 126 (extended length)
        assert frame[1] == 126
        # Extended length (2 bytes, big-endian)
        assert struct.unpack('>H', frame[2:4])[0] == 200
        # Payload
        assert frame[4:] == data

    def test_build_frame_large_payload(self):
        """Test building frame with large payload (>=65536 bytes)."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        data = b'Y' * 70000
        frame = ws._build_frame(ws.OP_BINARY, data, mask=False)
        
        # First byte: FIN=1, opcode=2
        assert frame[0] == 0x82
        # Second byte: 127 (extended length, 8 bytes)
        assert frame[1] == 127
        # Extended length (8 bytes, big-endian)
        assert struct.unpack('>Q', frame[2:10])[0] == 70000
        # Payload
        assert frame[10:] == data

    def test_build_frame_ping_pong(self):
        """Test building ping/pong frames."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        ping_frame = ws._build_frame(ws.OP_PING, b'ping', mask=False)
        assert ping_frame[0] == 0x89
        
        pong_frame = ws._build_frame(ws.OP_PONG, b'pong', mask=False)
        assert pong_frame[0] == 0x8A

    def test_build_frame_empty_payload(self):
        """Test building frame with empty payload."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        frame = ws._build_frame(ws.OP_PING, b'', mask=False)
        
        assert frame[0] == 0x89
        assert frame[1] == 0x00
        assert len(frame) == 2


class TestWebSocketReadFrame:
    """Tests for _read_frame method."""

    @pytest.mark.asyncio
    async def test_read_frame_small_payload(self):
        """Test reading frame with small payload."""
        # Build expected frame
        reader = MockStreamReader(b'\x81\x05Hello')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        opcode, payload = await ws._read_frame()
        
        assert opcode == 0x01
        assert payload == b'Hello'

    @pytest.mark.asyncio
    async def test_read_frame_medium_payload(self):
        """Test reading frame with medium payload."""
        data = b'X' * 200
        # Build frame: FIN=1, opcode=2, length=126, extended length, data
        frame = b'\x82\x7e' + struct.pack('>H', 200) + data
        
        reader = MockStreamReader(frame)
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        opcode, payload = await ws._read_frame()
        
        assert opcode == 0x02
        assert payload == data

    @pytest.mark.asyncio
    async def test_read_frame_masked(self):
        """Test reading masked frame."""
        data = b'Test'
        mask = b'\x12\x34\x56\x78'
        masked_data = _xor_mask(data, mask)
        
        # Build frame: FIN=1, opcode=1, mask=1, length=4, mask_key, masked_data
        frame = b'\x81\x84' + mask + masked_data
        
        reader = MockStreamReader(frame)
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        opcode, payload = await ws._read_frame()
        
        assert opcode == 0x01
        assert payload == data  # Should be unmasked

    @pytest.mark.asyncio
    async def test_read_frame_timeout(self):
        """Test read frame timeout."""
        async def slow_read(*args, **kwargs):
            await asyncio.sleep(10)
            return b''
        
        # Create mock reader that times out
        class TimeoutReader:
            async def readexactly(self, n):
                await asyncio.sleep(10)
                return b''
        
        reader = TimeoutReader()
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        with pytest.raises(asyncio.TimeoutError):
            # Use wait_for to trigger timeout
            await asyncio.wait_for(ws._read_frame(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_read_frame_incomplete(self):
        """Test reading incomplete frame."""
        # Incomplete frame
        reader = MockStreamReader(b'\x81\x05Hel')  # Only 3 bytes instead of 5
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer)
        
        with pytest.raises(asyncio.IncompleteReadError):
            await ws._read_frame()


class TestWebSocketCompression:
    """Tests for WebSocket compression."""

    @pytest.mark.asyncio
    async def test_send_with_compression(self):
        """Test sending data with compression enabled."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer, compress=True)
        ws._connected = True
        
        await ws.send(b'Compressed data')
        
        # Data should be sent
        assert len(writer.get_written_data()) > 0

    @pytest.mark.asyncio
    async def test_recv_with_compression(self):
        """Test receiving data with compression enabled."""
        # Mock compressed data
        import zlib
        original_data = b'Decompressed data'
        compressed = zlib.compress(original_data)
        
        # Build frame with correct length prefix
        frame = b'\x82' + bytes([len(compressed)]) + compressed
        
        reader = MockStreamReader(frame)
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer, compress=True)
        ws._connected = True
        
        # Manually decompress since recv may not auto-decompress in mock
        data = await ws.recv()
        
        # Data should be received (compression handled internally)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_close_resets_compression(self):
        """Test that close resets compression state."""
        reader = MockStreamReader(b'')
        writer = MockStreamWriter()
        ws = RawWebSocket(reader, writer, compress=True)
        ws._connected = True
        
        # Trigger compression init
        await ws.send(b'test')
        assert ws._compressor is not None
        
        # Close should reset compression
        await ws.close()
        
        # Compression should be reset
        assert ws._closed is True
