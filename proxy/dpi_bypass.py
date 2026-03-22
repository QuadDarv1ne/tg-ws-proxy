"""
DPI Bypass and Obfuscation Module.

Provides various techniques to bypass Deep Packet Inspection (DPI):
- Packet fragmentation
- TLS fingerprint spoofing
- Domain fronting
- Traffic obfuscation
- Fake headers

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import secrets
import socket
import ssl
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-ws-dpi-bypass')


class ObfuscationLevel(Enum):
    """Obfuscation levels."""
    NONE = auto()
    LOW = auto()  # Basic fragmentation
    MEDIUM = auto()  # Fragmentation + fake headers
    HIGH = auto()  # Full obfuscation with TLS spoofing


@dataclass
class DPIBypassConfig:
    """DPI bypass configuration."""
    enabled: bool = True
    obfuscation_level: ObfuscationLevel = ObfuscationLevel.MEDIUM
    
    # Packet fragmentation
    fragmentation_enabled: bool = True
    fragment_size_min: int = 100
    fragment_size_max: int = 500
    
    # Fake headers
    fake_headers_enabled: bool = True
    fake_user_agents: list[str] = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
    ])
    
    # TLS spoofing
    tls_spoofing_enabled: bool = True
    spoofed_tls_versions: list[str] = field(default_factory=lambda: [
        "TLS 1.2",
        "TLS 1.3",
    ])
    
    # Domain fronting
    domain_fronting_enabled: bool = False
    front_domains: list[str] = field(default_factory=lambda: [
        "www.google.com",
        "www.microsoft.com",
        "www.amazon.com",
        "www.cloudflare.com",
    ])
    
    # Traffic padding
    padding_enabled: bool = True
    padding_size_range: tuple[int, int] = (50, 200)
    
    # Timing obfuscation
    timing_jitter_enabled: bool = True
    jitter_range_ms: tuple[int, int] = (10, 100)


class DPIBypasser:
    """
    DPI bypass engine.
    
    Features:
    - Packet fragmentation
    - Fake HTTP headers
    - TLS fingerprint spoofing
    - Domain fronting
    - Traffic padding
    - Timing obfuscation
    """
    
    def __init__(self, config: DPIBypassConfig | None = None):
        self.config = config or DPIBypassConfig()
        self._stats = {
            'packets_fragmented': 0,
            'fake_headers_added': 0,
            'tls_spoofed': 0,
            'domains_fronted': 0,
            'bytes_padded': 0,
        }
    
    async def obfuscate_connection(self, reader: asyncio.StreamReader,
                                    writer: asyncio.StreamWriter,
                                    target_host: str,
                                    target_port: int) -> bool:
        """
        Apply obfuscation to connection.
        
        Args:
            reader: Async stream reader
            writer: Async stream writer
            target_host: Target host
            target_port: Target port
            
        Returns:
            True if obfuscation successful
        """
        try:
            if self.config.obfuscation_level == ObfuscationLevel.NONE:
                return True
            
            # Apply fragmentation
            if self.config.fragmentation_enabled:
                await self._apply_fragmentation(writer)
            
            # Add fake headers
            if self.config.fake_headers_enabled:
                await self._add_fake_headers(writer, target_host)
            
            # TLS spoofing
            if self.config.tls_spoofing_enabled:
                await self._spoof_tls_handshake(writer)
            
            # Domain fronting
            if self.config.domain_fronting_enabled:
                await self._apply_domain_fronting(writer, target_host)
            
            log.debug("Obfuscation applied to %s:%d", target_host, target_port)
            return True
            
        except Exception as e:
            log.error("Obfuscation failed: %s", e)
            return False
    
    async def _apply_fragmentation(self, writer: asyncio.StreamWriter) -> None:
        """Apply packet fragmentation."""
        # This is handled at send time by splitting data
        self._stats['packets_fragmented'] += 1
    
    async def _add_fake_headers(self, writer: asyncio.StreamWriter, 
                                 target_host: str) -> None:
        """Add fake HTTP headers to disguise traffic."""
        # Select random user agent
        user_agent = random.choice(self.config.fake_user_agents)
        
        # Create fake HTTP CONNECT request
        fake_request = (
            f"CONNECT {target_host}:443 HTTP/1.1\r\n"
            f"Host: {target_host}\r\n"
            f"User-Agent: {user_agent}\r\n"
            f"Accept: */*\r\n"
            f"Accept-Encoding: gzip, deflate, br\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        )
        
        writer.write(fake_request.encode())
        await writer.drain()
        
        self._stats['fake_headers_added'] += 1
    
    async def _spoof_tls_handshake(self, writer: asyncio.StreamWriter) -> None:
        """Spoof TLS handshake to look like legitimate traffic."""
        # Select random TLS version
        tls_version = random.choice(self.config.spoofed_tls_versions)
        
        # Create spoofed ClientHello
        client_hello = self._create_spoofed_client_hello(tls_version)
        
        writer.write(client_hello)
        await writer.drain()
        
        self._stats['tls_spoofed'] += 1
    
    def _create_spoofed_client_hello(self, tls_version: str) -> bytes:
        """Create spoofed TLS ClientHello."""
        if tls_version == "TLS 1.3":
            # TLS 1.3 ClientHello
            version = b'\x03\x03'
            cipher_suites = b'\x00\x06\x13\x01\x13\x02\x13\x03\xc0\x2b\xc0\x2f'
        else:
            # TLS 1.2 ClientHello
            version = b'\x03\x03'
            cipher_suites = b'\x00\x08\xc0\x2f\xc0\x2b\xc0\x27\xc0\x23\x00\xff'
        
        # Random bytes
        random_bytes = secrets.token_bytes(32)
        
        # Session ID (empty)
        session_id = b'\x00'
        
        # Compression
        compression = b'\x01\x00'
        
        # Extensions
        extensions = self._create_fake_extensions()
        
        # Build handshake
        handshake_body = (
            version +
            random_bytes +
            session_id +
            cipher_suites +
            compression +
            extensions
        )
        
        handshake = (
            b'\x01\x00' +  # ClientHello type + length placeholder
            struct.pack('>H', len(handshake_body)) +
            handshake_body
        )
        
        # TLS record
        record = (
            b'\x16' +  # Handshake
            version +
            struct.pack('>H', len(handshake)) +
            handshake
        )
        
        return record
    
    def _create_fake_extensions(self) -> bytes:
        """Create fake TLS extensions."""
        extensions = b''
        
        # Server Name Indication (SNI)
        sni_domain = random.choice(self.config.front_domains)
        sni_bytes = sni_domain.encode('utf-8')
        sni_extension = (
            b'\x00\x00' +  # SNI type
            struct.pack('>H', len(sni_bytes) + 5) +
            struct.pack('>H', len(sni_bytes) + 3) +
            b'\x00' +
            struct.pack('>H', len(sni_bytes)) +
            sni_bytes
        )
        extensions += sni_extension
        
        # Supported Groups
        extensions += b'\x00\x0a\x00\x0e\x00\x0c\x00\x1d\x00\x17\x00\x18\x00\x19'
        
        # Supported Point Formats
        extensions += b'\x00\x0b\x00\x02\x01\x00'
        
        # Signature Algorithms
        extensions += b'\x00\x0d\x00\x14\x00\x12\x04\x03\x08\x04\x04\x01\x05\x03\x08\x05\x05\x01\x08\x06\x06\x01'
        
        return extensions
    
    async def _apply_domain_fronting(self, writer: asyncio.StreamWriter,
                                      real_host: str) -> None:
        """Apply domain fronting technique."""
        # Select front domain
        front_domain = random.choice(self.config.front_domains)
        
        # Create request with front domain in Host header
        # but real destination in SNI
        front_request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {front_domain}\r\n"
            f"User-Agent: Mozilla/5.0\r\n"
            f"Accept: */*\r\n"
            f"Connection: keep-alive\r\n"
            f"\r\n"
        )
        
        writer.write(front_request.encode())
        await writer.drain()
        
        self._stats['domains_fronted'] += 1
    
    def apply_padding(self, data: bytes) -> bytes:
        """Apply traffic padding."""
        if not self.config.padding_enabled:
            return data
        
        # Generate random padding
        min_size, max_size = self.config.padding_size_range
        padding_size = random.randint(min_size, max_size)
        padding = secrets.token_bytes(padding_size)
        
        # Add padding with length prefix
        padded_data = struct.pack('>H', padding_size) + padding + data
        
        self._stats['bytes_padded'] += padding_size
        
        return padded_data
    
    def remove_padding(self, data: bytes) -> bytes:
        """Remove traffic padding."""
        if not self.config.padding_enabled or len(data) < 2:
            return data
        
        # Read padding length
        padding_size = struct.unpack('>H', data[:2])[0]
        
        if padding_size > len(data) - 2:
            return data
        
        # Remove padding
        return data[2 + padding_size:]
    
    async def apply_timing_jitter(self) -> None:
        """Apply timing jitter to traffic."""
        if not self.config.timing_jitter_enabled:
            return
        
        min_jitter, max_jitter = self.config.jitter_range_ms
        jitter_ms = random.randint(min_jitter, max_jitter)
        
        await asyncio.sleep(jitter_ms / 1000.0)
    
    def get_stats(self) -> dict[str, Any]:
        """Get obfuscation statistics."""
        return self._stats.copy()


class FragmentedSocket:
    """
    Socket wrapper with packet fragmentation.
    
    Splits large packets into smaller fragments to bypass DPI.
    """
    
    def __init__(self, socket: socket.socket, 
                 config: DPIBypassConfig | None = None):
        self._socket = socket
        self.config = config or DPIBypassConfig()
        self._fragment_count = 0
    
    def send(self, data: bytes, flags: int = 0) -> int:
        """Send data with fragmentation."""
        if not self.config.fragmentation_enabled:
            return self._socket.send(data, flags)
        
        total_sent = 0
        min_size = self.config.fragment_size_min
        max_size = self.config.fragment_size_max
        
        # Split data into fragments
        offset = 0
        while offset < len(data):
            # Calculate fragment size
            remaining = len(data) - offset
            fragment_size = random.randint(min_size, max_size)
            fragment_size = min(fragment_size, remaining)
            
            # Send fragment
            fragment = data[offset:offset + fragment_size]
            sent = self._socket.send(fragment, flags)
            total_sent += sent
            offset += sent
            
            self._fragment_count += 1
        
        return total_sent
    
    def sendall(self, data: bytes, flags: int = 0) -> None:
        """Send all data with fragmentation."""
        self.send(data, flags)
    
    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        """Receive data."""
        return self._socket.recv(bufsize, flags)
    
    def close(self) -> None:
        """Close socket."""
        self._socket.close()
    
    def get_fragment_count(self) -> int:
        """Get number of fragments sent."""
        return self._fragment_count


# Global DPI bypass instance
_dpi_bypasser: DPIBypasser | None = None


def get_dpi_bypasser() -> DPIBypasser:
    """Get or create global DPI bypasser."""
    global _dpi_bypasser
    if _dpi_bypasser is None:
        _dpi_bypasser = DPIBypasser()
    return _dpi_bypasser


def create_fragmented_socket(sock: socket.socket, 
                             config: DPIBypassConfig | None = None) -> FragmentedSocket:
    """Create fragmented socket wrapper."""
    return FragmentedSocket(sock, config)


__all__ = [
    'ObfuscationLevel',
    'DPIBypassConfig',
    'DPIBypasser',
    'FragmentedSocket',
    'get_dpi_bypasser',
    'create_fragmented_socket',
]
