"""
Bridge and Relay support for circumventing censorship.

Provides alternative routing through intermediate servers to bypass
geographic and network-level blocking.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import socket
import ssl
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("tg-ws-bridge")

# =============================================================================
# Bridge/Relay Configuration
# =============================================================================


@dataclass
class RelayNode:
    """Represents a relay/bridge node."""
    
    id: str
    host: str
    port: int
    protocol: str = "websocket"  # websocket, http2, quic, shadowsocks
    country: str = "Unknown"
    city: str = "Unknown"
    latency_ms: float = float('inf')
    success_rate: float = 1.0
    last_check: float = 0.0
    is_online: bool = True
    supports_obfs: bool = True
    supports_domain_fronting: bool = False
    front_domain: str | None = None
    # Shadowsocks config
    ss_password: str | None = None
    ss_cipher: str = "aes-256-gcm"
    # Authentication
    auth_token: str | None = None
    # Metadata
    tags: list[str] = field(default_factory=list)
    priority: int = 0  # Higher = preferred


# Pre-configured public relay nodes (community-contributed)
PUBLIC_RELAYS: list[RelayNode] = [
    # Europe
    RelayNode(
        id="eu-de-1",
        host="relay-de.example.org",
        port=443,
        protocol="websocket",
        country="Germany",
        city="Frankfurt",
        tags=["europe", "fast", "stable"],
        priority=10,
    ),
    RelayNode(
        id="eu-nl-1",
        host="relay-nl.example.org",
        port=443,
        protocol="websocket",
        country="Netherlands",
        city="Amsterdam",
        tags=["europe", "fast"],
        priority=10,
    ),
    # Asia
    RelayNode(
        id="asia-sg-1",
        host="relay-sg.example.org",
        port=443,
        protocol="websocket",
        country="Singapore",
        city="Singapore",
        tags=["asia", "fast"],
        priority=10,
    ),
    # North America
    RelayNode(
        id="us-east-1",
        host="relay-us-east.example.org",
        port=443,
        protocol="websocket",
        country="United States",
        city="New York",
        tags=["americas", "fast"],
        priority=10,
    ),
    RelayNode(
        id="us-west-1",
        host="relay-us-west.example.org",
        port=443,
        protocol="websocket",
        country="United States",
        city="San Francisco",
        tags=["americas", "fast"],
        priority=10,
    ),
]

# Domain fronting enabled relays
FRONTING_RELAYS: list[RelayNode] = [
    RelayNode(
        id="front-cloudflare-1",
        host="kws1.web.telegram.org",
        port=443,
        protocol="websocket",
        country="Cloudflare CDN",
        city="Global",
        supports_domain_fronting=True,
        front_domain="ajax.cloudflare.com",
        tags=["fronting", "cloudflare"],
        priority=5,
    ),
    RelayNode(
        id="front-google-1",
        host="kws1.web.telegram.org",
        port=443,
        protocol="websocket",
        country="Google CDN",
        city="Global",
        supports_domain_fronting=True,
        front_domain="www.google.com",
        tags=["fronting", "google"],
        priority=5,
    ),
]


# =============================================================================
# Bridge Protocol
# =============================================================================


class BridgeProtocol:
    """
    Bridge protocol handler for relay communication.
    
    Protocol format:
    +--------+--------+--------+--------+
    | Magic  | Version| Type   | Length |
    +--------+--------+--------+--------+
    | Payload (variable length)          |
    +------------------------------------+
    """
    
    MAGIC = b'TGWP'  # Telegram WebSocket Proxy
    VERSION = 0x01
    
    # Message types
    MSG_CONNECT = 0x01
    MSG_DATA = 0x02
    MSG_CLOSE = 0x03
    MSG_PING = 0x04
    MSG_PONG = 0x05
    MSG_AUTH = 0x06
    MSG_ERROR = 0x07
    
    def __init__(self):
        """Initialize protocol handler."""
        self.buffer = b''
        
    def encode_connect(
        self,
        target_host: str,
        target_port: int,
        auth_token: str | None = None,
    ) -> bytes:
        """Encode CONNECT message."""
        # Build payload
        payload = struct.pack('>H', len(target_host)) + target_host.encode()
        payload += struct.pack('>H', target_port)
        
        if auth_token:
            payload += struct.pack('>H', len(auth_token)) + auth_token.encode()
        else:
            payload += struct.pack('>H', 0)
            
        return self._encode_message(self.MSG_CONNECT, payload)
    
    def encode_data(self, data: bytes) -> bytes:
        """Encode DATA message."""
        return self._encode_message(self.MSG_DATA, data)
    
    def encode_close(self, reason: str = '') -> bytes:
        """Encode CLOSE message."""
        payload = reason.encode() if reason else b''
        return self._encode_message(self.MSG_CLOSE, payload)
    
    def encode_ping(self) -> bytes:
        """Encode PING message."""
        timestamp = struct.pack('>Q', int(time.time() * 1000))
        return self._encode_message(self.MSG_PING, timestamp)
    
    def encode_pong(self, timestamp: bytes) -> bytes:
        """Encode PONG message."""
        return self._encode_message(self.MSG_PONG, timestamp)
    
    def encode_auth(self, token: str) -> bytes:
        """Encode AUTH message."""
        payload = token.encode()
        return self._encode_message(self.MSG_AUTH, payload)
    
    def encode_error(self, error_code: int, error_msg: str) -> bytes:
        """Encode ERROR message."""
        payload = struct.pack('>H', error_code) + error_msg.encode()
        return self._encode_message(self.MSG_ERROR, payload)
    
    def _encode_message(self, msg_type: int, payload: bytes) -> bytes:
        """Encode a complete message."""
        header = self.MAGIC
        header += struct.pack('B', self.VERSION)
        header += struct.pack('B', msg_type)
        header += struct.pack('>I', len(payload))
        return header + payload
    
    def decode_messages(self) -> list[tuple[int, bytes]]:
        """
        Decode complete messages from buffer.
        
        Returns:
            List of (message_type, payload) tuples
        """
        messages = []
        
        while len(self.buffer) >= 10:  # Minimum header size
            # Check magic
            if self.buffer[:4] != self.MAGIC:
                log.error("Invalid magic bytes in bridge protocol")
                self.buffer = self.buffer[1:]
                continue
                
            # Parse header
            version = self.buffer[4]
            msg_type = self.buffer[5]
            length = struct.unpack('>I', self.buffer[6:10])[0]
            
            # Check if we have complete message
            if len(self.buffer) < 10 + length:
                break
                
            # Extract payload
            payload = self.buffer[10:10 + length]
            messages.append((msg_type, payload))
            
            # Remove from buffer
            self.buffer = self.buffer[10 + length:]
            
        return messages
    
    def feed(self, data: bytes) -> list[tuple[int, bytes]]:
        """Feed data to buffer and decode messages."""
        self.buffer += data
        return self.decode_messages()


# =============================================================================
# Bridge Client
# =============================================================================


class BridgeClient:
    """
    Client for connecting through a relay bridge.
    
    Establishes connection to relay and forwards traffic to target.
    """
    
    def __init__(
        self,
        relay: RelayNode,
        target_host: str,
        target_port: int,
        obfuscation_pipeline: Any | None = None,
    ):
        """
        Initialize bridge client.
        
        Args:
            relay: Relay node to use
            target_host: Final destination host
            target_port: Final destination port
            obfuscation_pipeline: Optional obfuscation pipeline
        """
        self.relay = relay
        self.target_host = target_host
        self.target_port = target_port
        self.obfuscation = obfuscation_pipeline
        
        self.protocol = BridgeProtocol()
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.connected = False
        self.latency_ms: float = float('inf')
        
    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to relay and establish bridge.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful
        """
        try:
            # Create SSL context with obfuscation if available
            if self.obfuscation:
                ssl_ctx = self.obfuscation.get_ssl_context()
            else:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE
            
            # Handle domain fronting
            server_hostname = self.relay.host
            if self.relay.supports_domain_fronting and self.relay.front_domain:
                server_hostname = self.relay.front_domain
                log.info(
                    "Using domain fronting: SNI=%s, Host=%s",
                    server_hostname,
                    self.relay.host,
                )
            
            # Connect to relay
            start_time = time.monotonic()
            
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.relay.host,
                    self.relay.port,
                    ssl=ssl_ctx,
                    server_hostname=server_hostname,
                ),
                timeout=timeout,
            )
            
            # Calculate latency
            self.latency_ms = (time.monotonic() - start_time) * 1000
            
            # Send CONNECT message
            connect_msg = self.protocol.encode_connect(
                self.target_host,
                self.target_port,
                self.relay.auth_token,
            )
            
            if self.obfuscation:
                fragments = self.obfuscation.obfuscate(connect_msg)
                for frag in fragments:
                    self.writer.write(frag)
            else:
                self.writer.write(connect_msg)
                
            await self.writer.drain()
            
            # Wait for response
            response = await self._read_response(timeout)
            
            if response is None:
                log.warning("Bridge connection timeout")
                await self.close()
                return False
                
            self.connected = True
            log.info(
                "Bridge connected via %s (%s) - latency: %.1fms",
                self.relay.id,
                self.relay.country,
                self.latency_ms,
            )
            
            return True
            
        except asyncio.TimeoutError:
            log.warning("Bridge connection timeout to %s", self.relay.host)
        except Exception as exc:
            log.error("Bridge connection error: %s", exc)
            
        return False
    
    async def _read_response(self, timeout: float) -> tuple[int, bytes] | None:
        """Read and decode response from relay."""
        start_time = time.monotonic()
        
        while time.monotonic() - start_time < timeout:
            try:
                data = await asyncio.wait_for(
                    self.reader.read(4096),  # type: ignore
                    timeout=timeout - (time.monotonic() - start_time),
                )
                
                if not data:
                    return None
                    
                # Deobfuscate if needed
                if self.obfuscation:
                    # Collect fragments
                    fragments = [data]
                    # Try to read more fragments
                    try:
                        while True:
                            more = await asyncio.wait_for(
                                self.reader.read(4096),  # type: ignore
                                timeout=0.1,
                            )
                            if not more:
                                break
                            fragments.append(more)
                    except asyncio.TimeoutError:
                        pass
                    
                    data = self.obfuscation.deobfuscate(fragments)
                
                # Decode messages
                messages = self.protocol.feed(data)
                
                for msg_type, payload in messages:
                    if msg_type == BridgeProtocol.MSG_CONNECT:
                        # Connection accepted
                        return (msg_type, payload)
                    elif msg_type == BridgeProtocol.MSG_ERROR:
                        error_code = struct.unpack('>H', payload[:2])[0]
                        error_msg = payload[2:].decode()
                        log.error("Bridge error %d: %s", error_code, error_msg)
                        return None
                        
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                log.error("Error reading bridge response: %s", exc)
                return None
                
        return None
    
    async def send(self, data: bytes) -> int:
        """
        Send data through bridge.
        
        Args:
            data: Data to send
            
        Returns:
            Bytes sent
        """
        if not self.connected or not self.writer:
            raise RuntimeError("Bridge not connected")
            
        # Encode as DATA message
        msg = self.protocol.encode_data(data)
        
        # Obfuscate if enabled
        if self.obfuscation:
            fragments = self.obfuscation.obfuscate(msg)
            total_sent = 0
            for frag in fragments:
                self.writer.write(frag)
                total_sent += len(frag)
            await self.writer.drain()
            return total_sent
        else:
            self.writer.write(msg)
            await self.writer.drain()
            return len(msg)
    
    async def recv(self, max_size: int = 65536) -> bytes | None:
        """
        Receive data from bridge.
        
        Args:
            max_size: Maximum bytes to read
            
        Returns:
            Received data or None if closed
        """
        if not self.connected or not self.reader:
            return None
            
        try:
            data = await self.reader.read(max_size)
            
            if not data:
                return None
                
            # Deobfuscate if enabled
            if self.obfuscation:
                data = self.obfuscation.deobfuscate([data])
            
            # Decode messages
            messages = self.protocol.feed(data)
            
            result = b''
            for msg_type, payload in messages:
                if msg_type == BridgeProtocol.MSG_DATA:
                    result += payload
                elif msg_type == BridgeProtocol.MSG_CLOSE:
                    await self.close()
                    return None
                    
            return result if result else None
            
        except Exception as exc:
            log.error("Bridge recv error: %s", exc)
            await self.close()
            return None
    
    async def ping(self) -> float | None:
        """
        Send ping to measure latency.
        
        Returns:
            Latency in ms or None if failed
        """
        if not self.connected:
            return None
            
        try:
            ping_msg = self.protocol.encode_ping()
            self.writer.write(ping_msg)  # type: ignore
            await self.writer.drain()
            
            start = time.monotonic()
            
            # Wait for pong
            while True:
                data = await self.reader.read(4096)  # type: ignore
                if not data:
                    return None
                    
                messages = self.protocol.feed(data)
                
                for msg_type, payload in messages:
                    if msg_type == BridgeProtocol.MSG_PONG:
                        return (time.monotonic() - start) * 1000
                        
        except Exception as exc:
            log.debug("Bridge ping error: %s", exc)
            return None
    
    async def close(self) -> None:
        """Close bridge connection."""
        self.connected = False
        
        if self.writer:
            try:
                close_msg = self.protocol.encode_close()
                self.writer.write(close_msg)
                await self.writer.drain()
            except Exception:
                pass
                
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
                
        self.writer = None
        self.reader = None


# =============================================================================
# Relay Manager
# =============================================================================


class RelayManager:
    """
    Manages relay nodes and selects optimal routes.
    """
    
    def __init__(self):
        """Initialize relay manager."""
        self.relays: list[RelayNode] = []
        self.selected_relay: RelayNode | None = None
        self._lock = asyncio.Lock()
        
        # Load default relays
        self.relays.extend(PUBLIC_RELAYS)
        self.relays.extend(FRONTING_RELAYS)
        
    def add_relay(self, relay: RelayNode) -> None:
        """Add custom relay node."""
        self.relays.append(relay)
        log.info("Added relay: %s (%s)", relay.id, relay.country)
        
    def remove_relay(self, relay_id: str) -> bool:
        """Remove relay by ID."""
        for i, relay in enumerate(self.relays):
            if relay.id == relay_id:
                del self.relays[i]
                log.info("Removed relay: %s", relay_id)
                return True
        return False
    
    def get_relay(self, relay_id: str) -> RelayNode | None:
        """Get relay by ID."""
        for relay in self.relays:
            if relay.id == relay_id:
                return relay
        return None
    
    async def check_relay_health(
        self,
        relay: RelayNode,
        timeout: float = 5.0,
    ) -> bool:
        """
        Check if relay is healthy.
        
        Args:
            relay: Relay to check
            timeout: Check timeout
            
        Returns:
            True if relay is healthy
        """
        try:
            # Simple TCP connect check
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(relay.host, relay.port),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()
            
            relay.is_online = True
            relay.last_check = time.time()
            return True
            
        except Exception:
            relay.is_online = False
            relay.last_check = time.time()
            return False
    
    async def select_best_relay(
        self,
        preferred_country: str | None = None,
        require_fronting: bool = False,
        require_obfs: bool = True,
    ) -> RelayNode | None:
        """
        Select the best relay based on criteria.
        
        Args:
            preferred_country: Preferred country/region
            require_fronting: Require domain fronting support
            require_obfs: Require obfuscation support
            
        Returns:
            Selected relay node or None
        """
        async with self._lock:
            # Filter relays
            candidates = []
            
            for relay in self.relays:
                # Skip offline relays
                if not relay.is_online:
                    continue
                    
                # Check requirements
                if require_fronting and not relay.supports_domain_fronting:
                    continue
                if require_obfs and not relay.supports_obfs:
                    continue
                    
                candidates.append(relay)
            
            if not candidates:
                # Try to health-check offline relays
                log.info("No online relays, running health checks...")
                for relay in self.relays:
                    if require_fronting and not relay.supports_domain_fronting:
                        continue
                    await self.check_relay_health(relay)
                    if relay.is_online:
                        candidates.append(relay)
                        
            if not candidates:
                return None
                
            # Score candidates
            def score_relay(r: RelayNode) -> float:
                score = 0.0
                
                # Priority bonus
                score += r.priority * 10
                
                # Latency bonus (lower is better)
                if r.latency_ms < float('inf'):
                    score += max(0, 100 - r.latency_ms)
                    
                # Success rate bonus
                score += r.success_rate * 50
                
                # Country preference
                if preferred_country and preferred_country.lower() in r.country.lower():
                    score += 100
                    
                # Recent check bonus
                if time.time() - r.last_check < 60:
                    score += 20
                    
                return score
            
            # Sort by score
            candidates.sort(key=score_relay, reverse=True)
            
            self.selected_relay = candidates[0]
            log.info(
                "Selected relay: %s (%s) - score: %.1f",
                self.selected_relay.id,
                self.selected_relay.country,
                score_relay(self.selected_relay),
            )
            
            return self.selected_relay
    
    def update_relay_stats(
        self,
        relay_id: str,
        latency_ms: float | None = None,
        success: bool | None = None,
    ) -> None:
        """Update relay statistics."""
        relay = self.get_relay(relay_id)
        if not relay:
            return
            
        if latency_ms is not None:
            # Exponential moving average
            alpha = 0.3
            relay.latency_ms = alpha * latency_ms + (1 - alpha) * relay.latency_ms
            
        if success is not None:
            # Update success rate
            alpha = 0.1
            relay.success_rate = alpha * (1.0 if success else 0.0) + (1 - alpha) * relay.success_rate
    
    def get_all_relays(self) -> list[dict[str, Any]]:
        """Get all relays as dictionaries."""
        return [
            {
                'id': r.id,
                'host': r.host,
                'port': r.port,
                'protocol': r.protocol,
                'country': r.country,
                'city': r.city,
                'latency_ms': r.latency_ms if r.latency_ms < float('inf') else None,
                'success_rate': r.success_rate,
                'is_online': r.is_online,
                'supports_obfs': r.supports_obfs,
                'supports_fronting': r.supports_domain_fronting,
                'tags': r.tags,
            }
            for r in self.relays
        ]


# Global relay manager instance
_relay_manager = RelayManager()


def get_relay_manager() -> RelayManager:
    """Get global relay manager instance."""
    return _relay_manager
