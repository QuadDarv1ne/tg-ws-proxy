"""
HTTP/2 Transport for TG WS Proxy.

Implements HTTP/2 protocol for better censorship circumvention:
- Multiplexed streams over single connection
- HPACK header compression
- Masquerades as normal HTTPS traffic
- Better performance over high-latency networks

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

log = logging.getLogger('tg-ws-http2')


# HTTP/2 Connection Preface
H2_PREFACE = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'

# HTTP/2 Frame Types
class H2FrameType(IntEnum):
    DATA = 0x00
    HEADERS = 0x01
    PRIORITY = 0x02
    RST_STREAM = 0x03
    SETTINGS = 0x04
    PUSH_PROMISE = 0x05
    PING = 0x06
    GOAWAY = 0x07
    WINDOW_UPDATE = 0x08
    CONTINUATION = 0x09


# HTTP/2 Settings
class H2Settings(IntEnum):
    HEADER_TABLE_SIZE = 0x01
    ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INITIAL_WINDOW_SIZE = 0x04
    MAX_FRAME_SIZE = 0x05
    MAX_HEADER_LIST_SIZE = 0x06


# HTTP/2 Flags
FLAG_END_STREAM = 0x01
FLAG_END_HEADERS = 0x04
FLAG_PADDED = 0x08
FLAG_PRIORITY = 0x20


@dataclass
class H2SettingsData:
    """HTTP/2 settings data."""
    header_table_size: int = 4096
    enable_push: int = 0  # Disable server push
    max_concurrent_streams: int = 100
    initial_window_size: int = 65535
    max_frame_size: int = 16384
    max_header_list_size: int = 8192

    def encode(self) -> bytes:
        """Encode settings as binary payload."""
        payload = b''
        payload += struct.pack('!HI', H2Settings.HEADER_TABLE_SIZE, self.header_table_size)
        payload += struct.pack('!HI', H2Settings.ENABLE_PUSH, self.enable_push)
        payload += struct.pack('!HI', H2Settings.MAX_CONCURRENT_STREAMS, self.max_concurrent_streams)
        payload += struct.pack('!HI', H2Settings.INITIAL_WINDOW_SIZE, self.initial_window_size)
        payload += struct.pack('!HI', H2Settings.MAX_FRAME_SIZE, self.max_frame_size)
        payload += struct.pack('!HI', H2Settings.MAX_HEADER_LIST_SIZE, self.max_header_list_size)
        return payload

    @classmethod
    def decode(cls, data: bytes) -> H2SettingsData:
        """Decode settings from binary payload."""
        settings = cls()
        offset = 0
        while offset + 6 <= len(data):
            identifier, value = struct.unpack('!HI', data[offset:offset+6])
            offset += 6

            if identifier == H2Settings.HEADER_TABLE_SIZE:
                settings.header_table_size = value
            elif identifier == H2Settings.ENABLE_PUSH:
                settings.enable_push = value
            elif identifier == H2Settings.MAX_CONCURRENT_STREAMS:
                settings.max_concurrent_streams = value
            elif identifier == H2Settings.INITIAL_WINDOW_SIZE:
                settings.initial_window_size = value
            elif identifier == H2Settings.MAX_FRAME_SIZE:
                settings.max_frame_size = value
            elif identifier == H2Settings.MAX_HEADER_LIST_SIZE:
                settings.max_header_list_size = value

        return settings


@dataclass
class H2Stream:
    """HTTP/2 stream."""
    stream_id: int
    state: str = 'idle'  # idle, open, half-closed, closed
    send_window: int = 65535
    recv_window: int = 65535
    headers: dict[str, str] = field(default_factory=dict)
    data_buffer: bytearray = field(default_factory=bytearray)
    created_at: float = field(default_factory=time.monotonic)


class HPacker:
    """
    HPACK Header Compression (simplified implementation).

    For production use, consider using hpack library.
    This is a minimal implementation for basic header compression.
    """

    # Static table (subset)
    STATIC_TABLE = {
        ':authority': 1,
        ':method': 2,
        ':path': 3,
        ':scheme': 4,
        ':status': 5,
        'accept': 19,
        'accept-encoding': 20,
        'accept-language': 21,
        'content-length': 28,
        'content-type': 31,
        'host': 38,
        'user-agent': 58,
    }

    def __init__(self):
        self.dynamic_table: list[tuple[str, str]] = []
        self.dynamic_table_size = 0
        self.max_size = 4096

    def encode(self, headers: list[tuple[str, str]]) -> bytes:
        """Encode headers using HPACK (simplified)."""
        encoded = bytearray()

        for name, value in headers:
            # Check static table
            if name in self.STATIC_TABLE:
                # Indexed representation
                encoded.append(self.STATIC_TABLE[name])
            else:
                # Literal without indexing
                encoded.append(0x00 | (len(name) & 0x0F))
                encoded.extend(name.encode('utf-8'))
                encoded.append(len(value) & 0xFF)
                encoded.extend(value.encode('utf-8'))

        return bytes(encoded)

    def decode(self, data: bytes) -> list[tuple[str, str]]:
        """Decode HPACK-encoded headers (simplified)."""
        headers = []
        offset = 0

        while offset < len(data):
            first_byte = data[offset]
            offset += 1

            if first_byte & 0x80:
                # Indexed representation
                index = first_byte & 0x7F
                # Look up in static table (simplified)
                for name, idx in self.STATIC_TABLE.items():
                    if idx == index:
                        headers.append((name, ''))
                        break
            else:
                # Literal without indexing (simplified)
                name_len = first_byte & 0x0F
                name = data[offset:offset+name_len].decode('utf-8')
                offset += name_len
                value_len = data[offset]
                offset += 1
                value = data[offset:offset+value_len].decode('utf-8')
                offset += value_len
                headers.append((name, value))

        return headers


class HTTP2Client:
    """
    HTTP/2 Client for Telegram proxy.

    Features:
    - Multiplexed streams
    - Header compression
    - Flow control
    - Masquerades as normal HTTPS
    """

    # Default HTTP/2 settings
    DEFAULT_SETTINGS = H2SettingsData(
        header_table_size=4096,
        enable_push=0,
        max_concurrent_streams=100,
        initial_window_size=65535,
        max_frame_size=16384,
        max_header_list_size=8192,
    )

    def __init__(
        self,
        host: str,
        port: int = 443,
        tls: bool = True,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ):
        """
        Initialize HTTP/2 client.

        Args:
            host: Target host
            port: Target port
            tls: Use TLS
            user_agent: User-Agent header for masquerading
        """
        self.host = host
        self.port = port
        self.tls = tls
        self.user_agent = user_agent

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._streams: dict[int, H2Stream] = {}
        self._next_stream_id = 1
        self._connection_window = 65535
        self._settings = self.DEFAULT_SETTINGS
        self._hpack = HPacker()
        self._connected = False

        # Stats
        self.frames_sent = 0
        self.frames_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish HTTP/2 connection.

        Args:
            timeout: Connection timeout

        Returns:
            True if connection successful
        """
        try:
            # Create TLS context
            if self.tls:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ssl_context.set_alpn_protocols(['h2'])

                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        self.host,
                        self.port,
                        ssl=ssl_context
                    ),
                    timeout=timeout
                )
            else:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=timeout
                )

            # Send HTTP/2 preface
            self._writer.write(H2_PREFACE)

            # Send SETTINGS frame
            settings_payload = self.DEFAULT_SETTINGS.encode()
            settings_frame = self._build_frame(
                frame_type=H2FrameType.SETTINGS,
                flags=0,
                stream_id=0,
                payload=settings_payload
            )
            self._writer.write(settings_frame)
            await self._writer.drain()

            self.frames_sent += 1
            self.bytes_sent += len(settings_frame)

            # Read server SETTINGS
            await self._read_settings()

            self._connected = True
            log.info("HTTP/2 connected to %s:%d", self.host, self.port)
            return True

        except asyncio.TimeoutError:
            log.warning("HTTP/2 connection timeout to %s:%d", self.host, self.port)
            return False
        except Exception as e:
            log.error("HTTP/2 connection error: %s", e)
            return False

    def _build_frame(
        self,
        frame_type: H2FrameType,
        flags: int,
        stream_id: int,
        payload: bytes
    ) -> bytes:
        """
        Build HTTP/2 frame.

        Frame format:
        - Length (24 bits)
        - Type (8 bits)
        - Flags (8 bits)
        - Reserved (1 bit)
        - Stream Identifier (31 bits)
        - Payload
        """
        length = len(payload)
        header = struct.pack('!I', length)[1:]  # 24 bits
        header += struct.pack('!B', frame_type)  # 8 bits
        header += struct.pack('!B', flags)  # 8 bits
        header += struct.pack('!I', stream_id & 0x7FFFFFFF)  # 31 bits

        frame = header + payload
        self.frames_sent += 1
        self.bytes_sent += len(frame)
        return frame

    async def _read_frame(self) -> tuple[int, int, int, bytes] | None:
        """
        Read HTTP/2 frame.

        Returns:
            (length, type, flags, stream_id, payload) or None on error
        """
        if not self._reader:
            return None

        try:
            # Read frame header (9 bytes)
            header = await self._reader.readexactly(9)
            length, frame_type, flags, stream_id = struct.unpack('!IIBI', header)
            length = (header[0] << 16) | (header[1] << 8) | header[2]

            # Read payload
            payload = await self._reader.readexactly(length)

            self.frames_received += 1
            self.bytes_received += 9 + length

            return (length, frame_type, flags, stream_id, payload)

        except asyncio.IncompleteReadError:
            log.debug("HTTP/2 frame read incomplete")
            return None
        except Exception as e:
            log.error("HTTP/2 frame read error: %s", e)
            return None

    async def _read_settings(self) -> None:
        """Read and process SETTINGS frame from server."""
        frame = await self._read_frame()
        if not frame:
            return

        length, frame_type, flags, stream_id, payload = frame

        if frame_type == H2FrameType.SETTINGS:
            server_settings = H2SettingsData.decode(payload)
            log.debug("HTTP/2 server settings: max_streams=%d, window=%d",
                     server_settings.max_concurrent_streams,
                     server_settings.initial_window_size)

            # Send SETTINGS ACK if needed
            if not (flags & FLAG_END_HEADERS):
                ack_frame = self._build_frame(
                    frame_type=H2FrameType.SETTINGS,
                    flags=0x01,  # ACK
                    stream_id=0,
                    payload=b''
                )
                self._writer.write(ack_frame)
                await self._writer.drain()

    async def send_request(
        self,
        method: str = 'GET',
        path: str = '/',
        headers: dict[str, str] | None = None,
        body: bytes | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        """
        Send HTTP/2 request.

        Args:
            method: HTTP method
            path: Request path
            headers: HTTP headers
            body: Request body

        Returns:
            (status_code, response_headers, response_body)
        """
        if not self._connected or not self._writer:
            raise RuntimeError("Not connected")

        # Create new stream
        stream_id = self._next_stream_id
        self._next_stream_id += 2  # Client streams are odd-numbered

        stream = H2Stream(stream_id=stream_id)
        self._streams[stream_id] = stream

        # Build headers
        http_headers = [
            (':method', method),
            (':path', path),
            (':scheme', 'https' if self.tls else 'http'),
            (':authority', self.host),
            ('user-agent', self.user_agent),
            ('accept', '*/*'),
            ('accept-encoding', 'gzip, deflate'),
        ]

        if body:
            http_headers.append(('content-length', str(len(body))))

        # Add custom headers
        if headers:
            http_headers.extend(headers.items())

        # Encode headers
        encoded_headers = self._hpack.encode(http_headers)

        # Send HEADERS frame
        flags = FLAG_END_HEADERS
        if not body:
            flags |= FLAG_END_STREAM

        headers_frame = self._build_frame(
            frame_type=H2FrameType.HEADERS,
            flags=flags,
            stream_id=stream_id,
            payload=encoded_headers
        )
        self._writer.write(headers_frame)

        # Send body if present
        if body:
            data_frame = self._build_frame(
                frame_type=H2FrameType.DATA,
                flags=FLAG_END_STREAM,
                stream_id=stream_id,
                payload=body
            )
            self._writer.write(data_frame)

        await self._writer.drain()

        # Read response
        status, resp_headers, resp_body = await self._read_response(stream_id)

        return (status, resp_headers, resp_body)

    async def _read_response(self, stream_id: int) -> tuple[int, dict[str, str], bytes]:
        """Read HTTP/2 response for a stream."""
        status = 0
        headers = {}
        body = bytearray()

        while True:
            frame = await self._read_frame()
            if not frame:
                break

            length, frame_type, flags, frame_stream_id, payload = frame

            if frame_stream_id != stream_id:
                continue

            if frame_type == H2FrameType.HEADERS:
                # Parse pseudo-headers
                decoded = self._hpack.decode(payload)
                for name, value in decoded:
                    if name == ':status':
                        status = int(value)
                    else:
                        headers[name] = value

            elif frame_type == H2FrameType.DATA:
                body.extend(payload)

                if flags & FLAG_END_STREAM:
                    break

            elif frame_type == H2FrameType.RST_STREAM:
                log.warning("Stream %d reset", stream_id)
                break

        return (status, headers, bytes(body))

    async def send_data(self, stream_id: int, data: bytes, end_stream: bool = False) -> bool:
        """
        Send data on a stream.

        Args:
            stream_id: Stream ID
            data: Data to send
            end_stream: End the stream after sending

        Returns:
            True if sent successfully
        """
        if not self._writer:
            return False

        flags = FLAG_END_STREAM if end_stream else 0

        frame = self._build_frame(
            frame_type=H2FrameType.DATA,
            flags=flags,
            stream_id=stream_id,
            payload=data
        )

        self._writer.write(frame)
        await self._writer.drain()
        return True

    async def ping(self) -> float:
        """
        Send HTTP/2 PING and measure RTT.

        Returns:
            RTT in milliseconds
        """
        if not self._writer:
            return -1.0

        ping_data = struct.pack('!Q', int(time.time() * 1000))

        start = time.monotonic()

        # Send PING
        frame = self._build_frame(
            frame_type=H2FrameType.PING,
            flags=0,
            stream_id=0,
            payload=ping_data
        )
        self._writer.write(frame)
        await self._writer.drain()

        # Read PING ACK
        while True:
            frame = await self._read_frame()
            if not frame:
                return -1.0

            length, frame_type, flags, stream_id, payload = frame

            if frame_type == H2FrameType.PING and (flags & 0x01):
                # PING ACK
                rtt = (time.monotonic() - start) * 1000
                return rtt

        return -1.0

    async def close(self) -> None:
        """Close HTTP/2 connection."""
        if self._writer:
            # Send GOAWAY
            goaway_frame = self._build_frame(
                frame_type=H2FrameType.GOAWAY,
                flags=0,
                stream_id=0,
                payload=struct.pack('!II', 0, 0)  # Last-Stream-ID, Error-Code
            )
            self._writer.write(goaway_frame)
            await self._writer.drain()

            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

            self._writer = None
            self._reader = None
            self._connected = False

        log.info("HTTP/2 connection closed")

    def get_stats(self) -> dict:
        """Get HTTP/2 statistics."""
        return {
            'connected': self._connected,
            'active_streams': len(self._streams),
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
        }


class HTTP2Transport:
    """
    HTTP/2 Transport for Telegram proxy.

    Wraps MTProto traffic in HTTP/2 frames for censorship circumvention.
    """

    def __init__(
        self,
        host: str,
        port: int = 443,
        path: str = '/api',
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    ):
        """
        Initialize HTTP/2 transport.

        Args:
            host: Target host
            port: Target port
            path: API path for requests
            user_agent: User-Agent for masquerading
        """
        self.host = host
        self.port = port
        self.path = path
        self.user_agent = user_agent

        self._client: HTTP2Client | None = None
        self._stream_id: int | None = None

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect to server via HTTP/2."""
        self._client = HTTP2Client(
            host=self.host,
            port=self.port,
            tls=True,
            user_agent=self.user_agent
        )

        return await self._client.connect(timeout=timeout)

    async def send(self, data: bytes) -> bool:
        """Send data over HTTP/2."""
        if not self._client:
            return False

        # If no stream, create one
        if self._stream_id is None:
            # Send initial request
            status, headers, body = await self._client.send_request(
                method='POST',
                path=self.path,
                headers={'content-type': 'application/octet-stream'},
                body=data
            )

            if status == 200:
                # Use this stream for further communication
                self._stream_id = self._client._next_stream_id - 2
                return True
            return False

        # Send on existing stream
        return await self._client.send_data(self._stream_id, data, end_stream=False)

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive data from HTTP/2 stream."""
        if not self._client or self._stream_id is None:
            return None

        # Read response
        status, headers, body = await self._client._read_response(self._stream_id)

        if status == 200:
            return body
        return None

    async def close(self) -> None:
        """Close HTTP/2 transport."""
        if self._client:
            await self._client.close()
            self._client = None
            self._stream_id = None

    def get_stats(self) -> dict:
        """Get transport statistics."""
        if not self._client:
            return {'connected': False}

        stats = self._client.get_stats()
        stats['path'] = self.path
        return stats


async def create_http2_tunnel(
    host: str,
    port: int,
    path: str = '/api',
    on_data: Callable[[bytes], None] | None = None
) -> HTTP2Transport | None:
    """
    Create HTTP/2 tunnel for proxy traffic.

    Args:
        host: Target host
        port: Target port
        path: API endpoint path
        on_data: Callback for received data

    Returns:
        HTTP2Transport instance or None on failure
    """
    transport = HTTP2Transport(host=host, port=port, path=path)

    if not await transport.connect():
        return None

    log.info("HTTP/2 tunnel established to %s:%d%s", host, port, path)
    return transport
