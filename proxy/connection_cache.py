"""
Connection Cache for TG WS Proxy.

Provides fast connection caching:
- LRU cache for connections
- Connection pooling with TTL
- Automatic cleanup of expired connections
- Statistics tracking

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Generic, TypeVar

log = logging.getLogger('tg-conn-cache')

T = TypeVar('T')


@dataclass
class CachedConnection(Generic[T]):
    """Cached connection with metadata."""
    value: T
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    ttl: float = 300.0  # 5 minutes default

    @property
    def is_expired(self) -> bool:
        """Check if connection is expired."""
        return (time.time() - self.last_used) > self.ttl

    @property
    def age(self) -> float:
        """Get connection age in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last used time and increment use count."""
        self.last_used = time.time()
        self.use_count += 1


class ConnectionCache(Generic[T]):
    """
    LRU connection cache with TTL support.

    Features:
    - Automatic eviction of expired connections
    - Max size limit
    - Statistics tracking
    - Thread-safe operations
    """

    def __init__(
        self,
        max_size: int = 100,
        default_ttl: float = 300.0,
        cleanup_interval: float = 60.0,
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

        self._cache: OrderedDict[str, CachedConnection[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: asyncio.Task | None = None

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    async def start(self) -> None:
        """Start the cache cleanup task."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        log.info(
            "Connection cache started (max_size: %d, ttl: %.1fs)",
            self.max_size,
            self.default_ttl
        )

    async def stop(self) -> None:
        """Stop the cache cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        log.info("Connection cache stopped")

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired connections."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Cache cleanup error: %s", e)

    async def _cleanup_expired(self) -> None:
        """Remove expired connections."""
        async with self._lock:
            expired_keys = [
                key for key, conn in self._cache.items()
                if conn.is_expired
            ]

            for key in expired_keys:
                del self._cache[key]
                self.expirations += 1

            if expired_keys:
                log.debug("Cleaned up %d expired connections", len(expired_keys))

    async def get(self, key: str) -> T | None:
        """
        Get connection from cache.

        Returns None if not found or expired.
        """
        async with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            conn = self._cache[key]

            if conn.is_expired:
                del self._cache[key]
                self.expirations += 1
                self.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            conn.touch()
            self.hits += 1

            return conn.value

    async def put(
        self,
        key: str,
        value: T,
        ttl: float | None = None,
    ) -> None:
        """
        Put connection into cache.

        If cache is full, evicts least recently used connection.
        """
        async with self._lock:
            # If key exists, remove old entry
            if key in self._cache:
                del self._cache[key]

            # Evict LRU if cache is full
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self.evictions += 1

            # Add new connection
            conn = CachedConnection(
                value=value,
                ttl=ttl if ttl is not None else self.default_ttl,
            )
            self._cache[key] = conn

    async def remove(self, key: str) -> bool:
        """Remove connection from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all connections from cache."""
        async with self._lock:
            self._cache.clear()
            log.debug("Connection cache cleared")

    async def contains(self, key: str) -> bool:
        """Check if key exists in cache (without updating LRU)."""
        async with self._lock:
            return key in self._cache

    async def size(self) -> int:
        """Get current cache size."""
        async with self._lock:
            return len(self._cache)

    def get_statistics(self) -> dict:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0.0

        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate_percent': round(hit_rate, 2),
            'evictions': self.evictions,
            'expirations': self.expirations,
            'default_ttl': self.default_ttl,
        }

    async def get_keys(self) -> list[str]:
        """Get all keys in cache."""
        async with self._lock:
            return list(self._cache.keys())


class ConnectionPool(Generic[T]):
    """
    Connection pool with automatic sizing.

    Similar to ConnectionCache but designed for pooling
    multiple connections to the same endpoint.
    """

    def __init__(
        self,
        endpoint: str,
        min_size: int = 2,
        max_size: int = 10,
        ttl: float = 300.0,
    ):
        self.endpoint = endpoint
        self.min_size = min_size
        self.max_size = max_size
        self.ttl = ttl

        self._connections: list[CachedConnection[T]] = []
        self._lock = asyncio.Lock()
        self._stats = {
            'created': 0,
            'reused': 0,
            'discarded': 0,
        }

    async def acquire(self) -> T | None:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Find available connection
            for conn in self._connections:
                if not conn.is_expired:
                    conn.touch()
                    self._stats['reused'] += 1
                    return conn.value

            # No available connections
            return None

    async def release(self, connection: T) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            # Check if we already have this connection
            for conn in self._connections:
                if conn.value is connection:
                    return  # Already in pool

            # Add new connection if pool is not full
            if len(self._connections) < self.max_size:
                conn = CachedConnection(
                    value=connection,
                    ttl=self.ttl,
                )
                self._connections.append(conn)
                self._stats['created'] += 1

    async def discard(self, connection: T) -> None:
        """Discard a connection from the pool."""
        async with self._lock:
            self._connections = [
                conn for conn in self._connections
                if conn.value is not connection
            ]
            self._stats['discarded'] += 1

    async def cleanup(self) -> int:
        """Remove expired connections. Returns count of removed connections."""
        async with self._lock:
            original_count = len(self._connections)
            self._connections = [
                conn for conn in self._connections
                if not conn.is_expired
            ]
            removed = original_count - len(self._connections)
            return removed

    def get_statistics(self) -> dict:
        """Get pool statistics."""
        return {
            'endpoint': self.endpoint,
            'size': len(self._connections),
            'min_size': self.min_size,
            'max_size': self.max_size,
            'created': self._stats['created'],
            'reused': self._stats['reused'],
            'discarded': self._stats['discarded'],
            'reuse_ratio': round(
                self._stats['reused'] /
                (self._stats['created'] + self._stats['reused']) * 100,
                2
            ) if (self._stats['created'] + self._stats['reused']) > 0 else 0.0,
        }


# Global cache instance
_connection_cache: ConnectionCache | None = None


def get_connection_cache(
    max_size: int = 100,
    ttl: float = 300.0,
) -> ConnectionCache:
    """Get or create global connection cache."""
    global _connection_cache
    if _connection_cache is None:
        _connection_cache = ConnectionCache(max_size=max_size, default_ttl=ttl)
    return _connection_cache


async def start_connection_cache(max_size: int = 100, ttl: float = 300.0) -> None:
    """Start the global connection cache."""
    cache = get_connection_cache(max_size, ttl)
    await cache.start()


async def stop_connection_cache() -> None:
    """Stop the global connection cache."""
    if _connection_cache:
        await _connection_cache.stop()


__all__ = [
    'ConnectionCache',
    'ConnectionPool',
    'CachedConnection',
    'get_connection_cache',
    'start_connection_cache',
    'stop_connection_cache',
]
