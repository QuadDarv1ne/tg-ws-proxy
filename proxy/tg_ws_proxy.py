"""Telegram Desktop WebSocket Bridge Proxy."""

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
from typing import Any, Callable

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)
from .constants import (
    _IP_TO_DC,
    DC_FAIL_COOLDOWN,
    DEFAULT_PORT,
    INIT_DC_OFFSET,
    INIT_IV_OFFSET,
    INIT_IV_SIZE,
    INIT_KEY_OFFSET,
    INIT_KEY_SIZE,
    INIT_PACKET_SIZE,
    PROTO_ABRIDGED,
    PROTO_OBFUSCATED,
    PROTO_PADDED_ABRIDGED,
    RECV_BUF_SIZE,
    SEND_BUF_SIZE,
    TCP_NODELAY,
    TG_RANGES,
    WS_POOL_MAX_AGE,
    WS_POOL_MAX_SIZE,
    WS_POOL_SIZE,
)
from .crypto import (
    CryptoConfig,
    CryptoManager,
    EncryptionType,
)
from .stats import Stats, _human_bytes

log = logging.getLogger('tg-ws-proxy')

_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# DNS cache: {domain: [(ip, expiry_time), ...]}
_dns_cache: dict[str, list[tuple[str, float]]] = {}
_dns_cache_ttl = 300.0  # 5 minutes default TTL
_dns_cache_lock = asyncio.Lock()  # Lock for thread-safe cache access

# Async DNS resolver (aiodns - optional for better performance)
_dns_resolver = None

# Connection optimization settings
_OPTIMIZATION_CONFIG = {
    'enable_dns_cache': True,
    'enable_connection_pooling': True,
    'enable_auto_dc_selection': True,
    'pool_min_size': 2,
    'pool_max_size': 8,
    'pool_max_age': 120.0,
    'dns_cache_ttl': 300.0,
    'max_concurrent_connections': 500,
}


def _init_async_dns() -> None:
    """Initialize async DNS resolver if aiodns is available."""
    global _dns_resolver
    try:
        import aiodns
        _dns_resolver = aiodns.DNSResolver()
        log.debug("Async DNS resolver initialized (aiodns)")
    except ImportError:
        log.debug("aiodns not installed, using asyncio.getaddrinfo()")
        _dns_resolver = None


async def _resolve_domain_cached(domain: str, port: int = 443, timeout: float = 5.0) -> list[tuple[str, int]]:
    """
    Resolve domain with caching (thread-safe).

    Args:
        domain: Domain name to resolve
        port: Target port
        timeout: Resolution timeout

    Returns:
        List of (ip, port) tuples
    """
    if not _OPTIMIZATION_CONFIG.get('enable_dns_cache', True):
        # DNS cache disabled - resolve directly
        return await _resolve_domain_direct(domain, port, timeout)

    now = time.monotonic()

    async with _dns_cache_lock:
        # Check cache
        if domain in _dns_cache:
            # Filter expired entries
            valid_entries = [(ip, exp) for ip, exp in _dns_cache[domain] if exp > now]
            if valid_entries:
                log.debug("DNS cache hit for %s: %d entries", domain, len(valid_entries))
                return [(ip, port) for ip, _ in valid_entries]
            else:
                log.debug("DNS cache expired for %s", domain)
                del _dns_cache[domain]

    # Resolve from scratch using aiodns if available
    ips = []
    try:
        if _dns_resolver is not None:
            # Use aiodns for faster async resolution
            result = await asyncio.wait_for(
                _dns_resolver.query(domain, 'A'),
                timeout=timeout
            )
            ips = [r.host for r in result]
        else:
            # Fallback to asyncio.getaddrinfo()
            loop = asyncio.get_event_loop()
            results = await loop.getaddrinfo(domain, port, family=_socket.AF_INET, type=_socket.SOCK_STREAM)
            ips = list({r[4][0] for r in results})

        if ips:
            expiry = now + _dns_cache_ttl
            async with _dns_cache_lock:
                _dns_cache[domain] = [(ip, expiry) for ip in ips]
            log.debug("DNS resolved %s -> %s (cached for %ds)", domain, ips, int(_dns_cache_ttl))
            return [(ip, port) for ip in ips]
        else:
            log.debug("DNS resolved empty for %s", domain)
            return []

    except Exception as e:
        log.debug("DNS resolution failed for %s: %s", domain, e)
        return []


async def _resolve_domain_direct(domain: str, port: int = 443, timeout: float = 5.0) -> list[tuple[str, int]]:
    """
    Resolve domain without caching (for when cache is disabled).

    Args:
        domain: Domain name to resolve
        port: Target port
        timeout: Resolution timeout

    Returns:
        List of (ip, port) tuples
    """
    ips = []
    try:
        if _dns_resolver is not None:
            result = await asyncio.wait_for(
                _dns_resolver.query(domain, 'A'),
                timeout=timeout
            )
            ips = [r.host for r in result]
        else:
            loop = asyncio.get_event_loop()
            results = await loop.getaddrinfo(domain, port, family=_socket.AF_INET, type=_socket.SOCK_STREAM)
            ips = list({r[4][0] for r in results})

        return [(ip, port) for ip in ips]
    except Exception as e:
        log.debug("Direct DNS resolution failed for %s: %s", domain, e)
        return []


def _clear_dns_cache() -> None:
    """Clear DNS cache."""
    _dns_cache.clear()
    log.info("DNS cache cleared")


def update_optimization_config(config: dict) -> None:
    """
    Update optimization configuration at runtime.

    Args:
        config: Dictionary with optimization settings
    """
    global _dns_cache_ttl, _OPTIMIZATION_CONFIG

    for key, value in config.items():
        if key in _OPTIMIZATION_CONFIG:
            _OPTIMIZATION_CONFIG[key] = value
            log.info("Optimization config updated: %s = %s", key, value)
        elif key == 'dns_cache_ttl':
            _dns_cache_ttl = float(value)
            log.info("DNS cache TTL updated: %s seconds", _dns_cache_ttl)

    log.debug("Current optimization config: %s", _OPTIMIZATION_CONFIG)


def get_optimization_config() -> dict:
    """Get current optimization configuration."""
    return {
        **_OPTIMIZATION_CONFIG,
        'dns_cache_ttl': _dns_cache_ttl,
        'dns_cache_size': len(_dns_cache),
    }


async def _check_ws_domain_available(dc_id: int, timeout: float = 5.0) -> tuple[bool, str | None]:
    """
    Check if WebSocket domain for a DC is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    from .constants import WS_DOMAIN_MEDIA_TEMPLATE, WS_DOMAIN_TEMPLATE

    domains_to_check = [
        WS_DOMAIN_TEMPLATE.format(dc=dc_id),
        WS_DOMAIN_MEDIA_TEMPLATE.format(dc=dc_id),
    ]

    for domain in domains_to_check:
        try:
            # Use cached DNS resolution
            resolved = await _resolve_domain_cached(domain, 443, timeout)
            if resolved:
                log.debug("Domain %s is resolvable (cached: %s)", domain, resolved[0][0])
            else:
                return False, f"Cannot resolve {domain}"
        except Exception as e:
            log.warning("Domain %s is not available: %s", domain, e)
            return False, f"Cannot resolve {domain}"

    return True, None


async def _check_ws_domains_available(dc_opt: dict[int, str | None], timeout: float = 5.0) -> dict[int, tuple[bool, str | None]]:
    """
    Check WebSocket domains for all configured DCs.

    Returns:
        Dict mapping dc_id -> (is_available, error_message)
    """
    results = {}
    for dc_id in dc_opt.keys():
        is_available, error = await _check_ws_domain_available(dc_id, timeout)
        results[dc_id] = (is_available, error)
        if is_available:
            log.info("DC%d: WebSocket domain is available", dc_id)
        else:
            log.warning("DC%d: WebSocket domain check failed - %s", dc_id, error)
    return results


async def _measure_dc_ping(dc_id: int, timeout: float = 5.0) -> tuple[float | None, str | None]:
    """
    Measure ping (latency) to a DC by attempting TCP connection to WebSocket domain.

    Returns:
        Tuple of (latency_ms, error_message)
        latency_ms is None if connection failed
    """
    from .constants import WS_DOMAIN_TEMPLATE

    domain = WS_DOMAIN_TEMPLATE.format(dc=dc_id)

    try:
        start_time = time.monotonic()

        # Try to establish TCP connection to measure latency
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(domain, 443),
            timeout=timeout
        )

        # Close immediately after connection
        writer.close()
        await writer.wait_closed()

        latency_ms = (time.monotonic() - start_time) * 1000
        log.debug("DC%d (%s): ping=%.1fms", dc_id, domain, latency_ms)
        return latency_ms, None

    except asyncio.TimeoutError:
        log.debug("DC%d (%s): ping timeout", dc_id, domain)
        return None, "Connection timeout"
    except Exception as e:
        log.debug("DC%d (%s): ping error: %s", dc_id, domain, e)
        return None, str(e)


async def _measure_all_dc_pings(dc_opt: dict[int, str | None], timeout: float = 5.0) -> dict[int, float]:
    """
    Measure ping to all configured DCs and return results.

    Returns:
        Dict mapping dc_id -> latency_ms (only successful measurements)
    """
    results = {}

    log.info("Measuring ping to Telegram DCs...")

    # Measure all DCs concurrently
    tasks = {}
    for dc_id in dc_opt.keys():
        tasks[dc_id] = asyncio.create_task(_measure_dc_ping(dc_id, timeout))

    # Collect results
    for dc_id, task in tasks.items():
        try:
            latency_ms, error = await task
            if latency_ms is not None:
                results[dc_id] = latency_ms
                log.info("DC%d: %.1fms", dc_id, latency_ms)
            else:
                log.warning("DC%d: failed - %s", dc_id, error)
        except Exception as e:
            log.warning("DC%d: measurement failed - %s", dc_id, e)

    if results:
        best_dc = min(results, key=lambda x: results[x])
        log.info("Best DC: DC%d (%.1fms)", best_dc, results[best_dc])
    else:
        log.warning("All DC ping measurements failed")

    return results


async def _close_writer_safe(writer: asyncio.StreamWriter | None) -> None:
    """Safely close and wait for writer to close."""
    if writer is None:
        return
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def _cancel_tasks(tasks: list[asyncio.Task]) -> None:
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
    - Modern encryption (AES-256-GCM, ChaCha20-Poly1305, XChaCha20-Poly1305)
    """

    def __init__(
        self,
        dc_opt: dict[int, str | None],
        host: str = '127.0.0.1',
        port: int = DEFAULT_PORT,
        auth_required: bool = False,
        auth_credentials: dict[str, str] | None = None,
        ip_whitelist: list[str] | None = None,
        encryption_config: dict | None = None,
        rate_limit_config: dict | None = None,
    ):
        self.dc_opt = dc_opt
        self.host = host
        self.port = port
        self.auth_required = auth_required
        self.auth_credentials = auth_credentials
        self.ip_whitelist = set(ip_whitelist) if ip_whitelist else None

        # Rate limiting support
        self.rate_limiter: RateLimiter | None = None
        self._rate_limit_task: asyncio.Task | None = None

        if rate_limit_config:
            self._setup_rate_limiter(rate_limit_config)

        # Modern encryption support
        self.encryption_enabled = False
        self.crypto_manager: CryptoManager | None = None
        self._key_rotation_task: asyncio.Task | None = None
        self._key_rotation_interval = 3600  # Default 1 hour

        if encryption_config:
            self._setup_encryption(encryption_config)

        # DCs where WS is known to fail (302 redirect)
        # Raw TCP fallback will be used instead
        # Keyed by (dc, is_media)
        self.ws_blacklist: set[tuple[int, bool]] = set()

        # Rate-limit re-attempts per (dc, is_media)
        self.dc_fail_until: dict[tuple[int, bool], float] = {}

        # Consecutive error count for exponential backoff
        self.dc_error_count: dict[tuple[int, bool], int] = {}

        # Statistics with memory optimization
        self.stats = Stats(enable_alerts=True, optimize_memory=True)

        # Start real-time monitoring with auto-export
        import os

        import appdirs
        stats_dir = os.path.join(appdirs.user_data_dir('TgWsProxy', 'Dupley Maxim'), 'stats')
        self.stats.start_realtime_monitoring(
            check_interval=30.0,  # Check every 30 seconds
            auto_export=True,
            export_dir=stats_dir
        )

        # Circuit breakers for cascade failure protection
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._init_circuit_breakers()

        # WebSocket connection pool (lazy initialized)
        self._ws_pool: _WsPool | None = None

        # Background tasks for graceful shutdown
        self._log_stats_task: asyncio.Task | None = None
        self._dc_monitor_task: asyncio.Task | None = None
        self._optimize_pool_task: asyncio.Task | None = None

        # Memory profiler
        self._memory_profiler: Any | None = None

        # Server instance for graceful shutdown
        self._server_instance: asyncio.Server | None = None
        self._server_stop_event: asyncio.Event | None = None

        # Optimization metrics
        self._optimization_metrics = {
            'total_dns_resolutions': 0,
            'dns_cache_hits': 0,
            'dns_cache_misses': 0,
            'avg_connection_time_ms': 0.0,
            'peak_connections': 0,
        }

    def get_optimization_metrics(self) -> dict:
        """Get current optimization metrics."""
        return {
            **self._optimization_metrics,
            'config': get_optimization_config(),
        }

    def update_optimization_metrics(self, **kwargs: Any) -> None:
        """Update optimization metrics."""
        for key, value in kwargs.items():
            if key in self._optimization_metrics:
                self._optimization_metrics[key] = value

    def record_dns_cache_hit(self) -> None:
        """Record DNS cache hit."""
        self._optimization_metrics['total_dns_resolutions'] += 1
        self._optimization_metrics['dns_cache_hits'] += 1

    def record_dns_cache_miss(self) -> None:
        """Record DNS cache miss."""
        self._optimization_metrics['total_dns_resolutions'] += 1
        self._optimization_metrics['dns_cache_misses'] += 1

    def _setup_encryption(self, config: dict) -> None:
        """Setup modern encryption based on configuration."""
        try:
            # Map config string to EncryptionType enum
            encryption_map = {
                "aes-256-gcm": EncryptionType.AES_256_GCM,
                "chacha20-poly1305": EncryptionType.CHACHA20_POLY1305,
                "xchacha20-poly1305": EncryptionType.XCHACHA20_POLY1305,
                "aes-256-ctr": EncryptionType.AES_256_CTR,
                "mtproto-ige": EncryptionType.MTROTO_IGE,
            }

            algo_name = config.get("encryption_type", "aes-256-gcm")
            algo = encryption_map.get(algo_name, EncryptionType.AES_256_GCM)

            # Create crypto configuration
            crypto_config = CryptoConfig(
                algorithm=algo,
                key_size=32,  # 256-bit
                nonce_size=12,
                tag_size=16,
                kdf_iterations=100_000,
            )

            # Initialize crypto manager
            self.crypto_manager = CryptoManager(crypto_config)
            self.encryption_enabled = config.get("encryption_enabled", True)
            self._key_rotation_interval = config.get("key_rotation_interval", 3600)

            log.info(
                "Modern encryption enabled: %s (key rotation: %ds)",
                algo_name.upper(),
                self._key_rotation_interval
            )

        except Exception as e:
            log.warning("Failed to setup encryption: %s. Running without encryption.", e)
            self.encryption_enabled = False

    async def _start_key_rotation(self) -> None:
        """Start automatic key rotation task."""
        if not self.encryption_enabled or self._key_rotation_interval <= 0:
            return

        async def rotate_keys_loop() -> None:
            while True:
                await asyncio.sleep(self._key_rotation_interval)
                if self.crypto_manager:
                    self.crypto_manager.rotate_all_keys()
                    log.info("Encryption keys rotated automatically")

        self._key_rotation_task = asyncio.create_task(rotate_keys_loop())
        log.debug("Key rotation task started")

    def _stop_key_rotation(self) -> None:
        """Stop automatic key rotation."""
        if self._key_rotation_task:
            self._key_rotation_task.cancel()
            self._key_rotation_task = None
            log.debug("Key rotation task stopped")

    def _setup_rate_limiter(self, config: dict) -> None:
        """Setup rate limiter based on configuration."""
        try:
            from proxy.rate_limiter import RateLimitConfig, RateLimiter

            self.rate_limiter = RateLimiter(
                RateLimitConfig(
                    requests_per_second=config.get("requests_per_second", 10.0),
                    requests_per_minute=config.get("requests_per_minute", 100),
                    requests_per_hour=config.get("requests_per_hour", 1000),
                    max_concurrent_connections=config.get("max_concurrent_connections", 500),
                    max_connections_per_ip=config.get("max_connections_per_ip", 10),
                    ban_threshold=config.get("ban_threshold", 5),
                    ban_duration_seconds=config.get("ban_duration_seconds", 300.0),
                )
            )
            log.info(
                "Rate limiter configured: %d req/min, %d max connections",
                config.get("requests_per_minute", 100),
                config.get("max_concurrent_connections", 500),
            )
        except Exception as e:
            log.warning("Failed to setup rate limiter: %s. Running without rate limiting.", e)
            self.rate_limiter = None

    def _init_circuit_breakers(self) -> None:
        """Initialize circuit breakers for cascade failure protection."""
        # Circuit breaker for WebSocket connections
        self._circuit_breakers['websocket'] = CircuitBreaker(
            name='websocket',
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout=30.0,
                half_open_max_calls=3,
            ),
        )
        # Circuit breaker for TCP connections
        self._circuit_breakers['tcp'] = CircuitBreaker(
            name='tcp',
            config=CircuitBreakerConfig(
                failure_threshold=10,
                success_threshold=5,
                timeout=15.0,
                half_open_max_calls=5,
            ),
        )
        # Circuit breaker for DNS resolution
        self._circuit_breakers['dns'] = CircuitBreaker(
            name='dns',
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout=60.0,
                half_open_max_calls=3,
            ),
        )
        log.info("Circuit breakers initialized: websocket, tcp, dns")

    def get_circuit_breaker(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._circuit_breakers.get(name)

    def get_all_circuit_breakers_info(self) -> list[dict]:
        """Get info for all circuit breakers."""
        return [cb.get_info() for cb in self._circuit_breakers.values()]

    async def _start_rate_limiter(self) -> None:
        """Start rate limiter background tasks."""
        if self.rate_limiter:
            await self.rate_limiter.start()
            log.info("Rate limiter started")

    async def _stop_rate_limiter(self) -> None:
        """Stop rate limiter."""
        if self.rate_limiter:
            await self.rate_limiter.stop()
            log.info("Rate limiter stopped")

    @property
    def ws_pool(self) -> _WsPool:
        """Lazy initialization of WebSocket pool."""
        if self._ws_pool is None:
            self._ws_pool = _WsPool(self.stats)
            log.debug("WebSocket pool initialized lazily")
        return self._ws_pool

    def get_stats(self) -> dict:
        """Get current proxy statistics."""
        stats = self.stats.to_dict()

        # Add encryption statistics
        if self.encryption_enabled and self.crypto_manager:
            stats["encryption"] = {
                "enabled": True,
                "algorithm": self.crypto_manager.config.algorithm.name,
                "key_rotation_interval": self._key_rotation_interval,
                "supported_algorithms": [
                    algo.name for algo in self.crypto_manager.get_supported_algorithms()
                ],
            }
        else:
            stats["encryption"] = {
                "enabled": False,
            }

        return stats

    def get_stats_summary(self) -> str:
        """Get current stats as a human-readable summary."""
        base_summary = self.stats.summary()

        if self.encryption_enabled and self.crypto_manager:
            algo = self.crypto_manager.config.algorithm.name
            return f"{base_summary} | encrypt={algo}"

        return base_summary

    async def _negotiate_socks5(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        label: str,
    ) -> bool:
        """
        Perform SOCKS5 handshake.

        Returns True if negotiation successful, False otherwise.
        """
        try:
            # Read greeting
            hdr = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            if hdr[0] != 5:
                log.debug("%s not SOCKS5 (ver=%d)", label, hdr[0])
                return False

            nmethods = hdr[1]
            methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10)

            # Check if auth required
            if self.auth_required and self.auth_credentials:
                if 0x02 not in methods:
                    log.warning("%s client doesn't support auth method", label)
                    writer.write(b'\x05\xff')  # No acceptable methods
                    await writer.drain()
                    return False

                writer.write(b'\x05\x02')  # Use username/password
                await writer.drain()

                # Read auth credentials
                auth_ver = await asyncio.wait_for(reader.readexactly(1), timeout=10)
                if auth_ver[0] != 1:
                    log.warning("%s unknown auth version %d", label, auth_ver[0])
                    writer.write(b'\x01\x01')  # Authentication failed
                    await writer.drain()
                    return False

                ulen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
                username = await asyncio.wait_for(reader.readexactly(ulen), timeout=10)
                plen = (await asyncio.wait_for(reader.readexactly(1), timeout=10))[0]
                password = await asyncio.wait_for(reader.readexactly(plen), timeout=10)

                # Validate credentials
                if (username.decode() != self.auth_credentials.get('username') or
                    password.decode() != self.auth_credentials.get('password')):
                    log.warning("%s auth failed for user %s", label, username.decode())
                    writer.write(b'\x01\x01')  # Authentication failed
                    await writer.drain()
                    return False

                writer.write(b'\x01\x00')  # Authentication successful
                await writer.drain()
                log.info("%s auth successful for user %s", label, username.decode())
            else:
                # No auth required
                writer.write(b'\x05\x00')  # No auth
                await writer.drain()

            return True
        except Exception as e:
            log.debug("%s SOCKS5 negotiation error: %s", label, e)
            return False

    async def _read_socks5_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        label: str,
    ) -> tuple[str | None, int] | None:
        """
        Read SOCKS5 CONNECT request.

        Returns (destination_host, port) tuple or None on error.
        """
        try:
            req = await asyncio.wait_for(reader.readexactly(4), timeout=10)
            _ver, cmd, _rsv, atyp = req

            if cmd != 1:  # Only CONNECT supported
                writer.write(_socks5_reply(0x07))
                await writer.drain()
                return None

            if atyp == 1:  # IPv4
                raw = await reader.readexactly(4)
                dst = _socket.inet_ntoa(raw)
            elif atyp == 3:  # Domain name
                dlen = (await reader.readexactly(1))[0]
                dst = (await reader.readexactly(dlen)).decode()
            elif atyp == 4:  # IPv6
                raw = await reader.readexactly(16)
                dst = _socket.inet_ntop(_socket.AF_INET6, raw)
            else:
                log.warning("%s unknown address type %d", label, atyp)
                return None

            port = struct.unpack('!H', await reader.readexactly(2))[0]

            # Return None for IPv6 destinations (not supported)
            return (None if ':' in dst else dst), port
        except Exception as e:
            log.debug("%s SOCKS5 request error: %s", label, e)
            return None


def _set_sock_opts(transport: asyncio.BaseTransport) -> None:
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
                 headers: dict[str, str] | None = None, location: str | None = None):
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
                      timeout: float = 10.0) -> RawWebSocket:
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

    async def send(self, data: bytes) -> None:
        """Send a masked binary WebSocket frame."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        frame = self._build_frame(self.OP_BINARY, data, mask=True)
        self.writer.write(frame)
        await self.writer.drain()

    async def send_batch(self, parts: list[bytes]) -> None:
        """Send multiple binary frames with a single drain (less overhead)."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        for part in parts:
            frame = self._build_frame(self.OP_BINARY, part, mask=True)
            self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> bytes | None:
        """
        Receive the next data frame.  Handles ping/pong/close
        internally.  Returns payload bytes, or None on clean close.
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

    async def close(self) -> None:
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

    async def _read_frame(self) -> tuple[int, bytes]:
        """Read a single WebSocket frame from the reader."""
        try:
            hdr = await asyncio.wait_for(self.reader.readexactly(2), timeout=30.0)
        except asyncio.TimeoutError as e:
            raise asyncio.TimeoutError("Frame header read timeout") from e
        except asyncio.IncompleteReadError as e:
            raise asyncio.IncompleteReadError(e.partial, e.expected) from e

        opcode = hdr[0] & 0x0F
        is_masked = bool(hdr[1] & 0x80)
        length = hdr[1] & 0x7F

        if length == 126:
            try:
                length = struct.unpack('>H', await asyncio.wait_for(self.reader.readexactly(2), timeout=30.0))[0]
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(e.partial, e.expected) from e
        elif length == 127:
            try:
                length = struct.unpack('>Q', await asyncio.wait_for(self.reader.readexactly(8), timeout=30.0))[0]
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(e.partial, e.expected) from e

        if is_masked:
            try:
                mask_key = await asyncio.wait_for(self.reader.readexactly(4), timeout=30.0)
                payload = await asyncio.wait_for(self.reader.readexactly(length), timeout=30.0)
                return opcode, _xor_mask(payload, mask_key)
            except asyncio.IncompleteReadError as e:
                raise asyncio.IncompleteReadError(e.partial, e.expected) from e

        try:
            payload = await asyncio.wait_for(self.reader.readexactly(length), timeout=30.0)
        except asyncio.IncompleteReadError as e:
            raise asyncio.IncompleteReadError(e.partial, e.expected) from e
        return opcode, payload


def _is_telegram_ip(ip: str) -> bool:
    try:
        n = struct.unpack('!I', _socket.inet_aton(ip))[0]
        return any(lo <= n <= hi for lo, hi in TG_RANGES)
    except OSError:
        return False


def _is_http_transport(data: bytes) -> bool:
    return (data[:5] == b'POST ' or data[:4] == b'GET ' or
            data[:5] == b'HEAD ' or data[:8] == b'OPTIONS ')


def _dc_from_init(data: bytes) -> tuple[int | None, bool]:
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

    def split(self, chunk: bytes) -> list[bytes]:
        """Decrypt to find message boundaries, return split ciphertext."""
        plain = self._dec.update(chunk)
        boundaries: list[int] = []
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
        parts: list[bytes] = []
        prev = 0
        for b in boundaries:
            parts.append(chunk[prev:b])
            prev = b
        if prev < len(chunk):
            parts.append(chunk[prev:])
        return parts


def _ws_domains(dc: int, is_media: bool | None) -> list[str]:
    if is_media is None or is_media:
        return [f'kws{dc}-1.web.telegram.org', f'kws{dc}.web.telegram.org']
    return [f'kws{dc}.web.telegram.org', f'kws{dc}-1.web.telegram.org']


# Global instance for backward compatibility
_server_instance: ProxyServer | None = None

# Callback for client connection notifications
_on_client_connect_callback = None
_on_client_error_callback = None
_on_high_latency_callback = None


def set_on_client_connect_callback(callback: Callable[[str, int], None] | None) -> None:
    """Set callback for client connection notifications."""
    global _on_client_connect_callback
    _on_client_connect_callback = callback


def set_on_client_error_callback(callback: Callable[[Exception], None] | None) -> None:
    """Set callback for client error notifications."""
    global _on_client_error_callback
    _on_client_error_callback = callback


def set_on_high_latency_callback(callback: Callable[[int, float], None] | None) -> None:
    """Set callback for high latency notifications."""
    global _on_high_latency_callback
    _on_high_latency_callback = callback


def get_stats() -> dict:
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


def get_dns_cache_info() -> dict[str, int | dict[str, dict[str, int | float]]]:
    """Get DNS cache statistics."""
    now = time.monotonic()
    entries_dict: dict[str, dict[str, int | float]] = {}
    for domain, entries in _dns_cache.items():
        valid = [(ip, exp) for ip, exp in entries if exp > now]
        if valid:
            entries_dict[domain] = {
                "count": len(valid),
                "ttl_remaining": max(0, valid[0][1] - now) if valid else 0
            }
    return {
        "domains_cached": len(_dns_cache),
        "entries": entries_dict
    }


def clear_dns_cache() -> None:
    """Clear DNS cache."""
    _clear_dns_cache()


class _WsPool:
    def __init__(self, stats: Stats):
        self.stats = stats
        self._idle: dict[tuple[int, bool], list] = {}
        self._refilling: set[tuple[int, bool]] = set()

        # Dynamic pool sizing
        self._pool_size = WS_POOL_SIZE  # Current dynamic pool size
        self._pool_max_size = WS_POOL_MAX_SIZE
        self._last_hit_count = 0
        self._last_miss_count = 0
        self._optimization_interval = 30  # Check every 30 seconds
        self._last_optimization = 0.0

        # Health check configuration
        self._heartbeat_interval = 45.0  # Send PING every 45 seconds
        self._heartbeat_timeout = 10.0   # Timeout for PONG response
        self._last_heartbeat = 0.0
        self._health_check_task: asyncio.Task | None = None

        # Memory profiling
        try:
            from .profiler import get_profiler
            profiler = get_profiler()
            self._profiler = profiler.register_component('WsPool')
        except Exception:
            self._profiler = None  # type: ignore[assignment]

    async def start_health_checker(self) -> None:
        """Start background health check task."""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self) -> None:
        """Periodically send PING to all pooled connections."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._send_heartbeats()

    async def _send_heartbeats(self) -> None:
        """Send PING frames to all pooled connections and remove unresponsive ones."""
        checked_count = 0
        failed_count = 0

        for key, bucket in list(self._idle.items()):
            valid_ws: list[tuple[RawWebSocket, float]] = []
            for ws, created in bucket:
                if ws._closed:
                    continue
                try:
                    # Send PING frame
                    await ws.send(b'', opcode=RawWebSocket.OP_PING)
                    valid_ws.append((ws, created))
                    checked_count += 1
                except asyncio.TimeoutError:
                    log.debug("Health check timeout for DC%d%s", key[0], 'm' if key[1] else '')
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
                except Exception as e:
                    log.debug("Health check failed for DC%d%s: %s", key[0], 'm' if key[1] else '', e)
                    asyncio.create_task(self._quiet_close(ws))
                    failed_count += 1
            self._idle[key] = valid_ws

        if failed_count > 0:
            log.info("Health check: %d checked, %d failed", checked_count, failed_count)
        else:
            log.debug("Health check completed: %d connections checked", checked_count)

    async def get(self, dc: int, is_media: bool,
                  target_ip: str, domains: list[str]
                  ) -> RawWebSocket | None:
        key = (dc, is_media)
        now = time.monotonic()

        bucket: list[tuple[RawWebSocket, float]] = self._idle.get(key, [])
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

    def _can_add_to_pool(self, key: tuple[int, bool]) -> bool:
        """Check if pool can accept more connections."""
        bucket = self._idle.get(key, [])
        return len(bucket) < self._pool_max_size

    def _schedule_refill(self, key: tuple[int, bool], target_ip: str, domains: list[str]) -> None:
        if key in self._refilling:
            return
        self._refilling.add(key)
        asyncio.create_task(self._refill(key, target_ip, domains))

    async def _refill(self, key: tuple[int, bool], target_ip: str, domains: list[str]) -> None:
        dc, is_media = key
        try:
            bucket = self._idle.setdefault(key, [])
            needed = self._pool_size - len(bucket)
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

    def _optimize_pool_size(self) -> None:
        """
        Dynamically adjust pool size based on hit/miss ratio.

        Strategy:
        - If miss rate > 30%: increase pool size (up to max)
        - If miss rate < 5% and pool usage < 50%: decrease pool size
        """
        now = time.monotonic()
        if now - self._last_optimization < self._optimization_interval:
            return

        total = self.stats.pool_hits + self.stats.pool_misses
        if total == 0:
            return

        self.stats.pool_misses / total

        # Calculate change in hits/misses since last check
        delta_hits = self.stats.pool_hits - self._last_hit_count
        delta_misses = self.stats.pool_misses - self._last_miss_count
        delta_total = delta_hits + delta_misses

        if delta_total > 0:
            current_miss_rate = delta_misses / delta_total

            if current_miss_rate > 0.3 and self._pool_size < self._pool_max_size:
                # High miss rate - increase pool
                old_size = self._pool_size
                self._pool_size = min(self._pool_size + 1, self._pool_max_size)
                log.info("Pool optimization: miss rate %.1f%% > 30%%, increased size %d→%d",
                        current_miss_rate * 100, old_size, self._pool_size)
            elif current_miss_rate < 0.05 and self._pool_size > 2:
                # Low miss rate - decrease pool to save resources
                old_size = self._pool_size
                self._pool_size = max(self._pool_size - 1, 2)
                log.info("Pool optimization: miss rate %.1f%% < 5%%, decreased size %d→%d",
                        current_miss_rate * 100, old_size, self._pool_size)

        # Update counters
        self._last_hit_count = self.stats.pool_hits
        self._last_miss_count = self.stats.pool_misses
        self._last_optimization = now

    @staticmethod
    async def _connect_one(target_ip: str, domains: list[str]) -> RawWebSocket | None:
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
    async def _quiet_close(ws: RawWebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass

    async def warmup(self, dc_opt: dict[int, str | None]) -> None:
        """Pre-fill pool for all configured DCs on startup."""
        for dc, target_ip in dc_opt.items():
            if target_ip is None:
                continue
            for is_media in (False, True):
                domains = _ws_domains(dc, is_media)
                key = (dc, is_media)
                self._schedule_refill(key, target_ip, domains)
        log.info("WS pool warmup started for %d DC(s)", len(dc_opt))


class _TcpPool:
    """
    Connection pool for TCP fallback connections.
    Reuses existing TCP connections to reduce latency and connection overhead.
    """

    def __init__(self, stats: Stats, max_size: int = 4, max_age: float = 60.0):
        self.stats = stats
        self.max_size = max_size
        self.max_age = max_age
        self._idle: dict[str, list] = {}  # key: "host:port" -> [(reader, writer, created)]

    async def get(self, host: str, port: int) -> tuple | None:
        """Get a cached TCP connection or None."""
        key = f"{host}:{port}"
        now = time.monotonic()

        bucket = self._idle.get(key, [])
        while bucket:
            reader, writer, created = bucket.pop(0)
            age = now - created

            # Check if connection is still valid
            if age > self.max_age:
                log.debug("TCP pool: connection expired (age=%.1fs)", age)
                await self._close_one(writer)
                continue

            # Check if writer is still open
            if writer.is_closing() or writer.transport.is_closing():
                log.debug("TCP pool: connection closed")
                continue

            log.debug("TCP pool hit for %s (age=%.1fs)", key, age)
            return reader, writer

        return None

    def put(self, host: str, port: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Return a connection to the pool."""
        key = f"{host}:{port}"
        bucket = self._idle.setdefault(key, [])

        # Limit pool size
        if len(bucket) >= self.max_size:
            log.debug("TCP pool full for %s, closing connection", key)
            asyncio.create_task(self._close_one(writer))
            return

        bucket.append((reader, writer, time.monotonic()))
        log.debug("TCP pool: connection returned to %s (size=%d)", key, len(bucket))

    async def _close_one(self, writer: asyncio.StreamWriter) -> None:
        """Close a single connection."""
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

    def clear(self) -> None:
        """Clear all pooled connections (called on shutdown)."""
        for _key, bucket in self._idle.items():
            for _, writer, _ in bucket:
                asyncio.create_task(self._close_one(writer))
        self._idle.clear()
        log.info("TCP pool cleared")


# Global TCP pool instance (lazy initialized)
_tcp_pool: _TcpPool | None = None


def _get_tcp_pool() -> _TcpPool:
    """Lazy initialization of global TCP pool."""
    global _tcp_pool
    if _tcp_pool is None:
        from .stats import Stats
        _tcp_pool = _TcpPool(Stats())
        log.debug("TCP pool initialized lazily")
    return _tcp_pool


async def _bridge_ws(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ws: RawWebSocket, label: str, stats: Stats,
                     dc: int | None = None, dst: str | None = None, port: int | None = None, is_media: bool = False,
                     splitter: _MsgSplitter | None = None) -> tuple[int, int]:
    """Bidirectional TCP <-> WebSocket forwarding.

    Optimizations:
    - Zero-copy reads using memoryview where possible
    - Batch small packets for efficiency
    - Adaptive drain based on buffer pressure
    """
    dc_tag = f"DC{dc}{'m' if is_media else ''}" if dc else "DC?"
    dst_tag = f"{dst}:{port}" if dst else "?"

    up_bytes = 0
    down_bytes = 0
    up_packets = 0
    down_packets = 0
    start_time = asyncio.get_event_loop().time()

    # Batch buffer for small packets (reduce WebSocket frame overhead)
    BATCH_SIZE = 4096  # Batch small packets <4KB
    batch_buffer: bytearray = bytearray()

    async def tcp_to_ws() -> None:
        nonlocal up_bytes, up_packets, batch_buffer
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break

                # Use memoryview for zero-copy length check
                mv = memoryview(chunk)
                chunk_len = len(mv)
                if chunk_len == 0:
                    break

                stats.add_bytes(up=chunk_len)
                up_bytes += chunk_len
                up_packets += 1

                if splitter:
                    # Splitter needs bytes, not memoryview
                    parts = splitter.split(bytes(mv))
                    if len(parts) > 1:
                        await ws.send_batch(parts)
                    else:
                        await ws.send(parts[0])
                else:
                    # Batch small packets for efficiency
                    if chunk_len < BATCH_SIZE:
                        batch_buffer.extend(mv)
                        # Send batch if large enough or timeout
                        if len(batch_buffer) >= BATCH_SIZE:
                            await ws.send(bytes(batch_buffer))
                            batch_buffer.clear()
                    else:
                        # Send large chunks immediately
                        if batch_buffer:
                            await ws.send(bytes(batch_buffer))
                            batch_buffer.clear()
                        await ws.send(chunk)
        except (asyncio.CancelledError, ConnectionError, OSError):
            return
        except Exception as e:
            log.debug("[%s] tcp->ws ended: %s", label, e)
        finally:
            # Flush remaining batch buffer
            if batch_buffer:
                try:
                    await ws.send(bytes(batch_buffer))
                    batch_buffer.clear()
                except Exception:
                    pass

    async def ws_to_tcp() -> None:
        nonlocal down_bytes, down_packets
        try:
            while True:
                data = await ws.recv()
                if data is None:
                    break

                # Use memoryview for zero-copy operations
                mv = memoryview(data)
                data_len = len(mv)
                if data_len == 0:
                    continue

                stats.bytes_down += data_len
                down_bytes += data_len
                down_packets += 1
                writer.write(data)

                # Adaptive drain: only when buffer is filling up
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
        await _close_writer_safe(None)  # ws is RawWebSocket, not StreamWriter
        await _close_writer_safe(writer)

    return up_bytes, down_bytes


async def _bridge_tcp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, remote_reader: asyncio.StreamReader, remote_writer: asyncio.StreamWriter,
                      label: str, stats: Stats, dc: int | None = None, dst: str | None = None, port: int | None = None,
                      is_media: bool = False) -> None:
    """Bidirectional TCP <-> TCP forwarding (for fallback)."""
    async def forward(src: asyncio.StreamReader, dst_w: asyncio.StreamWriter, tag: str) -> None:
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


async def _pipe(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
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
        await _close_writer_safe(None)  # w is StreamWriter


async def _pipe_passthrough(r1: asyncio.StreamReader, w1: asyncio.StreamWriter, r2: asyncio.StreamReader, w2: asyncio.StreamWriter) -> None:
    """Bidirectional TCP relay for passthrough traffic."""
    async def forward(src: asyncio.StreamReader, dst_w: asyncio.StreamWriter, direction: str) -> None:
        try:
            while True:
                data = await src.read(65536)
                if not data:
                    break
                dst_w.write(data)
                await dst_w.drain()
        except asyncio.CancelledError:
            pass
        except (ConnectionResetError, BrokenPipeError):
            log.debug("[%s] %s connection reset", "passthrough", direction)
        except Exception as exc:
            log.debug("[%s] %s error: %s", "passthrough", direction, exc)
        finally:
            await _close_writer_safe(dst_w)

    tasks = [
        asyncio.create_task(forward(r1, w2, 'client->remote')),
        asyncio.create_task(forward(r2, w1, 'remote->client')),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_tasks(tasks)


def _socks5_reply(status: int) -> bytes:
    return bytes([0x05, status, 0x00, 0x01]) + b'\x00' * 6


async def _tcp_fallback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, dst: str, port: int, init: bytes, label: str,
                        dc: int | None = None, is_media: bool = False, stats: Stats | None = None) -> bool:
    """
    Fall back to direct TCP to the original DC IP.
    Uses connection pooling to reduce latency.
    Throttled by ISP, but functional. Returns True on success.
    """
    # Get TCP pool (lazy initialized)
    tcp_pool = _get_tcp_pool()

    # Try to get cached connection
    rr, rw = None, None
    cached = await tcp_pool.get(dst, port)
    if cached:
        rr, rw = cached
        log.debug("[%s] TCP pool hit for %s:%d", label, dst, port)

    # Create new connection if cache miss
    if rr is None or rw is None:
        try:
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(dst, port), timeout=10)
            log.debug("[%s] TCP new connection to %s:%d", label, dst, port)
        except Exception as exc:
            log.warning("[%s] TCP fallback connect to %s:%d failed: %s",
                        label, dst, port, exc)
            return False

    if stats:
        stats.add_connection('tcp_fallback', dc=dc)
    if rw is not None:
        rw.write(init)
        await rw.drain()
    if stats and rr is not None and rw is not None:
        await _bridge_tcp(reader, writer, rr, rw, label, stats,
                          dc=dc, dst=dst, port=port, is_media=is_media)

    # Return connection to pool if still valid
    if rw is not None and not rw.is_closing() and rr is not None:
        tcp_pool.put(dst, port, rr, rw)
    else:
        # Close if not pooling
        try:
            if rw is not None:
                rw.close()
        except Exception:
            pass

    return True


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    stats: Stats,
    dc_opt: dict[int, str | None],
    ws_pool: _WsPool,
    ws_blacklist: set[tuple[int, bool]],
    dc_fail_until: dict[tuple[int, bool], float],
    auth_required: bool = False,
    auth_credentials: dict[str, str] | None = None,
    ip_whitelist: set[str] | None = None,
    dc_error_count: dict[tuple[int, bool], int] | None = None,
    rate_limiter: object | None = None,  # RateLimiter instance
) -> None:
    peer = writer.get_extra_info('peername')
    client_ip = peer[0] if peer else "unknown"
    client_port = peer[1] if peer else 0
    # Generate unique client ID for tracking
    import random
    client_id = f"{client_ip}:{client_port}-{random.randint(1000, 9999)}"
    label = f"[C{client_id}]"

    # Check rate limiting first
    if rate_limiter is not None:
        from proxy.rate_limiter import RateLimitAction
        action, delay = rate_limiter.check_rate_limit(client_ip)  # type: ignore[attr-defined]

        if action == RateLimitAction.BAN:
            log.warning("%s client banned (IP: %s)", label, client_ip)
            stats.add_connection('http_rejected', dc=None)
            writer.close()
            return
        elif action == RateLimitAction.REJECT:
            log.warning("%s rate limit exceeded - rejected", label)
            stats.add_connection('http_rejected', dc=None)
            writer.write(b'\x05\x01')  # Connection refused
            await writer.drain()
            writer.close()
            return
        elif action == RateLimitAction.DELAY:
            log.debug("%s rate limited - delaying %.1fs", label, delay)
            await asyncio.sleep(delay)

    # Check IP whitelist
    if ip_whitelist is not None and client_ip not in ip_whitelist:
        log.warning("%s client IP not in whitelist - rejected", label)
        stats.add_connection('http_rejected', dc=None)
        writer.close()
        return

    _set_sock_opts(writer.transport)

    try:
        # -- SOCKS5 greeting --
        hdr = await asyncio.wait_for(reader.readexactly(2), timeout=10)
        if hdr[0] != 5:
            log.debug("%s not SOCKS5 (ver=%d)", label, hdr[0])
            stats.add_connection('passthrough', dc=None)
            writer.close()
            return

        nmethods = hdr[1]
        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10)

        # Check if client supports auth method (0x02) when auth is required
        if auth_required and auth_credentials:
            if 0x02 not in methods:
                log.warning("%s client doesn't support auth method", label)
                writer.write(b'\x05\xff')  # No acceptable methods
                await writer.drain()
                writer.close()
                return
            writer.write(b'\x05\x02')  # Use username/password auth
            await writer.drain()

            # Read auth credentials from client
            auth_ver = await asyncio.wait_for(reader.readexactly(1), timeout=10)
            if auth_ver[0] != 1:
                log.warning("%s unknown auth version %d", label, auth_ver[0])
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
                log.warning("%s auth failed for user %s", label, username.decode())
                writer.write(b'\x01\x01')  # Authentication failed
                await writer.drain()
                writer.close()
                stats.add_connection('http_rejected', dc=None)
                return

            writer.write(b'\x01\x00')  # Authentication successful
            await writer.drain()
            log.info("%s auth successful for user %s", label, username.decode())
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
            log.debug("%s passthrough -> %s:%d", label, dst, port)
            try:
                rr, rw = await asyncio.wait_for(
                    asyncio.open_connection(dst, port), timeout=10)
            except Exception as exc:
                log.warning("%s passthrough failed to %s: %s: %s", label, dst, type(exc).__name__, str(exc) or "(no message)")
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
            log.debug("%s client disconnected before init", label)
            return

        # HTTP transport -> reject
        if _is_http_transport(init):
            stats.connections_http_rejected += 1
            log.debug("%s HTTP transport to %s:%d (rejected)",
                      label, dst, port)
            writer.close()
            return

        # -- Extract DC ID --
        dc, is_media = _dc_from_init(init)
        init_patched = False

        # Android (may be ios too) with useSecret=0 has random dc_id bytes — patch it
        if dc is None and dst in _IP_TO_DC:
            dc_result = _IP_TO_DC.get(dst)
            if dc_result is not None:
                dc, is_media = dc_result
            if dc is not None and dc in dc_opt:
                init = _patch_init_dc(init, dc if is_media else -dc)
                init_patched = True

        if dc is None or dc not in dc_opt:
            log.warning("%s unknown DC%s for %s:%d -> TCP passthrough",
                        label, dc, dst, port)
            await _tcp_fallback(reader, writer, dst, port, init, label)
            return

        dc_key = (dc, is_media if is_media is not None else False)
        now = time.monotonic()
        media_tag = (" media" if is_media
                     else (" media?" if is_media is None else ""))

        # -- WS blacklist check --
        if dc_key in ws_blacklist:
            log.debug("%s DC%d%s WS blacklisted -> TCP %s:%d",
                      label, dc, media_tag, dst, port)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("%s DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- Cooldown check --
        fail_until = dc_fail_until.get(dc_key, 0)
        if now < fail_until:
            remaining = fail_until - now
            log.debug("%s DC%d%s WS cooldown (%.0fs) -> TCP",
                      label, dc, media_tag, remaining)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("%s DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- Try WebSocket via direct connection --
        domains = _ws_domains(dc, is_media)
        target = dc_opt[dc]
        ws = None
        ws_failed_redirect = False
        all_redirects = True

        ws = await ws_pool.get(dc, is_media, target, domains)  # type: ignore[arg-type]
        if ws:
            log.info("%s DC%d%s (%s:%d) -> pool hit via %s",
                     label, dc, media_tag, dst, port, target)
        else:
            for domain in domains:
                url = f'wss://{domain}/apiws'
                log.info("%s DC%d%s (%s:%d) -> %s via %s",
                         label, dc, media_tag, dst, port, url, target)
                try:
                    ws = await RawWebSocket.connect(target, domain,  # type: ignore[arg-type]
                                                    timeout=10)
                    all_redirects = False
                    break
                except WsHandshakeError as exc:
                    stats.ws_errors += 1
                    # Notify about error
                    if _on_client_error_callback:
                        try:
                            _on_client_error_callback(dc, dst, port, "websocket_handshake", str(exc))  # type: ignore[arg-type, call-arg]
                        except Exception:
                            pass
                    if exc.is_redirect:
                        ws_failed_redirect = True
                        log.warning("%s DC%d%s got %d from %s -> %s",
                                    label, dc, media_tag,
                                    exc.status_code, domain,
                                    exc.location or '?')
                        continue
                    else:
                        all_redirects = False
                        log.warning("%s DC%d%s WS handshake: %s",
                                    label, dc, media_tag, exc.status_line)
                except Exception as exc:
                    stats.add_ws_error(dc=dc)
                    # Notify about error
                    if _on_client_error_callback:
                        try:
                            _on_client_error_callback(dc, dst, port, "websocket_connect", str(exc))  # type: ignore[arg-type, call-arg]
                        except Exception:
                            pass
                    all_redirects = False
                    err_str = str(exc)
                    if ('CERTIFICATE_VERIFY_FAILED' in err_str or
                            'Hostname mismatch' in err_str):
                        log.warning("%s DC%d%s SSL error: %s",
                                    label, dc, media_tag, exc)
                    else:
                        log.warning("%s DC%d%s WS connect failed: %s",
                                    label, dc, media_tag, exc)

        # -- WS failed -> fallback --
        if ws is None:
            if ws_failed_redirect and all_redirects:
                ws_blacklist.add(dc_key)
                log.warning(
                    "%s DC%d%s blacklisted for WS (all 302)",
                    label, dc, media_tag)
            elif ws_failed_redirect:
                # Exponential backoff: base cooldown * 2^(error_count-1)
                if dc_error_count is not None:
                    error_count = dc_error_count.get(dc_key, 0) + 1
                    dc_error_count[dc_key] = error_count
                else:
                    error_count = 1
                backoff_multiplier = 2 ** (error_count - 1)
                dc_fail_until[dc_key] = now + (DC_FAIL_COOLDOWN * backoff_multiplier)
                log.info("%s DC%d%s WS cooldown for %ds (attempt #%d)",
                         label, dc, media_tag, int(DC_FAIL_COOLDOWN * backoff_multiplier), error_count)
            else:
                # Increment error count for non-redirect failures too
                if dc_error_count is not None:
                    error_count = dc_error_count.get(dc_key, 0) + 1
                    dc_error_count[dc_key] = error_count
                else:
                    error_count = 1
                backoff_multiplier = min(2 ** (error_count - 1), 8)  # Cap at 8x
                dc_fail_until[dc_key] = now + (DC_FAIL_COOLDOWN * backoff_multiplier)
                log.info("%s DC%d%s WS cooldown for %ds (attempt #%d)",
                         label, dc, media_tag, int(DC_FAIL_COOLDOWN * backoff_multiplier), error_count)

            log.info("%s DC%d%s -> TCP fallback to %s:%d",
                     label, dc, media_tag, dst, port)
            ok = await _tcp_fallback(reader, writer, dst, port, init,
                                     label, dc=dc, is_media=is_media)
            if ok:
                log.info("%s DC%d%s TCP fallback closed",
                         label, dc, media_tag)
            return

        # -- WS success --
        # Reset error count on successful connection
        if dc_error_count is not None:
            dc_error_count.pop(dc_key, None)
        dc_fail_until.pop(dc_key, None)
        stats.add_connection('ws', dc=dc)

        # Notify about client connection
        if _on_client_connect_callback:
            try:
                _on_client_connect_callback(dc, dst, port)  # type: ignore[arg-type, call-arg]
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
        log.debug("%s timeout during SOCKS5 handshake", label)
    elif isinstance(exc, asyncio.IncompleteReadError):
        log.debug("%s client disconnected", label)
    elif isinstance(exc, asyncio.CancelledError):
        log.debug("%s cancelled", label)
    elif isinstance(exc, ConnectionResetError):
        log.debug("%s connection reset", label)
    # Unexpected errors - log at ERROR level
    else:
        log.error("%s unexpected error: %s", label, exc)


def _close_client_writer(writer: asyncio.StreamWriter | None) -> None:
    """Safely close client writer connection."""
    try:
        if writer is not None:
            writer.close()
    except Exception:
        pass


async def _run(
    port: int,
    dc_opt: dict[int, str | None],
    stop_event: asyncio.Event | None = None,
    host: str = '127.0.0.1',
    auth_required: bool = False,
    auth_credentials: dict[str, str] | None = None,
    ip_whitelist: list[str] | None = None,
    encryption_config: dict | None = None,
    rate_limit_config: dict | None = None,
) -> None:
    global _server_instance

    # Initialize async DNS resolver (aiodns) for better performance
    _init_async_dns()

    # Create proxy server instance with encapsulated state
    server_instance = ProxyServer(
        dc_opt,
        host,
        port,
        auth_required,
        auth_credentials,
        ip_whitelist,
        encryption_config,
        rate_limit_config,
    )
    _server_instance = server_instance

    # Start automatic key rotation if encryption is enabled
    await server_instance._start_key_rotation()

    # Start rate limiter if configured
    await server_instance._start_rate_limiter()

    # Create a wrapper for _handle_client that passes server state
    async def handle_client_wrapper(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _handle_client(
            reader, writer,
            stats=server_instance.stats,
            dc_opt=server_instance.dc_opt,
            ws_pool=server_instance.ws_pool,
            ws_blacklist=server_instance.ws_blacklist,
            dc_fail_until=server_instance.dc_fail_until,
            auth_required=server_instance.auth_required,
            auth_credentials=server_instance.auth_credentials,
            ip_whitelist=server_instance.ip_whitelist,
            dc_error_count=server_instance.dc_error_count,
            rate_limiter=server_instance.rate_limiter,
        )

    server = await asyncio.start_server(
        handle_client_wrapper, host, port)
    server_instance._server_instance = server

    for sock in server.sockets:
        try:
            sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            pass

    # Check WebSocket domain availability
    log.info("Checking WebSocket domain availability...")
    domain_status = await _check_ws_domains_available(dc_opt)
    failed_dcs = [dc for dc, (ok, _) in domain_status.items() if not ok]
    if failed_dcs:
        log.warning("WebSocket domains unavailable for DCs: %s", failed_dcs)
        log.warning("Proxy will use TCP fallback for these DCs")
    else:
        log.info("All WebSocket domains are available")

    # Measure DC ping and select optimal DC
    log.info("Measuring DC latency for optimal selection...")
    dc_pings = await _measure_all_dc_pings(dc_opt)

    # Store ping results in stats
    for dc_id, latency_ms in dc_pings.items():
        server_instance.stats.record_latency(dc_id, latency_ms)

    # Log optimal DC selection
    if dc_pings:
        best_dc = min(dc_pings, key=lambda x: dc_pings[x])
        log.info("Optimal DC selected: DC%d (%.1fms)", best_dc, dc_pings[best_dc])
    else:
        log.warning("Could not measure DC latency - will use default routing")

    log.info("=" * 60)
    log.info("  Telegram WS Bridge Proxy")
    log.info("  Listening on   %s:%d", host, port)
    log.info("  Target DC IPs:")
    for dc in dc_opt.keys():
        ip = dc_opt.get(dc)
        log.info("    DC%d: %s", dc, ip)
    if dc_pings:
        log.info("  DC Latency:")
        for dc_id, latency in sorted(dc_pings.items()):
            marker = " ✓" if dc_id == min(dc_pings, key=lambda x: dc_pings[x]) else ""
            log.info("    DC%d: %.1fms%s", dc_id, latency, marker)
    log.info("=" * 60)
    log.info("  Configure Telegram Desktop:")
    if auth_required and auth_credentials:
        log.info("    SOCKS5 proxy -> %s:%d  (user/pass required)", host, port)
    else:
        log.info("    SOCKS5 proxy -> %s:%d  (no user/pass)", host, port)
    log.info("=" * 60)

    # Check for updates (non-blocking)
    try:
        from .updater import check_for_updates

        async def check_update_async() -> None:
            try:
                update_info = await check_for_updates(force=False)
                if update_info:
                    log.info(
                        "🚀 New version available: %s → %s | Download: %s",
                        update_info['current_version'],
                        update_info['latest_version'],
                        update_info['release_url']
                    )
                else:
                    log.debug("Already on latest version")
            except Exception as e:
                log.debug("Update check failed: %s", e)

        # Schedule update check (don't block startup)
        asyncio.create_task(check_update_async())
    except Exception as e:
        log.debug("Failed to schedule update check: %s", e)

    async def log_stats() -> None:
        while True:
            await asyncio.sleep(60)
            bl = ', '.join(
                f'DC{d}{"m" if m else ""}'
                for d, m in sorted(server_instance.ws_blacklist)) or 'none'
            log.info("stats: %s | ws_bl: %s", server_instance.stats.summary(), bl)

    server_instance._log_stats_task = asyncio.create_task(log_stats())

    # Background task for periodic DC ping monitoring with auto-switch
    _last_latency_alert: dict[int, float] = {}  # dc_id -> last alert time
    _last_dc_switch: float = 0.0
    _switch_cooldown = 300.0  # 5 minutes between DC switches
    _high_latency_threshold = 200.0  # ms
    _alert_cooldown = 300.0  # 5 minutes between alerts for same DC
    _current_best_dc: int | None = None

    async def monitor_dc_latency() -> None:
        """Periodically re-measure DC latency and auto-switch to best DC."""
        nonlocal _last_latency_alert, _last_dc_switch, _current_best_dc, dc_opt

        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            log.debug("Re-checking DC latency...")
            dc_pings = await _measure_all_dc_pings(dc_opt)
            now = time.monotonic()

            if not dc_pings:
                continue

            # Find best DC by latency
            best_dc = min(dc_pings, key=lambda x: dc_pings[x])
            best_latency = dc_pings[best_dc]

            # Store latency in stats
            for dc_id, latency_ms in dc_pings.items():
                server_instance.stats.record_latency(dc_id, latency_ms)

            # Auto-switch to best DC if conditions met
            if _current_best_dc != best_dc:
                # Check if we should switch
                should_switch = False

                # Always switch on first measurement
                if _current_best_dc is None:
                    should_switch = True
                    log.info("Initial DC selection: DC%d (%.1fms)", best_dc, best_latency)
                # Switch if current DC has high latency and best is significantly better
                elif best_dc in dc_pings and _current_best_dc in dc_pings:
                    current_latency = dc_pings.get(_current_best_dc, float('inf'))
                    latency_diff = current_latency - best_latency

                    # Switch if difference > 50ms and cooldown passed
                    if latency_diff > 50 and (now - _last_dc_switch) > _switch_cooldown:
                        should_switch = True
                        log.info("DC switch: DC%d (%.1fms) -> DC%d (%.1fms) [diff: %.1fms]",
                                _current_best_dc, current_latency, best_dc, best_latency, latency_diff)

                if should_switch and best_dc in dc_opt:
                    # Update dc_opt to prioritize best DC
                    # Move best DC to first position in routing
                    current_ip = dc_opt[best_dc]
                    dc_opt.pop(best_dc)
                    dc_opt = {best_dc: current_ip, **dc_opt}
                    server_instance.dc_opt = dc_opt
                    _current_best_dc = best_dc
                    _last_dc_switch = now

                    # Warmup WS pool for new best DC
                    asyncio.create_task(server_instance.ws_pool.warmup({best_dc: current_ip}))
                    log.info("DC switched to DC%d (new primary)", best_dc)

            # Check for high latency and notify
            for dc_id, latency_ms in dc_pings.items():
                if latency_ms > _high_latency_threshold:
                    last_alert = _last_latency_alert.get(dc_id, 0)
                    if now - last_alert > _alert_cooldown:
                        _last_latency_alert[dc_id] = now
                        log.warning("DC%d: HIGH LATENCY %.1fms (threshold: %.1fms)",
                                   dc_id, latency_ms, _high_latency_threshold)

            log.info("DC latency: best=DC%d (%.1fms), current=%s",
                    best_dc, best_latency,
                    f"DC{_current_best_dc}" if _current_best_dc else "none")

    server_instance._dc_monitor_task = asyncio.create_task(monitor_dc_latency())

    # Background task for dynamic pool optimization
    async def optimize_pool() -> None:
        """Periodically optimize WebSocket pool size."""
        while True:
            await asyncio.sleep(30)  # Check every 30 seconds
            try:
                server_instance.ws_pool._optimize_pool_size()
            except Exception as e:
                log.debug("Pool optimization error: %s", e)

    server_instance._optimize_pool_task = asyncio.create_task(optimize_pool())

    # Background task for DNS cache cleanup
    async def cleanup_dns_cache() -> None:
        """Periodically clean expired DNS cache entries."""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = time.monotonic()
            expired_domains = []

            for domain, entries in _dns_cache.items():
                valid = [(ip, exp) for ip, exp in entries if exp > now]
                if valid:
                    _dns_cache[domain] = valid
                else:
                    expired_domains.append(domain)

            for domain in expired_domains:
                del _dns_cache[domain]

            if expired_domains:
                log.debug("DNS cache cleaned: %d expired domains", len(expired_domains))

    asyncio.create_task(cleanup_dns_cache())

    # Warmup WebSocket pool and start health checker
    await server_instance.ws_pool.warmup(dc_opt)
    await server_instance.ws_pool.start_health_checker()
    log.info("WS pool health checker started (interval: %.1fs)", server_instance.ws_pool._heartbeat_interval)

    # Start memory profiler (optional, enabled via config)
    try:
        from .profiler import get_profiler
        server_instance._memory_profiler = get_profiler(check_interval=300.0)  # 5 min
        server_instance._memory_profiler.start()
        log.info("Memory profiler started (interval: 300s)")
    except Exception as e:
        log.debug("Memory profiler not started: %s", e)

    if stop_event:
        async def wait_stop() -> None:
            await stop_event.wait()
            log.info("Graceful shutdown initiated...")

            # Stop real-time monitoring
            server_instance.stats.stop_realtime_monitoring()
            log.info("Real-time monitoring stopped")

            # Stop rate limiter
            await server_instance._stop_rate_limiter()
            log.info("Rate limiter stopped")

            # Close server socket first (stop accepting new connections)
            server.close()
            await server.wait_closed()
            log.info("Server socket closed")

            # Close all idle WebSocket connections in pool
            ws_count = 0
            for key, bucket in server_instance.ws_pool._idle.items():
                dc, is_media = key
                for ws, _ in bucket:
                    try:
                        await ws.close()
                        ws_count += 1
                    except Exception:
                        pass
            log.info("WebSocket pool closed (%d connections)", ws_count)

            # Stop DC latency monitor
            if hasattr(server_instance, '_dc_monitor_task') and server_instance._dc_monitor_task:
                server_instance._dc_monitor_task.cancel()
                try:
                    await server_instance._dc_monitor_task
                except asyncio.CancelledError:
                    pass
                log.info("DC monitor stopped")

            # Stop log stats task
            if hasattr(server_instance, '_log_stats_task') and server_instance._log_stats_task:
                server_instance._log_stats_task.cancel()
                try:
                    await server_instance._log_stats_task
                except asyncio.CancelledError:
                    pass
                log.info("Log stats stopped")

            # Stop pool optimization task
            if hasattr(server_instance, '_optimize_pool_task') and server_instance._optimize_pool_task:
                server_instance._optimize_pool_task.cancel()
                try:
                    await server_instance._optimize_pool_task
                except asyncio.CancelledError:
                    pass
                log.info("Pool optimization stopped")

            # Stop health checker
            if hasattr(server_instance.ws_pool, '_health_check_task') and server_instance.ws_pool._health_check_task:
                server_instance.ws_pool._health_check_task.cancel()
                try:
                    await server_instance.ws_pool._health_check_task
                except asyncio.CancelledError:
                    pass
                log.info("Health checker stopped")

            # Stop memory profiler
            if server_instance._memory_profiler:
                server_instance._memory_profiler.stop()
                log.info("Memory profiler stopped")

                # Log final memory report
                report = server_instance._memory_profiler.get_leak_report()
                if report != "No memory leaks detected":
                    log.info("Final memory report:\n%s", report)

            log.info("Graceful shutdown completed")

        asyncio.create_task(wait_stop())

    async with server:
        try:
            # Start Crash Watchdog - auto-restart on critical errors
            _crash_count = 0
            _max_crashes = 3
            _crash_window = 300.0  # 5 minutes
            _crash_times: list[float] = []

            async def crash_watchdog() -> None:
                """Monitor for crashes and restart if needed."""
                nonlocal _crash_count, _crash_times
                while True:
                    await asyncio.sleep(60)
                    # Clean old crash times
                    now = time.monotonic()
                    _crash_times = [t for t in _crash_times if now - t < _crash_window]

                    # Check if we exceeded crash threshold
                    if len(_crash_times) >= _max_crashes:
                        log.error("CRASH WATCHDOG: %d crashes in %.0f minutes, restarting...",
                                 _max_crashes, _crash_window / 60)
                        # Reset crash counter after restart
                        _crash_count = 0
                        _crash_times = []
                        # Restart would be handled by outer loop in production

            asyncio.create_task(crash_watchdog())
            log.info("Crash Watchdog started (max %d crashes per %.0f min)",
                    _max_crashes, _crash_window / 60)

            await server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.exception("CRITICAL ERROR in server: %s", e)
            _crash_count += 1
            _crash_times.append(time.monotonic())
            raise
    _server_instance = None


def parse_dc_ip_list(dc_ip_list: list[str]) -> dict[int, str | None]:
    """
    Parse list of 'DC:IP' strings into {dc: ip} dict.

    Args:
        dc_ip_list: List of strings in format 'DC:IP' (e.g., ['2:149.154.167.220'])

    Returns:
        Dictionary mapping DC IDs to IP addresses

    Raises:
        ValueError: If any entry has invalid format
    """
    dc_opt: dict[int, str | None] = {}
    for entry in dc_ip_list:
        if ':' not in entry:
            raise ValueError(f"Invalid --dc-ip format {entry!r}, expected DC:IP")
        dc_s, ip_s = entry.split(':', 1)
        try:
            dc_n = int(dc_s)
            _socket.inet_aton(ip_s)
        except (ValueError, OSError) as exc:
            raise ValueError(f"Invalid --dc-ip {entry!r}") from exc
        dc_opt[dc_n] = ip_s
    return dc_opt


def run_proxy(
    port: int,
    dc_opt: dict[int, str | None],
    stop_event: asyncio.Event | None = None,
    host: str = '127.0.0.1',
    auth_required: bool = False,
    auth_credentials: dict[str, str] | None = None,
    encryption_config: dict | None = None,
    rate_limit_config: dict | None = None,
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
        encryption_config: Optional dict with encryption settings
        rate_limit_config: Optional dict with rate limiting settings
    """
    asyncio.run(_run(
        port,
        dc_opt,
        stop_event,
        host,
        auth_required,
        auth_credentials,
        None,  # ip_whitelist
        encryption_config,
        rate_limit_config,
    ))


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
        dc_opt: dict[int, str | None] = parse_dc_ip_list(args.dc_ip)
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
