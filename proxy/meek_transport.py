"""
Meek Transport for TG WS Proxy.

Implements domain fronting via CDN for advanced censorship circumvention:
- Routes traffic through trusted CDNs (Cloudflare, Google, Amazon)
- Makes traffic appear as normal HTTPS to CDN domains
- Bypasses DPI and IP-based blocking
- Reflection routing through CDN edge servers

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import random
import ssl
import time
from dataclasses import dataclass, field

log = logging.getLogger('tg-ws-meek')


@dataclass
class MeekConfig:
    """Meek transport configuration."""
    # Front domains (trusted CDN domains)
    front_domains: list[str] = field(default_factory=lambda: [
        'www.google.com',
        'www.microsoft.com',
        'www.cloudflare.com',
        'www.amazon.com',
        'cdn.jsdelivr.net',
        'unpkg.com',
    ])

    # Actual bridge address (hidden)
    bridge_host: str = ''
    bridge_port: int = 443

    # CDN-specific paths
    cdn_path: str = '/api/meek'

    # Request parameters
    poll_interval: float = 0.1  # Seconds between polls
    max_poll_size: int = 65536  # Max bytes per poll
    request_timeout: float = 30.0  # HTTP request timeout

    # Obfuscation
    add_random_padding: bool = True
    padding_min: int = 100
    padding_max: int = 500

    # TLS settings
    tls_sni_override: str = ''  # SNI domain (appears in TLS handshake)
    tls_verify: bool = False  # Disable cert verification for proxy

    # Session
    session_duration: float = 300.0  # Max session duration (seconds)
    reconnect_delay: float = 5.0  # Delay before reconnect


class MeekSession:
    """
    Meek session for bidirectional communication.

    Uses long-polling to simulate full-duplex over HTTP.
    """

    def __init__(self, config: MeekConfig):
        """
        Initialize meek session.

        Args:
            config: Meek configuration
        """
        self.config = config
        self.session_id = self._generate_session_id()
        self.created_at = time.monotonic()
        self.last_activity = time.monotonic()

        # Queues for bidirectional communication
        self._send_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._recv_queue: asyncio.Queue[bytes] = asyncio.Queue()

        # Connection state
        self._connected = False
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

        # Stats
        self.bytes_sent = 0
        self.bytes_received = 0
        self.requests_made = 0
        self.bytes_overhead = 0

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        return base64.urlsafe_b64encode(os.urandom(16)).decode('ascii')[:12]

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Establish meek connection.

        Connects to front domain with SNI override to hide actual destination.
        """
        try:
            # Select random front domain
            front_domain = random.choice(self.config.front_domains)

            # Use SNI override if configured
            sni_host = self.config.tls_sni_override or front_domain

            # Create TLS context
            ssl_context = ssl.create_default_context()
            if not self.config.tls_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to front domain
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(
                    front_domain,
                    443,
                    ssl=ssl_context,
                    server_hostname=sni_host
                ),
                timeout=timeout
            )

            self._connected = True
            self.last_activity = time.monotonic()

            log.info("Meek session connected via %s (SNI: %s)",
                    front_domain, sni_host)
            return True

        except asyncio.TimeoutError:
            log.warning("Meek connection timeout")
            return False
        except Exception as e:
            log.error("Meek connection error: %s", e)
            return False

    async def send(self, data: bytes) -> bool:
        """
        Send data via meek transport.

        Encapsulates data in HTTP POST request with domain fronting.
        """
        if not self._connected or not self._writer:
            return False

        try:
            # Build HTTP POST request with domain fronting
            front_domain = random.choice(self.config.front_domains)

            # Add padding for obfuscation
            payload = data
            if self.config.add_random_padding:
                padding_size = random.randint(
                    self.config.padding_min,
                    self.config.padding_max
                )
                padding = os.urandom(padding_size)
                payload = data + b'\x00' + padding
                self.bytes_overhead += padding_size

            # Build HTTP request
            request = self._build_post_request(
                front_domain=front_domain,
                bridge_host=self.config.bridge_host,
                bridge_port=self.config.bridge_port,
                session_id=self.session_id,
                data=payload
            )

            # Send request
            self._writer.write(request)
            await self._writer.drain()

            self.bytes_sent += len(request)
            self.requests_made += 1
            self.last_activity = time.monotonic()

            # Read response
            response = await self._read_response()

            if response:
                # Extract data from response
                received_data = self._parse_response(response)
                if received_data:
                    await self._recv_queue.put(received_data)
                    self.bytes_received += len(received_data)

            return True

        except Exception as e:
            log.error("Meek send error: %s", e)
            self._connected = False
            return False

    async def recv(self) -> bytes | None:
        """
        Receive data from meek transport.

        Uses long-polling to wait for incoming data.
        """
        try:
            # Get data from receive queue
            data = await asyncio.wait_for(
                self._recv_queue.get(),
                timeout=self.config.poll_interval
            )
            return data

        except asyncio.TimeoutError:
            # Poll for new data
            await self._poll()
            return None
        except Exception as e:
            log.error("Meek recv error: %s", e)
            return None

    async def _poll(self) -> None:
        """Poll server for incoming data."""
        if not self._connected or not self._writer:
            return

        try:
            front_domain = random.choice(self.config.front_domains)

            # Build GET request for polling
            request = self._build_get_request(
                front_domain=front_domain,
                session_id=self.session_id
            )

            self._writer.write(request)
            await self._writer.drain()

            self.requests_made += 1

            # Read response
            response = await self._read_response()

            if response:
                received_data = self._parse_response(response)
                if received_data:
                    await self._recv_queue.put(received_data)
                    self.bytes_received += len(received_data)

        except Exception as e:
            log.debug("Meek poll error: %s", e)

    def _build_post_request(
        self,
        front_domain: str,
        bridge_host: str,
        bridge_port: int,
        session_id: str,
        data: bytes
    ) -> bytes:
        """Build HTTP POST request with domain fronting headers."""
        # Encode data
        encoded_data = base64.b64encode(data).decode('ascii')

        # Build request line
        request = f'POST {self.config.cdn_path}?sid={session_id} HTTP/1.1\r\n'

        # Build headers with domain fronting
        headers = [
            f'Host: {front_domain}',  # Front domain (visible to DPI)
            f'X-Forwarded-Host: {bridge_host}',  # Actual bridge (hidden in HTTPS)
            f'X-Forwarded-Port: {bridge_port}',
            f'X-Session-ID: {session_id}',
            'Content-Type: application/octet-stream',
            f'Content-Length: {len(encoded_data)}',
            'Connection: keep-alive',
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept: */*',
            'Accept-Encoding: gzip, deflate',
        ]

        # Add custom header for bridge routing (encrypted in HTTPS)
        bridge_header = base64.b64encode(
            f'{bridge_host}:{bridge_port}'.encode()
        ).decode('ascii')
        headers.append(f'X-Bridge: {bridge_header}')

        request += '\r\n'.join(headers)
        request += '\r\n\r\n'
        request += encoded_data

        return request.encode('utf-8')

    def _build_get_request(
        self,
        front_domain: str,
        session_id: str
    ) -> bytes:
        """Build HTTP GET request for long-polling."""
        request = f'GET {self.config.cdn_path}/poll?sid={session_id} HTTP/1.1\r\n'

        headers = [
            f'Host: {front_domain}',
            f'X-Session-ID: {session_id}',
            'Connection: keep-alive',
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept: */*',
        ]

        request += '\r\n'.join(headers)
        request += '\r\n\r\n'

        return request.encode('utf-8')

    async def _read_response(self) -> bytes | None:
        """Read HTTP response."""
        if not self._reader:
            return None

        try:
            # Read status line
            status_line = await self._reader.readline()
            if not status_line:
                return None

            # Read headers
            headers = {}
            while True:
                line = await self._reader.readline()
                if line == b'\r\n':
                    break
                if b':' in line:
                    key, value = line.decode('utf-8').split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Read body
            body = b''
            if 'content-length' in headers:
                length = int(headers['content-length'])
                body = await self._reader.readexactly(length)
            elif headers.get('transfer-encoding') == 'chunked':
                # Read chunked encoding
                while True:
                    chunk_size_line = await self._reader.readline()
                    chunk_size = int(chunk_size_line.strip(), 16)
                    if chunk_size == 0:
                        break
                    chunk = await self._reader.readexactly(chunk_size)
                    body += chunk
                    await self._reader.readline()  # CRLF after chunk

            return status_line + body

        except Exception as e:
            log.debug("Failed to read response: %s", e)
            return None

    def _parse_response(self, response: bytes) -> bytes | None:
        """Parse HTTP response and extract data."""
        try:
            # Find body start
            header_end = response.find(b'\r\n\r\n')
            if header_end == -1:
                return None

            body = response[header_end + 4:]

            if not body:
                return None

            # Decode base64
            data = base64.b64decode(body)

            # Remove padding if present
            if b'\x00' in data:
                null_idx = data.rfind(b'\x00')
                if null_idx > 0:
                    data = data[:null_idx]

            return data

        except Exception as e:
            log.debug("Failed to parse response: %s", e)
            return None

    async def close(self) -> None:
        """Close meek session."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

            self._writer = None
            self._reader = None
            self._connected = False

        log.info("Meek session closed")

    def get_stats(self) -> dict:
        """Get session statistics."""
        return {
            'session_id': self.session_id,
            'connected': self._connected,
            'duration': time.monotonic() - self.created_at,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'bytes_overhead': self.bytes_overhead,
            'requests_made': self.requests_made,
            'last_activity': time.monotonic() - self.last_activity,
        }


class MeekTransport:
    """
    Meek Transport for Telegram proxy.

    Routes traffic through CDN with domain fronting to bypass censorship.
    """

    def __init__(
        self,
        bridge_host: str,
        bridge_port: int = 443,
        front_domains: list[str] | None = None,
        use_cdn: str = 'cloudflare',  # cloudflare, google, amazon
    ):
        """
        Initialize meek transport.

        Args:
            bridge_host: Actual bridge server host (hidden)
            bridge_port: Bridge server port
            front_domains: CDN front domains
            use_cdn: Preset CDN configuration
        """
        self.bridge_host = bridge_host
        self.bridge_port = bridge_port

        # Configure front domains based on CDN
        if front_domains:
            self.front_domains = front_domains
        else:
            self.front_domains = self._get_cdn_domains(use_cdn)

        self.config = MeekConfig(
            front_domains=self.front_domains,
            bridge_host=bridge_host,
            bridge_port=bridge_port,
        )

        self._session: MeekSession | None = None
        self._connected = False

        # Stats
        self.sessions_created = 0
        self.bytes_sent = 0
        self.bytes_received = 0

    def _get_cdn_domains(self, cdn: str) -> list[str]:
        """Get front domains for specific CDN."""
        cdn_domains = {
            'cloudflare': [
                'www.cloudflare.com',
                'cdn.cloudflare.com',
                'cdnjs.cloudflare.com',
            ],
            'google': [
                'www.google.com',
                'www.gstatic.com',
                'fonts.googleapis.com',
                'ajax.googleapis.com',
            ],
            'amazon': [
                'www.amazon.com',
                'cdn.amazon.com',
                'cloudfront.net',
            ],
            'microsoft': [
                'www.microsoft.com',
                'ajax.aspnetcdn.com',
                'cdnjs.cloudflare.com',
            ],
        }
        return cdn_domains.get(cdn, cdn_domains['cloudflare'])

    async def connect(self, timeout: float = 10.0) -> bool:
        """Establish meek connection."""
        self._session = MeekSession(self.config)

        if await self._session.connect(timeout=timeout):
            self._connected = True
            self.sessions_created += 1
            log.info("Meek transport connected to %s:%d via CDN",
                    self.bridge_host, self.bridge_port)
            return True

        return False

    async def send(self, data: bytes) -> bool:
        """Send data via meek transport."""
        if not self._session:
            return False

        success = await self._session.send(data)

        if success:
            self.bytes_sent += len(data)

        return success

    async def recv(self) -> bytes | None:
        """Receive data from meek transport."""
        if not self._session:
            return None

        return await self._session.recv()

    async def close(self) -> None:
        """Close meek transport."""
        if self._session:
            await self._session.close()
            self._session = None
            self._connected = False

    def get_stats(self) -> dict:
        """Get transport statistics."""
        session_stats = self._session.get_stats() if self._session else {}

        return {
            'connected': self._connected,
            'bridge': f"{self.bridge_host}:{self.bridge_port}",
            'front_domains': self.front_domains,
            'sessions_created': self.sessions_created,
            'bytes_sent': self.bytes_sent,
            'bytes_received': self.bytes_received,
            'current_session': session_stats,
        }


async def create_meek_transport(
    bridge_host: str,
    bridge_port: int = 443,
    use_cdn: str = 'cloudflare',
    timeout: float = 10.0
) -> MeekTransport | None:
    """
    Create meek transport with specified CDN.

    Args:
        bridge_host: Bridge server host
        bridge_port: Bridge server port
        use_cdn: CDN provider to use
        timeout: Connection timeout

    Returns:
        MeekTransport instance or None
    """
    transport = MeekTransport(
        bridge_host=bridge_host,
        bridge_port=bridge_port,
        use_cdn=use_cdn
    )

    if await transport.connect(timeout=timeout):
        return transport

    return None


def check_meek_availability() -> dict:
    """
    Check availability of meek front domains.

    Returns:
        Dictionary with availability information
    """
    import socket

    results = {}
    cdn_domains = [
        'www.cloudflare.com',
        'www.google.com',
        'www.microsoft.com',
        'www.amazon.com',
    ]

    for domain in cdn_domains:
        try:
            # Try to resolve
            socket.gethostbyname(domain)
            results[domain] = {'available': True, 'error': None}
        except socket.gaierror as e:
            results[domain] = {'available': False, 'error': str(e)}

    return results
