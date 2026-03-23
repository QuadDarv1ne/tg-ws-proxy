"""
Obfsproxy Integration for TG WS Proxy.

Implements additional obfuscation layers:
- obfs4 - Obfuscation protocol v4
- scramblesuit - Multi-protocol obfuscation
- meek-lite - Lightweight domain fronting

Based on the original obfsproxy design but implemented in Python.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-ws-obfsproxy')


class ObfsProtocol(Enum):
    """Obfuscation protocols."""
    OBFUSCATED = auto()  # Simple obfuscation
    OBFSC4 = auto()      # obfs4-like
    SCRAMBLESUIT = auto()
    MEK_LITE = auto()


@dataclass
class ObfsConfig:
    """Obfuscation configuration."""
    protocol: ObfsProtocol = ObfsProtocol.OBFSC4
    
    # obfs4 settings
    cert: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    seed: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    
    # ScrambleSuit settings
    password: str = ''
    interval_min: int = 50
    interval_max: int = 300
    
    # Meek-lite settings
    front_domain: str = 'www.google.com'
    
    # Common settings
    add_padding: bool = True
    timing_jitter: bool = True
    jitter_ms: tuple[int, int] = (10, 100)


class Obfs4Obfuscator:
    """
    obfs4-like obfuscation.

    Makes traffic look like random noise to DPI systems.
    """

    # Handshake sizes
    CLIENT_HANDSHAKE_SIZE = 1968
    SERVER_HANDSHAKE_SIZE = 1948

    def __init__(self, cert: bytes | None = None, seed: bytes | None = None):
        """
        Initialize obfs4 obfuscator.

        Args:
            cert: Certificate for authentication
            seed: Seed for deterministic key generation
        """
        self.cert = cert or secrets.token_bytes(32)
        self.seed = seed or secrets.token_bytes(32)
        self._client_key: bytes | None = None
        self._server_key: bytes | None = None
        self._initialized = False

    def _derive_keys(self, shared_secret: bytes) -> tuple[bytes, bytes]:
        """Derive client and server keys from shared secret."""
        client_key = hashlib.sha256(shared_secret + b'client').digest()
        server_key = hashlib.sha256(shared_secret + b'server').digest()
        return client_key, server_key

    def _xor_with_keystream(self, data: bytes, key: bytes, counter: int = 0) -> bytes:
        """XOR data with keystream generated from key."""
        keystream = b''
        block_idx = counter
        
        while len(keystream) < len(data):
            block = hashlib.sha256(key + struct.pack('>I', block_idx)).digest()
            keystream += block
            block_idx += 1
        
        keystream = keystream[:len(data)]
        return bytes(a ^ b for a, b in zip(data, keystream))

    def create_client_handshake(self) -> bytes:
        """Create client-side obfuscated handshake."""
        # Generate random padding
        padding_size = self.CLIENT_HANDSHAKE_SIZE - 64
        padding = secrets.token_bytes(padding_size)

        # Create handshake with embedded key material
        ephemeral_key = secrets.token_bytes(32)
        handshake = padding + ephemeral_key + self.cert

        # Derive keys
        shared_secret = hashlib.sha256(self.seed + ephemeral_key).digest()
        self._client_key, self._server_key = self._derive_keys(shared_secret)
        self._initialized = True

        # Obfuscate with keystream
        obfuscated = self._xor_with_keystream(handshake, self._client_key or b'')

        return obfuscated

    def process_server_handshake(self, handshake: bytes) -> bool:
        """Process server handshake and verify."""
        if len(handshake) != self.SERVER_HANDSHAKE_SIZE:
            return False

        # Derive keys
        shared_secret = hashlib.sha256(self.seed + handshake[-32:]).digest()
        self._server_key, self._client_key = self._derive_keys(shared_secret)
        self._initialized = True

        return True

    def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data."""
        if not self._initialized:
            # Auto-create handshake
            self.create_client_handshake()

        # Add length prefix
        length_prefix = struct.pack('>I', len(data))

        # XOR with keystream
        counter = 1  # Start after handshake
        obfuscated = self._xor_with_keystream(length_prefix + data, self._client_key or b'', counter)

        return obfuscated

    def deobfuscate(self, data: bytes) -> bytes | None:
        """Deobfuscate data."""
        if not self._initialized:
            return None

        # XOR with keystream
        counter = 1
        deobfuscated = self._xor_with_keystream(data, self._server_key or b'', counter)

        # Extract length and data
        if len(deobfuscated) < 4:
            return None

        length = struct.unpack('>I', deobfuscated[:4])[0]

        if len(deobfuscated) < 4 + length:
            return None

        return deobfuscated[4:4+length]


class ScrambleSuitObfuscator:
    """
    ScrambleSuit-like obfuscation.

    Combines multiple obfuscation techniques with periodic key changes.
    """

    def __init__(self, password: str, interval_min: int = 50, interval_max: int = 300):
        """
        Initialize ScrambleSuit obfuscator.

        Args:
            password: Shared password
            interval_min: Minimum packet interval (ms)
            interval_max: Maximum packet interval (ms)
        """
        self.password = password
        self.interval_min = interval_min
        self.interval_max = interval_max

        # Derive keys from password
        self.uniform_dh_key = hashlib.sha256(password.encode() + b'uniform').digest()
        self.hmac_key = hashlib.sha256(password.encode() + b'hmac').digest()

        self._packet_counter = 0

    def _hmac_sign(self, data: bytes) -> bytes:
        """HMAC sign data."""
        return hmac.new(self.hmac_key, data, hashlib.sha256).digest()[:10]

    def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate packet with ScrambleSuit."""
        self._packet_counter += 1

        # Add HMAC
        signature = self._hmac_sign(data + struct.pack('>I', self._packet_counter))

        # Add length prefix
        length = len(data) + len(signature)
        length_prefix = struct.pack('>H', length & 0x3FFF)  # 14-bit length

        # Add timing obfuscation (padding)
        if self.interval_min < self.interval_max:
            padding_size = secrets.randbelow(self.interval_max - self.interval_min) + self.interval_min
            padding = secrets.token_bytes(padding_size)
        else:
            padding = b''

        # Combine
        packet = length_prefix + padding + data + signature

        # XOR with keystream
        keystream = hashlib.sha256(
            self.uniform_dh_key + struct.pack('>I', self._packet_counter)
        ).digest() * (len(packet) // 32 + 1)
        keystream = keystream[:len(packet)]

        obfuscated = bytes(a ^ b for a, b in zip(packet, keystream))

        return obfuscated

    def deobfuscate(self, data: bytes) -> bytes | None:
        """Deobfuscate ScrambleSuit packet."""
        # XOR with keystream
        self._packet_counter += 1
        keystream = hashlib.sha256(
            self.uniform_dh_key + struct.pack('>I', self._packet_counter)
        ).digest() * (len(data) // 32 + 1)
        keystream = keystream[:len(data)]

        deobfuscated = bytes(a ^ b for a, b in zip(data, keystream))

        # Extract length
        if len(deobfuscated) < 2:
            return None

        length = struct.unpack('>H', deobfuscated[:2])[0] & 0x3FFF

        # Validate HMAC
        if len(deobfuscated) < 2 + length:
            return None

        packet = deobfuscated[2:2+length]
        signature = packet[-10:]
        payload = packet[:-10]

        expected_sig = self._hmac_sign(payload + struct.pack('>I', self._packet_counter))

        if signature != expected_sig[:10]:
            return None

        return payload


class MeekLiteObfuscator:
    """
    Lightweight domain fronting obfuscation.

    Makes traffic appear as HTTPS to a front domain.
    """

    def __init__(self, front_domain: str = 'www.google.com'):
        """
        Initialize Meek-lite.

        Args:
            front_domain: Domain to front
        """
        self.front_domain = front_domain
        self.session_id = secrets.token_hex(8)

    def obfuscate(self, data: bytes) -> bytes:
        """Wrap data in HTTPS-like envelope."""
        # Build HTTP-like header
        header = (
            f'POST /update?sid={self.session_id} HTTP/1.1\r\n'
            f'Host: {self.front_domain}\r\n'
            f'Content-Type: application/octet-stream\r\n'
            f'Content-Length: {len(data)}\r\n'
            f'Connection: keep-alive\r\n'
            f'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n'
            f'X-Forwarded-Host: {self.front_domain}\r\n'
            f'\r\n'
        ).encode('utf-8')

        return header + data

    def deobfuscate(self, data: bytes) -> bytes | None:
        """Extract payload from HTTP-like envelope."""
        # Find header end
        header_end = data.find(b'\r\n\r\n')
        if header_end == -1:
            return None

        # Extract body
        return data[header_end + 4:]


class ObfsproxyTransport:
    """
    Obfsproxy wrapper transport.

    Adds obfuscation layer to any underlying transport.
    """

    def __init__(
        self,
        transport: Any,
        config: ObfsConfig | None = None
    ):
        """
        Initialize obfsproxy transport.

        Args:
            transport: Underlying transport
            config: Obfuscation configuration
        """
        self.transport = transport
        self.config = config or ObfsConfig()

        # Create obfuscator based on protocol
        if self.config.protocol == ObfsProtocol.OBFSC4:
            self.obfuscator = Obfs4Obfuscator(
                cert=self.config.cert,
                seed=self.config.seed
            )
        elif self.config.protocol == ObfsProtocol.SCRAMBLESUIT:
            self.obfuscator = ScrambleSuitObfuscator(
                password=self.config.password or 'default_password',
                interval_min=self.config.interval_min,
                interval_max=self.config.interval_max
            )
        elif self.config.protocol == ObfsProtocol.MEK_LITE:
            self.obfuscator = MeekLiteObfuscator(
                front_domain=self.config.front_domain
            )
        else:
            self.obfuscator = None

        self._handshake_sent = False

    async def connect(self, timeout: float = 10.0) -> bool:
        """Connect with obfuscation."""
        if not await self.transport.connect(timeout):
            return False

        # Send obfs4 handshake if needed
        if isinstance(self.obfuscator, Obfs4Obfuscator):
            handshake = self.obfuscator.create_client_handshake()
            await self.transport.send(handshake)
            self._handshake_sent = True

        return True

    async def send(self, data: bytes) -> bool:
        """Send obfuscated data."""
        if not self.obfuscator:
            return await self.transport.send(data)

        obfuscated = self.obfuscator.obfuscate(data)
        return await self.transport.send(obfuscated)

    async def recv(self, max_size: int = 65536) -> bytes | None:
        """Receive and deobfuscate data."""
        if not self.obfuscator:
            return await self.transport.recv(max_size)

        obfuscated = await self.transport.recv(max_size)
        if not obfuscated:
            return None

        # Handle server handshake for obfs4
        if isinstance(self.obfuscator, Obfs4Obfuscator) and not self._handshake_sent:
            if self.obfuscator.process_server_handshake(obfuscated):
                self._handshake_sent = True
                return b''  # Handshake complete

        return self.obfuscator.deobfuscate(obfuscated)

    async def close(self) -> None:
        """Close transport."""
        await self.transport.close()

    def get_stats(self) -> dict:
        """Get statistics."""
        stats = self.transport.get_stats()
        stats['obfuscation'] = self.config.protocol.name
        return stats


def create_obfs_transport(
    transport: Any,
    protocol: str = 'obfs4',
    password: str = '',
    front_domain: str = 'www.google.com'
) -> ObfsproxyTransport:
    """
    Create obfuscated transport.

    Args:
        transport: Underlying transport
        protocol: Obfuscation protocol (obfs4, scramblesuit, meek-lite)
        password: Password for ScrambleSuit
        front_domain: Front domain for Meek-lite

    Returns:
        ObfsproxyTransport instance
    """
    protocol_map = {
        'obfs4': ObfsProtocol.OBFSC4,
        'scramblesuit': ObfsProtocol.SCRAMBLESUIT,
        'meek-lite': ObfsProtocol.MEK_LITE,
    }

    config = ObfsConfig(
        protocol=protocol_map.get(protocol, ObfsProtocol.OBFSC4),
        password=password,
        front_domain=front_domain
    )

    return ObfsproxyTransport(transport, config)


def check_obfs_availability() -> dict[str, Any]:
    """Check obfuscation availability."""
    return {
        'obfs4_available': True,
        'scramblesuit_available': True,
        'meek_lite_available': True,
        'protocols': ['obfs4', 'scramblesuit', 'meek-lite'],
        'recommendation': 'obfs4 for most cases, scramblesuit for strict DPI'
    }


if __name__ == '__main__':
    # Demo
    print("Obfsproxy Integration Demo")
    print("=" * 50)

    avail = check_obfs_availability()
    print(f"Available: {avail['protocols']}")
    print(f"Recommendation: {avail['recommendation']}")

    # Test obfs4
    obfs4 = Obfs4Obfuscator()
    handshake = obfs4.create_client_handshake()
    print(f"\nobfs4 handshake size: {len(handshake)} bytes")

    # Test data
    original = b"Hello, obfuscated world!"
    obfuscated = obfs4.obfuscate(original)
    print(f"Original: {len(original)} bytes")
    print(f"Obfuscated: {len(obfuscated)} bytes")
