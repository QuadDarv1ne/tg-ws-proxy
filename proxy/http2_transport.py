"""
HTTP/2 Transport for TG WS Proxy.

Provides HTTP/2 as an alternative transport layer when WebSocket is blocked.
Uses h2c (HTTP/2 Cleartext) or h2 (HTTP/2 over TLS) based on availability.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import struct
import time
from typing import Any

log = logging.getLogger("tg-ws-http2")

# HTTP/2 protocol constants
H2_MAGIC = b'PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n'
H2_FRAME_DATA = 0x00
H2_FRAME_HEADERS = 0x01
H2_FRAME_PRIORITY = 0x02
H2_FRAME_RST_STREAM = 0x03
H2_FRAME_SETTINGS = 0x04
H2_FRAME_PUSH_PROMISE = 0x05
H2_FRAME_PING = 0x06
H2_FRAME_GOAWAY = 0x07
H2_FRAME_WINDOW_UPDATE = 0x08
H2_FRAME_CONTINUATION = 0x09

H2_FLAG_END_STREAM = 0x01
H2_FLAG_END_HEADERS = 0x04
H2_FLAG_PADDED = 0x08
H2_FLAG_PRIORITY = 0x20

# HTTP/2 settings
H2_SETTINGS_HEADER_TABLE_SIZE = 0x01
H2_SETTINGS_ENABLE_PUSH = 0x02
H2_SETTINGS_MAX_CONCURRENT_STREAMS = 0x03
H2_SETTINGS_INITIAL_WINDOW_SIZE = 0x04
H2_SETTINGS_MAX_FRAME_SIZE = 0x05
H2_SETTINGS_MAX_HEADER_LIST_SIZE = 0x06

# Default settings
DEFAULT_SETTINGS = {
    H2_SETTINGS_HEADER_TABLE_SIZE: 4096,
    H2_SETTINGS_ENABLE_PUSH: 0,
    H2_SETTINGS_MAX_CONCURRENT_STREAMS: 100,
    H2_SETTINGS_INITIAL_WINDOW_SIZE: 65535,
    H2_SETTINGS_MAX_FRAME_SIZE: 16384,
    H2_SETTINGS_MAX_HEADER_LIST_SIZE: 8192,
}


class HTTP2Error(Exception):
    """HTTP/2 protocol error."""
    pass


class HTTP2Connection:
    """
    HTTP/2 connection handler.

    Implements HTTP/2 framing layer for tunneling Telegram traffic.
    """

    def __init__(
        self,
        host: str,
        port: int,
        use_tls: bool = True,
        ssl_context: ssl.SSLContext | None = None,
    ):
        """
        Initialize HTTP/2 connection.

        Args:
            host: Target host
            port: Target port
            use_tls: Use TLS (h2) or cleartext (h2c)
            ssl_context: Optional SSL context
        """
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.ssl_context = ssl_context

        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False

        # Connection state
        self.next_stream_id = 1  # Client-initiated streams start at 1
        self.local_settings = DEFAULT_SETTINGS.copy()
        self.remote_settings = DEFAULT_SETTINGS.copy()
        self.local_window = 65535
        self.remote_window = 65535

        # Stream state
        self.streams: dict[int, dict[str, Any]] = {}
        self.response_buffers: dict[int, bytes] = {}

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish HTTP/2 connection.

        Args:
            timeout: Connection timeout

        Returns:
            True if successful
        """
        try:
            # Create SSL context if needed
            if self.use_tls and not self.ssl_context:
                self.ssl_context = ssl.create_default_context()
                self.ssl_context.check_hostname = False
                self.ssl_context.verify_mode = ssl.CERT_NONE
                self.ssl_context.set_alpn_protocols(['h2'])

            # Connect
            if self.use_tls:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        self.host,
                        self.port,
                        ssl=self.ssl_context,
                        server_hostname=self.host,
                    ),
                    timeout=timeout,
                )
            else:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=timeout,
                )

            # Send connection preface
            if not self.use_tls:
                # h2c: send magic preface
                self.writer.write(H2_MAGIC)

            # Send SETTINGS frame
            settings_frame = self._build_settings_frame()
            self.writer.write(settings_frame)
            await self.writer.drain()

            # Read server preface and SETTINGS
            if not self.use_tls:
                preface = await asyncio.wait_for(
                    self.reader.readexactly(len(H2_MAGIC)),
                    timeout=timeout,
                )
                if preface != H2_MAGIC:
                    log.error("Invalid server preface: %s", preface)
                    return False

            # Read SETTINGS frame
            await self._read_settings_frame(timeout)

            self.connected = True
            log.info("HTTP/2 connection established to %s:%d", self.host, self.port)
            return True

        except asyncio.TimeoutError:
            log.warning("HTTP/2 connection timeout to %s:%d", self.host, self.port)
        except ssl.SSLError as exc:
            log.error("HTTP/2 SSL error: %s", exc)
        except Exception as exc:
            log.error("HTTP/2 connection error: %s", exc)

        return False

    def _build_settings_frame(self) -> bytes:
        """Build SETTINGS frame with local settings."""
        payload = b''
        for setting_id, value in self.local_settings.items():
            payload += struct.pack('>H', setting_id)
            payload += struct.pack('>I', value)

        return self._build_frame(H2_FRAME_SETTINGS, payload)

    async def _read_settings_frame(self, timeout: float) -> None:
        """Read and process SETTINGS frame from server."""
        # Read frame header (9 bytes)
        header = await asyncio.wait_for(
            self.reader.readexactly(9),  # type: ignore
            timeout=timeout,
        )

        length = struct.unpack('>I', b'\x00' + header[:3])[0]
        frame_type = header[3]
        flags = header[4]
        _ = struct.unpack('>I', header[5:9])[0] & 0x7FFFFFFF

        if frame_type != H2_FRAME_SETTINGS:
            raise HTTP2Error(f"Expected SETTINGS frame, got {frame_type}")

        # Read payload
        payload = await asyncio.wait_for(
            self.reader.readexactly(length),  # type: ignore
            timeout=timeout,
        )

        # Parse settings
        offset = 0
        while offset < len(payload):
            setting_id = struct.unpack('>H', payload[offset:offset+2])[0]
            value = struct.unpack('>I', payload[offset+2:offset+6])[0]
            self.remote_settings[setting_id] = value
            offset += 6

        log.debug("Remote HTTP/2 settings: %s", self.remote_settings)

        # Send SETTINGS ACK if needed
        if flags & H2_FLAG_END_HEADERS == 0:
            ack_frame = self._build_frame(H2_FRAME_SETTINGS, b'', flags=H2_FLAG_END_HEADERS)
            self.writer.write(ack_frame)
            await self.writer.drain()

    def _build_frame(
        self,
        frame_type: int,
        payload: bytes,
        flags: int = 0,
        stream_id: int = 0,
    ) -> bytes:
        """Build HTTP/2 frame."""
        # Frame header: 9 bytes
        header = struct.pack('>I', len(payload))[1:]  # 3 bytes length
        header += struct.pack('B', frame_type)  # 1 byte type
        header += struct.pack('B', flags)  # 1 byte flags
        header += struct.pack('>I', stream_id & 0x7FFFFFFF)  # 4 bytes stream ID

        return header + payload

    async def create_stream(
        self,
        method: str = 'POST',
        path: str = '/apiws',
        headers: dict[str, str] | None = None,
    ) -> int:
        """
        Create new HTTP/2 stream.

        Args:
            method: HTTP method
            path: Request path
            headers: Additional headers

        Returns:
            Stream ID
        """
        if not self.connected:
            raise HTTP2Error("Not connected")

        stream_id = self.next_stream_id
        self.next_stream_id += 2

        # Build headers
        request_headers = [
            (':method', method),
            (':path', path),
            (':scheme', 'https' if self.use_tls else 'http'),
            (':authority', self.host),
        ]

        if headers:
            request_headers.extend(headers.items())

        # Encode headers (simple HPACK-like encoding)
        header_block = self._encode_headers(request_headers)

        # Send HEADERS frame
        headers_frame = self._build_frame(
            H2_FRAME_HEADERS,
            header_block,
            flags=H2_FLAG_END_HEADERS,
            stream_id=stream_id,
        )

        self.writer.write(headers_frame)  # type: ignore
        await self.writer.drain()

        # Initialize stream state
        self.streams[stream_id] = {
            'state': 'open',
            'local_window': self.local_settings[H2_SETTINGS_INITIAL_WINDOW_SIZE],
            'remote_window': self.remote_settings[H2_SETTINGS_INITIAL_WINDOW_SIZE],
        }
        self.response_buffers[stream_id] = b''

        return stream_id

    def _encode_headers(self, headers: list[tuple[str, str]]) -> bytes:
        """
        Encode headers (simplified HPACK).

        For production use, implement full HPACK compression.
        """
        # Simple encoding without compression
        # Each header: 1 byte name length + name + 1 byte value length + value
        encoded = b''
        for name, value in headers:
            encoded += bytes([len(name)]) + name.encode()
            encoded += bytes([len(value)]) + value.encode()
        return encoded

    async def send_data(
        self,
        stream_id: int,
        data: bytes,
        end_stream: bool = False,
    ) -> None:
        """
        Send data on stream.

        Args:
            stream_id: Stream ID
            data: Data to send
            end_stream: End the stream after sending
        """
        if not self.connected:
            raise HTTP2Error("Not connected")
        if stream_id not in self.streams:
            raise HTTP2Error(f"Stream {stream_id} not found")

        # Split into frames based on MAX_FRAME_SIZE
        max_size = self.remote_settings[H2_SETTINGS_MAX_FRAME_SIZE]
        offset = 0

        while offset < len(data):
            chunk = data[offset:offset + max_size]
            offset += max_size

            flags = 0
            if offset >= len(data) and end_stream:
                flags = H2_FLAG_END_STREAM

            frame = self._build_frame(
                H2_FRAME_DATA,
                chunk,
                flags=flags,
                stream_id=stream_id,
            )

            self.writer.write(frame)  # type: ignore

        await self.writer.drain()

        # Update window
        self.streams[stream_id]['remote_window'] -= len(data)

    async def recv_data(
        self,
        stream_id: int,
        timeout: float = 30.0,
    ) -> bytes | None:
        """
        Receive data from stream.

        Args:
            stream_id: Stream ID
            timeout: Read timeout

        Returns:
            Received data or None if stream ended
        """
        if not self.connected:
            return None

        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            try:
                # Read frame header
                header = await asyncio.wait_for(
                    self.reader.readexactly(9),  # type: ignore
                    timeout=min(1.0, timeout - (time.monotonic() - start_time)),
                )

                length = struct.unpack('>I', b'\x00' + header[:3])[0]
                frame_type = header[3]
                flags = header[4]
                frame_stream_id = struct.unpack('>I', header[5:9])[0] & 0x7FFFFFFF

                # Read payload
                payload = await asyncio.wait_for(
                    self.reader.readexactly(length),  # type: ignore
                    timeout=timeout - (time.monotonic() - start_time),
                )

                # Handle frame
                if frame_stream_id == stream_id:
                    if frame_type == H2_FRAME_DATA:
                        self.response_buffers[stream_id] += payload

                        # Update window
                        self.streams[stream_id]['local_window'] -= len(payload)
                        self.local_window -= len(payload)

                        # Send WINDOW_UPDATE if needed
                        if self.local_window < 32768:
                            self._send_window_update(0, 65535 - self.local_window)
                            self.local_window = 65535

                        if flags & H2_FLAG_END_STREAM:
                            self.streams[stream_id]['state'] = 'half-closed'
                            result = self.response_buffers[stream_id]
                            self.response_buffers[stream_id] = b''
                            return result

                    elif frame_type == H2_FRAME_RST_STREAM:
                        self.streams[stream_id]['state'] = 'closed'
                        return None

                elif frame_type == H2_FRAME_GOAWAY:
                    log.info("Received GOAWAY, closing connection")
                    await self.close()
                    return None

            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                log.error("HTTP/2 recv error: %s", exc)
                return None

        return None

    def _send_window_update(self, stream_id: int, increment: int) -> None:
        """Send WINDOW_UPDATE frame."""
        payload = struct.pack('>I', increment & 0x7FFFFFFF)
        frame = self._build_frame(
            H2_FRAME_WINDOW_UPDATE,
            payload,
            stream_id=stream_id,
        )
        self.writer.write(frame)  # type: ignore

    async def ping(self) -> float | None:
        """
        Send HTTP/2 PING and measure latency.

        Returns:
            Latency in ms or None
        """
        if not self.connected:
            return None

        try:
            # Send PING
            ping_data = struct.pack('>Q', int(time.time() * 1000))
            ping_frame = self._build_frame(H2_FRAME_PING, ping_data)
            self.writer.write(ping_frame)  # type: ignore
            await self.writer.drain()

            start = time.monotonic()

            # Wait for PING ACK
            while True:
                header = await self.reader.readexactly(9)  # type: ignore
                length = struct.unpack('>I', b'\x00' + header[:3])[0]
                frame_type = header[3]

                if frame_type == H2_FRAME_PING:
                    await self.reader.readexactly(length)  # type: ignore
                    return (time.monotonic() - start) * 1000

        except Exception as exc:
            log.debug("HTTP/2 ping error: %s", exc)
            return None

    async def close(self) -> None:
        """Close HTTP/2 connection."""
        self.connected = False

        if self.writer:
            try:
                # Send GOAWAY
                goaway = self._build_frame(
                    H2_FRAME_GOAWAY,
                    struct.pack('>I', 0),  # Last stream ID
                )
                self.writer.write(goaway)
                await self.writer.drain()

                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

        self.writer = None
        self.reader = None


class HTTP2Transport:
    """
    HTTP/2 transport for Telegram traffic tunneling.

    Wraps HTTP/2 connection to provide Telegram-compatible interface.
    """

    def __init__(
        self,
        host: str,
        port: int,
        use_tls: bool = True,
        path: str = '/apiws',
        obfuscation: Any | None = None,
    ):
        """
        Initialize HTTP/2 transport.

        Args:
            host: Target host
            port: Target port
            use_tls: Use TLS
            path: Request path
            obfuscation: Optional obfuscation pipeline
        """
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.path = path
        self.obfuscation = obfuscation

        self.connection: HTTP2Connection | None = None
        self.stream_id: int | None = None

    async def connect(self, timeout: float = 10.0) -> bool:
        """Establish HTTP/2 transport."""
        try:
            # Create SSL context with obfuscation if available
            ssl_ctx = None
            if self.use_tls:
                if self.obfuscation:
                    ssl_ctx = self.obfuscation.get_ssl_context()
                else:
                    ssl_ctx = ssl.create_default_context()
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE
                    ssl_ctx.set_alpn_protocols(['h2'])

            # Create connection
            self.connection = HTTP2Connection(
                self.host,
                self.port,
                use_tls=self.use_tls,
                ssl_context=ssl_ctx,
            )

            if not await self.connection.connect(timeout):
                return False

            # Create stream
            headers = {
                'content-type': 'application/octet-stream',
                'te': 'trailers',
            }

            self.stream_id = await self.connection.create_stream(
                path=self.path,
                headers=headers,
            )

            log.info("HTTP/2 transport established to %s:%d", self.host, self.port)
            return True

        except Exception as exc:
            log.error("HTTP/2 transport error: %s", exc)
            return False

    async def send(self, data: bytes) -> int:
        """Send data through HTTP/2 transport."""
        if not self.connection or self.stream_id is None:
            raise RuntimeError("HTTP/2 transport not connected")

        # Obfuscate if enabled
        if self.obfuscation:
            fragments = self.obfuscation.obfuscate(data)
            total = 0
            for frag in fragments:
                await self.connection.send_data(
                    self.stream_id,
                    frag,
                    end_stream=False,
                )
                total += len(frag)
            return total
        else:
            await self.connection.send_data(self.stream_id, data, end_stream=False)
            return len(data)

    async def recv(self, max_size: int = 65536, timeout: float = 30.0) -> bytes | None:
        """Receive data from HTTP/2 transport."""
        if not self.connection or self.stream_id is None:
            return None

        data = await self.connection.recv_data(self.stream_id, timeout)

        if data is None:
            return None

        # Deobfuscate if enabled
        if self.obfuscation:
            data = self.obfuscation.deobfuscate([data])

        return data

    async def close(self) -> None:
        """Close HTTP/2 transport."""
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.stream_id = None


async def test_http2_transport():
    """Test HTTP/2 transport."""
    transport = HTTP2Transport('kws1.web.telegram.org', 443)

    if await transport.connect():
        print("Connected!")

        # Send test data
        await transport.send(b'Hello, HTTP/2!')

        # Try to receive
        data = await transport.recv(timeout=5)
        print(f"Received: {data}")

        await transport.close()
    else:
        print("Failed to connect")


if __name__ == '__main__':
    asyncio.run(test_http2_transport())
