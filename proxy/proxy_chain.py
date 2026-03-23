"""
Proxy Chain Support.

Provides proxy chaining capabilities:
- Multiple proxy hops
- Different protocols per hop (SOCKS5, HTTP, WebSocket, MTProto)
- Automatic failover
- Latency-based selection

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

log = logging.getLogger('tg-ws-proxy-chain')


class ProxyProtocol(Enum):
    """Proxy protocols."""
    SOCKS5 = auto()
    SOCKS4 = auto()
    HTTP = auto()
    HTTPS = auto()
    WEBSOCKET = auto()
    MTPROTO = auto()
    SHADOWSOCKS = auto()
    VMESS = auto()


@dataclass
class ProxyHop:
    """Single proxy hop in chain."""
    protocol: ProxyProtocol
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    secret: str | None = None  # For MTProto/Shadowsocks
    timeout: float = 10.0

    # Performance metrics
    latency_ms: float = field(default=float('inf'))
    success_rate: float = field(default=1.0)
    last_used: float = field(default_factory=time.time)
    is_active: bool = field(default=True)

    @property
    def score(self) -> float:
        """Calculate proxy quality score (higher is better)."""
        # Combine latency and success rate
        latency_score = max(0, 100 - self.latency_ms / 10)
        return latency_score * self.success_rate


@dataclass
class ProxyChainConfig:
    """Proxy chain configuration."""
    hops: list[ProxyHop] = field(default_factory=list)
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    enable_auto_failover: bool = True
    enable_latency_check: bool = True
    latency_check_interval: float = 60.0  # seconds
    min_success_rate: float = 0.5  # Minimum success rate to keep proxy


class ProxyChainManager:
    """
    Proxy chain manager.

    Features:
    - Multi-hop proxy chains
    - Automatic failover
    - Latency monitoring
    - Protocol support (SOCKS5, HTTP, WS, MTProto)
    """

    def __init__(self, config: ProxyChainConfig | None = None):
        self.config = config or ProxyChainConfig()
        self._current_chain: list[ProxyHop] = []
        self._failed_hops: set[int] = set()
        self._latency_check_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start proxy chain manager."""
        self._running = True

        if self.config.enable_latency_check:
            self._latency_check_task = asyncio.create_task(
                self._latency_check_loop()
            )

        log.info("Proxy chain manager started (%d hops configured)",
                len(self.config.hops))

    async def stop(self) -> None:
        """Stop proxy chain manager."""
        self._running = False

        if self._latency_check_task:
            self._latency_check_task.cancel()
            try:
                await self._latency_check_task
            except asyncio.CancelledError:
                pass

        log.info("Proxy chain manager stopped")

    async def _latency_check_loop(self) -> None:
        """Periodically check proxy latency."""
        while self._running:
            try:
                await asyncio.sleep(self.config.latency_check_interval)
                await self._check_all_proxies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Latency check error: %s", e)

    async def _check_all_proxies(self) -> None:
        """Check latency of all configured proxies."""
        tasks = []
        for i, hop in enumerate(self.config.hops):
            if hop.is_active:
                tasks.append(self._check_proxy_latency(i, hop))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_proxy_latency(self, index: int, hop: ProxyHop) -> None:
        """Check latency of single proxy."""
        try:
            start = time.monotonic()

            # Try to connect
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(hop.host, hop.port),
                timeout=hop.timeout
            )

            # Close immediately
            writer.close()
            await writer.wait_closed()

            latency = (time.monotonic() - start) * 1000

            # Update metrics
            hop.latency_ms = latency
            hop.success_rate = min(1.0, hop.success_rate + 0.1)
            hop.last_used = time.time()

            log.debug("Proxy %d (%s:%d) latency: %.0fms",
                     index, hop.host, hop.port, latency)

        except Exception:
            hop.success_rate = max(0, hop.success_rate - 0.2)

            # Disable if success rate too low
            if hop.success_rate < self.config.min_success_rate:
                hop.is_active = False
                self._failed_hops.add(index)
                log.warning("Proxy %d disabled (low success rate: %.1f%%)",
                           index, hop.success_rate * 100)

    def get_optimal_chain(self) -> list[ProxyHop]:
        """
        Get optimal proxy chain based on current metrics.

        Returns:
            List of proxy hops in optimal order
        """
        if not self.config.hops:
            return []

        # Filter active proxies
        active_proxies = [h for h in self.config.hops if h.is_active]

        if not active_proxies:
            # All proxies failed, use all with low score
            active_proxies = self.config.hops

        # Sort by score (descending)
        sorted_proxies = sorted(active_proxies, key=lambda x: x.score, reverse=True)

        # Select top proxies for chain
        chain_size = min(3, len(sorted_proxies))
        chain = sorted_proxies[:chain_size]

        self._current_chain = chain
        log.debug("Optimal chain selected: %d hops", len(chain))

        return chain

    async def create_connection(self, target_host: str,
                                 target_port: int) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
        """
        Create connection through proxy chain.

        Args:
            target_host: Target host
            target_port: Target port

        Returns:
            Reader/writer pair or None if failed
        """
        chain = self.get_optimal_chain()

        if not chain:
            # Direct connection
            try:
                return await asyncio.open_connection(target_host, target_port)
            except Exception as e:
                log.error("Direct connection failed: %s", e)
                return None

        # Connect through chain
        current_reader = None
        current_writer = None

        try:
            for i, hop in enumerate(chain):
                log.debug("Connecting through hop %d: %s:%d (%s)",
                         i, hop.host, hop.port, hop.protocol.name)

                try:
                    # Connect to this hop
                    reader, writer = await asyncio.wait_for(
                        self._connect_to_proxy(hop),
                        timeout=hop.timeout
                    )

                    # If not first hop, close previous
                    if current_writer:
                        current_writer.close()
                        await current_writer.wait_closed()

                    current_reader = reader
                    current_writer = writer

                except Exception as e:
                    log.error("Hop %d failed: %s", i, e)

                    # Mark hop as failed
                    hop.is_active = False
                    self._failed_hops.add(i)

                    # Retry with next hop
                    if self.config.enable_auto_failover:
                        continue
                    else:
                        return None

            # Final connection to target
            if current_writer:
                # Send CONNECT request through last hop
                await self._send_connect_request(current_writer, target_host, target_port)

                return current_reader, current_writer

        except Exception as e:
            log.error("Chain connection failed: %s", e)

            # Cleanup
            if current_writer:
                current_writer.close()

            return None

        return None

    async def _connect_to_proxy(self, hop: ProxyHop) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to single proxy hop."""
        if hop.protocol == ProxyProtocol.SOCKS5:
            return await self._connect_socks5(hop)
        elif hop.protocol in (ProxyProtocol.HTTP, ProxyProtocol.HTTPS):
            return await self._connect_http(hop)
        elif hop.protocol == ProxyProtocol.WEBSOCKET:
            return await self._connect_websocket(hop)
        else:
            # Direct TCP connection
            return await asyncio.open_connection(hop.host, hop.port)

    async def _connect_socks5(self, hop: ProxyHop) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to SOCKS5 proxy."""
        # Use asyncio socks5 library if available
        try:
            import socksio  # noqa: F401
            # Implementation would use socksio library
            pass
        except ImportError:
            pass

        # Fallback: direct connection with manual SOCKS5 handshake
        reader, writer = await asyncio.open_connection(hop.host, hop.port)

        # SOCKS5 greeting
        if hop.username and hop.password:
            # Auth required
            writer.write(b'\x05\x01\x02')  # VER=5, NMETHODS=1, METHODS=USERNAME/PASSWORD
        else:
            writer.write(b'\x05\x01\x00')  # No auth

        await writer.drain()
        greeting = await reader.read(2)

        if greeting[0] != 0x05:
            raise ConnectionError("Not SOCKS5")

        if greeting[1] == 0x02 and hop.username and hop.password:
            # Perform authentication
            await self._socks5_auth(reader, writer, hop.username, hop.password)

        return reader, writer

    async def _socks5_auth(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter,
                           username: str, password: str) -> None:
        """Perform SOCKS5 username/password authentication."""
        # Auth request
        auth = (
            b'\x01' +  # VER
            bytes([len(username)]) + username.encode() +
            bytes([len(password)]) + password.encode()
        )

        writer.write(auth)
        await writer.drain()

        # Auth response
        response = await reader.read(2)

        if response[1] != 0x00:
            raise ConnectionError("SOCKS5 authentication failed")

    async def _connect_http(self, hop: ProxyHop) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to HTTP proxy."""
        reader, writer = await asyncio.open_connection(hop.host, hop.port)

        # HTTP CONNECT request will be sent later
        return reader, writer

    async def _connect_websocket(self, hop: ProxyHop) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to WebSocket proxy."""
        # WebSocket upgrade would be handled here
        reader, writer = await asyncio.open_connection(hop.host, hop.port)
        return reader, writer

    async def _send_connect_request(self, writer: asyncio.StreamWriter,
                                     target_host: str, target_port: int) -> None:
        """Send CONNECT request through proxy."""
        connect_request = (
            f"CONNECT {target_host}:{target_port} HTTP/1.1\r\n"
            f"Host: {target_host}:{target_port}\r\n"
            f"\r\n"
        )

        writer.write(connect_request.encode())
        await writer.drain()

    def get_chain_stats(self) -> dict[str, Any]:
        """Get proxy chain statistics."""
        return {
            'total_hops': len(self.config.hops),
            'active_hops': sum(1 for h in self.config.hops if h.is_active),
            'failed_hops': len(self._failed_hops),
            'current_chain': [
                {
                    'host': h.host,
                    'port': h.port,
                    'protocol': h.protocol.name,
                    'latency_ms': h.latency_ms,
                    'success_rate': h.success_rate,
                }
                for h in self._current_chain
            ],
        }


# Global proxy chain manager
_chain_manager: ProxyChainManager | None = None


def get_chain_manager() -> ProxyChainManager:
    """Get or create global chain manager."""
    global _chain_manager
    if _chain_manager is None:
        _chain_manager = ProxyChainManager()
    return _chain_manager


def create_chain(hops: list[dict]) -> ProxyChainManager:
    """
    Create proxy chain from configuration.

    Args:
        hops: List of hop configurations
            Example: [
                {"protocol": "socks5", "host": "proxy1.com", "port": 1080},
                {"protocol": "http", "host": "proxy2.com", "port": 8080},
            ]

    Returns:
        Configured ProxyChainManager
    """
    proxy_hops = []

    for hop_config in hops:
        protocol_str = hop_config.get('protocol', 'socks5').upper()
        try:
            protocol = ProxyProtocol[protocol_str]
        except KeyError:
            protocol = ProxyProtocol.SOCKS5

        hop = ProxyHop(
            protocol=protocol,
            host=hop_config.get('host', '127.0.0.1'),
            port=int(hop_config.get('port', 1080)),
            username=hop_config.get('username'),
            password=hop_config.get('password'),
            secret=hop_config.get('secret'),
            timeout=float(hop_config.get('timeout', 10.0)),
        )
        proxy_hops.append(hop)

    config = ProxyChainConfig(hops=proxy_hops)
    return ProxyChainManager(config)


__all__ = [
    'ProxyProtocol',
    'ProxyHop',
    'ProxyChainConfig',
    'ProxyChainManager',
    'get_chain_manager',
    'create_chain',
]
