"""
Tests for DNS resolver.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import asyncio
import time

import pytest

from proxy.dns_resolver import DNSCacheEntry, DNSMetrics, DNSResolver


def test_dns_cache_entry_expiry():
    """Test DNS cache entry expiry check."""
    now = time.monotonic()
    entry = DNSCacheEntry(ips=['1.2.3.4'], expiry=now + 10)
    
    assert not entry.is_expired(now)
    assert not entry.is_expired(now + 5)
    assert entry.is_expired(now + 10)
    assert entry.is_expired(now + 15)


def test_dns_metrics_cache_hit_rate():
    """Test DNS metrics cache hit rate calculation."""
    metrics = DNSMetrics()
    
    # No queries yet
    assert metrics.cache_hit_rate == 0.0
    
    # 3 hits, 1 miss = 75%
    metrics.cache_hits = 3
    metrics.cache_misses = 1
    assert metrics.cache_hit_rate == 0.75
    
    # 10 hits, 0 misses = 100%
    metrics.cache_hits = 10
    metrics.cache_misses = 0
    assert metrics.cache_hit_rate == 1.0


def test_dns_metrics_avg_resolution_time():
    """Test DNS metrics average resolution time."""
    metrics = DNSMetrics()
    
    # No queries yet
    assert metrics.avg_resolution_time == 0.0
    
    # 3 queries, 0.3s total = 0.1s avg
    metrics.total_queries = 3
    metrics.total_resolution_time = 0.3
    assert abs(metrics.avg_resolution_time - 0.1) < 0.001


@pytest.mark.asyncio
async def test_dns_resolver_init():
    """Test DNS resolver initialization."""
    resolver = DNSResolver(ttl=60.0, max_cache_size=100)
    
    assert resolver.ttl == 60.0
    assert resolver.max_cache_size == 100
    assert resolver.enable_metrics is True


@pytest.mark.asyncio
async def test_dns_resolver_resolve_localhost():
    """Test resolving localhost."""
    resolver = DNSResolver()
    
    results = await resolver.resolve('localhost', port=80, timeout=5.0)
    
    assert len(results) > 0
    assert all(isinstance(r, tuple) and len(r) == 2 for r in results)
    assert all(r[1] == 80 for r in results)
    
    # Should contain 127.0.0.1
    ips = [r[0] for r in results]
    assert '127.0.0.1' in ips


@pytest.mark.asyncio
async def test_dns_resolver_cache_hit():
    """Test DNS cache hit."""
    resolver = DNSResolver(ttl=60.0)
    
    # First resolve - cache miss
    results1 = await resolver.resolve('localhost', port=80)
    assert len(results1) > 0
    assert resolver._metrics.cache_misses == 1
    assert resolver._metrics.cache_hits == 0
    
    # Second resolve - cache hit
    results2 = await resolver.resolve('localhost', port=80)
    assert results2 == results1
    assert resolver._metrics.cache_hits == 1


@pytest.mark.asyncio
async def test_dns_resolver_cache_expiry():
    """Test DNS cache expiry."""
    resolver = DNSResolver(ttl=0.1)  # 100ms TTL
    
    # First resolve
    results1 = await resolver.resolve('localhost', port=80)
    assert len(results1) > 0
    
    # Wait for expiry
    await asyncio.sleep(0.2)
    
    # Second resolve - should be cache miss due to expiry
    results2 = await resolver.resolve('localhost', port=80)
    assert results2 == results1
    assert resolver._metrics.cache_misses == 2  # Both were misses


@pytest.mark.asyncio
async def test_dns_resolver_no_cache():
    """Test DNS resolution without cache."""
    resolver = DNSResolver()
    
    # Resolve with cache disabled
    results = await resolver.resolve('localhost', port=80, use_cache=False)
    
    assert len(results) > 0
    assert resolver._metrics.cache_hits == 0
    assert resolver._metrics.cache_misses == 0


@pytest.mark.asyncio
async def test_dns_resolver_invalid_domain():
    """Test resolving invalid domain."""
    resolver = DNSResolver()
    
    results = await resolver.resolve('invalid.domain.that.does.not.exist.xyz', timeout=1.0)
    
    assert results == []
    assert resolver._metrics.failed_queries == 1


@pytest.mark.asyncio
async def test_dns_resolver_clear_cache():
    """Test clearing DNS cache."""
    resolver = DNSResolver()
    
    # Add entry to cache
    await resolver.resolve('localhost', port=80)
    cache_info = await resolver.get_cache_info()
    assert cache_info['total_entries'] > 0
    
    # Clear cache
    await resolver.clear_cache()
    cache_info = await resolver.get_cache_info()
    assert cache_info['total_entries'] == 0


@pytest.mark.asyncio
async def test_dns_resolver_cache_size_limit():
    """Test DNS cache size limit."""
    resolver = DNSResolver(max_cache_size=2)
    
    # Add 3 entries (should evict oldest)
    await resolver.resolve('localhost', port=80)
    await resolver.resolve('127.0.0.1', port=80)
    await resolver.resolve('::1', port=80)
    
    cache_info = await resolver.get_cache_info()
    assert cache_info['total_entries'] <= 2


@pytest.mark.asyncio
async def test_dns_resolver_get_cache_info():
    """Test getting cache info."""
    resolver = DNSResolver()
    
    await resolver.resolve('localhost', port=80)
    
    cache_info = await resolver.get_cache_info()
    
    assert 'total_entries' in cache_info
    assert 'expired_entries' in cache_info
    assert 'total_hits' in cache_info
    assert 'max_size' in cache_info
    assert 'ttl_seconds' in cache_info
    
    assert cache_info['total_entries'] > 0
    assert cache_info['max_size'] == 1000


@pytest.mark.asyncio
async def test_dns_resolver_get_metrics():
    """Test getting resolver metrics."""
    resolver = DNSResolver()
    
    await resolver.resolve('localhost', port=80)
    await resolver.resolve('localhost', port=80)  # Cache hit
    
    metrics = resolver.get_metrics()
    
    assert 'total_queries' in metrics
    assert 'cache_hits' in metrics
    assert 'cache_misses' in metrics
    assert 'failed_queries' in metrics
    assert 'cache_hit_rate' in metrics
    assert 'avg_resolution_time_ms' in metrics
    
    assert metrics['total_queries'] == 2
    assert metrics['cache_hits'] == 1
    assert metrics['cache_misses'] == 1
    assert metrics['cache_hit_rate'] == 0.5


@pytest.mark.asyncio
async def test_dns_resolver_cleanup_expired():
    """Test cleanup of expired entries."""
    resolver = DNSResolver(ttl=0.1)
    
    # Add entries
    await resolver.resolve('localhost', port=80)
    
    # Wait for expiry
    await asyncio.sleep(0.2)
    
    # Cleanup
    removed = await resolver.cleanup_expired()
    
    assert removed > 0
    
    cache_info = await resolver.get_cache_info()
    assert cache_info['expired_entries'] == 0


@pytest.mark.asyncio
async def test_dns_resolver_metrics_disabled():
    """Test resolver with metrics disabled."""
    resolver = DNSResolver(enable_metrics=False)
    
    await resolver.resolve('localhost', port=80)
    
    metrics = resolver.get_metrics()
    assert metrics == {}


@pytest.mark.asyncio
async def test_get_global_resolver():
    """Test getting global resolver instance."""
    from proxy.dns_resolver import get_resolver
    
    resolver1 = get_resolver()
    resolver2 = get_resolver()
    
    # Should return same instance
    assert resolver1 is resolver2


@pytest.mark.asyncio
async def test_resolve_domain_helper():
    """Test resolve_domain helper function."""
    from proxy.dns_resolver import resolve_domain
    
    results = await resolve_domain('localhost', port=80, timeout=5.0)
    
    assert len(results) > 0
    assert all(r[1] == 80 for r in results)
