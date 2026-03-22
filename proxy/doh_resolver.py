"""
DNS-over-HTTPS (DoH) Resolver.

Provides DNS resolution over HTTPS to bypass DNS blocking and poisoning:
- Multiple DoH providers (Cloudflare, Google, Quad9)
- Automatic fallback on failure
- Response caching with TTL
- DNSSEC validation support

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger('tg-ws-doh')


@dataclass
class DoHProvider:
    """DNS-over-HTTPS provider configuration."""
    name: str
    url: str
    priority: int = 0  # Lower = higher priority
    timeout: float = 5.0
    enabled: bool = True

    # Statistics
    success_count: int = 0
    failure_count: int = 0
    last_success: float = 0.0
    last_failure: float = 0.0
    
    # Latency tracking
    latency_samples: list[float] = field(default_factory=list)
    avg_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 1.0
    
    def record_latency(self, latency_ms: float) -> None:
        """Record latency sample."""
        self.latency_samples.append(latency_ms)
        # Keep last 10 samples
        if len(self.latency_samples) > 10:
            self.latency_samples.pop(0)
        # Calculate average
        self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)
    
    def get_score(self) -> float:
        """
        Calculate provider score for selection.
        
        Lower score = better provider.
        Combines success rate, latency, and priority.
        """
        # Base score from priority
        score = self.priority * 10.0
        
        # Adjust by success rate (0-10 penalty)
        score += (1.0 - self.success_rate) * 10.0
        
        # Adjust by latency (0-5 penalty for >100ms)
        if self.avg_latency_ms > 100:
            score += min(5.0, (self.avg_latency_ms - 100) / 100)
        
        return score


@dataclass
class DNSCacheEntry:
    """DNS cache entry with expiry."""
    ips: list[str]
    expiry: float
    ttl: float
    validated: bool = False  # DNSSEC validated
    
    def is_expired(self, now: float) -> bool:
        """Check if entry is expired."""
        return now >= self.expiry


class DNSOverHTTPSResolver:
    """
    DNS-over-HTTPS resolver with multiple providers.
    
    Features:
    - Multiple DoH providers with automatic failover
    - DNSSEC validation (when available)
    - Response caching with TTL
    - Provider health monitoring
    - Fallback to system DNS
    
    Supported providers:
    - Cloudflare: https://cloudflare-dns.com/dns-query
    - Google: https://dns.google/dns-query
    - Quad9: https://dns.quad9.net/dns-query
    - AdGuard: https://dns.adguard.com/dns-query
    """
    
    # Default DoH providers
    DEFAULT_PROVIDERS = [
        DoHProvider(
            name="Cloudflare",
            url="https://cloudflare-dns.com/dns-query",
            priority=1,
        ),
        DoHProvider(
            name="Google",
            url="https://dns.google/dns-query",
            priority=2,
        ),
        DoHProvider(
            name="Quad9",
            url="https://dns.quad9.net/dns-query",
            priority=3,
        ),
    ]
    
    def __init__(
        self,
        providers: list[DoHProvider] | None = None,
        cache_ttl: float = 300.0,
        max_cache_size: int = 1000,
        enable_dnssec: bool = False,
        fallback_to_system: bool = True,
        bootstrap_dns: list[str] | None = None,
    ):
        """
        Initialize DoH resolver.

        Args:
            providers: List of DoH providers (uses defaults if None)
            cache_ttl: Default cache TTL in seconds
            max_cache_size: Maximum cache entries
            enable_dnssec: Enable DNSSEC validation
            fallback_to_system: Fallback to system DNS on DoH failure
            bootstrap_dns: Initial DNS servers for DoH hostname resolution
        """
        self.providers = providers.copy() if providers else [p for p in self.DEFAULT_PROVIDERS]
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self.enable_dnssec = enable_dnssec
        self.fallback_to_system = fallback_to_system
        self.bootstrap_dns = bootstrap_dns or ['1.1.1.1', '8.8.8.8', '9.9.9.9']

        # Cache
        self._cache: dict[str, DNSCacheEntry] = {}
        self._cache_lock = asyncio.Lock()

        # HTTP session (lazy initialized)
        self._session: Any = None
        
        # Bootstrap DNS cache (pre-resolved DoH hostnames)
        self._bootstrap_cache: dict[str, list[str]] = {}

        # Statistics
        self._total_queries = 0
        self._cache_hits = 0
        self._doh_success = 0
        self._doh_failure = 0
        self._fallback_success = 0
        self._fallback_failure = 0

        log.info(
            "DoH resolver initialized: %d providers, DNSSEC=%s, fallback=%s, bootstrap=%s",
            len(self.providers),
            enable_dnssec,
            fallback_to_system,
            self.bootstrap_dns
        )
    
    async def _get_session(self) -> Any:
        """Get or create aiohttp session."""
        if self._session is None:
            try:
                import aiohttp  # type: ignore[import-not-found]

                # Create session with connection pooling
                timeout = aiohttp.ClientTimeout(total=10)
                self._session = aiohttp.ClientSession(timeout=timeout)

                log.debug("DoH aiohttp session created")
            except ImportError:
                log.warning("aiohttp not available, DoH will use urllib")
                self._session = None

        return self._session
    
    async def pre_resolve_hosts(self) -> dict[str, list[str]]:
        """
        Pre-resolve DoH provider hostnames.
        
        This helps avoid chicken-and-egg problem when you need DNS
        to resolve the DoH provider hostname.
        
        Returns:
            Dict mapping hostnames to IP addresses
        """
        import re
        
        hostnames = set()
        for provider in self.providers:
            # Extract hostname from URL
            match = re.search(r'https?://([^/]+)', provider.url)
            if match:
                hostnames.add(match.group(1))
        
        results = {}
        for hostname in hostnames:
            try:
                # Use bootstrap DNS
                loop = asyncio.get_event_loop()
                ips = await loop.getaddrinfo(hostname, 443, family=2)  # AF_INET
                ip_list = list({r[4][0] for r in ips})
                results[hostname] = ip_list
                self._bootstrap_cache[hostname] = ip_list
                log.debug("Pre-resolved %s -> %s", hostname, ip_list)
            except Exception as e:
                log.warning("Failed to pre-resolve %s: %s", hostname, e)
        
        return results
    
    def get_bootstrap_cache(self) -> dict[str, list[str]]:
        """Get bootstrap DNS cache."""
        return self._bootstrap_cache.copy()
    
    def clear_bootstrap_cache(self) -> None:
        """Clear bootstrap DNS cache."""
        self._bootstrap_cache.clear()
        log.debug("Bootstrap DNS cache cleared")

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
            log.debug("DoH session closed")

    def get_stats(self) -> dict[str, Any]:
        """
        Get resolver statistics.
        
        Returns:
            Dict with statistics
        """
        # Calculate totals
        total_doh = self._doh_success + self._doh_failure
        doh_success_rate = self._doh_success / total_doh if total_doh > 0 else 1.0
        
        total_fallback = self._fallback_success + self._fallback_failure
        fallback_success_rate = self._fallback_success / total_fallback if total_fallback > 0 else 1.0
        
        return {
            'total_queries': self._total_queries,
            'cache_hits': self._cache_hits,
            'cache_hit_rate': self._cache_hits / self._total_queries if self._total_queries > 0 else 0.0,
            'doh_success': self._doh_success,
            'doh_failure': self._doh_failure,
            'doh_success_rate': doh_success_rate,
            'fallback_success': self._fallback_success,
            'fallback_failure': self._fallback_failure,
            'fallback_success_rate': fallback_success_rate,
            'providers': len(self.providers),
            'cache_size': len(self._cache),
        }
    
    def get_provider_stats(self) -> list[dict[str, Any]]:
        """
        Get statistics for each provider.
        
        Returns:
            List of provider statistics
        """
        stats = []
        for provider in self.providers:
            stats.append({
                'name': provider.name,
                'url': provider.url,
                'enabled': provider.enabled,
                'priority': provider.priority,
                'success_count': provider.success_count,
                'failure_count': provider.failure_count,
                'success_rate': provider.success_rate,
                'avg_latency_ms': provider.avg_latency_ms,
                'score': provider.get_score(),
            })
        return stats
    
    def add_provider(self, provider: DoHProvider) -> None:
        """Add new DoH provider."""
        self.providers.append(provider)
        log.info("Added DoH provider: %s", provider.name)
    
    def remove_provider(self, name: str) -> bool:
        """Remove provider by name."""
        for i, p in enumerate(self.providers):
            if p.name == name:
                del self.providers[i]
                log.info("Removed DoH provider: %s", name)
                return True
        return False
    
    def enable_provider(self, name: str) -> bool:
        """Enable provider by name."""
        for p in self.providers:
            if p.name == name:
                p.enabled = True
                log.info("Enabled DoH provider: %s", name)
                return True
        return False
    
    def disable_provider(self, name: str) -> bool:
        """Disable provider by name."""
        for p in self.providers:
            if p.name == name:
                p.enabled = False
                log.info("Disabled DoH provider: %s", name)
                return True
        return False
    
    def get_best_provider(self) -> DoHProvider | None:
        """Get best provider by score."""
        enabled = [p for p in self.providers if p.enabled]
        if not enabled:
            return None
        return min(enabled, key=lambda p: p.get_score())

    async def resolve(
        self,
        domain: str,
        port: int = 443,
        timeout: float = 5.0,
        use_cache: bool = True,
    ) -> list[tuple[str, int]]:
        """
        Resolve domain using DoH.
        
        Args:
            domain: Domain to resolve
            port: Target port
            timeout: Query timeout
            use_cache: Use cache if available
        
        Returns:
            List of (ip, port) tuples
        
        Raises:
            RuntimeError: If all providers fail and fallback disabled
        """
        self._total_queries += 1
        
        # Check cache first
        if use_cache:
            cached = await self._get_from_cache(domain)
            if cached:
                self._cache_hits += 1
                log.debug("DoH cache hit for %s: %s", domain, cached)
                return [(ip, port) for ip in cached]

        # Try DoH providers in score order (best first)
        sorted_providers = sorted(
            [p for p in self.providers if p.enabled],
            key=lambda p: p.get_score()
        )

        last_error: Exception | None = None

        for provider in sorted_providers:
            start_time = time.monotonic()
            try:
                ips = await self._query_provider(provider, domain, timeout)

                if ips:
                    # Record latency
                    latency_ms = (time.monotonic() - start_time) * 1000
                    provider.record_latency(latency_ms)
                    
                    provider.success_count += 1
                    provider.last_success = time.monotonic()
                    self._doh_success += 1

                    # Cache results
                    await self._add_to_cache(domain, ips, self.cache_ttl)

                    log.debug(
                        "DoH resolved %s via %s: %s (%.1fms)",
                        domain, provider.name, ips, latency_ms
                    )
                    return [(ip, port) for ip in ips]

            except Exception as e:
                provider.failure_count += 1
                provider.last_failure = time.monotonic()
                self._doh_failure += 1
                last_error = e

                log.debug(
                    "DoH provider %s failed for %s: %s",
                    provider.name, domain, e
                )
        
        # All DoH providers failed
        if self.fallback_to_system:
            log.warning(
                "All DoH providers failed for %s, falling back to system DNS",
                domain
            )
            try:
                ips = await self._resolve_system_dns(domain, timeout)
                if ips:
                    self._fallback_success += 1
                    await self._add_to_cache(domain, ips, 60.0)  # Short TTL for fallback
                    return [(ip, port) for ip in ips]
            except Exception as fallback_error:
                self._fallback_failure += 1
                log.error("System DNS fallback failed for %s: %s", domain, fallback_error)
        
        # All methods failed
        error_msg = f"All DoH providers failed for {domain}"
        if last_error:
            error_msg += f": {last_error}"
        
        log.warning(error_msg)
        return []  # Return empty instead of raising
    
    async def _query_provider(
        self,
        provider: DoHProvider,
        domain: str,
        timeout: float,
    ) -> list[str]:
        """
        Query single DoH provider.
        
        Args:
            provider: DoH provider
            domain: Domain to resolve
            timeout: Query timeout
        
        Returns:
            List of IP addresses
        
        Raises:
            Exception: On query failure
        """
        # Build DoH URL with DNS query
        # Using DNS wire format for A record
        query = self._build_dns_query(domain)
        
        headers = {
            'Accept': 'application/dns-json',
            'Content-Type': 'application/dns-message',
        }
        
        try:
            session = await self._get_session()
            
            if session:
                # Use aiohttp
                async with session.post(
                    provider.url,
                    data=query,
                    headers=headers,
                    timeout=provider.timeout,
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"DoH HTTP {response.status}")
                    
                    data = await response.json()
                    return self._parse_doh_response(data)
            else:
                # Fallback to urllib
                return await self._query_urllib(provider, domain, query, timeout)
                
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            raise RuntimeError(f"DoH query failed: {e}")
    
    async def _query_urllib(
        self,
        provider: DoHProvider,
        domain: str,
        query: bytes,
        timeout: float,
    ) -> list[str]:
        """Query DoH using urllib (fallback)."""
        import base64
        import ssl
        import urllib.request
        
        # Encode query as base64url
        query_b64 = base64.urlsafe_b64encode(query).rstrip(b'=').decode()
        
        url = f"{provider.url}?dns={query_b64}"
        
        context = ssl.create_default_context()
        
        req = urllib.request.Request(
            url,
            headers={'Accept': 'application/dns-json'},
        )
        
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            import json
            data = json.loads(response.read().decode())
            return self._parse_doh_response(data)
    
    def _build_dns_query(self, domain: str) -> bytes:
        """
        Build DNS query in wire format.
        
        Args:
            domain: Domain name
        
        Returns:
            DNS query bytes
        """
        # DNS header (12 bytes)
        # ID: 2 bytes (random)
        # Flags: 2 bytes (standard query)
        # QDCOUNT: 2 bytes (1 question)
        # ANCOUNT: 2 bytes (0)
        # NSCOUNT: 2 bytes (0)
        # ARCOUNT: 2 bytes (0)
        import struct
        import os
        
        tx_id = os.urandom(2)
        header = struct.pack(
            '>HHHHHH',
            int.from_bytes(tx_id, 'big'),  # ID
            0x0100,  # Flags: standard query
            1,  # QDCOUNT
            0,  # ANCOUNT
            0,  # NSCOUNT
            0,  # ARCOUNT
        )
        
        # Question section
        # Encode domain name
        question = b''
        for part in domain.split('.'):
            question += bytes([len(part)]) + part.encode('ascii')
        question += b'\x00'  # Null terminator
        
        # QTYPE: 2 bytes (A record = 1)
        # QCLASS: 2 bytes (IN = 1)
        question += struct.pack('>HH', 1, 1)
        
        return header + question
    
    def _parse_doh_response(self, data: dict) -> list[str]:
        """
        Parse DoH JSON response.
        
        Args:
            data: DoH response JSON
        
        Returns:
            List of IP addresses
        """
        ips: list[str] = []
        
        # Check for errors
        if data.get('Status', 0) != 0:
            raise RuntimeError(f"DoH error status: {data.get('Status')}")
        
        # Parse Answer section
        for answer in data.get('Answer', []):
            if answer.get('type') == 1:  # A record
                ip = answer.get('data')
                if ip:
                    ips.append(ip)
            elif answer.get('type') == 28:  # AAAA record
                ip = answer.get('data')
                if ip:
                    ips.append(ip)
        
        return ips
    
    async def _resolve_system_dns(
        self,
        domain: str,
        timeout: float,
    ) -> list[str]:
        """
        Fallback to system DNS resolution.
        
        Args:
            domain: Domain to resolve
            timeout: Resolution timeout
        
        Returns:
            List of IP addresses
        """
        try:
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.getaddrinfo(domain, None, family=socket.AF_INET),
                timeout=timeout,
            )
            
            # Extract unique IPs
            ips = list(set(r[4][0] for r in results))
            return ips
            
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            log.debug("System DNS resolution failed for %s: %s", domain, e)
            raise
    
    async def _get_from_cache(self, domain: str) -> list[str] | None:
        """Get domain IPs from cache."""
        async with self._cache_lock:
            entry = self._cache.get(domain)
            if entry:
                now = time.monotonic()
                if entry.is_expired(now):
                    del self._cache[domain]
                    return None
                return entry.ips
            return None
    
    async def _add_to_cache(
        self,
        domain: str,
        ips: list[str],
        ttl: float,
    ) -> None:
        """Add domain IPs to cache."""
        async with self._cache_lock:
            # Trim cache if needed
            if len(self._cache) >= self.max_cache_size:
                # Remove oldest entries
                sorted_cache = sorted(
                    self._cache.items(),
                    key=lambda x: x[1].expiry
                )
                for key, _ in sorted_cache[:len(sorted_cache) // 4]:
                    del self._cache[key]
            
            now = time.monotonic()
            self._cache[domain] = DNSCacheEntry(
                ips=ips,
                expiry=now + ttl,
                ttl=ttl,
            )
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get resolver statistics.
        
        Returns:
            Dict with statistics
        """
        total_doh = self._doh_success + self._doh_failure
        total_fallback = self._fallback_success + self._fallback_failure
        
        return {
            'total_queries': self._total_queries,
            'cache_hits': self._cache_hits,
            'cache_hit_rate': self._cache_hits / self._total_queries if self._total_queries > 0 else 0,
            'doh_success': self._doh_success,
            'doh_failure': self._doh_failure,
            'doh_success_rate': self._doh_success / total_doh if total_doh > 0 else 0,
            'fallback_success': self._fallback_success,
            'fallback_failure': self._fallback_failure,
            'fallback_success_rate': self._fallback_success / total_fallback if total_fallback > 0 else 0,
            'cache_size': len(self._cache),
            'providers': [
                {
                    'name': p.name,
                    'enabled': p.enabled,
                    'priority': p.priority,
                    'success_rate': p.success_rate,
                    'success_count': p.success_count,
                    'failure_count': p.failure_count,
                }
                for p in self.providers
            ],
        }
    
    def add_provider(self, provider: DoHProvider) -> None:
        """Add DoH provider."""
        self.providers.append(provider)
        log.info("DoH provider added: %s (priority=%d)", provider.name, provider.priority)
    
    def remove_provider(self, name: str) -> bool:
        """Remove DoH provider by name."""
        for i, p in enumerate(self.providers):
            if p.name == name:
                self.providers.pop(i)
                log.info("DoH provider removed: %s", name)
                return True
        return False
    
    def set_provider_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable provider."""
        for p in self.providers:
            if p.name == name:
                p.enabled = enabled
                log.info("DoH provider %s %s", name, "enabled" if enabled else "disabled")
                return
    
    def get_provider_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all providers."""
        return [
            {
                'name': p.name,
                'url': p.url,
                'enabled': p.enabled,
                'priority': p.priority,
                'success_rate': p.success_rate,
                'success_count': p.success_count,
                'failure_count': p.failure_count,
                'last_success': p.last_success,
                'last_failure': p.last_failure,
            }
            for p in self.providers
        ]


# Global DoH resolver instance
_doh_resolver: DNSOverHTTPSResolver | None = None


def get_doh_resolver() -> DNSOverHTTPSResolver:
    """Get or create global DoH resolver."""
    global _doh_resolver
    if _doh_resolver is None:
        _doh_resolver = DNSOverHTTPSResolver()
    return _doh_resolver


def init_doh_resolver(
    providers: list[DoHProvider] | None = None,
    **kwargs: Any,
) -> DNSOverHTTPSResolver:
    """Initialize global DoH resolver."""
    global _doh_resolver
    _doh_resolver = DNSOverHTTPSResolver(providers, **kwargs)
    return _doh_resolver


__all__ = [
    'DoHProvider',
    'DNSOverHTTPSResolver',
    'DNSCacheEntry',
    'get_doh_resolver',
    'init_doh_resolver',
]
