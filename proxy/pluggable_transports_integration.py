"""
Pluggable Transports Integration Layer.

Integrates obfuscation techniques with WebSocket connections:
- Obfs4 obfuscation wrapper
- Domain fronting integration
- Traffic shaping
- Automatic transport selection

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .pluggable_transports import (
    DomainFronting,
    Obfs4Obfuscator,
    ShadowsocksObfs,
    TLSFingerprintSpoof,
    WSFragmenter,
)

log = logging.getLogger('tg-ws-pt-integration')


class ObfuscationPreset(Enum):
    """Predefined obfuscation presets."""
    NONE = "none"
    DEFAULT = "default"
    AGGRESSIVE = "aggressive"
    STEALTH = "stealth"


@dataclass
class TransportConfig:
    """Pluggable transports configuration."""
    # Obfuscation settings
    enable_obfs4: bool = False
    enable_fragmentation: bool = False
    fragment_min_size: int = 64
    fragment_max_size: int = 256
    enable_traffic_shaping: bool = False
    traffic_jitter_ms: int = 50
    traffic_padding_ratio: float = 0.1

    # TLS spoofing
    enable_tls_spoof: bool = False
    browser_profile: str = "chrome_120"

    # Domain fronting
    enable_domain_fronting: bool = False
    fronting_provider: str = "cloudflare"

    # Shadowsocks encryption
    enable_shadowsocks: bool = False
    shadowsocks_cipher: str = "aes-256-gcm"
    shadowsocks_password: str = ""

    # Preset mode
    preset: ObfuscationPreset = ObfuscationPreset.NONE

    def apply_preset(self) -> None:
        """Apply preset configuration."""
        if self.preset == ObfuscationPreset.NONE:
            # All disabled
            pass
        elif self.preset == ObfuscationPreset.DEFAULT:
            self.enable_obfs4 = True
            self.enable_fragmentation = True
            self.enable_tls_spoof = True
        elif self.preset == ObfuscationPreset.AGGRESSIVE:
            self.enable_obfs4 = True
            self.enable_fragmentation = True
            self.fragment_min_size = 32
            self.fragment_max_size = 128
            self.enable_tls_spoof = True
            self.enable_domain_fronting = True
            self.enable_traffic_shaping = True
            self.traffic_jitter_ms = 100
        elif self.preset == ObfuscationPreset.STEALTH:
            self.enable_obfs4 = True
            self.enable_fragmentation = True
            self.fragment_min_size = 16
            self.fragment_max_size = 64
            self.enable_tls_spoof = True
            self.browser_profile = "firefox_121"
            self.enable_domain_fronting = True
            self.fronting_provider = "google"
            self.enable_traffic_shaping = True
            self.traffic_jitter_ms = 200
            self.traffic_padding_ratio = 0.2
            self.enable_shadowsocks = True


@dataclass
class TransportStats:
    """Transport statistics."""
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_obfuscated: int = 0
    packets_fragmented: int = 0
    domain_fronting_requests: int = 0
    encryption_overhead_bytes: int = 0
    avg_latency_ms: float = 0.0
    last_error: str = ""


class PluggableTransportWrapper:
    """
    Wrapper for WebSocket connections with pluggable transports.

    Features:
    - Obfs4 obfuscation
    - Domain fronting
    - Traffic shaping
    - Automatic fallback
    - Statistics tracking
    """

    def __init__(self, config: TransportConfig | None = None):
        """
        Initialize transport wrapper.

        Args:
            config: Transport configuration
        """
        self.config = config or TransportConfig()
        self.config.apply_preset()

        # Initialize components
        self._obfs4: Obfs4Obfuscator | None = None
        self._fragmenter: WSFragmenter | None = None
        self._domain_fronting: DomainFronting | None = None
        self._tls_spoof: TLSFingerprintSpoof | None = None
        self._shadowsocks: ShadowsocksObfs | None = None

        # Statistics
        self._stats = TransportStats()

        # State
        self._initialized = False
        self._handshake_complete = False

        self._init_components()

    def _init_components(self) -> None:
        """Initialize obfuscation components based on config."""
        if self.config.enable_obfs4:
            self._obfs4 = Obfs4Obfuscator()
            log.debug("Obfs4 obfuscator initialized")

        if self.config.enable_fragmentation:
            self._fragmenter = WSFragmenter(
                min_fragment_size=self.config.fragment_min_size,
                max_fragment_size=self.config.fragment_max_size,
                randomize_sizes=True,
            )
            log.debug("WebSocket fragmenter initialized")

        if self.config.enable_domain_fronting:
            try:
                self._domain_fronting = DomainFronting(
                    self.config.fronting_provider
                )
                log.debug(
                    "Domain fronting initialized (%s)",
                    self.config.fronting_provider
                )
            except ValueError as e:
                log.warning("Domain fronting init failed: %s", e)
                self._domain_fronting = None

        if self.config.enable_tls_spoof:
            self._tls_spoof = TLSFingerprintSpoof(
                self.config.browser_profile
            )
            log.debug(
                "TLS fingerprint spoofing initialized (%s)",
                self.config.browser_profile
            )

        if self.config.enable_shadowsocks and self.config.shadowsocks_password:
            try:
                self._shadowsocks = ShadowsocksObfs(
                    password=self.config.shadowsocks_password,
                    cipher=self.config.shadowsocks_cipher,
                )
                log.debug("Shadowsocks encryption initialized")
            except ValueError as e:
                log.warning("Shadowsocks init failed: %s", e)
                self._shadowsocks = None

    def get_ssl_context(self) -> Any:
        """
        Get SSL context with obfuscation.

        Returns:
            Configured SSL context or None
        """
        if self._tls_spoof:
            return self._tls_spoof.create_ssl_context()

        if self._domain_fronting:
            return self._domain_fronting.wrap_connection(
                None,  # Will be set during connection
                "kws1.web.telegram.org"
            )

        return None

    def get_server_hostname(self) -> str:
        """
        Get server hostname for SNI.

        Returns:
            Hostname to use for SNI
        """
        if self._domain_fronting:
            return self._domain_fronting.get_front_domain()

        return "kws1.web.telegram.org"

    def get_host_header(self) -> str:
        """
        Get Host header value.

        Returns:
            Host header for HTTP request
        """
        if self._domain_fronting:
            return self._domain_fronting.get_host_header()

        return "kws1.web.telegram.org"

    async def perform_handshake(self) -> bool:
        """
        Perform obfuscation handshake.

        Returns:
            True if successful
        """
        if not self._obfs4:
            self._handshake_complete = True
            return True

        try:
            # Generate client handshake
            client_hs = self._obfs4.create_client_handshake()

            # Send handshake (would be sent over network)
            self._stats.bytes_sent += len(client_hs)

            # Server handshake would be received here
            # For now, mark as complete
            self._handshake_complete = True

            log.debug("Obfs4 handshake completed")
            return True

        except Exception as e:
            self._stats.last_error = str(e)
            log.error("Obfs4 handshake failed: %s", e)
            return False

    def obfuscate(self, data: bytes) -> list[bytes]:
        """
        Obfuscate data before sending.

        Args:
            data: Plain data

        Returns:
            List of obfuscated fragments
        """
        if not self._handshake_complete:
            raise RuntimeError("Handshake not complete")

        result: list[bytes] = data

        # Apply Shadowsocks encryption
        if self._shadowsocks:
            encrypted = self._shadowsocks.encrypt(result)
            self._stats.encryption_overhead_bytes += len(encrypted) - len(result)
            result = encrypted

        # Apply obfs4 obfuscation
        if self._obfs4:
            result = self._obfs4.obfuscate(result)
            self._stats.packets_obfuscated += 1

        # Apply fragmentation
        if self._fragmenter:
            fragments = self._fragmenter.fragment(result)
            self._stats.packets_fragmented += len(fragments)
            result = fragments

        # Apply traffic shaping (padding)
        if self.config.enable_traffic_shaping:
            result = self._apply_padding(result)

        # Update stats
        for chunk in result if isinstance(result, list) else [result]:
            self._stats.bytes_sent += len(chunk)

        return result if isinstance(result, list) else [result]

    def deobfuscate(self, data: bytes) -> bytes:
        """
        Deobfuscate received data.

        Args:
            data: Obfuscated data

        Returns:
            Plain data
        """
        result = data

        # Remove padding
        if self.config.enable_traffic_shaping:
            result = self._remove_padding(result)

        # Reassemble fragments
        if self._fragmenter:
            result = self._fragmenter.reassemble([result])

        # Deobfuscate
        if self._obfs4:
            result = self._obfs4.deobfuscate(result)

        # Decrypt Shadowsocks
        if self._shadowsocks:
            result = self._shadowsocks.decrypt(result)

        self._stats.bytes_received += len(result)

        return result

    def _apply_padding(self, data: list[bytes] | bytes) -> list[bytes]:
        """Apply random padding to data."""
        if isinstance(data, bytes):
            data = [data]

        result = []
        for chunk in data:
            # Add random padding
            if self.config.traffic_padding_ratio > 0:
                padding_size = int(len(chunk) * self.config.traffic_padding_ratio)
                padding = bytes([padding_size & 0xFF]) * padding_size
                chunk = chunk + padding
            result.append(chunk)

        return result

    def _remove_padding(self, data: bytes) -> bytes:
        """Remove padding from data."""
        if not data or self.config.traffic_padding_ratio <= 0:
            return data

        # Read padding size from last byte
        padding_size = data[-1] if data else 0

        if padding_size > 0 and padding_size < len(data):
            return data[:-padding_size]

        return data

    async def apply_jitter(self, delay_ms: int | None = None) -> None:
        """
        Apply random jitter delay.

        Args:
            delay_ms: Optional fixed delay (uses config if None)
        """
        if not self.config.enable_traffic_shaping:
            return

        jitter = delay_ms or self.config.traffic_jitter_ms

        if jitter > 0:
            # Add random variation (±50%)
            import secrets
            actual_jitter = jitter * (0.5 + secrets.randbelow(100) / 200.0)
            await asyncio.sleep(actual_jitter / 1000.0)

    def get_stats(self) -> dict[str, Any]:
        """
        Get transport statistics.

        Returns:
            Dict with statistics
        """
        return {
            'bytes_sent': self._stats.bytes_sent,
            'bytes_received': self._stats.bytes_received,
            'packets_obfuscated': self._stats.packets_obfuscated,
            'packets_fragmented': self._stats.packets_fragmented,
            'domain_fronting_requests': self._stats.domain_fronting_requests,
            'encryption_overhead_bytes': self._stats.encryption_overhead_bytes,
            'avg_latency_ms': self._stats.avg_latency_ms,
            'last_error': self._stats.last_error,
            'config': {
                'preset': self.config.preset.value,
                'obfs4_enabled': self.config.enable_obfs4,
                'fragmentation_enabled': self.config.enable_fragmentation,
                'domain_fronting_enabled': self.config.enable_domain_fronting,
                'tls_spoof_enabled': self.config.enable_tls_spoof,
                'shadowsocks_enabled': self.config.enable_shadowsocks,
            },
        }

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = TransportStats()

    def is_ready(self) -> bool:
        """Check if transport is ready for use."""
        return self._handshake_complete


# Global transport wrapper instance
_transport_wrapper: PluggableTransportWrapper | None = None


def get_transport_wrapper(
    config: TransportConfig | None = None,
) -> PluggableTransportWrapper:
    """Get or create global transport wrapper."""
    global _transport_wrapper
    if _transport_wrapper is None:
        _transport_wrapper = PluggableTransportWrapper(config)
    return _transport_wrapper


def init_transport_wrapper(
    preset: ObfuscationPreset = ObfuscationPreset.NONE,
    **kwargs: Any,
) -> PluggableTransportWrapper:
    """Initialize global transport wrapper."""
    global _transport_wrapper
    config = TransportConfig(preset=preset, **kwargs)
    _transport_wrapper = PluggableTransportWrapper(config)
    return _transport_wrapper


__all__ = [
    'ObfuscationPreset',
    'TransportConfig',
    'TransportStats',
    'PluggableTransportWrapper',
    'get_transport_wrapper',
    'init_transport_wrapper',
]
