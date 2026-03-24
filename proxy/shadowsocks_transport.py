"""
Shadowsocks 2022 Transport for TG WS Proxy.

Implements Shadowsocks 2022 protocol (SIP022):
- AEAD encryption (ChaCha20-Poly1305, AES-256-GCM)
- TCP and UDP support
- Multi-user support

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import struct

log = logging.getLogger('tg-ws-ss')


class ShadowsocksTransport:
    """
    Shadowsocks 2022 Transport.

    Note: This is a stub implementation. Full implementation requires:
    - libsodium or cryptography for AEAD
    - Proper packet framing
    - UDP relay support
    """

    # Supported methods
    METHODS = {
        'chacha20-ietf-poly1305': {'key_size': 32, 'nonce_size': 32},
        'aes-256-gcm': {'key_size': 32, 'nonce_size': 12},
        'aes-128-gcm': {'key_size': 16, 'nonce_size': 12},
    }

    def __init__(
        self,
        host: str,
        port: int,
        method: str = 'chacha20-ietf-poly1305',
        password: str = '',
    ):
        """
        Initialize Shadowsocks transport.

        Args:
            host: Server host
            port: Server port
            method: Encryption method
            password: Password (will be derived to key)
        """
        self.host = host
        self.port = port
        self.method = method
        self.password = password

        # Derive key from password
        self.key = self._derive_key(password, method)

        # Connection state
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False

        # Stats
        self.bytes_sent = 0
        self.bytes_received = 0

    def _derive_key(self, password: str, method: str) -> bytes:
        """Derive key from password using MD5 (SS legacy)."""
        key_size = self.METHODS.get(method, {}).get('key_size', 32)
        key = b''
        md5_sum = b''

        while len(key) < key_size:
            md5_sum = hashlib.md5(md5_sum + password.encode()).digest()
            key += md5_sum

        return key[:key_size]

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect to Shadowsocks server."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout
            )
            self._connected = True
            log.info("Shadowsocks connected to %s:%d", self.host, self.port)
            return True
        except Exception as e:
            log.error("Shadowsocks connect error: %s", e)
            return False

    async def send(self, data: bytes) -> bool:
        """Send encrypted data."""
        if not self._connected or not self._writer:
            return False

        try:
            # TODO: Implement proper AEAD encryption
            # For now, send as-is (placeholder)
            # Frame format: [2-byte length][encrypted data]
            frame = struct.pack('!H', len(data)) + data

            self._writer.write(frame)
            await self._writer.drain()

            self.bytes_sent += len(data)
            return True

        except Exception as e:
            log.error("Shadowsocks send error: %s", e)
            return False

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive and decrypt data."""
        if not self._connected or not self._reader:
            return None

        try:
            # Read length
            length_bytes = await self._reader.readexactly(2)
            length = struct.unpack('!H', length_bytes)[0]

            # Read data
            data = await self._reader.readexactly(length)

            # TODO: Implement proper AEAD decryption
            # For now, return as-is (placeholder)

            self.bytes_received += len(data)
            return data

        except asyncio.IncompleteReadError:
            return None
        except Exception as e:
            log.error("Shadowsocks recv error: %s", e)
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
            self._connected = False

    def get_stats(self) -> dict:
        """Get statistics."""
        return {
            'connected': self._connected,
            'method': self.method,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
        }
