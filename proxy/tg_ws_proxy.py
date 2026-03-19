from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import os
import socket as _socket
import ssl
import struct
import sys
import time
from typing import Dict, List, Optional, Set, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .stats import Stats, _human_bytes

from .constants import (
    DEFAULT_PORT,
    TCP_NODELAY,
    RECV_BUF_SIZE,
    SEND_BUF_SIZE,
    WS_POOL_SIZE,
    WS_POOL_MAX_AGE,
    WS_POOL_MAX_SIZE,
    DC_FAIL_COOLDOWN,
    INIT_PACKET_SIZE,
    INIT_KEY_OFFSET,
    INIT_KEY_SIZE,
    INIT_IV_OFFSET,
    INIT_IV_SIZE,
    INIT_DC_OFFSET,
    INIT_DC_SIZE,
    PROTO_OBFUSCATED,
    PROTO_ABRIDGED,
    PROTO_PADDED_ABRIDGED,
    ABRIDGED_SHORT_PREFIX,
    TG_RANGES,
    _IP_TO_DC,
    WSAEADDRINUSE,
)


log = logging.getLogger('tg-ws-proxy')

# IP -> (dc_id, is_media)
_IP_TO_DC: Dict[str, Tuple[int, bool]] = _IP_TO_DC

# Local aliases for frequently used constants
_TG_RANGES = TG_RANGES

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


async def _close_writer_safe(writer) -> None:
    """Safely close and wait for writer to close."""
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def _cancel_tasks(tasks) -> None:
    """Cancel tasks and wait for completion, suppressing exceptions."""
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except Exception:
            pass


class ProxyServer:
    """
    Main proxy server class that encapsulates all global state.
    
    This class manages:
    - DC configuration and routing
    - WebSocket connection pool
    - Statistics tracking
    - Client connection handling
    """

    def __init__(self, dc_opt: Dict[int, Optional[str]], host: str = '127.0.0.1', port: int = DEFAULT_PORT,
                 auth_required: bool = False, auth_credentials: Optional[Dict[str, str]] = None,
                 ip_whitelist: Optional[List[str]] = None):
        self.dc_opt = dc_opt
        self.host = host
        self.port = port
        self.auth_required = auth_required
        self.auth_credentials = auth_credentials
        self.ip_whitelist = set(ip_whitelist) if ip_whitelist else None

        # DCs where WS is known to fail (302 redirect)
        # Raw TCP fallback will be used instead
        # Keyed by (dc, is_media)
        self.ws_blacklist: Set[Tuple[int, bool]] = set()

        # Rate-limit re-attempts per (dc, is_media)
        self.dc_fail_until: Dict[Tuple[int, bool], float] = {}

        # Statistics
        self.stats = Stats()

        # WebSocket connection pool
        self.ws_pool = _WsPool(self.stats)

        # Server instance for graceful shutdown
        self._server_instance: Optional[asyncio.Server] = None
        self._server_stop_event: Optional[asyncio.Event] = None
    
    def get_stats(self) -> Dict:
        """Get current proxy statistics."""
        return self.stats.to_dict()

    def get_stats_summary(self) -> str:
        """Get current stats as a human-readable summary."""
        return self.stats.summary()


def _set_sock_opts(transport: asyncio.Transport) -> None:
    sock = transport.get_extra_info('socket')
    if sock is None:
        return
    if TCP_NODELAY:
        try:
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            pass
    try:
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_RCVBUF, RECV_BUF_SIZE)
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_SNDBUF, SEND_BUF_SIZE)
    except OSError:
        pass


class WsHandshakeError(Exception):
    def __init__(self, status_code: int, status_line: str,
                 headers: dict = None, location: str = None):
        self.status_code = status_code
        self.status_line = status_line
        self.headers = headers or {}
        self.location = location
        super().__init__(f"HTTP {status_code}: {status_line}")

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308)


def _xor_mask(data: bytes, mask: bytes) -> bytes:
    if not data:
        return data
    n = len(data)
    mask_rep = (mask * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'big') ^ int.from_bytes(mask_rep, 'big')).to_bytes(n, 'big')


class RawWebSocket:
    """
    Lightweight WebSocket client over asyncio reader/writer streams.

    Connects DIRECTLY to a target IP via TCP+TLS (bypassing any system
    proxy), performs the HTTP Upgrade handshake, and provides send/recv
    for binary frames with proper masking, ping/pong, and close handling.
    """

    OP_CONTINUATION = 0x0
    OP_TEXT = 0x1
    OP_BINARY = 0x2
    OP_CLOSE = 0x8
    OP_PING = 0x9
    OP_PONG = 0xA

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False

    @staticmethod
    async def connect(ip: str, domain: str, path: str = '/apiws',
                      timeout: float = 10.0) -> 'RawWebSocket':
        """
        Connect via TLS to the given IP,
        perform WebSocket upgrade, return a RawWebSocket.

        Raises WsHandshakeError on non-101 response.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 443, ssl=_ssl_ctx,
                                    server_hostname=domain),
            timeout=min(timeout, 10))
        _set_sock_opts(writer.transport)

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
            f'\r\n'
        )
        writer.write(req.encode())
        await writer.drain()

        # Read HTTP response headers line-by-line so the reader stays
        # positioned right at the start of WebSocket frames.
        response_lines: list[str] = []
        try:
            while True:
                line = await asyncio.wait_for(reader.readline(),
                                              timeout=timeout)
                if line in (b'\r\n', b'\n', b''):
                    break
                response_lines.append(
                    line.decode('utf-8', errors='replace').strip())
        except asyncio.TimeoutError:
            writer.close()
            raise

        if not response_lines:
            writer.close()
            raise WsHandshakeError(0, 'empty response')

        first_line = response_lines[0]
        parts = first_line.split(' ', 2)
        try:
            status_code = int(parts[1]) if len(parts) >= 2 else 0
        except ValueError:
            status_code = 0

        if status_code == 101:
            return RawWebSocket(reader, writer)

        headers: dict[str, str] = {}
        for hl in response_lines[1:]:
            if ':' in hl:
                k, v = hl.split(':', 1)
                headers[k.strip().lower()] = v.strip()

        writer.close()
        raise WsHandshakeError(status_code, first_line, headers,
                                location=headers.get('location'))

    async def send(self, data: bytes):
        """Send a masked binary WebSocket frame."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        frame = self._build_frame(self.OP_BINARY, data, mask=True)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_batch(self, parts: List[bytes]):
        """Send multiple binary frames with a single drain (less overhead)."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            frame = self._build_frame(self.OP_BINARY, part, mask=True)
            self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> Optional[bytes]:
        """
        Receive the next data frame.  Handles ping/pong/close
        internally.  Returns payload bytes, or None on clean close.
        """
        while not self._closed:
            opcode, payload = await self._read_frame()

            if opcode == self.OP_CLOSE:
                self._closed = True
                try:
                    reply = self._build_frame(
                        self.OP_CLOSE,
                        payload[:2] if payload else b'',
                        mask=True)
                    self.writer.write(reply)
                    await self.writer.drain()
                except Exception:
                    pass
                return None

            if opcode == self.OP_PING:
                try:
                    pong = self._build_frame(self.OP_PONG, payload,
                                             mask=True)
                    self.writer.write(pong)
                    await self.writer.drain()
                except Exception:
                    pass
                continue

            if opcode == self.OP_PONG:
                continue

            if opcode in (self.OP_TEXT, self.OP_BINARY):
                return payload

            # Unknown opcode — skip
            continue

        return None

    async def close(self):
        """Send close frame and shut down the transport."""
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.write(
                self._build_frame(self.OP_CLOSE, b'', mask=True))
            await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    @staticmethod
    def _build_frame(opcode: int, data: bytes,
                     mask: bool = False) -> bytes:
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

    async def _read_frame(self) -> Tuple[int, bytes]:
        hdr = await self.reader.readexactly(2)
        opcode = hdr[0] & 0x0F
        is_masked = bool(hdr[1] & 0x80)
        length = hdr[1] & 0x7F

        if length == 126:
            length = struct.unpack('>H',
                                   await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack('>Q',
                                   await self.reader.readexactly(8))[0]

        if is_masked:
            mask_key = await self.reader.readexactly(4)
            payload = await self.reader.readexactly(length)
            return opcode, _xor_mask(payload, mask_key)

        payload = await self.reader.readexactly(length)
        return opcode, payload


def _is_telegram_ip(ip: str) -> bool:
    try:
        n = struct.unpack('!I', _socket.inet_aton(ip))[0]
        return any(lo <= n <= hi for lo, hi in _TG_RANGES)
    except OSError:
        return False


def _is_http_transport(data: bytes) -> bool:
    return (data[:5] == b'POST ' or data[:4] == b'GET ' or
            data[:5] == b'HEAD ' or data[:8] == b'OPTIONS ')


def _dc_from_init(data: bytes) -> Tuple[Optional[int], bool]:
    """
    Extract DC ID from the 64-byte MTProto obfuscation init packet.
    Returns (dc_id, is_media).
    """
    if len(data) < INIT_PACKET_SIZE:
        return None, False
    
    try:
        key = bytes(data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        keystream = encryptor.update(b'\x00' * 64) + encryptor.finalize()
        plain = bytes(a ^ b for a, b in zip(
            data[56:64], keystream[56:64]))
        proto = struct.unpack('<I', plain[0:4])[0]
        dc_raw = struct.unpack('<h', plain[4:6])[0]
        log.debug("dc_from_init: proto=0x%08X dc_raw=%d plain=%s",
                  proto, dc_raw, plain.hex())
        if proto in (PROTO_OBFUSCATED, PROTO_ABRIDGED, PROTO_PADDED_ABRIDGED):
            dc = abs(dc_raw)
            if 1 <= dc <= 5:
                return dc, (dc_raw < 0)
    except Exception as exc:
        log.debug("DC extraction failed: %s", exc)
    return None, False


def _patch_init_dc(data: bytes, dc: int) -> bytes:
    """
    Patch dc_id in the 64-byte MTProto init packet.

    Mobile clients with useSecret=0 leave bytes 60-61 as random.
    The WS relay needs a valid dc_id to route correctly.
    """
    if len(data) < INIT_PACKET_SIZE:
        return data

    new_dc = struct.pack('<h', dc)
    try:
        key_raw = bytes(data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        enc = cipher.encryptor()
        ks = enc.update(b'\x00' * 64) + enc.finalize()
        patched = bytearray(data[:INIT_PACKET_SIZE])
        patched[INIT_DC_OFFSET] = ks[INIT_DC_OFFSET] ^ new_dc[0]
        patched[INIT_DC_OFFSET + 1] = ks[INIT_DC_OFFSET + 1] ^ new_dc[1]
        log.debug("init patched: dc_id -> %d", dc)
        if len(data) > INIT_PACKET_SIZE:
            return bytes(patched) + data[INIT_PACKET_SIZE:]
        return bytes(patched)
    except Exception:
        return data


class _MsgSplitter:
    """
    Splits client TCP data into individual MTProto abridged-protocol
    messages so each can be sent as a separate WebSocket frame.

    The Telegram WS relay processes one MTProto message per WS frame.
    Mobile clients batches multiple messages in a single TCP write (e.g.
    msgs_ack + req_DH_params).  If sent as one WS frame, the relay
    only processes the first message — DH handshake never completes.
    """

    def __init__(self, init_data: bytes):
        key_raw = bytes(init_data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(init_data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        self._dec = cipher.encryptor()
        self._dec.update(b'\x00' * 64)  # skip init packet

    def split(self, chunk: bytes) -> List[bytes]:
        """Decrypt to find message boundaries, return split ciphertext."""
        plain = self._dec.update(chunk)
        boundaries = []
        pos = 0
        while pos < len(plain):
            first = plain[pos]
            if first == 0x7f:
                if pos + 4 > len(plain):
                    break
                msg_len = (
                    struct.unpack_from('<I', plain, pos + 1)[0] & 0xFFFFFF
                ) * 4
                pos += 4
            else:
                msg_len = first * 4
                pos += 1
            if msg_len == 0 or pos + msg_len > len(plain):
                break
            pos += msg_len
            boundaries.append(pos)
        if len(boundaries) <= 1:
            return [chunk]
        parts = []
        prev = 0
        for b in boundaries:
            parts.append(chunk[prev:b])
            prev = b
        if prev < len(chunk):
            parts.append(chunk[prev:])
        return parts


def _ws_domains(dc: int, is_media: Optional[bool]) -> List[str]:
    if is_media is None or is_media:
        return [f'kws{dc}-1.web.telegram.org', f'kws{dc}.web.telegram.org']
    return [f'kws{dc}.web.telegram.org', f'kws{dc}-1.web.telegram.org']


# Global instance for backward compatibility
_server_instance: Optional[ProxyServer] = None

# Callback for client connection notifications
_on_client_connect_callback = None


def set_on_client_connect_callback(callback) -> None:
    """Set callback for client connection notifications."""
    global _on_client_connect_callback
    _on_client_connect_callback = callback


def get_stats() -> Dict:
    """Get current proxy statistics (backward compatibility)."""
    global _server_instance
    if _server_instance:
        return _server_instance.get_stats()
    return Stats().to_dict()


def get_stats_summary() -> str:
    """Get current stats as human-readable summary (backward compatibility)."""
    global _server_instance
    if _server_instance:
        return _server_instance.get_stats_summary()
    return Stats().summary()


class _WsPool:
    def __init__(self, stats: Stats):
        self.stats = stats
        self._idle: Dict[Tuple[int, bool], list] = {}
        self._refilling: Set[Tuple[int, bool]] = set()

    async def get(self, dc: int, is_media: bool,
                  target_ip: str, domains: List[str]
                  ) -> Optional[RawWebSocket]:
        key = (dc, is_media)
        now = time.monotonic()

        bucket = self._idle.get(key, [])
        while bucket:
            ws, created = bucket.pop(0)
            age = now - created
            if age > WS_POOL_MAX_AGE or ws._closed:
                asyncio.create_task(self._quiet_close(ws))
                continue
            self.stats.pool_hits += 1
            log.debug("WS pool hit for DC%d%s (age=%.1fs, left=%d)",
                      dc, 'm' if is_media else '', age, len(bucket))
            self._schedule_refill(key, target_ip, domains)
            return ws

        self.stats.pool_misses += 1
        self._schedule_refill(key, target_ip, domains)
        return None

    def _can_add_to_pool(self, key: Tuple[int, bool]) -> bool:
        """Check if pool can accept more connections."""
        bucket = self._idle.get(key, [])
        return len(bucket) < WS_POOL_MAX_SIZE

    def _schedule_refill(self, key, target_ip, domains):
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key, target_ip, domains))

    async def _refill(self, key, target_ip, domains):
        dc, is_media = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = WS_POOL_SIZE - len(bucket)
            if needed <= 0:
                return
            tasks = []
            for _ in range(needed):
                tasks.append(asyncio.create_task(
                    self._connect_one(target_ip, domains)))
            for t in tasks:
                try:
                    ws = await t
                    if ws and self._can_add_to_pool(key):
                        bucket.append((ws, time.monotonic()))
                    elif ws:
                        await self._quiet_close(ws)
                except Exception:
                    pass
            log.debug("WS pool refilled DC%d%s: %d ready",
                      dc, 'm' if is_media else '', len(bucket))
        finally:
            self._refilling.discard(key)

    @staticmethod
    async def _connect_one(target_ip, domains) -> Optional[RawWebSocket]:
        for domain in domains:
            try:
                ws = await RawWebSocket.connect(
                    target_ip, domain, timeout=8)
                return ws
            except WsHandshakeError as exc:
                if exc.is_redirect:
                    continue
                return None
            except Exception:
                return None
        return None

    @staticmethod
    async def _quiet_close(ws):
        try:
            await ws.close()
        except Exception:
            pass

    async def warmup(self, dc_opt: Dict[int, Optional[str]]):
        """Pre-fill pool for all configured DCs on startup."""
        for dc, target_ip in dc_opt.items():
            if target_ip is None:
                continue
            for is_media in (False, True):
                domains = _ws_domains(dc, is_media)
                key = (dc, is_media)
                self._schedule_refill(key, target_ip, domains)
        log.info("WS pool warmup started for %d DC(s)", len(dc_opt))


async def _bridge_ws(reader, writer, ws: RawWebSocket, label, stats: Stats,
                     dc=None, dst=None, port=None, is_media=False,
                     splitter: _MsgSplitter = None):
    """Bidirectional TCP <-> WebSocket forwarding."""
    dc_tag = f"DC{dc}{'m' if is_media else ''}" if dc else "DC?"
    dst_tag = f"{dst}:{port}" if dst else "?"

    up_bytes = 0
    down_bytes = 0
    up_packets = 0
    down_packets = 0
    start_time = asyncio.get_event_loop().time()

    async def tcp_to_ws():
        nonlocal up_bytes, up_packets
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                stats.add_bytes(up=len(chunk))
                up_bytes += len(chunk)
                up_packets += 1
                if splitter:
                    parts = splitter.split(chunk)
                    if len(parts) > 1:
                        await ws.send_batch(parts)
                    else:
                        await ws.send(parts[0])
                else:
                    await ws.send(chunk)
        except (asyncio.CancelledError, ConnectionError, OSError):
            return
        except Exception as e:
            log.debug("[%s] tcp->ws ended: %s", label, e)

    async def ws_to_tcp():
        nonlocal down_bytes, down_packets
        try:
            while True:
                data = await ws.recv()
                if data is None:
                    break
                stats.bytes_down += len(data)
                down_bytes += len(data)
                down_packets += 1
                writer.write(data)
                # drain only when kernel buffer is filling up
                buf = writer.transport.get_write_buffer_size()
                if buf > SEND_BUF_SIZE:
                    await writer.drain()
        except (asyncio.CancelledError, ConnectionError, OSError):
            return
        except Exception as e:
            log.debug("[%s] ws->tcp ended: %s", label, e)

    tasks = [asyncio.create_task(tcp_to_ws()),
             asyncio.create_task(ws_to_tcp())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_tasks(tasks)
        elapsed = asyncio.get_event_loop().time() - start_time
        log.info("[%s] %s (%s) WS session closed: "
                 "^%s (%d pkts) v%s (%d pkts) in %.1fs",
                 label, dc_tag, dst_tag,
                 _human_bytes(up_bytes), up_packets,
                 _human_bytes(down_bytes), down_packets,
                 elapsed)
        await _close_writer_safe(ws)
        await _close_writer_safe(writer)


async def _bridge_tcp(reader, writer, remote_reader, remote_writer,
                      label, stats: Stats, dc=None, dst=None, port=None,
                      is_media=False):
    """Bidirectional TCP <-> TCP forwarding (for fallback)."""
    async def forward(src, dst_w, tag):
        try:
            while True:
                data = await src.read(65536)
                if not data:
                    break
                if 'up' in tag:
                    stats.add_bytes(up=len(data))
                else:
                    stats.add_bytes(down=len(data))
                dst_w.write(data)
                await dst_w.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug("[%s] %s ended: %s", label, tag, e)

    tasks = [
        asyncio.create_task(forward(reader, remote_writer, 'up')),
        asyncio.create_task(forward(remote_reader, writer, 'down')),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_tasks(tasks)
        await _close_writer_safe(writer)
        await _close_writer_safe(remote_writer)


async def _pipe(r, w):
    """Plain TCP relay for non-Telegram traffic."""
    try:
        while True:
            data = await r.read(65536)
            if not data:
                break
            w.write(data)
            await w.drain()
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        await _close_writer_safe(w)


async def _pipe_passthrough(r1, w1, r2, w2):
    """Bidirectional TCP relay for passthrough traffic."""
    async def forward(src, dst_w):
        try:
            while True:
                data = await src.read(65536)
                if not data:
                    break
                dst_w.write(data)
                await dst_w.drain()
        except Exception:
            pass
        finally:
            await _close_writer_safe(dst_w)

    tasks = [
        asyncio.create_task(forward(r1, w2)),
        asyncio.create_task(forward(r2, w1)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_tasks(tasks)


def _socks5_reply(status):
    return bytes([0x05, status, 0x00, 0x01]) + b'\x00' * 6


async def _tcp_fallback(reader, writer, dst, port, init, label,
                        dc=None, is_media=False):
    """
    Fall back to direct TCP to the original DC IP.
    Throttled by ISP, but functional.  Returns True on success.
    """
    try:
        rr, rw = await asyncio.wait_for(
            asyncio.open_connection(dst, port), timeout=10)
    except Exception as exc:
        log.warning("[%s] TCP fallback connect to %s:%d failed: %s",
                    label, dst, port, exc)
        return False

    stats.add_connection('tcp_fallback', dc=dc)
    rw.write(init)
    await rw.drain()
    await _bridge_tcp(reader, writer, rr, rw, label, stats,
                      dc=dc, dst=dst, port=port, is_media=is_media)
    return True


async def _handle_client(reader, writer, stats: Stats, dc_opt: Dict[int, Optional[str]],
                         ws_pool: _WsPool, ws_blacklist: Set[Tuple[int, bool]],
                         dc_fail_until: Dict[Tuple[int, bool], float],
                         auth_required: bool = False,
                         auth_credentials: Optional[Dict[str, str]] = None,
                         ip_whitelist: Optional[Set[str]] = None):
    peer = writer.get_extra_info('peername')
    label = f"{peer[0]}:{peer[1]}" if peer else "?"
    client_ip = peer[0] if peer else "unknown"

    # Check IP whitelist
    if ip_whitelist is not None and client_ip not in ip_whitelist:
        log.warning("[%s] client IP not in whitelist - rejected", label)
        stats.add_connection('http_rejected', dc=None)
        writer.close()
        return

    _set_sock_opts(writer.transport)

    try:
        # -- SOCKS5 greeting --
        hdr = await asyncio.wait_for(reader.readexactly(2), timeout=10)
        if hdr[0] != 5:
            log.debug("[%s] not SOCKS5 (ver=%d)", label, hdr[0])
            stats.add_connection('passthrough', dc=None)
            writer.close()
            return
        
        nmethods = hdr[1]
        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10)
        
        # Check if client supports auth method (0x02) when auth is required
        if auth_required and auth_credentials:
            if 0x02 not in methods:
                log.warning("[%s] client doesn't support auth method", label)
                writer.write(b'\x05\xff')  # No acceptable methods
                await writer.drain()
                writer.close()
                return
            writer.write(b'\x05\x02')  # Use username/password auth
            await writer.drain()
            
            # Read auth credentials from client
            auth_ver = await asyncio.wait_for(reader.readexactly(1), timeout=10)
            if auth_ver[0] != 1:
                log.warning("[%s] unknown auth version %d", label, auth_ver[0])
                writer.write(b'\x01\x01')  # Authentication failed
                await writer.drain()
                writer.close()
                return
            
            ulen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
            username = await asyncio.wait_for(reader.readexactly(ulen), timeout=10)
            plen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
            password = await asyncio.wait_for(reader.readexactly(plen), timeout=10)
            
            # Validate credentials
            if (username.decode() != auth_credentials.get('username') or
                password.decode() != auth_credentials.get('password')):
                log.warning("[%s] auth failed for user %s", label, username.decode())
                writer.write(b'\x01\x01')  # Authentication failed
                await writer.drain()
                writer.close()
                stats.add_connection('http_rejected', dc=None)
                return
            
            writer.write(b'\x01\x00')  # Authentication successful
            await writer.drain()
            log.info("[%s] auth successful for user %s", label, username.decode())
        else:
            # No auth required
            writer.write(b'\x05\x00')  # no-auth
            await writer.drain()

        # -- SOCKS5 CONNECT request --
        req = await asyncio.wait_for(reader.readexactly(4), timeout=10)
        _ver, cmd, _rsv, atyp = req
        if cmd != 1:
            writer.write(_socks5_reply(0x07))
            await writer.drain()
            writer.close()
            return

        if atyp == 1:  # IPv4
            raw = await reader.readexactly(4)
            dst = _socket.inet_ntoa(raw)
        elif atyp == 3:  # domain
            dlen = (await reader.readexactly(1))[0]
            dst = (await reader.readexactly(dlen)).decode()
        elif atyp == 4:  # IPv6
            raw = await reader.readexactly(16)
            dst = _socket.inet_ntop(_socket.AF_INET6, raw)
        else:
            writer.write(_socks5_reply(0x08))
            await writer.drain()
            writer.close()
            return

        port = struct.unpack('!H', await reader.readexactly(2))[0]

        if ':' in dst:
            log.error(
                "[%s] IPv6 address detected: %s:%d — "
                "IPv6 addresses are not supported; "
                "disable IPv6 to continue using the proxy.",
                label, dst, port)
            writer.write(_socks5_reply(0x05))
            await writer.drain()
            writer.close()
            return

        # -- Non-Telegram IP -> direct passthrough --
        if not _is_telegram_ip(dst):
            stats.connections_passthrough += 1
            log.debug("[%s] passthrough -> %s:%d", label, dst, port)
            try:
                rr, rw = await asyncio.wait_for(
                    asyncio.open_connection(dst, port), timeout=10)
            except Exception as exc:
                log.warning("[%s] passthrough failed to %s: %s: %s", label, dst, type(exc).__name__, str(exc) or "(no message)")
                writer.write(_socks5_reply(0x05))
                await writer.drain()
                writer.close()
                return

            writer.write(_socks5_reply(0x00))
            await writer.drain()

            await _pipe_passthrough(reader, writer, rr, rw)
            return

        # -- Telegram DC: accept SOCKS, read init --
        writer.write(_socks5_reply(0x00))
        await writer.drain()

        try:
            init = await asyncio.wait_for(
                reader.readexactly(64), timeout=15)
        except asyncio.IncompleteReadError:
            log.debug("[%s] client disconnected before init", label)
            return

        # HTTP transport -> reject
        if _is_http_transport(init):
            stats.connections_http_rejected += 1
            log.debug("[%s] HTTP transport to %s:%d (rejected)",
                      label, dst, port)
            writer.close()
            return

        # -- Extract DC ID --
        dc, is_media = _dc_from_init(init)
        init_patched = False

        # Android (may be ios too) with useSecret=0 has random dc_id bytes — patch it
        if dc is None and dst in _IP_TO_DC:
            dc, is_media = _IP_TO_DC.get(dst)
            if dc in dc_opt:
                init = _patch_init_dc(init, dc if is_media else -dc)
                init_patched = True

        if dc is None or dc not in dc_opt:
            log.warning("[%s] unknown DC%s for %s:%d -> TCP passthrough",
                        label, dc, dst, port)
            await _tcp_fallback(reader, writer, dst, port, init, label)
            return

        dc_key = (dc, is_media if is_media is not None else True)
        now = time.monotonic()
        media_tag = (" media" if is_media
                     else (" media?" if is_media is None else ""))

        # -- WS blacklist check --
        if dc_key in ws_blacklist:
            log.debug("[%s] DC%d%s WS blacklisted -> TCP %s:%d",
                      label, dc, media_tag, dst, port)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("[%s] DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- Cooldown check --
        fail_until = dc_fail_until.get(dc_key, 0)
        if now < fail_until:
            remaining = fail_until - now
            log.debug("[%s] DC%d%s WS cooldown (%.0fs) -> TCP",
                      label, dc, media_tag, remaining)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("[%s] DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- Try WebSocket via direct connection --
        domains = _ws_domains(dc, is_media)
        target = dc_opt[dc]
        ws = None
        ws_failed_redirect = False
        all_redirects = True

        ws = await ws_pool.get(dc, is_media, target, domains)
        if ws:
            log.info("[%s] DC%d%s (%s:%d) -> pool hit via %s",
                     label, dc, media_tag, dst, port, target)
        else:
            for domain in domains:
                url = f'wss://{domain}/apiws'
                log.info("[%s] DC%d%s (%s:%d) -> %s via %s",
                         label, dc, media_tag, dst, port, url, target)
                try:
                    ws = await RawWebSocket.connect(target, domain,
                                                    timeout=10)
                    all_redirects = False
                    break
                except WsHandshakeError as exc:
                    stats.ws_errors += 1
                    if exc.is_redirect:
                        ws_failed_redirect = True
                        log.warning("[%s] DC%d%s got %d from %s -> %s",
                                    label, dc, media_tag,
                                    exc.status_code, domain,
                                    exc.location or '?')
                        continue
                    else:
                        all_redirects = False
                        log.warning("[%s] DC%d%s WS handshake: %s",
                                    label, dc, media_tag, exc.status_line)
                except Exception as exc:
                    stats.add_ws_error(dc=dc)
                    all_redirects = False
                    err_str = str(exc)
                    if ('CERTIFICATE_VERIFY_FAILED' in err_str or
                            'Hostname mismatch' in err_str):
                        log.warning("[%s] DC%d%s SSL error: %s",
                                    label, dc, media_tag, exc)
                    else:
                        log.warning("[%s] DC%d%s WS connect failed: %s",
                                    label, dc, media_tag, exc)

        # -- WS failed -> fallback --
        if ws is None:
            if ws_failed_redirect and all_redirects:
                ws_blacklist.add(dc_key)
                log.warning(
                    "[%s] DC%d%s blacklisted for WS (all 302)",
                    label, dc, media_tag)
            elif ws_failed_redirect:
                dc_fail_until[dc_key] = now + DC_FAIL_COOLDOWN
            else:
                dc_fail_until[dc_key] = now + DC_FAIL_COOLDOWN
                log.info("[%s] DC%d%s WS cooldown for %ds",
                         label, dc, media_tag, int(DC_FAIL_COOLDOWN))

            log.info("[%s] DC%d%s -> TCP fallback to %s:%d",
                     label, dc, media_tag, dst, port)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("[%s] DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- WS success --
        dc_fail_until.pop(dc_key, None)
        stats.add_connection('ws', dc=dc)

        # Notify about client connection
        if _on_client_connect_callback:
            try:
                _on_client_connect_callback(dc, dst, port)
            except Exception:
                pass

        splitter = None
        if init_patched:
            try:
                splitter = _MsgSplitter(init)
            except Exception:
                pass

        # Send the buffered init packet
        await ws.send(init)

        # Bidirectional bridge
        await _bridge_ws(reader, writer, ws, label, stats,
                         dc=dc, dst=dst, port=port, is_media=is_media,
                         splitter=splitter)

    except Exception:
        _handle_client_error(label)
    finally:
        _close_client_writer(writer)


def _handle_client_error(label: str) -> None:
    """Handle client connection errors with appropriate logging."""
    exc = sys.exc_info()[1]

    # Expected/common errors - log at DEBUG level
    if isinstance(exc, asyncio.TimeoutError):
        log.debug("[%s] timeout during SOCKS5 handshake", label)
    elif isinstance(exc, asyncio.IncompleteReadError):
        log.debug("[%s] client disconnected", label)
    elif isinstance(exc, asyncio.CancelledError):
        log.debug("[%s] cancelled", label)
    elif isinstance(exc, ConnectionResetError):
        log.debug("[%s] connection reset", label)
    # Unexpected errors - log at ERROR level
    else:
        log.error("[%s] unexpected: %s", label, exc)


def _close_client_writer(writer) -> None:
    """Safely close client writer connection."""
    try:
        writer.close()
    except Exception:
        pass


async def _run(port: int, dc_opt: Dict[int, Optional[str]],
               stop_event: Optional[asyncio.Event] = None,
               host: str = '127.0.0.1',
               auth_required: bool = False,
               auth_credentials: Optional[Dict[str, str]] = None,
               ip_whitelist: Optional[List[str]] = None):
    global _server_instance

    # Create proxy server instance with encapsulated state
    server_instance = ProxyServer(dc_opt, host, port, auth_required, auth_credentials, ip_whitelist)
    _server_instance = server_instance

    # Create a wrapper for _handle_client that passes server state
    async def handle_client_wrapper(reader, writer):
        await _handle_client(
            reader, writer,
            stats=server_instance.stats,
            dc_opt=server_instance.dc_opt,
            ws_pool=server_instance.ws_pool,
            ws_blacklist=server_instance.ws_blacklist,
            dc_fail_until=server_instance.dc_fail_until,
            auth_required=server_instance.auth_required,
            auth_credentials=server_instance.auth_credentials,
            ip_whitelist=server_instance.ip_whitelist
        )

    server = await asyncio.start_server(
        handle_client_wrapper, host, port)
    server_instance._server_instance = server

    for sock in server.sockets:
        try:
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            pass

    log.info("=" * 60)
    log.info("  Telegram WS Bridge Proxy")
    log.info("  Listening on   %s:%d", host, port)
    log.info("  Target DC IPs:")
    for dc in dc_opt.keys():
        ip = dc_opt.get(dc)
        log.info("    DC%d: %s", dc, ip)
    log.info("=" * 60)
    log.info("  Configure Telegram Desktop:")
    if auth_required and auth_credentials:
        log.info("    SOCKS5 proxy -> %s:%d  (user/pass required)", host, port)
    else:
        log.info("    SOCKS5 proxy -> %s:%d  (no user/pass)", host, port)
    log.info("=" * 60)

    async def log_stats():
        while True:
            await asyncio.sleep(60)
            bl = ', '.join(
                f'DC{d}{"m" if m else ""}'
                for d, m in sorted(server_instance.ws_blacklist)) or 'none'
            log.info("stats: %s | ws_bl: %s", server_instance.stats.summary(), bl)

    asyncio.create_task(log_stats())

    await server_instance.ws_pool.warmup(dc_opt)

    if stop_event:
        async def wait_stop():
            await stop_event.wait()
            server.close()
            me = asyncio.current_task()
            for task in list(asyncio.all_tasks()):
                if task is not me:
                    task.cancel()
            try:
                await server.wait_closed()
            except asyncio.CancelledError:
                pass
        asyncio.create_task(wait_stop())

    async with server:
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass
    _server_instance = None


def parse_dc_ip_list(dc_ip_list: List[str]) -> Dict[int, str]:
    """
    Parse list of 'DC:IP' strings into {dc: ip} dict.
    
    Args:
        dc_ip_list: List of strings in format 'DC:IP' (e.g., ['2:149.154.167.220'])
    
    Returns:
        Dictionary mapping DC IDs to IP addresses
    
    Raises:
        ValueError: If any entry has invalid format
    """
    dc_opt: Dict[int, str] = {}
    for entry in dc_ip_list:
        if ':' not in entry:
            raise ValueError(f"Invalid --dc-ip format {entry!r}, expected DC:IP")
        dc_s, ip_s = entry.split(':', 1)
        try:
            dc_n = int(dc_s)
            _socket.inet_aton(ip_s)
        except (ValueError, OSError):
            raise ValueError(f"Invalid --dc-ip {entry!r}")
        dc_opt[dc_n] = ip_s
    return dc_opt


def run_proxy(
    port: int,
    dc_opt: Dict[int, str],
    stop_event: Optional[asyncio.Event] = None,
    host: str = '127.0.0.1',
    auth_required: bool = False,
    auth_credentials: Optional[Dict[str, str]] = None
) -> None:
    """
    Run the proxy server (blocking).

    Can be called from threads. Use stop_event to gracefully shutdown.

    Args:
        port: Port to listen on
        dc_opt: Dictionary mapping DC IDs to target IPs
        stop_event: Optional event to signal shutdown
        host: Host to bind to (default: 127.0.0.1)
        auth_required: Require username/password authentication
        auth_credentials: Dict with 'username' and 'password' keys
    """
    asyncio.run(_run(port, dc_opt, stop_event, host, auth_required, auth_credentials))


def main() -> None:
    ap = argparse.ArgumentParser(
        description='Telegram Desktop WebSocket Bridge Proxy')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT,
                    help=f'Listen port (default {DEFAULT_PORT})')
    ap.add_argument('--host', type=str, default='127.0.0.1',
                    help='Listen host (default 127.0.0.1)')
    ap.add_argument('--dc-ip', metavar='DC:IP', action='append',
                    default=['2:149.154.167.220', '4:149.154.167.220'],
                    help='Target IP for a DC, e.g. --dc-ip 1:149.154.175.205'
                         ' --dc-ip 2:149.154.167.220')
    ap.add_argument('--auth', action='store_true',
                    help='Require username/password authentication')
    ap.add_argument('--auth-username', type=str, default='user',
                    help='Auth username (default: user)')
    ap.add_argument('--auth-password', type=str, default='pass',
                    help='Auth password (default: pass)')
    ap.add_argument('-v', '--verbose', action='store_true',
                    help='Debug logging')
    args = ap.parse_args()

    try:
        dc_opt = parse_dc_ip_list(args.dc_ip)
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s  %(levelname)-5s  %(message)s',
        datefmt='%H:%M:%S',
    )

    auth_credentials = None
    if args.auth:
        auth_credentials = {
            'username': args.auth_username,
            'password': args.auth_password
        }

    try:
        asyncio.run(_run(args.port, dc_opt, host=args.host,
                        auth_required=args.auth,
                        auth_credentials=auth_credentials))
    except KeyboardInterrupt:
        log.info("Shutting down. Final stats: %s", get_stats_summary())


if __name__ == '__main__':
    main()
