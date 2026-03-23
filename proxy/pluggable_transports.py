"""
Pluggable Transports for circumventing censorship.

Implements various obfuscation techniques to bypass DPI (Deep Packet Inspection):
- Obfs4-like obfuscation
- WebSocket fragmentation
- TLS fingerprint spoofing
- Domain fronting
- Shadowsocks-style encryption
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import socket
import ssl
import struct
import time
from typing import Any

log = logging.getLogger("tg-ws-obfs")

# =============================================================================
# Obfs4-like Obfuscation
# =============================================================================


class Obfs4Obfuscator:
    """
    Obfs4-style traffic obfuscation.

    Makes traffic look like random noise to DPI systems.
    Based on the obfs4 protocol design.
    """

    # Client and server handshake sizes
    CLIENT_HANDSHAKE_SIZE = 1968
    SERVER_HANDSHAKE_SIZE = 1948

    # Magic header to detect obfs4 traffic (optional)
    OBFUSCATION_MAGIC = b'\x00\x00\x00\x00'

    def __init__(self, cert: bytes | None = None, seed: bytes | None = None):
        """
        Initialize obfuscator.

        Args:
            cert: Optional certificate for authentication
            seed: Optional seed for deterministic key generation
        """
        self.cert = cert or secrets.token_bytes(32)
        self.seed = seed or secrets.token_bytes(32)
        self._client_key = None
        self._server_key = None
        self._initialized = False

    def _derive_keys(self, shared_secret: bytes) -> tuple[bytes, bytes]:
        """Derive client and server keys from shared secret."""
        client_key = hashlib.sha256(shared_secret + b'client').digest()
        server_key = hashlib.sha256(shared_secret + b'server').digest()
        return client_key, server_key

    def _generate_handshake(self, is_client: bool = True) -> bytes:
        """Generate obfuscated handshake data."""
        # Generate random padding
        padding_size = (self.CLIENT_HANDSHAKE_SIZE if is_client
                       else self.SERVER_HANDSHAKE_SIZE) - 32
        padding = secrets.token_bytes(padding_size)

        # Create handshake with embedded key material
        ephemeral_key = secrets.token_bytes(32)
        handshake = padding + ephemeral_key

        return handshake

    def create_client_handshake(self) -> bytes:
        """Create client-side obfuscated handshake."""
        handshake = self._generate_handshake(is_client=True)

        # Derive keys from handshake
        self._client_key, self._server_key = self._derive_keys(
            hashlib.sha256(handshake[-32:]).digest()
        )
        self._initialized = True

        return handshake

    def process_server_handshake(self, handshake: bytes) -> bool:
        """Process server handshake and verify."""
        if len(handshake) != self.SERVER_HANDSHAKE_SIZE:
            return False

        # Derive keys
        self._server_key, self._client_key = self._derive_keys(
            hashlib.sha256(handshake[-32:]).digest()
        )
        self._initialized = True
        return True

    def obfuscate(self, data: bytes) -> bytes:
        """
        Obfuscate data using XOR cipher with key expansion.

        Args:
            data: Plain data to obfuscate

        Returns:
            Obfuscated data
        """
        if not self._initialized:
            raise RuntimeError("Handshake not completed")

        # Generate keystream
        keystream = self._generate_keystream(len(data), self._client_key)

        # XOR encryption
        return bytes(a ^ b for a, b in zip(data, keystream))

    def deobfuscate(self, data: bytes) -> bytes:
        """
        Deobfuscate data.

        Args:
            data: Obfuscated data

        Returns:
            Original plain data
        """
        if not self._initialized:
            raise RuntimeError("Handshake not completed")

        # Generate keystream (same as client for symmetric encryption)
        keystream = self._generate_keystream(len(data), self._client_key)

        # XOR decryption
        return bytes(a ^ b for a, b in zip(data, keystream))

    def _generate_keystream(self, length: int, key: bytes) -> bytes:
        """Generate XOR keystream using HMAC-DRBG-like construction."""
        keystream = b''
        counter = 0
        while len(keystream) < length:
            block = hmac.new(key, struct.pack('>I', counter), hashlib.sha256).digest()
            keystream += block
            counter += 1
        return keystream[:length]


# =============================================================================
# WebSocket Fragmentation
# =============================================================================


class WSFragmenter:
    """
    WebSocket frame fragmentation for DPI bypass.

    Breaks large WebSocket frames into smaller chunks to evade
    pattern-based detection systems.
    """

    def __init__(
        self,
        min_fragment_size: int = 64,
        max_fragment_size: int = 256,
        randomize_sizes: bool = True,
    ):
        """
        Initialize fragmenter.

        Args:
            min_fragment_size: Minimum fragment size in bytes
            max_fragment_size: Maximum fragment size in bytes
            randomize_sizes: Whether to randomize fragment sizes
        """
        self.min_size = min_fragment_size
        self.max_size = max_fragment_size
        self.randomize = randomize_sizes

    def fragment(self, data: bytes) -> list[bytes]:
        """
        Split data into fragments.

        Args:
            data: Data to fragment

        Returns:
            List of fragmented data chunks
        """
        if len(data) <= self.min_size:
            return [data]

        fragments = []
        offset = 0

        while offset < len(data):
            # Determine fragment size
            if self.randomize:
                size = secrets.randbelow(
                    self.max_size - self.min_size + 1
                ) + self.min_size
            else:
                size = self.max_size

            # Calculate remaining bytes
            remaining = len(data) - offset
            actual_size = min(size, remaining)

            # Extract fragment
            fragment = data[offset:offset + actual_size]
            fragments.append(fragment)
            offset += actual_size

        return fragments

    def reassemble(self, fragments: list[bytes]) -> bytes:
        """
        Reassemble fragments into original data.

        Args:
            fragments: List of data fragments

        Returns:
            Reassembled original data
        """
        return b''.join(fragments)


# =============================================================================
# TLS Fingerprint Spoofing
# =============================================================================


class TLSFingerprintSpoof:
    """
    TLS fingerprint spoofing to evade JA3 detection.

    Modifies TLS ClientHello to mimic popular browsers.
    """

    # Common JA3 fingerprints to mimic
    BROWSER_FINGERPRINTS = {
        'chrome_120': {
            'version': '0x0303',  # TLS 1.2
            'ciphers': [
                0x1301,  # TLS_AES_128_GCM_SHA256
                0x1302,  # TLS_AES_256_GCM_SHA384
                0x1303,  # TLS_CHACHA20_POLY1305_SHA256
                0xC02B,  # TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
                0xC02F,  # TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
                0xC02C,  # TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
                0xC030,  # TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
                0xCCA9,  # TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
                0xCCA8,  # TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
                0xC013,  # TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA
                0xC014,  # TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA
                0x009C,  # TLS_RSA_WITH_AES_128_GCM_SHA256
                0x009D,  # TLS_RSA_WITH_AES_256_GCM_SHA384
                0x002F,  # TLS_RSA_WITH_AES_128_CBC_SHA
                0x0035,  # TLS_RSA_WITH_AES_256_CBC_SHA
            ],
            'extensions': [
                0x0000,  # SNI
                0x0005,  # Status Request
                0x000A,  # Supported Groups
                0x000B,  # EC Point Formats
                0x0010,  # ALPN
                0x0017,  # Extended Master Secret
                0x001B,  # Compress Certificate
                0x0023,  # Session Ticket
                0x002B,  # Supported Versions
                0x002D,  # PSK Key Exchange Modes
                0x0033,  # Key Share
                0x0039,  # Early Data
                0xFF01,  # Renegotiation Info
            ],
            'curves': [0x001D, 0x0017, 0x0018, 0x0019],
            'alpn': [b'h2', b'http/1.1'],
        },
        'firefox_121': {
            'version': '0x0303',
            'ciphers': [
                0x1301, 0x1302, 0x1303,
                0xC02B, 0xC02F, 0xC02C, 0xC030,
                0xCCA9, 0xCCA8,
                0xC013, 0xC014, 0x009C, 0x009D,
                0x002F, 0x0035, 0x000A, 0x0004,
            ],
            'extensions': [
                0x0000, 0x0005, 0x000A, 0x000B,
                0x0010, 0x0017, 0x0023, 0x002B,
                0x002D, 0x0033, 0x0039, 0xFF01,
                0xFE0D,  # Encrypted Client Hello
            ],
            'curves': [0x001D, 0x0017, 0x0018, 0xFF01],
            'alpn': [b'h2', b'http/1.1'],
        },
        'safari_17': {
            'version': '0x0303',
            'ciphers': [
                0x1301, 0x1302, 0x1303,
                0xC02B, 0xC02F, 0xC02C, 0xC030,
                0xCCA9, 0xCCA8,
                0xC013, 0xC014,
            ],
            'extensions': [
                0x0000, 0x0005, 0x000A, 0x000B,
                0x0010, 0x0017, 0x0023, 0x002B,
                0x002D, 0x0033, 0xFF01,
            ],
            'curves': [0x001D, 0x0017, 0x0018],
            'alpn': [b'h2', b'http/1.1'],
        },
    }

    def __init__(self, browser_profile: str = 'chrome_120'):
        """
        Initialize TLS spoofing.

        Args:
            browser_profile: Browser fingerprint to mimic
        """
        self.profile = browser_profile
        self.fingerprint = self.BROWSER_FINGERPRINTS.get(
            browser_profile, self.BROWSER_FINGERPRINTS['chrome_120']
        )

    def create_ssl_context(self) -> ssl.SSLContext:
        """
        Create SSL context with spoofed fingerprint.

        Returns:
            Configured SSL context
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Set TLS version
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3

        # Set ciphers
        cipher_string = self._build_cipher_string()
        ctx.set_ciphers(cipher_string)

        # Set ALPN protocols
        ctx.set_alpn_protocols([p.decode() for p in self.fingerprint['alpn']])

        return ctx

    def _build_cipher_string(self) -> str:
        """Build OpenSSL cipher string from fingerprint."""
        # Map cipher codes to OpenSSL names
        cipher_map = {
            0x1301: 'TLS_AES_128_GCM_SHA256',
            0x1302: 'TLS_AES_256_GCM_SHA384',
            0x1303: 'TLS_CHACHA20_POLY1305_SHA256',
            0xC02B: 'ECDHE-ECDSA-AES128-GCM-SHA256',
            0xC02F: 'ECDHE-RSA-AES128-GCM-SHA256',
            0xC02C: 'ECDHE-ECDSA-AES256-GCM-SHA384',
            0xC030: 'ECDHE-RSA-AES256-GCM-SHA384',
            0xCCA9: 'ECDHE-ECDSA-CHACHA20-POLY1305',
            0xCCA8: 'ECDHE-RSA-CHACHA20-POLY1305',
            0xC013: 'ECDHE-RSA-AES128-SHA',
            0xC014: 'ECDHE-RSA-AES256-SHA',
            0x009C: 'AES128-GCM-SHA256',
            0x009D: 'AES256-GCM-SHA384',
            0x002F: 'AES128-SHA',
            0x0035: 'AES256-SHA',
            0x000A: 'ECDHE-RSA-DES-CBC3-SHA',
            0x0004: 'DES-CBC3-SHA',
        }

        ciphers = []
        for code in self.fingerprint['ciphers']:
            if code in cipher_map:
                ciphers.append(cipher_map[code])

        return ':'.join(ciphers) if ciphers else 'DEFAULT'


# =============================================================================
# Domain Fronting
# =============================================================================


class DomainFronting:
    """
    Domain fronting for circumventing SNI-based blocking.

    Uses CDN domains to mask the actual destination.
    """

    # Fronting domains (CDN providers)
    FRONTING_DOMAINS = {
        'cloudflare': {
            'front': 'ajax.cloudflare.com',
            'host_header': 'kws1.web.telegram.org',
            'description': 'Cloudflare CDN',
        },
        'google': {
            'front': 'www.google.com',
            'host_header': 'kws1.web.telegram.org',
            'description': 'Google CDN',
        },
        'azure': {
            'front': 'ajax.aspnetcdn.com',
            'host_header': 'kws1.web.telegram.org',
            'description': 'Azure CDN',
        },
        'amazon': {
            'front': 'd0.awsstatic.com',
            'host_header': 'kws1.web.telegram.org',
            'description': 'Amazon CloudFront',
        },
    }

    def __init__(self, provider: str = 'cloudflare'):
        """
        Initialize domain fronting.

        Args:
            provider: CDN provider to use
        """
        if provider not in self.FRONTING_DOMAINS:
            raise ValueError(f"Unknown provider: {provider}")

        self.provider = provider
        self.config = self.FRONTING_DOMAINS[provider]

    def get_front_domain(self) -> str:
        """Get the fronting domain for SNI."""
        return self.config['front']

    def get_host_header(self) -> str:
        """Get the Host header value (actual destination)."""
        return self.config['host_header']

    def wrap_connection(
        self,
        sock: socket.socket,
        server_hostname: str,
    ) -> ssl.SSLContext:
        """
        Wrap socket with domain fronting.

        Args:
            sock: Raw socket
            server_hostname: Actual server hostname

        Returns:
            SSL context configured for fronting
        """
        # Create SSL context with spoofed fingerprint
        tls_spoof = TLSFingerprintSpoof('chrome_120')
        ctx = tls_spoof.create_ssl_context()

        # Wrap with SNI set to front domain
        wrapped = ctx.wrap_socket(
            sock,
            server_hostname=self.get_front_domain(),
            do_handshake_on_connect=False,
        )

        # Store actual host header for later use
        wrapped._actual_host = self.get_host_header()

        return wrapped


# =============================================================================
# Shadowsocks-style Encryption
# =============================================================================


class ShadowsocksObfs:
    """
    Shadowsocks-compatible encryption for additional obfuscation.

    Provides an extra layer of encryption on top of TLS.
    """

    SUPPORTED_CIPHERS = {
        'aes-256-gcm': {
            'key_size': 32,
            'nonce_size': 12,
            'tag_size': 16,
        },
        'chacha20-ietf-poly1305': {
            'key_size': 32,
            'nonce_size': 12,
            'tag_size': 16,
        },
        'aes-128-gcm': {
            'key_size': 16,
            'nonce_size': 12,
            'tag_size': 16,
        },
    }

    def __init__(self, password: str, cipher: str = 'aes-256-gcm'):
        """
        Initialize Shadowsocks obfuscator.

        Args:
            password: Password for key derivation
            cipher: Encryption cipher to use
        """
        if cipher not in self.SUPPORTED_CIPHERS:
            raise ValueError(f"Unsupported cipher: {cipher}")

        self.cipher_name = cipher
        self.cipher_config = self.SUPPORTED_CIPHERS[cipher]

        # Derive key from password
        self.key = self._derive_key(password)
        self.nonce_counter = 0

    def _derive_key(self, password: str) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        salt = b'tg-ws-proxy-salt'
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            iterations=100000,
            dklen=self.cipher_config['key_size'],
        )
        return key

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data with Shadowsocks-style encryption.

        Args:
            data: Plain data

        Returns:
            Encrypted data with nonce prefix
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            # Fallback to simple XOR if cryptography not available
            return self._xor_encrypt(data)

        # Generate nonce
        nonce = self._generate_nonce()

        # Encrypt
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, data, None)

        # Prepend nonce to ciphertext
        return nonce + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt Shadowsocks-style encrypted data.

        Args:
            data: Encrypted data with nonce prefix

        Returns:
            Decrypted plain data
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            # Fallback to simple XOR if cryptography not available
            return self._xor_decrypt(data)

        # Extract nonce and ciphertext
        nonce_size = self.cipher_config['nonce_size']
        nonce = data[:nonce_size]
        ciphertext = data[nonce_size:]

        # Decrypt
        aesgcm = AESGCM(self.key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext

    def _generate_nonce(self) -> bytes:
        """Generate unique nonce for each encryption."""
        self.nonce_counter += 1
        nonce = struct.pack('>Q', self.nonce_counter)
        nonce += b'\x00' * (self.cipher_config['nonce_size'] - len(nonce))
        return nonce

    def _xor_encrypt(self, data: bytes) -> bytes:
        """Simple XOR encryption fallback."""
        keystream = self._generate_keystream(len(data))
        return bytes(a ^ b for a, b in zip(data, keystream))

    def _xor_decrypt(self, data: bytes) -> bytes:
        """Simple XOR decryption fallback."""
        return self._xor_encrypt(data)

    def _generate_keystream(self, length: int) -> bytes:
        """Generate XOR keystream."""
        keystream = b''
        counter = 0
        while len(keystream) < length:
            block = hmac.new(
                self.key,
                struct.pack('>I', counter),
                hashlib.sha256,
            ).digest()
            keystream += block
            counter += 1
        return keystream[:length]


# =============================================================================
# Traffic Shaping
# =============================================================================


class TrafficShaper:
    """
    Traffic shaping to evade pattern-based detection.

    Adds timing jitter and padding to make traffic patterns
    less distinguishable.
    """

    def __init__(
        self,
        jitter_ms: tuple[int, int] = (10, 100),
        padding_enabled: bool = True,
        padding_ratio: float = 0.1,
    ):
        """
        Initialize traffic shaper.

        Args:
            jitter_ms: Random delay range in milliseconds
            padding_enabled: Whether to add padding
            padding_ratio: Ratio of padding to add (0.0-1.0)
        """
        self.jitter_range = jitter_ms
        self.padding_enabled = padding_enabled
        self.padding_ratio = padding_ratio

    def apply_jitter(self) -> None:
        """Apply random delay."""
        import random
        delay_ms = random.randint(self.jitter_range[0], self.jitter_range[1])
        time.sleep(delay_ms / 1000.0)

    def add_padding(self, data: bytes) -> bytes:
        """
        Add random padding to data.

        Args:
            data: Original data

        Returns:
            Padded data with length prefix
        """
        if not self.padding_enabled:
            return data

        # Calculate padding size
        padding_size = int(len(data) * self.padding_ratio)
        padding_size = max(padding_size, secrets.randbelow(64) + 16)

        # Generate random padding
        padding = secrets.token_bytes(padding_size)

        # Prepend length header
        header = struct.pack('>H', len(data))

        return header + data + padding

    def remove_padding(self, padded_data: bytes) -> bytes:
        """
        Remove padding from data.

        Args:
            padded_data: Padded data with length header

        Returns:
            Original data without padding
        """
        if not self.padding_enabled:
            return padded_data

        # Extract length from header
        original_length = struct.unpack('>H', padded_data[:2])[0]

        # Extract original data
        return padded_data[2:2 + original_length]


# =============================================================================
# Combined Obfuscation Pipeline
# =============================================================================


class ObfuscationPipeline:
    """
    Combined obfuscation pipeline with multiple layers.

    Applies multiple obfuscation techniques in sequence:
    1. Shadowsocks encryption (optional)
    2. Obfs4 obfuscation
    3. WebSocket fragmentation
    4. Traffic shaping
    """

    def __init__(
        self,
        enable_obfs4: bool = True,
        enable_shadowsocks: bool = False,
        enable_fragmentation: bool = True,
        enable_traffic_shaping: bool = True,
        shadowsocks_password: str | None = None,
        browser_profile: str = 'chrome_120',
        domain_fronting_provider: str | None = None,
    ):
        """
        Initialize obfuscation pipeline.

        Args:
            enable_obfs4: Enable obfs4 obfuscation
            enable_shadowsocks: Enable Shadowsocks encryption
            enable_fragmentation: Enable WebSocket fragmentation
            enable_traffic_shaping: Enable traffic shaping
            shadowsocks_password: Password for Shadowsocks
            browser_profile: Browser fingerprint to mimic
            domain_fronting_provider: CDN provider for domain fronting
        """
        self.enabled_layers = []

        # Initialize components
        if enable_shadowsocks and shadowsocks_password:
            self.ss_obfs = ShadowsocksObfs(shadowsocks_password)
            self.enabled_layers.append('shadowsocks')
        else:
            self.ss_obfs = None

        if enable_obfs4:
            self.obfs4 = Obfs4Obfuscator()
            self.enabled_layers.append('obfs4')
        else:
            self.obfs4 = None

        if enable_fragmentation:
            self.fragmenter = WSFragmenter()
            self.enabled_layers.append('fragmentation')
        else:
            self.fragmenter = None

        if enable_traffic_shaping:
            self.shaper = TrafficShaper()
            self.enabled_layers.append('traffic_shaping')
        else:
            self.shaper = None

        self.tls_spoof = TLSFingerprintSpoof(browser_profile)

        if domain_fronting_provider:
            self.domain_fronting = DomainFronting(domain_fronting_provider)
            self.enabled_layers.append('domain_fronting')
        else:
            self.domain_fronting = None

        log.info(
            "Obfuscation pipeline initialized: %s",
            ', '.join(self.enabled_layers) if self.enabled_layers else 'none'
        )

    def obfuscate(self, data: bytes) -> list[bytes]:
        """
        Apply full obfuscation pipeline to data.

        Args:
            data: Original data

        Returns:
            List of obfuscated fragments
        """
        result = data

        # Layer 1: Shadowsocks encryption
        if self.ss_obfs:
            result = self.ss_obfs.encrypt(result)

        # Layer 2: Obfs4 obfuscation
        if self.obfs4:
            if not self.obfs4._initialized:
                # Perform handshake
                self.obfs4.create_client_handshake()
            result = self.obfs4.obfuscate(result)

        # Layer 3: Fragmentation
        if self.fragmenter:
            fragments = self.fragmenter.fragment(result)
        else:
            fragments = [result]

        # Layer 4: Traffic shaping (padding)
        if self.shaper and self.shaper.padding_enabled:
            shaped_fragments = []
            for frag in fragments:
                if self.shaper.padding_enabled:
                    shaped_fragments.append(self.shaper.add_padding(frag))
                else:
                    shaped_fragments.append(frag)
            fragments = shaped_fragments

        # Apply jitter between fragments
        if self.shaper:
            for i, _ in enumerate(fragments):
                if i > 0:
                    self.shaper.apply_jitter()

        return fragments

    def deobfuscate(self, fragments: list[bytes]) -> bytes:
        """
        Reverse obfuscation pipeline.

        Args:
            fragments: Obfuscated fragments

        Returns:
            Original data
        """
        # Reassemble fragments
        if self.fragmenter:
            result = self.fragmenter.reassemble(fragments)
        else:
            result = b''.join(fragments)

        # Remove traffic shaping padding
        if self.shaper and self.shaper.padding_enabled:
            result = self.shaper.remove_padding(result)

        # Layer 2: Deobfuscate obfs4
        if self.obfs4:
            result = self.obfs4.deobfuscate(result)

        # Layer 1: Decrypt Shadowsocks
        if self.ss_obfs:
            result = self.ss_obfs.decrypt(result)

        return result

    def get_ssl_context(self) -> ssl.SSLContext:
        """Get SSL context with TLS fingerprint spoofing."""
        return self.tls_spoof.create_ssl_context()


# =============================================================================
# Adaptive Obfuscation Pipeline
# =============================================================================


class AdaptiveObfuscationPipeline(ObfuscationPipeline):
    """
    Adaptive obfuscation pipeline with automatic DPI detection.

    Automatically adjusts obfuscation level based on detected censorship:
    - Level 0: No obfuscation (clean network)
    - Level 1: Light obfuscation (TLS spoofing only)
    - Level 2: Medium obfuscation (TLS + fragmentation)
    - Level 3: Heavy obfuscation (full pipeline)
    - Level 4: Stealth mode (aggressive obfuscation + domain fronting)
    """

    def __init__(
        self,
        enable_auto_escalation: bool = True,
        escalation_threshold: int = 3,
        de_escalation_timeout: float = 300.0,
        **kwargs: Any,
    ):
        """
        Initialize adaptive obfuscation pipeline.

        Args:
            enable_auto_escalation: Enable automatic obfuscation escalation
            escalation_threshold: Failures before escalating obfuscation
            de_escalation_timeout: Seconds before de-escalating after success
            **kwargs: Arguments for ObfuscationPipeline
        """
        super().__init__(**kwargs)

        self.enable_auto_escalation = enable_auto_escalation
        self.escalation_threshold = escalation_threshold
        self.de_escalation_timeout = de_escalation_timeout

        # Current obfuscation level (0-4)
        self._escalation_level = 0
        self._consecutive_failures = 0
        self._last_success_time = 0.0
        self._detector = CensorshipDetector()

        # Active configuration for current level
        self._active_config: dict[str, bool] = {}

        log.info(
            "Adaptive Obfuscation Pipeline initialized "
            "(auto_escalation=%s, threshold=%d)",
            enable_auto_escalation,
            escalation_threshold
        )

    def _update_active_config(self) -> None:
        """Update active configuration based on escalation level."""
        if self._escalation_level == 0:
            # No obfuscation
            self._active_config = {
                'obfs4': False,
                'shadowsocks': False,
                'fragmentation': False,
                'traffic_shaping': False,
                'domain_fronting': False,
                'tls_spoof': False,
            }
        elif self._escalation_level == 1:
            # Light: TLS spoofing only
            self._active_config = {
                'obfs4': False,
                'shadowsocks': False,
                'fragmentation': False,
                'traffic_shaping': False,
                'domain_fronting': False,
                'tls_spoof': True,
            }
        elif self._escalation_level == 2:
            # Medium: TLS + fragmentation
            self._active_config = {
                'obfs4': False,
                'shadowsocks': False,
                'fragmentation': True,
                'traffic_shaping': True,
                'domain_fronting': False,
                'tls_spoof': True,
            }
        elif self._escalation_level == 3:
            # Heavy: Full pipeline
            self._active_config = {
                'obfs4': True,
                'shadowsocks': False,
                'fragmentation': True,
                'traffic_shaping': True,
                'domain_fronting': False,
                'tls_spoof': True,
            }
        else:  # level >= 4
            # Stealth: Aggressive + domain fronting
            self._active_config = {
                'obfs4': True,
                'shadowsocks': True,
                'fragmentation': True,
                'traffic_shaping': True,
                'domain_fronting': True,
                'tls_spoof': True,
            }

        log.info(
            "Obfuscation level %d: %s",
            self._escalation_level,
            ', '.join(k for k, v in self._active_config.items() if v) or 'none'
        )

    def _escalate(self) -> None:
        """Escalate obfuscation level."""
        old_level = self._escalation_level
        self._escalation_level = min(self._escalation_level + 1, 4)
        if self._escalation_level != old_level:
            self._update_active_config()
            log.warning(
                "Obfuscation escalated: level %d → %d (failures=%d)",
                old_level,
                self._escalation_level,
                self._consecutive_failures
            )

    def _de_escalate(self) -> None:
        """De-escalate obfuscation level."""
        old_level = self._escalation_level
        self._escalation_level = max(self._escalation_level - 1, 0)
        if self._escalation_level != old_level:
            self._update_active_config()
            log.info(
                "Obfuscation de-escalated: level %d → %d (success after timeout)",
                old_level,
                self._escalation_level
            )

    def record_failure(
        self,
        error_type: str = 'unknown',
        error_msg: str = '',
        dc_id: int | None = None,
        domain: str | None = None,
    ) -> None:
        """
        Record connection failure and potentially escalate obfuscation.

        Args:
            error_type: Type of error
            error_msg: Error message
            dc_id: Datacenter ID
            domain: Domain
        """
        self._consecutive_failures += 1
        self._detector.record_failure(error_type, error_msg, dc_id, domain)

        if self.enable_auto_escalation:
            if self._consecutive_failures >= self.escalation_threshold:
                self._escalate()
                self._consecutive_failures = 0

    def record_success(self) -> None:
        """Record successful connection."""
        self._consecutive_failures = 0
        self._last_success_time = time.monotonic()

        # De-escalation is handled in obfuscate() method
        # based on timeout period of successful connections

    def obfuscate(self, data: bytes) -> list[bytes]:
        """
        Apply adaptive obfuscation based on current level.

        Args:
            data: Original data

        Returns:
            List of obfuscated fragments
        """
        # Check for de-escalation timeout
        if (self.enable_auto_escalation and
            self._escalation_level > 0 and
            self._last_success_time > 0):
            elapsed = time.monotonic() - self._last_success_time
            if elapsed > self.de_escalation_timeout:
                self._de_escalate()
                self._last_success_time = time.monotonic()

        # Build temporary pipeline based on active config
        result = data

        # Layer 1: Shadowsocks encryption
        if self._active_config.get('shadowsocks') and self.ss_obfs:
            result = self.ss_obfs.encrypt(result)

        # Layer 2: Obfs4 obfuscation
        if self._active_config.get('obfs4') and self.obfs4:
            if not self.obfs4._initialized:
                self.obfs4.create_client_handshake()
            result = self.obfs4.obfuscate(result)

        # Layer 3: Fragmentation
        if self._active_config.get('fragmentation') and self.fragmenter:
            fragments = self.fragmenter.fragment(result)
        else:
            fragments = [result]

        # Layer 4: Traffic shaping
        if self._active_config.get('traffic_shaping') and self.shaper:
            shaped_fragments = []
            for frag in fragments:
                shaped_fragments.append(self.shaper.add_padding(frag))
            fragments = shaped_fragments

            # Apply jitter
            for i, _ in enumerate(fragments):
                if i > 0:
                    self.shaper.apply_jitter()

        return fragments

    def get_ssl_context(self) -> ssl.SSLContext:
        """Get SSL context with TLS fingerprint spoofing if enabled."""
        if self._active_config.get('tls_spoof'):
            return self.tls_spoof.create_ssl_context()
        # Return default SSL context
        return ssl.create_default_context()

    def get_domain_fronting_host(self) -> str | None:
        """Get domain fronting host if enabled."""
        if self._active_config.get('domain_fronting') and self.domain_fronting:
            return self.domain_fronting.get_fronting_host('kws*.web.telegram.org')
        return None

    def get_status(self) -> dict[str, Any]:
        """Get adaptive obfuscation status."""
        return {
            'escalation_level': self._escalation_level,
            'consecutive_failures': self._consecutive_failures,
            'last_success_time': self._last_success_time,
            'auto_escalation_enabled': self.enable_auto_escalation,
            'active_config': self._active_config,
            'blocking_detected': self._detector.blocking_detected,
            'recommendation': self._detector.get_recommendation(),
        }


# =============================================================================
# Auto-detection of Censorship
# =============================================================================


class CensorshipDetector:
    """
    Detects various forms of internet censorship.

    Monitors connection patterns to identify blocking.
    """

    # Known blocking patterns
    BLOCKING_PATTERNS = {
        'tcp_reset': 'TCP RST packets detected',
        'dns_poisoning': 'DNS resolution returns wrong IP',
        'sni_blocking': 'Connection fails only with specific SNI',
        'timeout': 'Connection times out',
        'deep_packet_inspection': 'Traffic patterns match DPI',
    }

    def __init__(self):
        """Initialize detector."""
        self.failure_history: list[dict[str, Any]] = []
        self.blocking_detected: dict[str, bool] = {
            'tcp_reset': False,
            'dns_poisoning': False,
            'sni_blocking': False,
            'timeout': False,
            'dpi': False,
        }

    def record_failure(
        self,
        error_type: str,
        error_msg: str,
        dc_id: int | None = None,
        domain: str | None = None,
    ) -> None:
        """
        Record a connection failure.

        Args:
            error_type: Type of error
            error_msg: Error message
            dc_id: Datacenter ID if applicable
            domain: Domain if applicable
        """
        entry = {
            'timestamp': time.time(),
            'error_type': error_type,
            'error_msg': error_msg,
            'dc_id': dc_id,
            'domain': domain,
        }
        self.failure_history.append(entry)

        # Keep only last 100 failures
        if len(self.failure_history) > 100:
            self.failure_history = self.failure_history[-100:]

        # Analyze for patterns
        self._analyze_patterns()

    def _analyze_patterns(self) -> None:
        """Analyze failure patterns to detect blocking."""
        now = time.time()
        recent_failures = [
            f for f in self.failure_history
            if now - f['timestamp'] < 300  # Last 5 minutes
        ]

        if len(recent_failures) < 5:
            return

        # Check for TCP reset pattern
        reset_count = sum(
            1 for f in recent_failures
            if 'reset' in f['error_msg'].lower() or 'ECONNRESET' in f['error_msg']
        )
        self.blocking_detected['tcp_reset'] = reset_count > len(recent_failures) * 0.5

        # Check for timeout pattern
        timeout_count = sum(
            1 for f in recent_failures
            if 'timeout' in f['error_msg'].lower() or 'timed out' in f['error_msg']
        )
        self.blocking_detected['timeout'] = timeout_count > len(recent_failures) * 0.7

        # Check for SNI blocking
        if any(f.get('domain') for f in recent_failures):
            domain_failures: dict[str, int] = {}
            for f in recent_failures:
                domain = f.get('domain')
                if domain:
                    domain_failures[domain] = domain_failures.get(domain, 0) + 1

            # If one domain has many more failures, might be SNI blocking
            if domain_failures:
                max_failures = max(domain_failures.values())
                self.blocking_detected['sni_blocking'] = (
                    max_failures > len(recent_failures) * 0.6
                )

    def get_recommendation(self) -> str:
        """
        Get recommendation based on detected blocking.

        Returns:
            Recommended countermeasure
        """
        if self.blocking_detected['tcp_reset']:
            return "Enable obfs4 obfuscation to hide traffic patterns"
        if self.blocking_detected['sni_blocking']:
            return "Enable domain fronting to bypass SNI blocking"
        if self.blocking_detected['timeout']:
            return "Try alternative DC servers or enable HTTP/2 fallback"
        if self.blocking_detected['dpi']:
            return "Enable full obfuscation pipeline with traffic shaping"
        return "No specific blocking detected"

    def is_blocked(self) -> bool:
        """Check if any blocking is detected."""
        return any(self.blocking_detected.values())


# Global censorship detector instance
_censorship_detector = CensorshipDetector()


def get_censorship_detector() -> CensorshipDetector:
    """Get global censorship detector instance."""
    return _censorship_detector
