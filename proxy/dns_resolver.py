"""
DNS Resolver with caching and optimization.

Provides async DNS resolution with TTL-based caching, metrics tracking,
and fallback mechanisms.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any

log = logging.getLogger('tg-ws-dns')


@dataclass
class DNSCacheEntry:
    """DNS cache entry with expiry."""
    ips: list[str]
    expiry: float
    hits: int = 0

    def is_expired(self, now: float) -> bool:
        """Check if entry is expired."""
        return now >= self.expiry


@dataclass
class DNSMetrics:
    """DNS resolver metrics."""
    total_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    failed_queries: int = 0
    total_resolution_time: float = 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    @property
    def avg_resolution_time(self) -> float:
        """Calculate average resolution time."""
        return self.total_resolution_time / self.total_queries if self.total_queries > 0 else 0.0


class DNSResolver:
    """
    Async DNS resolver with caching.

    Features:
    - TTL-based caching
    - Metrics tracking
    - aiodns support (optional)
    - Thread-safe operations
    """

    def __init__(
        self,
        ttl: float = 300.0,
        max_cache_size: int = 1000,
        enable_metrics: bool = True
    ):
        """
        Initialize DNS resolver.

        Args:
            ttl: Cache TTL in seconds
            max_cache_size: Maximum cache entries
            enable_metrics: Enable metrics tracking
        """
        self.ttl = ttl
        self.max_cache_size = max_cache_size
        self.enable_metrics = enable_metrics

        self._cache: dict[str, DNSCacheEntry] = {}
        self._lock = asyncio.Lock()
        self._metrics = DNSMetrics()
        self._aiodns_resolver: Any = None

        # Try to initialize aiodns
        try:
            import aiodns
            self._aiodns_resolver = aiodns.DNSResolver()
            log.debug("aiodns resolver initialized")
        except ImportError:
            log.debug("aiodns not available, using asyncio.getaddrinfo()")

    async def resolve(
        self,
        domain: str,
        port: int = 443,
        timeout: float = 5.0,
        use_cache: bool = True
    ) -> list[tuple[str, int]]:
        """
        Resolve domain to IP addresses.

        Args:
            domain: Domain name to resolve
            port: Target port
            timeout: Resolution timeout
            use_cache: Whether to use cache

        Returns:
            List of (ip, port) tuples
        """
        if self.enable_metrics:
            self._metrics.total_queries += 1

        # Check cache first
        if use_cache:
            cached = await self._get_from_cache(domain)
            if cached:
                if self.enable_metrics:
                    self._metrics.cache_hits += 1
                return [(ip, port) for ip in cached]

        if self.enable_metrics:
            self._metrics.cache_misses += 1

        # Resolve from DNS
        start_time = time.monotonic()
        try:
            ips = await self._resolve_direct(domain, timeout)
            
            if self.enable_metrics:
                self._metrics.total_resolution_time += time.monotonic() - start_time

            if ips and use_cache:
                await self._add_to_cache(domain, ips)

            return [(ip, port) for ip in ips]

        except Exception as e:
            if self.enable_metrics:
                self._metrics.failed_queries += 1
            log.debug("DNS resolution failed for %s: %s", domain, e)
            return []

    async def _get_from_cache(self, domain: str) -> list[str] | None:
        """
        Get IPs from cache if not expired.

        Args:
            domain: Domain name

        Returns:
            List of IPs or None if not cached/expired
        """
        now = time.monotonic()

        async with self._lock:
            entry = self._cache.get(domain)
            if entry and not entry.is_expired(now):
                entry.hits += 1
                log.debug("DNS cache hit for %s: %s", domain, entry.ips)
                return entry.ips

            # Remove expired entry
            if entry:
                del self._cache[domain]

        return None

    async def _add_to_cache(self, domain: str, ips: list[str]) -> None:
        """
        Add IPs to cache.

        Args:
            domain: Domain name
            ips: List of IP addresses
        """
        now = time.monotonic()
        expiry = now + self.ttl

        async with self._lock:
            # Evict oldest entry if cache is full
            if len(self._cache) >= self.max_cache_size:
                oldest_domain = min(
                    self._cache.keys(),
                    key=lambda d: self._cache[d].expiry
                )
                del self._cache[oldest_domain]
                log.debug("DNS cache evicted: %s", oldest_domain)

            self._cache[domain] = DNSCacheEntry(ips=ips, expiry=expiry)
            log.debug("DNS cached %s -> %s (TTL: %ds)", domain, ips, int(self.ttl))

    async def _resolve_direct(self, domain: str, timeout: float) -> list[str]:
        """
        Resolve domain directly (no cache).

        Args:
            domain: Domain name
            timeout: Resolution timeout

        Returns:
            List of IP addresses
        """
        if self._aiodns_resolver:
            # Use aiodns for faster resolution
            try:
                result = await asyncio.wait_for(
                    self._aiodns_resolver.query(domain, 'A'),
                    timeout=timeout
                )
                return [r.host for r in result]
            except Exception as e:
                log.debug("aiodns resolution failed for %s: %s", domain, e)
                # Fallback to getaddrinfo
                pass

        # Use asyncio.getaddrinfo()
        loop = asyncio.get_event_loop()
        try:
            results = await asyncio.wait_for(
                loop.getaddrinfo(
                    domain, None,
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM
                ),
                timeout=timeout
            )
            ips = list({r[4][0] for r in results})
            log.debug("DNS resolved %s -> %s", domain, ips)
            return ips
        except Exception as e:
            log.debug("getaddrinfo failed for %s: %s", domain, e)
            return []

    async def clear_cache(self) -> None:
        """Clear DNS cache."""
        async with self._lock:
            self._cache.clear()
        log.debug("DNS cache cleared")

    async def get_cache_info(self) -> dict[str, Any]:
        """
        Get cache information.

        Returns:
            Dictionary with cache stats
        """
        now = time.monotonic()

        async with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for entry in self._cache.values()
                if entry.is_expired(now)
            )
            total_hits = sum(entry.hits for entry in self._cache.values())

            return {
                'total_entries': total_entries,
                'expired_entries': expired_entries,
                'total_hits': total_hits,
                'max_size': self.max_cache_size,
                'ttl_seconds': self.ttl,
            }

    def get_metrics(self) -> dict[str, Any]:
        """
        Get resolver metrics.

        Returns:
            Dictionary with metrics
        """
        if not self.enable_metrics:
            return {}

        return {
            'total_queries': self._metrics.total_queries,
            'cache_hits': self._metrics.cache_hits,
            'cache_misses': self._metrics.cache_misses,
            'failed_queries': self._metrics.failed_queries,
            'cache_hit_rate': self._metrics.cache_hit_rate,
            'avg_resolution_time_ms': self._metrics.avg_resolution_time * 1000,
        }

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        now = time.monotonic()
        removed = 0

        async with self._lock:
            expired_domains = [
                domain for domain, entry in self._cache.items()
                if entry.is_expired(now)
            ]
            for domain in expired_domains:
                del self._cache[domain]
                removed += 1

        if removed > 0:
            log.debug("DNS cache cleanup: removed %d expired entries", removed)

        return removed


# Global resolver instance
_global_resolver: DNSResolver | None = None


def get_resolver() -> DNSResolver:
    """
    Get global DNS resolver instance.

    Returns:
        Global DNSResolver instance
    """
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = DNSResolver()
    return _global_resolver


async def resolve_domain(
    domain: str,
    port: int = 443,
    timeout: float = 5.0
) -> list[tuple[str, int]]:
    """
    Resolve domain using global resolver.

    Args:
        domain: Domain name
        port: Target port
        timeout: Resolution timeout

    Returns:
        List of (ip, port) tuples
    """
    resolver = get_resolver()
    return await resolver.resolve(domain, port, timeout)
