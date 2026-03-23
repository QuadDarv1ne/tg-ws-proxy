"""Tests for doh_resolver.py module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.doh_resolver import (
    DNSCacheEntry,
    DNSOverHTTPSResolver,
    DoHProvider,
    get_doh_resolver,
    init_doh_resolver,
)


class TestDoHProvider:
    """Tests for DoHProvider dataclass."""

    def test_provider_default(self):
        """Test default DoHProvider."""
        provider = DoHProvider(name="Test", url="https://test.com/dns-query")
        
        assert provider.name == "Test"
        assert provider.url == "https://test.com/dns-query"
        assert provider.priority == 0
        assert provider.timeout == 5.0
        assert provider.enabled is True
        assert provider.success_count == 0
        assert provider.failure_count == 0

    def test_provider_custom(self):
        """Test custom DoHProvider."""
        provider = DoHProvider(
            name="Custom",
            url="https://custom.com/dns-query",
            priority=10,
            timeout=3.0,
            enabled=False,
        )
        
        assert provider.priority == 10
        assert provider.timeout == 3.0
        assert provider.enabled is False

    def test_provider_success_rate(self):
        """Test success rate calculation."""
        provider = DoHProvider(name="Test", url="https://test.com/dns-query")
        
        # No queries yet
        assert provider.success_rate == 1.0
        
        # Add some results
        provider.success_count = 8
        provider.failure_count = 2
        
        assert provider.success_rate == 0.8


class TestDNSCacheEntry:
    """Tests for DNSCacheEntry dataclass."""

    def test_cache_entry_default(self):
        """Test default DNSCacheEntry."""
        import time
        entry = DNSCacheEntry(
            ips=["1.2.3.4"],
            expiry=time.monotonic() + 300,
            ttl=300,
        )
        
        assert entry.ips == ["1.2.3.4"]
        assert entry.ttl == 300
        assert entry.validated is False

    def test_cache_entry_is_expired(self):
        """Test cache entry expiry check."""
        import time
        now = time.monotonic()
        
        # Not expired
        entry = DNSCacheEntry(ips=["1.2.3.4"], expiry=now + 300, ttl=300)
        assert entry.is_expired(now) is False
        
        # Expired
        expired_entry = DNSCacheEntry(ips=["1.2.3.4"], expiry=now - 100, ttl=300)
        assert expired_entry.is_expired(now) is True


class TestDNSOverHTTPSResolverInit:
    """Tests for DNSOverHTTPSResolver initialization."""

    def test_resolver_init_default(self):
        """Test default initialization."""
        resolver = DNSOverHTTPSResolver()
        
        assert len(resolver.providers) > 0
        assert resolver.cache_ttl == 300.0
        assert resolver.max_cache_size == 1000
        assert resolver.enable_dnssec is False
        assert resolver.fallback_to_system is True

    def test_resolver_init_custom(self):
        """Test custom initialization."""
        providers = [
            DoHProvider(name="Custom", url="https://custom.com/dns-query"),
        ]
        
        resolver = DNSOverHTTPSResolver(
            providers=providers,
            cache_ttl=600.0,
            max_cache_size=500,
            enable_dnssec=True,
            fallback_to_system=False,
        )
        
        assert len(resolver.providers) == 1
        assert resolver.providers[0].name == "Custom"
        assert resolver.cache_ttl == 600.0
        assert resolver.max_cache_size == 500
        assert resolver.enable_dnssec is True
        assert resolver.fallback_to_system is False


class TestDNSOverHTTPSResolverResolve:
    """Tests for DNSOverHTTPSResolver.resolve method."""

    @pytest.mark.asyncio
    async def test_resolve_from_cache(self):
        """Test resolution from cache."""
        resolver = DNSOverHTTPSResolver()
        
        # Add to cache manually
        import time
        now = time.monotonic()
        resolver._cache["test.example.com"] = DNSCacheEntry(
            ips=["192.0.2.1"],
            expiry=now + 300,
            ttl=300,
        )
        
        result = await resolver.resolve("test.example.com")
        
        assert len(result) == 1
        assert result[0][0] == "192.0.2.1"
        assert result[0][1] == 443
        assert resolver._cache_hits == 1

    @pytest.mark.asyncio
    async def test_resolve_from_doh_success(self):
        """Test successful DoH resolution."""
        resolver = DNSOverHTTPSResolver()
        
        # Mock successful DoH response
        mock_response = {
            "Status": 0,
            "Answer": [
                {"type": 1, "data": "192.0.2.1"},
                {"type": 1, "data": "192.0.2.2"},
            ],
        }
        
        with patch.object(resolver, '_query_provider', return_value=["192.0.2.1", "192.0.2.2"]):
            result = await resolver.resolve("example.com")
        
        assert len(result) == 2
        assert result[0][0] == "192.0.2.1"
        assert result[1][0] == "192.0.2.2"

    @pytest.mark.asyncio
    async def test_resolve_doh_failure_fallback(self):
        """Test DoH failure with system DNS fallback."""
        resolver = DNSOverHTTPSResolver(fallback_to_system=True)
        
        # Mock DoH failure
        with patch.object(resolver, '_query_provider', side_effect=Exception("DoH failed")):
            with patch.object(resolver, '_resolve_system_dns', return_value=["192.0.2.1"]):
                result = await resolver.resolve("example.com")
        
        assert len(result) == 1
        assert result[0][0] == "192.0.2.1"
        assert resolver._fallback_success == 1

    @pytest.mark.asyncio
    async def test_resolve_all_failures_empty_result(self):
        """Test all methods fail - return empty."""
        resolver = DNSOverHTTPSResolver(fallback_to_system=False)
        
        # Mock DoH failure
        with patch.object(resolver, '_query_provider', side_effect=Exception("DoH failed")):
            result = await resolver.resolve("example.com")
        
        assert result == []
        assert resolver._doh_failure > 0


class TestDNSOverHTTPSResolverQueryProvider:
    """Tests for _query_provider method."""

    @pytest.mark.asyncio
    async def test_query_provider_success(self):
        """Test successful provider query."""
        resolver = DNSOverHTTPSResolver()
        provider = DoHProvider(name="Test", url="https://test.com/dns-query")
        
        # Mock _parse_doh_response directly
        with patch.object(resolver, '_parse_doh_response', return_value=["192.0.2.1"]):
            with patch.object(resolver, '_query_urllib', return_value=["192.0.2.1"]):
                # Mock session to None to force urllib fallback
                resolver._session = None
                result = await resolver._query_provider(provider, "example.com", 5.0)
        
        assert result == ["192.0.2.1"]

    @pytest.mark.asyncio
    async def test_query_provider_http_error(self):
        """Test HTTP error from provider."""
        resolver = DNSOverHTTPSResolver()
        provider = DoHProvider(name="Test", url="https://test.com/dns-query")
        
        # Mock urllib to raise error
        with patch.object(resolver, '_query_urllib', side_effect=RuntimeError("HTTP 500")):
            resolver._session = None
            with pytest.raises(RuntimeError, match="HTTP 500"):
                await resolver._query_provider(provider, "example.com", 5.0)


class TestDNSOverHTTPSResolverParseResponse:
    """Tests for _parse_doh_response method."""

    def test_parse_response_a_records(self):
        """Test parsing A records."""
        resolver = DNSOverHTTPSResolver()
        
        data = {
            "Status": 0,
            "Answer": [
                {"type": 1, "data": "192.0.2.1"},
                {"type": 1, "data": "192.0.2.2"},
            ],
        }
        
        result = resolver._parse_doh_response(data)
        
        assert result == ["192.0.2.1", "192.0.2.2"]

    def test_parse_response_aaaa_records(self):
        """Test parsing AAAA records."""
        resolver = DNSOverHTTPSResolver()
        
        data = {
            "Status": 0,
            "Answer": [
                {"type": 28, "data": "2001:db8::1"},
            ],
        }
        
        result = resolver._parse_doh_response(data)
        
        assert result == ["2001:db8::1"]

    def test_parse_response_error_status(self):
        """Test parsing error status."""
        resolver = DNSOverHTTPSResolver()
        
        data = {
            "Status": 3,  # NXDOMAIN
        }
        
        with pytest.raises(RuntimeError, match="error status"):
            resolver._parse_doh_response(data)

    def test_parse_response_empty(self):
        """Test parsing empty response."""
        resolver = DNSOverHTTPSResolver()
        
        data = {
            "Status": 0,
            "Answer": [],
        }
        
        result = resolver._parse_doh_response(data)
        
        assert result == []


class TestDNSOverHTTPSResolverBuildQuery:
    """Tests for _build_dns_query method."""

    def test_build_dns_query(self):
        """Test DNS query building."""
        resolver = DNSOverHTTPSResolver()
        
        query = resolver._build_dns_query("example.com")
        
        # Query should have header (12 bytes) + question
        assert len(query) > 12
        
        # Should contain domain name
        assert b'example' in query
        assert b'com' in query


class TestDNSOverHTTPSResolverCache:
    """Tests for cache operations."""

    @pytest.mark.asyncio
    async def test_add_to_cache(self):
        """Test adding to cache."""
        resolver = DNSOverHTTPSResolver()
        
        await resolver._add_to_cache("test.com", ["1.2.3.4"], 300)
        
        assert "test.com" in resolver._cache
        assert resolver._cache["test.com"].ips == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_cache_trim(self):
        """Test cache trimming when full."""
        resolver = DNSOverHTTPSResolver(max_cache_size=10)
        
        # Fill cache
        for i in range(15):
            await resolver._add_to_cache(f"test{i}.com", [f"1.2.3.{i}"], 300)
        
        # Should have trimmed
        assert len(resolver._cache) <= 10

    @pytest.mark.asyncio
    async def test_get_from_cache_expired(self):
        """Test getting expired entry from cache."""
        resolver = DNSOverHTTPSResolver()
        
        import time
        now = time.monotonic()
        
        # Add expired entry
        resolver._cache["expired.com"] = DNSCacheEntry(
            ips=["1.2.3.4"],
            expiry=now - 100,
            ttl=300,
        )
        
        result = await resolver._get_from_cache("expired.com")
        
        assert result is None
        assert "expired.com" not in resolver._cache


class TestDNSOverHTTPSResolverStatistics:
    """Tests for statistics methods."""

    def test_get_statistics(self):
        """Test getting statistics."""
        resolver = DNSOverHTTPSResolver()
        
        # Simulate some queries
        resolver._total_queries = 100
        resolver._cache_hits = 40
        resolver._doh_success = 50
        resolver._doh_failure = 10
        
        stats = resolver.get_statistics()
        
        assert stats['total_queries'] == 100
        assert stats['cache_hits'] == 40
        assert stats['cache_hit_rate'] == 0.4
        assert stats['doh_success'] == 50
        assert 'providers' in stats

    def test_get_provider_stats(self):
        """Test getting provider statistics."""
        resolver = DNSOverHTTPSResolver()
        
        provider_stats = resolver.get_provider_stats()
        
        assert len(provider_stats) > 0
        assert 'name' in provider_stats[0]
        assert 'url' in provider_stats[0]
        assert 'success_rate' in provider_stats[0]


class TestDNSOverHTTPSResolverProviderManagement:
    """Tests for provider management methods."""

    def test_add_provider(self):
        """Test adding provider."""
        resolver = DNSOverHTTPSResolver()
        
        initial_count = len(resolver.providers)
        
        new_provider = DoHProvider(name="NewProvider", url="https://new.com/dns-query")
        resolver.add_provider(new_provider)
        
        assert len(resolver.providers) == initial_count + 1

    def test_remove_provider(self):
        """Test removing provider."""
        resolver = DNSOverHTTPSResolver()
        
        # Add then remove
        new_provider = DoHProvider(name="ToRemove", url="https://remove.com/dns-query")
        resolver.add_provider(new_provider)
        
        result = resolver.remove_provider("ToRemove")
        
        assert result is True

    def test_remove_provider_not_found(self):
        """Test removing non-existent provider."""
        resolver = DNSOverHTTPSResolver()
        
        result = resolver.remove_provider("NonExistent")
        
        assert result is False

    def test_enable_disable_provider(self):
        """Test enabling/disabling provider."""
        resolver = DNSOverHTTPSResolver()

        # Find first provider
        provider_name = resolver.providers[0].name

        resolver.disable_provider(provider_name)

        assert resolver.providers[0].enabled is False


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    def test_get_doh_resolver_singleton(self):
        """Test get_doh_resolver returns singleton."""
        import proxy.doh_resolver as doh
        
        # Reset
        doh._doh_resolver = None
        
        resolver1 = get_doh_resolver()
        resolver2 = get_doh_resolver()
        
        assert resolver1 is resolver2
        
        # Cleanup
        doh._doh_resolver = None

    def test_init_doh_resolver(self):
        """Test init_doh_resolver creates new instance."""
        import proxy.doh_resolver as doh
        
        # Reset
        doh._doh_resolver = None
        
        resolver = init_doh_resolver(cache_ttl=600.0)
        
        assert resolver is not None
        assert resolver.cache_ttl == 600.0
        
        # Cleanup
        doh._doh_resolver = None


class TestDNSOverHTTPSResolverClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing session."""
        resolver = DNSOverHTTPSResolver()
        
        # Create mock session
        mock_session = AsyncMock()
        resolver._session = mock_session
        
        await resolver.close()
        
        mock_session.close.assert_awaited()
        assert resolver._session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        """Test close with no session."""
        resolver = DNSOverHTTPSResolver()
        resolver._session = None
        
        # Should not raise
        await resolver.close()
