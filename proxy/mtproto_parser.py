"""
MTProto Protocol Parser.

Provides parsing and manipulation of MTProto packets:
- DC ID extraction from init packets
- Init packet patching
- Message splitting for WebSocket frames
- Protocol detection

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import logging
import socket as _socket
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    INIT_DC_OFFSET,
    INIT_IV_OFFSET,
    INIT_IV_SIZE,
    INIT_KEY_OFFSET,
    INIT_KEY_SIZE,
    INIT_PACKET_SIZE,
    PROTO_ABRIDGED,
    PROTO_OBFUSCATED,
    PROTO_PADDED_ABRIDGED,
    TG_RANGES,
)

log = logging.getLogger('tg-ws-mtproto')


def is_telegram_ip(ip: str) -> bool:
    """
    Check if IP address belongs to Telegram ranges.

    Args:
        ip: IP address string

    Returns:
        True if IP is in Telegram ranges
    """
    try:
        n = struct.unpack('!I', _socket.inet_aton(ip))[0]
        return any(lo <= n <= hi for lo, hi in TG_RANGES)
    except OSError:
        return False


def is_http_transport(data: bytes) -> bool:
    """
    Check if data starts with HTTP method.

    Args:
        data: Packet data

    Returns:
        True if data looks like HTTP request
    """
    return (
        data[:5] == b'POST ' or
        data[:4] == b'GET ' or
        data[:5] == b'HEAD ' or
        data[:8] == b'OPTIONS '
    )


def extract_dc_from_init(data: bytes) -> tuple[int | None, bool]:
    """
    Extract DC ID from the 64-byte MTProto obfuscation init packet.

    Args:
        data: Init packet data (64 bytes)

    Returns:
        Tuple of (dc_id, is_media)
        - dc_id: Data center ID (1-5) or None if extraction failed
        - is_media: True if media DC (negative dc_raw)
    """
    if len(data) < INIT_PACKET_SIZE:
        return None, False

    try:
        # Extract encryption key and IV
        key = bytes(data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])

        # Decrypt bytes 56-64 to get protocol and DC info
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        keystream = encryptor.update(b'\x00' * 64) + encryptor.finalize()

        # XOR to get plaintext
        plain = bytes(a ^ b for a, b in zip(data[56:64], keystream[56:64]))

        # Parse protocol and DC
        proto = struct.unpack('<I', plain[0:4])[0]
        dc_raw = struct.unpack('<h', plain[4:6])[0]

        log.debug(
            "DC extraction: proto=0x%08X dc_raw=%d plain=%s",
            proto, dc_raw, plain.hex()
        )

        # Validate protocol
        if proto in (PROTO_OBFUSCATED, PROTO_ABRIDGED, PROTO_PADDED_ABRIDGED):
            dc = abs(dc_raw)
            if 1 <= dc <= 5:
                return dc, (dc_raw < 0)

    except Exception as exc:
        log.debug("DC extraction failed: %s", exc)

    return None, False


def patch_init_dc(data: bytes, dc: int) -> bytes:
    """
    Patch dc_id in the 64-byte MTProto init packet.

    Mobile clients with useSecret=0 leave bytes 60-61 as random.
    The WS relay needs a valid dc_id to route correctly.

    Args:
        data: Init packet data
        dc: Target DC ID to patch

    Returns:
        Patched init packet
    """
    if len(data) < INIT_PACKET_SIZE:
        return data

    new_dc = struct.pack('<h', dc)

    try:
        # Extract key and IV
        key_raw = bytes(data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])

        # Generate keystream
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        enc = cipher.encryptor()
        ks = enc.update(b'\x00' * 64) + enc.finalize()

        # Patch DC bytes
        patched = bytearray(data[:INIT_PACKET_SIZE])
        patched[INIT_DC_OFFSET] = ks[INIT_DC_OFFSET] ^ new_dc[0]
        patched[INIT_DC_OFFSET + 1] = ks[INIT_DC_OFFSET + 1] ^ new_dc[1]

        log.debug("Init packet patched: dc_id -> %d", dc)

        # Append remaining data if any
        if len(data) > INIT_PACKET_SIZE:
            return bytes(patched) + data[INIT_PACKET_SIZE:]
        return bytes(patched)

    except Exception as exc:
        log.debug("DC patching failed: %s", exc)
        return data


class MsgSplitter:
    """
    Splits client TCP data into individual MTProto abridged-protocol
    messages so each can be sent as a separate WebSocket frame.

    The Telegram WS relay processes one MTProto message per WS frame.
    Mobile clients batch multiple messages in a single TCP write (e.g.
    msgs_ack + req_DH_params). If sent as one WS frame, the relay
    only processes the first message — DH handshake never completes.
    """

    def __init__(self, init_data: bytes):
        """
        Initialize message splitter.

        Args:
            init_data: 64-byte init packet containing encryption key and IV
        """
        key_raw = bytes(init_data[INIT_KEY_OFFSET:INIT_KEY_OFFSET + INIT_KEY_SIZE])
        iv = bytes(init_data[INIT_IV_OFFSET:INIT_IV_OFFSET + INIT_IV_SIZE])
        cipher = Cipher(algorithms.AES(key_raw), modes.CTR(iv))
        self._encryptor = cipher.encryptor()
        self._buf = b''

    def split(self, chunk: bytes) -> list[bytes]:
        """
        Split chunk into individual MTProto messages.

        Args:
            chunk: Raw TCP data from client

        Returns:
            List of individual messages ready for WebSocket frames
        """
        self._buf += chunk
        messages: list[bytes] = []

        while len(self._buf) >= 4:
            # Decrypt first 4 bytes to get message length
            keystream = self._encryptor.update(b'\x00' * 4)
            plain_len = bytes(a ^ b for a, b in zip(self._buf[:4], keystream))
            msg_len_val = struct.unpack('<I', plain_len)[0]

            # Calculate total message size
            if msg_len_val < 0x7F:
                # Short length (1 byte)
                total_len = 1 + msg_len_val * 4
            else:
                # Long length (4 bytes)
                if len(self._buf) < 4:
                    break
                total_len = 4 + msg_len_val * 4

            # Check if we have complete message
            if len(self._buf) < total_len:
                # Rewind encryptor (not possible with CTR, so we break)
                break

            # Extract message
            msg = self._buf[:total_len]
            self._buf = self._buf[total_len:]
            messages.append(msg)

            # Update encryptor position
            if total_len > 4:
                self._encryptor.update(b'\x00' * (total_len - 4))

        return messages


def parse_mtproto_length(data: bytes) -> int | None:
    """
    Parse MTProto message length from abridged protocol.

    Args:
        data: Message data

    Returns:
        Message length in bytes or None if invalid
    """
    if len(data) < 1:
        return None

    first_byte = data[0]

    if first_byte < 0x7F:
        # Short length: 1 byte + length * 4
        return 1 + first_byte * 4
    elif len(data) >= 4:
        # Long length: 4 bytes + length * 4
        length: int = struct.unpack('<I', data[:4])[0]
        return 4 + length * 4

    return None


__all__ = [
    'is_telegram_ip',
    'is_http_transport',
    'extract_dc_from_init',
    'patch_init_dc',
    'MsgSplitter',
    'parse_mtproto_length',
]
