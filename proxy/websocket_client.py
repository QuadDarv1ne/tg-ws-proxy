"""
Lightweight WebSocket Client for Telegram.

Implements WebSocket protocol over asyncio streams with proper masking,
ping/pong handling, and TLS support.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import ssl
import struct
import zlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zlib import _Compress as Compress
    from zlib import _Decompress as Decompress

log = logging.getLogger('tg-ws-client')


class WsHandshakeError(Exception):
    """WebSocket handshake error."""

    def __init__(
        self,
        status_code: int,
        status_line: str,
        headers: dict[str, str] | None = None,
        location: str | None = None
    ):
        """
        Initialize handshake error.

        Args:
            status_code: HTTP status code
            status_line: HTTP status line
            headers: Response headers
            location: Redirect location (if any)
        """
        self.status_code = status_code
        self.status_line = status_line
        self.headers = headers or {}
        self.location = location
        super().__init__(f"HTTP {status_code}: {status_line}")

    @property
    def is_redirect(self) -> bool:
        """Check if error is a redirect."""
        return self.status_code in (301, 302, 303, 307, 308)


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    """
    XOR data with mask for WebSocket frame masking.

    Args:
        data: Data to mask
        mask: 4-byte mask key

    Returns:
        Masked data
    """
    if not data:
        return data
    n = len(data)
    mask_rep = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'big') ^ int.from_bytes(mask_rep, 'big')).to_bytes(n, 'big')


def _set_sock_opts(transport: asyncio.BaseTransport) -> None:
    """
    Set socket options for optimal performance.

    Args:
        transport: asyncio transport
    """
    try:
        sock = transport.get_extra_info('socket')
        if sock:
            import socket
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    except Exception as e:
        log.debug("Failed to set socket options: %s", e)


class RawWebSocket:
    """
    Lightweight WebSocket client over asyncio reader/writer streams.

    Connects directly to a target IP via TCP+TLS, performs HTTP Upgrade
    handshake, and provides send/recv for binary frames with proper masking,
    ping/pong, and close handling.

    Supports permessage-deflate compression (RFC 7692).
    """

    # WebSocket opcodes
    OP_CONTINUATION = 0x0
    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        compress: bool = False
    ):
        """
        Initialize WebSocket.

        Args:
            reader: Stream reader
            writer: Stream writer
            compress: Enable permessage-deflate compression
        """
        self.reader = reader
        self.writer = writer
        self._closed = False
        self._compress = compress
        self._compressor: Compress | None = zlib.compressobj(level=6, wbits=-15) if compress else None
        self._decompressor: Decompress | None = zlib.decompressobj(wbits=-15) if compress else None

    @staticmethod
    async def connect(
        ip: str,
        domain: str,
        path: str = '/apiws',
        timeout: float = 10.0,
        ssl_context: ssl.SSLContext | None = None,
        compress: bool = False
    ) -> RawWebSocket:
        """
        Connect via TLS to the given IP and perform WebSocket upgrade.

        Args:
            ip: Target IP address
            domain: Domain name for SNI
            path: WebSocket path
            timeout: Connection timeout
            ssl_context: SSL context (creates default if None)
            compress: Enable permessage-deflate compression

        Returns:
            Connected WebSocket instance

        Raises:
            WsHandshakeError: On non-101 response
            asyncio.TimeoutError: On connection timeout
        """
        if ssl_context is None:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                ip, 443,
                ssl=ssl_context,
                server_hostname=domain
            ),
            timeout=min(timeout, 10)
        )
        _set_sock_opts(writer.transport)

        # Build WebSocket handshake request
        ws_key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f'GET {path} HTTP/1.1\r\n'
            f'Host: {domain}\r\n'
            f'Upgrade: websocket\r\n'
            f'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {ws_key}\r\n'
            f'Sec-WebSocket-Version: 13\r\n'
            f'Sec-WebSocket-Protocol: binary\r\n'
            f'Origin: https://web.telegram.org\r\n'
            f'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            f'AppleWebKit/537.36 (KHTML, like Gecko) '
            f'Chrome/131.0.0.0 Safari/537.36\r\n'
        )

        # Add compression extension (RFC 7692)
        if compress:
            req += 'Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits; server_max_window_bits=15\r\n'

        req += '\r\n'

        writer.write(req.encode())
        await writer.drain()

        # Read HTTP response headers line-by-line
        response_lines: list[str] = []
        try:
            while True:
                line = await asyncio.wait_for(
                    reader.readline(),
                    timeout=timeout
                )
                if line in (b'\r\n', b'\n', b''):
                    break
                response_lines.append(
                    line.decode('utf-8', errors='replace').strip()
                )
        except asyncio.TimeoutError:
            writer.close()
            raise

        if not response_lines:
            writer.close()
            raise WsHandshakeError(0, 'empty response')

        # Parse status line
        first_line = response_lines[0]
        parts = first_line.split(' ', 2)
        try:
            status_code = int(parts[1]) if len(parts) >= 2 else 0
        except ValueError:
            status_code = 0

        if status_code == 101:
            log.debug("WebSocket connected to %s (%s)%s", domain, ip, " [compression enabled]" if compress else "")
            return RawWebSocket(reader, writer, compress=compress)

        # Parse headers for error details
        headers: dict[str, str] = {}
        for hl in response_lines[1:]:
            if ':' in hl:
                k, v = hl.split(':', 1)
                headers[k.strip().lower()] = v.strip()

        writer.close()
        raise WsHandshakeError(
            status_code,
            first_line,
            headers,
            location=headers.get('location')
        )

    async def send(self, data: bytes) -> None:
        """
        Send a masked binary WebSocket frame.

        Args:
            data: Data to send

        Raises:
            ConnectionError: If WebSocket is closed
        """
        if self._closed:
            raise ConnectionError("WebSocket closed")

        # Compress data if enabled
        if self._compress and self._compressor and len(data) > 0:
            # Compress with permessage-deflate (RFC 7692)
            compressed = self._compressor.compress(data) + self._compressor.flush(zlib.Z_SYNC_FLUSH)
            # Remove trailing 4 bytes (0x00 0x00 0xFF 0xFF) as per RFC 7692
            if compressed.endswith(b'\x00\x00\xff\xff'):
                compressed = compressed[:-4]
            data = compressed

        frame = self._build_frame(self.OP_BINARY, data, mask=True)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_batch(self, parts: list[bytes]) -> None:
        """
        Send multiple binary frames with a single drain (less overhead).

        Args:
            parts: List of data chunks to send

        Raises:
            ConnectionError: If WebSocket is closed
        """
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            # Compress each part if enabled
            if self._compress and self._compressor and len(part) > 0:
                compressed = self._compressor.compress(part) + self._compressor.flush(zlib.Z_SYNC_FLUSH)
                if compressed.endswith(b'\x00\x00\xff\xff'):
                    compressed = compressed[:-4]
                part = compressed
            frame = self._build_frame(self.OP_BINARY, part, mask=True)
            self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> bytes | None:
        """
        Receive the next data frame.

        Handles ping/pong/close internally.
        Decompresses payload if compression is enabled.

        Returns:
            Payload bytes, or None on clean close
        """
        while not self._closed:
            try:
                opcode, payload = await self._read_frame()
            except asyncio.IncompleteReadError:
                # Connection closed gracefully
                self._closed = True
                return None
            except asyncio.TimeoutError:
                # Read timeout — connection may be stuck
                self._closed = True
                return None

            if opcode == self.OP_CLOSE:
                self._closed = True
                try:
                    reply = self._build_frame(
                        self.OP_CLOSE,
                        payload[:2] if payload else b'',
                        mask=True
                    )
                    self.writer.write(reply)
                    await self.writer.drain()
                except Exception:
                    pass
                return None

            if opcode == self.OP_PING:
                try:
                    pong = self._build_frame(
                        self.OP_PONG,
                        payload,
                        mask=True
                    )
                    self.writer.write(pong)
                    await self.writer.drain()
                except Exception:
                    pass
                continue

            if opcode == self.OP_PONG:
                continue

            if opcode in (self.OP_TEXT, self.OP_BINARY):
                # Decompress if compression enabled
                if self._compress and self._decompressor:
                    try:
                        # Add trailing 4 bytes (0x00 0x00 0xFF 0xFF) as per RFC 7692
                        payload_with_trailer = payload + b'\x00\x00\xff\xff'
                        payload = self._decompressor.decompress(payload_with_trailer)
                    except Exception as e:
                        log.debug("Decompression error: %s", e)
                        # Fall back to uncompressed data
                return payload

            # Unknown opcode — skip
            continue

        return None

    async def close(self) -> None:
        """Send close frame and shut down the transport."""
        if self._closed:
            return
        self._closed = True

        # Reset compression state
        if self._compressor:
            try:
                self._compressor.reset()  # type: ignore[attr-defined]
            except Exception:
                pass
        if self._decompressor:
            try:
                self._decompressor.flush()
            except Exception:
                pass

        try:
            self.writer.write(
                self._build_frame(self.OP_CLOSE, b'', mask=True)
            )
            await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    @staticmethod
    def _build_frame(
        opcode: int,
        data: bytes,
        mask: bool = False
    ) -> bytes:
        """
        Build a WebSocket frame.

        Args:
            opcode: Frame opcode
            data: Frame payload
            mask: Whether to mask the payload

        Returns:
            Complete WebSocket frame
        """
        header = bytearray()
        header.append(0x80 | opcode)  # FIN=1 + opcode
        length = len(data)
        mask_bit = 0x80 if mask else 0x00

        if length < 126:
            header.append(mask_bit | length)
        elif length < 65536:
            header.append(mask_bit | 126)
            header.extend(struct.pack('>H', length))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack('>Q', length))

        if mask:
            mask_key = os.urandom(4)
            header.extend(mask_key)
            return bytes(header) + _xor_mask(data, mask_key)
        return bytes(header) + data

    async def _read_frame(self) -> tuple[int, bytes]:
        """
        Read a single WebSocket frame from the reader.

        Returns:
            Tuple of (opcode, payload)

        Raises:
            asyncio.TimeoutError: On read timeout
            asyncio.IncompleteReadError: On connection close
        """
        try:
            hdr = await asyncio.wait_for(
                self.reader.readexactly(2),
                timeout=30.0
            )
        except asyncio.TimeoutError as e:
            raise asyncio.TimeoutError("Frame header read timeout") from e
        except asyncio.IncompleteReadError as e:
            raise asyncio.IncompleteReadError(
                e.partial, e.expected
            ) from e

        opcode = hdr[0] & 0x0F
        is_masked = bool(hdr[1] & 0x80)
        length = hdr[1] & 0x7F

        if length == 126:
            try:
                length = struct.unpack(
                    '>H',
                    await asyncio.wait_for(
                        self.reader.readexactly(2),
                        timeout=30.0
                    )
                )[0]
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(
                    e.partial, e.expected
                ) from e
        elif length == 127:
            try:
                length = struct.unpack(
                    '>Q',
                    await asyncio.wait_for(
                        self.reader.readexactly(8),
                        timeout=30.0
                    )
                )[0]
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(
                    e.partial, e.expected
                ) from e

        if is_masked:
            try:
                mask_key = await asyncio.wait_for(
                    self.reader.readexactly(4),
                    timeout=30.0
                )
                payload = await asyncio.wait_for(
                    self.reader.readexactly(length),
                    timeout=30.0
                )
                return opcode, _xor_mask(payload, mask_key)
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(
                    e.partial, e.expected
                ) from e

        try:
            payload = await asyncio.wait_for(
                self.reader.readexactly(length),
                timeout=30.0
            )
        except asyncio.IncompleteReadError as e:
            raise asyncio.IncompleteReadError(
                e.partial, e.expected
            ) from e
        return opcode, payload
