"""Tests for connection_cache.py module."""

from __future__ import annotations

import time

import pytest

from proxy.connection_cache import (
    CachedConnection,
    ConnectionCache,
    ConnectionPool,
    get_connection_cache,
)


class TestCachedConnection:
    """Tests for CachedConnection class."""

    def test_cached_connection_init(self):
        """Test CachedConnection initialization."""
        conn = CachedConnection(value="test_value")

        assert conn.value == "test_value"
        assert conn.use_count == 0
        assert conn.ttl == 300.0
        assert conn.created_at > 0
        assert conn.last_used > 0

    def test_cached_connection_custom_ttl(self):
        """Test CachedConnection with custom TTL."""
        conn = CachedConnection(value="test", ttl=600.0)

        assert conn.ttl == 600.0

    def test_cached_connection_is_expired_false(self):
        """Test is_expired for fresh connection."""
        conn = CachedConnection(value="test", ttl=300.0)

        assert conn.is_expired is False

    def test_cached_connection_is_expired_true(self):
        """Test is_expired for expired connection."""
        conn = CachedConnection(
            value="test",
            ttl=0.001,  # 1ms TTL
        )
        time.sleep(0.01)  # Wait 10ms

        assert conn.is_expired is True

    def test_cached_connection_touch(self):
        """Test touch method."""
        conn = CachedConnection(value="test")
        old_last_used = conn.last_used
        old_use_count = conn.use_count

        time.sleep(0.01)
        conn.touch()

        assert conn.last_used > old_last_used
        assert conn.use_count == old_use_count + 1

    def test_cached_connection_age(self):
        """Test age property."""
        conn = CachedConnection(value="test")
        time.sleep(0.1)

        assert conn.age >= 0.1


class TestConnectionCache:
    """Tests for ConnectionCache class."""

    @pytest.mark.asyncio
    async def test_connection_cache_init(self):
        """Test ConnectionCache initialization."""
        cache = ConnectionCache(max_size=50, default_ttl=600.0)

        assert cache.max_size == 50
        assert cache.default_ttl == 600.0
        assert cache.hits == 0
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_connection_cache_put_get(self):
        """Test putting and getting from cache."""
        cache = ConnectionCache()

        await cache.put("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"
        assert cache.hits == 1
        assert cache.misses == 0

    @pytest.mark.asyncio
    async def test_connection_cache_get_missing(self):
        """Test getting missing key from cache."""
        cache = ConnectionCache()

        result = await cache.get("nonexistent")

        assert result is None
        assert cache.misses == 1

    @pytest.mark.asyncio
    async def test_connection_cache_get_expired(self):
        """Test getting expired key from cache."""
        cache = ConnectionCache(default_ttl=0.1)

        await cache.put("key1", "value1")
        time.sleep(0.2)  # Wait for expiration
        result = await cache.get("key1")

        assert result is None
        assert cache.expirations == 1

    @pytest.mark.asyncio
    async def test_connection_cache_max_size_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = ConnectionCache(max_size=3)

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.put("key3", "value3")

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add key4, should evict key2 (LRU)
        await cache.put("key4", "value4")

        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"
        assert cache.evictions == 1

    @pytest.mark.asyncio
    async def test_connection_cache_remove(self):
        """Test removing from cache."""
        cache = ConnectionCache()

        await cache.put("key1", "value1")
        result = await cache.remove("key1")

        assert result is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_connection_cache_remove_nonexistent(self):
        """Test removing nonexistent key."""
        cache = ConnectionCache()

        result = await cache.remove("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_connection_cache_clear(self):
        """Test clearing cache."""
        cache = ConnectionCache()

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")
        await cache.clear()

        assert await cache.size() == 0

    @pytest.mark.asyncio
    async def test_connection_cache_contains(self):
        """Test contains method."""
        cache = ConnectionCache()

        await cache.put("key1", "value1")

        assert await cache.contains("key1") is True
        assert await cache.contains("nonexistent") is False

    @pytest.mark.asyncio
    async def test_connection_cache_size(self):
        """Test size method."""
        cache = ConnectionCache()

        assert await cache.size() == 0

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")

        assert await cache.size() == 2

    @pytest.mark.asyncio
    async def test_connection_cache_get_keys(self):
        """Test get_keys method."""
        cache = ConnectionCache()

        await cache.put("key1", "value1")
        await cache.put("key2", "value2")

        keys = await cache.get_keys()

        assert "key1" in keys
        assert "key2" in keys

    @pytest.mark.asyncio
    async def test_connection_cache_statistics(self):
        """Test get_statistics method."""
        cache = ConnectionCache(max_size=10)

        await cache.put("key1", "value1")
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss

        stats = cache.get_statistics()

        assert stats['size'] == 1
        assert stats['max_size'] == 10
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate_percent'] == 50.0

    @pytest.mark.asyncio
    async def test_connection_cache_start_stop(self):
        """Test start and stop."""
        cache = ConnectionCache(cleanup_interval=0.1)

        await cache.start()
        assert cache._running is True

        time.sleep(0.2)

        await cache.stop()
        assert cache._running is False


class TestConnectionPool:
    """Tests for ConnectionPool class."""

    @pytest.mark.asyncio
    async def test_connection_pool_init(self):
        """Test ConnectionPool initialization."""
        pool = ConnectionPool(
            endpoint="test_endpoint",
            min_size=2,
            max_size=10,
        )

        assert pool.endpoint == "test_endpoint"
        assert pool.min_size == 2
        assert pool.max_size == 10

    @pytest.mark.asyncio
    async def test_connection_pool_acquire_empty(self):
        """Test acquiring from empty pool."""
        pool = ConnectionPool(endpoint="test")

        result = await pool.acquire()

        assert result is None

    @pytest.mark.asyncio
    async def test_connection_pool_release_acquire(self):
        """Test releasing and acquiring connection."""
        pool = ConnectionPool(endpoint="test")

        await pool.release("connection1")
        result = await pool.acquire()

        assert result == "connection1"
        assert pool._stats['reused'] == 1

    @pytest.mark.asyncio
    async def test_connection_pool_discard(self):
        """Test discarding connection."""
        pool = ConnectionPool(endpoint="test")

        await pool.release("connection1")
        await pool.discard("connection1")

        result = await pool.acquire()
        assert result is None
        assert pool._stats['discarded'] == 1

    @pytest.mark.asyncio
    async def test_connection_pool_cleanup(self):
        """Test cleanup of expired connections."""
        pool = ConnectionPool(endpoint="test", ttl=0.1)

        await pool.release("connection1")
        time.sleep(0.2)

        removed = await pool.cleanup()

        assert removed == 1

    def test_connection_pool_statistics(self):
        """Test get_statistics method."""
        pool = ConnectionPool(endpoint="test", max_size=10)

        stats = pool.get_statistics()

        assert stats['endpoint'] == "test"
        assert stats['max_size'] == 10
        assert stats['size'] == 0


class TestGetConnectionCache:
    """Tests for get_connection_cache function."""

    def test_get_connection_cache_singleton(self):
        """Test get_connection_cache returns singleton."""
        cache1 = get_connection_cache()
        cache2 = get_connection_cache()

        assert cache1 is cache2

    def test_get_connection_cache_custom_params(self):
        """Test get_connection_cache with custom params."""
        import proxy.connection_cache as cc_mod
        cc_mod._connection_cache = None

        cache = get_connection_cache(max_size=50, ttl=600.0)

        assert cache.max_size == 50
        assert cache.default_ttl == 600.0
