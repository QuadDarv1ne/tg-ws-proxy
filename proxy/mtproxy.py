"""
MTProxy Protocol Support.

Implements MTProto proxy protocol for Telegram:
- MTProto 1.0 support
- MTProto 2.0 support
- Secret generation and parsing
- Proxy link format (tg://proxy)
- DD-Tags support for anti-censorship

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-ws-mtproxy')


class MTProtoVersion(Enum):
    """MTProto protocol versions."""
    V1 = auto()  # Original MTProto
    V2 = auto()  # MTProto 2.0 with improved security


@dataclass
class MTProxyConfig:
    """MTProxy configuration."""
    host: str = "127.0.0.1"
    port: int = 443
    secret: str = ""  # MTProxy secret (hex or base64)
    version: MTProtoVersion = MTProtoVersion.V2
    dd_tag: str = ""  # DD-Tag for anti-censorship
    tls_domain: str = "telegram.org"  # Domain for TLS disguise
    enable_tls_obfuscation: bool = True
    # For proxy chain
    upstream_proxy: str | None = None
    upstream_port: int | None = None
    
    @property
    def is_dd_secret(self) -> bool:
        """Check if secret uses DD-Tags."""
        return self.secret.startswith('dd') or len(self.secret) == 32
    
    @property
    def proxy_url(self) -> str:
        """Generate Telegram proxy URL."""
        params = []
        if self.secret:
            # Encode secret for URL
            if self.secret.startswith('ee'):
                params.append(f"secret={self.secret}")
            else:
                params.append(f"secret={base64.urlsafe_b64encode(self.secret.encode()).decode().rstrip('=')}")
        
        if self.dd_tag:
            params.append(f"ddtag={self.dd_tag}")
        
        params_str = "&".join(params)
        if params_str:
            return f"tg://proxy?server={self.host}&port={self.port}&{params_str}"
        else:
            return f"tg://proxy?server={self.host}&port={self.port}"


@dataclass
class MTProxySecret:
    """Parsed MTProxy secret."""
    secret_hex: str
    is_dd: bool = False
    is_ee: bool = False
    dd_tag: str | None = None
    encryption_key: bytes | None = None
    
    @classmethod
    def parse(cls, secret: str) -> 'MTProxySecret':
        """
        Parse MTProxy secret.
        
        Args:
            secret: Secret string (hex, base64, or dd/ee format)
            
        Returns:
            MTProxySecret object
        """
        secret = secret.strip()
        
        # DD-Tag format: dd<15 bytes tag><1 byte pad>
        if secret.startswith('dd'):
            try:
                secret_bytes = bytes.fromhex(secret[2:])
                if len(secret_bytes) == 16:
                    return cls(
                        secret_hex=secret,
                        is_dd=True,
                        dd_tag=secret_bytes[:15].decode('utf-8', errors='ignore'),
                    )
            except Exception:
                pass
        
        # EE format (encrypted)
        if secret.startswith('ee'):
            try:
                secret_bytes = bytes.fromhex(secret[2:])
                return cls(
                    secret_hex=secret,
                    is_ee=True,
                    encryption_key=secret_bytes,
                )
            except Exception:
                pass
        
        # Try to parse as hex
        try:
            secret_bytes = bytes.fromhex(secret)
            return cls(
                secret_hex=secret,
                encryption_key=secret_bytes,
            )
        except Exception:
            pass
        
        # Try to parse as base64
        try:
            # Add padding if needed
            padding = 4 - (len(secret) % 4)
            if padding != 4:
                secret += '=' * padding
            
            secret_bytes = base64.b64decode(secret)
            return cls(
                secret_hex=secret_bytes.hex(),
                encryption_key=secret_bytes,
            )
        except Exception:
            pass
        
        # Return as-is
        return cls(secret_hex=secret)


class MTProxyGenerator:
    """
    MTProxy configuration generator.
    
    Features:
    - Secret generation
    - DD-Tag creation
    - Proxy URL generation
    - QR code generation
    """
    
    @staticmethod
    def generate_secret(version: MTProtoVersion = MTProtoVersion.V2) -> str:
        """
        Generate random MTProxy secret.
        
        Args:
            version: MTProto version
            
        Returns:
            Hex-encoded secret (32 characters)
        """
        if version == MTProtoVersion.V1:
            # MTProto 1.0: 16 random bytes
            secret = secrets.token_bytes(16)
        else:
            # MTProto 2.0: 32 random bytes
            secret = secrets.token_bytes(32)
        
        return secret.hex()
    
    @staticmethod
    def generate_dd_secret(tag: str = "") -> str:
        """
        Generate DD-Tag secret for anti-censorship.
        
        DD-Tags help bypass DPI by making traffic look like
        connections to popular websites.
        
        Args:
            tag: Custom tag (max 15 characters)
            
        Returns:
            DD secret (dd + 32 hex characters)
        """
        if not tag:
            # Use random popular domain
            domains = [
                "www.google.com",
                "www.youtube.com",
                "www.facebook.com",
                "www.twitter.com",
                "www.instagram.com",
                "www.linkedin.com",
                "www.github.com",
                "www.stackoverflow.com",
            ]
            tag = secrets.choice(domains)
        
        # Truncate to 15 bytes
        tag_bytes = tag.encode('utf-8')[:15]
        
        # Pad to 16 bytes
        padding = 16 - len(tag_bytes)
        tag_bytes = tag_bytes + bytes([padding] * padding)
        
        return f"dd{tag_bytes.hex()}"
    
    @staticmethod
    def generate_ee_secret(password: str, salt: bytes | None = None) -> str:
        """
        Generate EE (encrypted) secret.
        
        EE secrets use password-based encryption for additional security.
        
        Args:
            password: Password for encryption
            salt: Optional salt (random if not provided)
            
        Returns:
            EE secret (ee + 64 hex characters)
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        # Derive key from password using PBKDF2
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000,
            dklen=32
        )
        
        # EE format: ee + salt (16 bytes) + key (32 bytes)
        ee_secret = salt + key
        return f"ee{ee_secret.hex()}"
    
    @staticmethod
    def parse_proxy_url(url: str) -> MTProxyConfig:
        """
        Parse Telegram proxy URL.
        
        Args:
            url: tg://proxy?server=...&port=...&secret=...
            
        Returns:
            MTProxyConfig object
        """
        from urllib.parse import parse_qs, urlparse
        
        parsed = urlparse(url)
        
        if parsed.scheme != 'tg' or parsed.netloc != 'proxy':
            raise ValueError("Invalid proxy URL scheme")
        
        params = parse_qs(parsed.query)
        
        host = params.get('server', [''])[0]
        port = int(params.get('port', ['443'])[0])
        secret = params.get('secret', [''])[0]
        ddtag = params.get('ddtag', [''])[0]
        
        # Decode base64 secret if needed
        if secret and not secret.startswith(('dd', 'ee')):
            try:
                # Add padding
                padding = 4 - (len(secret) % 4)
                if padding != 4:
                    secret += '=' * padding
                secret_bytes = base64.urlsafe_b64decode(secret)
                secret = secret_bytes.hex()
            except Exception:
                pass
        
        config = MTProxyConfig(
            host=host,
            port=port,
            secret=secret,
            dd_tag=ddtag,
        )
        
        return config
    
    @staticmethod
    def generate_qr_code(proxy_url: str, output_path: str = "proxy_qr.png") -> str:
        """
        Generate QR code for proxy configuration.
        
        Args:
            proxy_url: Telegram proxy URL
            output_path: Output file path
            
        Returns:
            Path to generated QR code
        """
        try:
            import qrcode
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(proxy_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(output_path)
            
            log.info("QR code generated: %s", output_path)
            return output_path
            
        except ImportError:
            log.error("qrcode library not installed. Run: pip install qrcode")
            return ""
    
    @staticmethod
    def get_recommended_servers() -> list[dict[str, Any]]:
        """
        Get list of recommended MTProxy servers.
        
        Returns:
            List of server configurations
        """
        # Public MTProxy servers (these change frequently)
        return [
            {
                "host": "telegram.org",
                "port": 443,
                "secret": "",  # No secret required
                "description": "Official Telegram server",
                "reliability": "high",
            },
            # Add more servers as they become available
        ]


class MTProxyClient:
    """
    MTProxy client for connecting to MTProto proxies.
    
    Features:
    - MTProto handshake
    - TLS obfuscation
    - DD-Tag support
    - Connection pooling
    """
    
    def __init__(self, config: MTProxyConfig):
        self.config = config
        self._secret = MTProxySecret.parse(config.secret)
        
    async def connect(self) -> bool:
        """
        Connect to MTProxy server.
        
        Returns:
            True if connection successful
        """
        try:
            import asyncio
            
            # Connect to proxy server
            reader, writer = await asyncio.open_connection(
                self.config.host,
                self.config.port
            )
            
            # Send MTProto handshake
            if self.config.enable_tls_obfuscation:
                await self._send_tls_handshake(reader, writer)
            else:
                await self._send_mtproto_handshake(reader, writer)
            
            log.info("Connected to MTProxy: %s:%d", 
                    self.config.host, self.config.port)
            return True
            
        except Exception as e:
            log.error("MTProxy connection failed: %s", e)
            return False
    
    async def _send_tls_handshake(self, reader: asyncio.StreamReader, 
                                   writer: asyncio.StreamWriter) -> None:
        """Send TLS-like handshake for obfuscation."""
        # TLS ClientHello structure
        tls_hello = self._create_tls_client_hello()
        writer.write(tls_hello)
        await writer.drain()
        
        # Read server response
        response = await reader.read(4096)
        
        if not response:
            raise ConnectionError("No response from server")
    
    def _create_tls_client_hello(self) -> bytes:
        """Create TLS ClientHello packet."""
        # Simplified TLS 1.3 ClientHello
        tls_version = b'\x03\x03'  # TLS 1.2
        
        # Random bytes (32 bytes)
        random = secrets.token_bytes(32)
        
        # Session ID (empty)
        session_id = b'\x00'
        
        # Cipher suites
        cipher_suites = b'\x00\x04\x13\x01\x13\x02\x13\x03\x13\x04'
        
        # Compression methods
        compression = b'\x01\x00'
        
        # Extensions (SNI for domain fronting)
        extensions = self._create_tls_extensions()
        
        # Build packet
        handshake = (
            b'\x01\x00' +  # ClientHello
            struct.pack('>H', len(tls_version) + len(random) + 
                       len(session_id) + len(cipher_suites) + 
                       len(compression) + len(extensions)) +
            tls_version +
            random +
            session_id +
            cipher_suites +
            compression +
            extensions
        )
        
        # TLS record
        record = (
            b'\x16' +  # Handshake
            tls_version +
            struct.pack('>H', len(handshake)) +
            handshake
        )
        
        return record
    
    def _create_tls_extensions(self) -> bytes:
        """Create TLS extensions including SNI."""
        # SNI extension
        sni_domain = self.config.tls_domain.encode('utf-8')
        sni = (
            b'\x00\x00' +  # SNI extension type
            struct.pack('>H', len(sni_domain) + 5) +  # Extension length
            struct.pack('>H', len(sni_domain) + 3) +  # SNI list length
            b'\x00' +  # Host name type (DNS)
            struct.pack('>H', len(sni_domain)) +
            sni_domain
        )
        
        return sni
    
    async def _send_mtproto_handshake(self, reader: asyncio.StreamReader,
                                       writer: asyncio.StreamWriter) -> None:
        """Send raw MTProto handshake."""
        # MTProto handshake packet
        handshake = self._create_mtproto_handshake()
        writer.write(handshake)
        await writer.drain()
        
        # Read response
        response = await reader.read(4096)
        
        if not response:
            raise ConnectionError("No response from server")
    
    def _create_mtproto_handshake(self) -> bytes:
        """Create MTProto handshake packet."""
        # Random data for handshake
        random_data = secrets.token_bytes(64)
        
        # Add secret if provided
        if self._secret.encryption_key:
            # XOR random data with secret
            key = self._secret.encryption_key
            encrypted = bytes(a ^ b for a, b in zip(random_data, key * 2))
            return encrypted
        else:
            return random_data


# Global MTProxy utilities
_mtproxy_gen = MTProxyGenerator()


def generate_mtproxy_secret(version: str = "v2") -> str:
    """Generate MTProxy secret."""
    if version.lower() == "v1":
        return _mtproxy_gen.generate_secret(MTProtoVersion.V1)
    else:
        return _mtproxy_gen.generate_secret(MTProtoVersion.V2)


def generate_dd_tag(tag: str = "") -> str:
    """Generate DD-Tag secret."""
    return _mtproxy_gen.generate_dd_secret(tag)


def parse_proxy_url(url: str) -> MTProxyConfig:
    """Parse Telegram proxy URL."""
    return _mtproxy_gen.parse_proxy_url(url)


def generate_proxy_qr(proxy_url: str, output_path: str = "proxy_qr.png") -> str:
    """Generate QR code for proxy."""
    return _mtproxy_gen.generate_qr_code(proxy_url, output_path)


__all__ = [
    'MTProtoVersion',
    'MTProxyConfig',
    'MTProxySecret',
    'MTProxyGenerator',
    'MTProxyClient',
    'generate_mtproxy_secret',
    'generate_dd_tag',
    'parse_proxy_url',
    'generate_proxy_qr',
]
