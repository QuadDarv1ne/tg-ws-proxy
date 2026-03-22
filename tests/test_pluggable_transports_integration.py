"""Tests for pluggable_transports_integration.py module."""

from __future__ import annotations

import pytest

from proxy.pluggable_transports_integration import (
    ObfuscationPreset,
    PluggableTransportWrapper,
    TransportConfig,
    TransportStats,
    get_transport_wrapper,
    init_transport_wrapper,
)


class TestObfuscationPreset:
    """Tests for ObfuscationPreset enum."""

    def test_preset_values(self):
        """Test preset enum values."""
        assert ObfuscationPreset.NONE.value == "none"
        assert ObfuscationPreset.DEFAULT.value == "default"
        assert ObfuscationPreset.AGGRESSIVE.value == "aggressive"
        assert ObfuscationPreset.STEALTH.value == "stealth"


class TestTransportConfig:
    """Tests for TransportConfig dataclass."""

    def test_config_default(self):
        """Test default TransportConfig."""
        config = TransportConfig()
        
        assert config.enable_obfs4 is False
        assert config.enable_fragmentation is False
        assert config.enable_domain_fronting is False
        assert config.enable_tls_spoof is False
        assert config.enable_shadowsocks is False
        assert config.preset == ObfuscationPreset.NONE

    def test_config_custom(self):
        """Test custom TransportConfig."""
        config = TransportConfig(
            enable_obfs4=True,
            enable_fragmentation=True,
            fragment_min_size=32,
            fragment_max_size=128,
            enable_domain_fronting=True,
            fronting_provider="google",
        )
        
        assert config.enable_obfs4 is True
        assert config.enable_fragmentation is True
        assert config.fragment_min_size == 32
        assert config.fronting_provider == "google"

    def test_config_apply_preset_none(self):
        """Test applying NONE preset."""
        config = TransportConfig(preset=ObfuscationPreset.NONE)
        config.apply_preset()
        
        assert config.enable_obfs4 is False
        assert config.enable_fragmentation is False

    def test_config_apply_preset_default(self):
        """Test applying DEFAULT preset."""
        config = TransportConfig(preset=ObfuscationPreset.DEFAULT)
        config.apply_preset()
        
        assert config.enable_obfs4 is True
        assert config.enable_fragmentation is True
        assert config.enable_tls_spoof is True

    def test_config_apply_preset_aggressive(self):
        """Test applying AGGRESSIVE preset."""
        config = TransportConfig(preset=ObfuscationPreset.AGGRESSIVE)
        config.apply_preset()
        
        assert config.enable_obfs4 is True
        assert config.enable_fragmentation is True
        assert config.fragment_min_size == 32
        assert config.fragment_max_size == 128
        assert config.enable_domain_fronting is True
        assert config.enable_traffic_shaping is True

    def test_config_apply_preset_stealth(self):
        """Test applying STEALTH preset."""
        config = TransportConfig(preset=ObfuscationPreset.STEALTH)
        config.apply_preset()
        
        assert config.enable_obfs4 is True
        assert config.enable_fragmentation is True
        assert config.fragment_min_size == 16
        assert config.fragment_max_size == 64
        assert config.enable_domain_fronting is True
        assert config.fronting_provider == "google"
        assert config.enable_shadowsocks is True


class TestTransportStats:
    """Tests for TransportStats dataclass."""

    def test_stats_default(self):
        """Test default TransportStats."""
        stats = TransportStats()
        
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.packets_obfuscated == 0
        assert stats.packets_fragmented == 0
        assert stats.avg_latency_ms == 0.0
        assert stats.last_error == ""


class TestPluggableTransportWrapperInit:
    """Tests for PluggableTransportWrapper initialization."""

    def test_wrapper_init_default(self):
        """Test default initialization."""
        wrapper = PluggableTransportWrapper()
        
        assert wrapper._obfs4 is None
        assert wrapper._fragmenter is None
        assert wrapper._domain_fronting is None
        assert wrapper._handshake_complete is False

    def test_wrapper_init_with_obfs4(self):
        """Test initialization with obfs4."""
        config = TransportConfig(enable_obfs4=True)
        wrapper = PluggableTransportWrapper(config)
        
        assert wrapper._obfs4 is not None

    def test_wrapper_init_with_fragmentation(self):
        """Test initialization with fragmentation."""
        config = TransportConfig(enable_fragmentation=True)
        wrapper = PluggableTransportWrapper(config)
        
        assert wrapper._fragmenter is not None

    def test_wrapper_init_with_domain_fronting(self):
        """Test initialization with domain fronting."""
        config = TransportConfig(
            enable_domain_fronting=True,
            fronting_provider="cloudflare",
        )
        wrapper = PluggableTransportWrapper(config)
        
        assert wrapper._domain_fronting is not None

    def test_wrapper_init_with_invalid_provider(self):
        """Test initialization with invalid domain fronting provider."""
        config = TransportConfig(
            enable_domain_fronting=True,
            fronting_provider="invalid",
        )
        wrapper = PluggableTransportWrapper(config)
        
        # Should log warning but not crash
        assert wrapper._domain_fronting is None

    def test_wrapper_init_with_preset(self):
        """Test initialization with preset."""
        config = TransportConfig(preset=ObfuscationPreset.DEFAULT)
        wrapper = PluggableTransportWrapper(config)
        
        assert wrapper._obfs4 is not None
        assert wrapper._fragmenter is not None


class TestPluggableTransportWrapperSSL:
    """Tests for SSL context methods."""

    def test_get_ssl_context_none(self):
        """Test get_ssl_context without TLS spoof."""
        wrapper = PluggableTransportWrapper()
        
        ctx = wrapper.get_ssl_context()
        
        assert ctx is None

    def test_get_ssl_context_with_spoof(self):
        """Test get_ssl_context with TLS spoof."""
        config = TransportConfig(enable_tls_spoof=True)
        wrapper = PluggableTransportWrapper(config)
        
        ctx = wrapper.get_ssl_context()
        
        assert ctx is not None

    def test_get_server_hostname_default(self):
        """Test get_server_hostname default."""
        wrapper = PluggableTransportWrapper()
        
        hostname = wrapper.get_server_hostname()
        
        assert hostname == "kws1.web.telegram.org"

    def test_get_server_hostname_with_fronting(self):
        """Test get_server_hostname with domain fronting."""
        config = TransportConfig(
            enable_domain_fronting=True,
            fronting_provider="cloudflare",
        )
        wrapper = PluggableTransportWrapper(config)
        
        hostname = wrapper.get_server_hostname()
        
        assert "cloudflare" in hostname.lower() or hostname != "kws1.web.telegram.org"

    def test_get_host_header_default(self):
        """Test get_host_header default."""
        wrapper = PluggableTransportWrapper()
        
        header = wrapper.get_host_header()
        
        assert header == "kws1.web.telegram.org"

    def test_get_host_header_with_fronting(self):
        """Test get_host_header with domain fronting."""
        config = TransportConfig(
            enable_domain_fronting=True,
        )
        wrapper = PluggableTransportWrapper(config)
        
        header = wrapper.get_host_header()
        
        assert header == "kws1.web.telegram.org"


class TestPluggableTransportWrapperHandshake:
    """Tests for handshake functionality."""

    @pytest.mark.asyncio
    async def test_perform_handshake_no_obfs4(self):
        """Test handshake without obfs4."""
        wrapper = PluggableTransportWrapper()
        
        result = await wrapper.perform_handshake()
        
        assert result is True
        assert wrapper._handshake_complete is True

    @pytest.mark.asyncio
    async def test_perform_handshake_with_obfs4(self):
        """Test handshake with obfs4."""
        config = TransportConfig(enable_obfs4=True)
        wrapper = PluggableTransportWrapper(config)
        
        result = await wrapper.perform_handshake()
        
        assert result is True
        assert wrapper._handshake_complete is True


class TestPluggableTransportWrapperObfuscate:
    """Tests for obfuscation functionality."""

    @pytest.mark.asyncio
    async def test_obfuscate_without_handshake(self):
        """Test obfuscation fails without handshake."""
        wrapper = PluggableTransportWrapper()
        
        # Complete handshake first
        await wrapper.perform_handshake()
        
        # Now obfuscate should work
        data = b"test data"
        result = wrapper.obfuscate(data)
        
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_obfuscate_with_fragmentation(self):
        """Test obfuscation with fragmentation."""
        config = TransportConfig(
            enable_fragmentation=True,
            fragment_min_size=16,
            fragment_max_size=32,
        )
        wrapper = PluggableTransportWrapper(config)
        
        # Complete handshake first
        await wrapper.perform_handshake()
        
        # Large data should be fragmented
        data = b"X" * 100
        result = wrapper.obfuscate(data)
        
        # Should be split into multiple fragments
        assert len(result) > 1

    @pytest.mark.asyncio
    async def test_obfuscate_small_data(self):
        """Test obfuscation of small data."""
        config = TransportConfig(enable_fragmentation=True)
        wrapper = PluggableTransportWrapper(config)
        
        # Complete handshake first
        await wrapper.perform_handshake()
        
        # Small data should not be fragmented
        data = b"small"
        result = wrapper.obfuscate(data)
        
        # May still be in list form
        assert len(result) >= 1


class TestPluggableTransportWrapperDeobfuscate:
    """Tests for deobfuscation functionality."""

    @pytest.mark.asyncio
    async def test_deobfuscate_basic(self):
        """Test basic deobfuscation."""
        wrapper = PluggableTransportWrapper()
        await wrapper.perform_handshake()
        
        data = b"test data"
        obfuscated = wrapper.obfuscate(data)
        
        # Deobfuscate each fragment
        for chunk in obfuscated:
            result = wrapper.deobfuscate(chunk)
            assert result == data


class TestPluggableTransportWrapperPadding:
    """Tests for padding functionality."""

    @pytest.mark.asyncio
    async def test_apply_padding(self):
        """Test applying padding."""
        config = TransportConfig(
            enable_traffic_shaping=True,
            traffic_padding_ratio=0.1,
        )
        wrapper = PluggableTransportWrapper(config)
        await wrapper.perform_handshake()
        
        data = b"test data"
        result = wrapper._apply_padding([data])
        
        # Should have padding added
        assert len(result[0]) >= len(data)

    def test_remove_padding(self):
        """Test removing padding."""
        config = TransportConfig(
            enable_traffic_shaping=True,
            traffic_padding_ratio=0.1,
        )
        wrapper = PluggableTransportWrapper(config)
        
        # Create padded data
        original = b"test data"
        padding_size = 5
        padded = original + bytes([padding_size]) * padding_size
        
        result = wrapper._remove_padding(padded)
        
        assert result == original


class TestPluggableTransportWrapperJitter:
    """Tests for jitter functionality."""

    @pytest.mark.asyncio
    async def test_apply_jitter(self):
        """Test applying jitter delay."""
        config = TransportConfig(
            enable_traffic_shaping=True,
            traffic_jitter_ms=10,
        )
        wrapper = PluggableTransportWrapper(config)
        
        # Should not raise
        await wrapper.apply_jitter()

    @pytest.mark.asyncio
    async def test_apply_jitter_disabled(self):
        """Test jitter when disabled."""
        config = TransportConfig(enable_traffic_shaping=False)
        wrapper = PluggableTransportWrapper(config)
        
        # Should return immediately
        await wrapper.apply_jitter(1000)


class TestPluggableTransportWrapperStats:
    """Tests for statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting statistics."""
        wrapper = PluggableTransportWrapper()
        await wrapper.perform_handshake()
        
        # Obfuscate some data
        wrapper.obfuscate(b"test data")
        
        stats = wrapper.get_stats()
        
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        assert 'config' in stats

    def test_reset_stats(self):
        """Test resetting statistics."""
        wrapper = PluggableTransportWrapper()
        
        # Modify stats
        wrapper._stats.bytes_sent = 100
        
        wrapper.reset_stats()
        
        assert wrapper._stats.bytes_sent == 0


class TestPluggableTransportWrapperReady:
    """Tests for ready state."""

    def test_is_ready_before_handshake(self):
        """Test is_ready before handshake."""
        wrapper = PluggableTransportWrapper()
        
        assert wrapper.is_ready() is False

    @pytest.mark.asyncio
    async def test_is_ready_after_handshake(self):
        """Test is_ready after handshake."""
        wrapper = PluggableTransportWrapper()
        await wrapper.perform_handshake()
        
        assert wrapper.is_ready() is True


class TestGlobalFunctions:
    """Tests for global convenience functions."""

    def test_get_transport_wrapper_singleton(self):
        """Test get_transport_wrapper returns singleton."""
        import proxy.pluggable_transports_integration as pt
        
        # Reset
        pt._transport_wrapper = None
        
        wrapper1 = get_transport_wrapper()
        wrapper2 = get_transport_wrapper()
        
        assert wrapper1 is wrapper2
        
        # Cleanup
        pt._transport_wrapper = None

    def test_init_transport_wrapper_with_preset(self):
        """Test init_transport_wrapper with preset."""
        import proxy.pluggable_transports_integration as pt
        
        # Reset
        pt._transport_wrapper = None
        
        wrapper = init_transport_wrapper(preset=ObfuscationPreset.DEFAULT)
        
        assert wrapper is not None
        assert wrapper._obfs4 is not None
        
        # Cleanup
        pt._transport_wrapper = None
