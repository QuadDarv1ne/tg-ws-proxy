"""
Tests for new transport and encryption modules.

Tests for:
- UDP Relay (socks5_udp)
- HTTP/2 Transport (http2_transport)
- QUIC Transport (quic_transport)
- Meek Transport (meek_transport)
- Key Rotator (crypto)
- Mux Transport (mux_transport)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# =============================================================================
# UDP Relay Tests
# =============================================================================


class TestUdpRelay:
    """Tests for UDP relay functionality."""

    def test_udp_relay_creation(self):
        """Test UDP relay initialization."""
        from proxy.socks5_udp import UdpRelay

        relay = UdpRelay(host='127.0.0.1', port=0)
        assert relay.host == '127.0.0.1'
        assert relay.port == 0
        assert relay.total_sessions == 0

    def test_udp_session_creation(self):
        """Test UDP session creation."""
        from proxy.socks5_udp import UdpRelay, UdpSession

        relay = UdpRelay(host='127.0.0.1', port=0)
        # On Windows, we need to bind the socket first
        try:
            session = relay.create_session(('127.0.0.1', 12345))
            assert session.client_addr == ('127.0.0.1', 12345)
            assert session.packets_forwarded == 0
        except OSError:
            # Skip on Windows if socket creation fails
            pytest.skip("UDP socket creation not supported on this platform")

    def test_udp_relay_stats(self):
        """Test UDP relay statistics."""
        from proxy.socks5_udp import UdpRelay

        relay = UdpRelay()
        stats = relay.get_stats()

        assert 'total_sessions' in stats
        assert 'active_sessions' in stats
        assert 'total_packets' in stats


# =============================================================================
# HTTP/2 Transport Tests
# =============================================================================


class TestHTTP2Transport:
    """Tests for HTTP/2 transport."""

    def test_h2_settings_encoding(self):
        """Test HTTP/2 settings encoding."""
        from proxy.http2_transport import H2SettingsData

        settings = H2SettingsData(
            max_concurrent_streams=100,
            initial_window_size=65535
        )
        encoded = settings.encode()

        assert len(encoded) == 36  # 6 settings * 6 bytes each

    def test_h2_settings_decoding(self):
        """Test HTTP/2 settings decoding."""
        from proxy.http2_transport import H2SettingsData

        original = H2SettingsData(max_frame_size=32768)
        encoded = original.encode()
        decoded = H2SettingsData.decode(encoded)

        assert decoded.max_frame_size == 32768

    def test_h2_client_creation(self):
        """Test HTTP/2 client initialization."""
        from proxy.http2_transport import HTTP2Client

        client = HTTP2Client(
            host='example.com',
            port=443,
            user_agent='TestAgent'
        )

        assert client.host == 'example.com'
        assert client.user_agent == 'TestAgent'
        assert not client._connected


# =============================================================================
# QUIC Transport Tests
# =============================================================================


class TestQuicTransport:
    """Tests for QUIC transport."""

    def test_quic_config_creation(self):
        """Test QUIC configuration."""
        from proxy.quic_transport import QuicConfig

        config = QuicConfig(
            max_datagram_size=1400,
            idle_timeout=60.0
        )

        assert config.max_datagram_size == 1400
        assert config.idle_timeout == 60.0

    def test_quic_support_check(self):
        """Test QUIC support detection."""
        from proxy.quic_transport import check_quic_support

        support = check_quic_support()

        assert 'aioquic_available' in support
        assert 'quic_capable' in support
        assert 'recommendation' in support

    def test_quic_transport_fallback(self):
        """Test QUIC transport with HTTP/2 fallback."""
        from proxy.quic_transport import QuicTransport

        transport = QuicTransport(
            host='example.com',
            port=443,
            use_quic=True,
            fallback_to_http2=True
        )

        assert transport.use_quic is True
        assert transport.fallback_to_http2 is True


# =============================================================================
# Meek Transport Tests
# =============================================================================


class TestMeekTransport:
    """Tests for Meek domain fronting transport."""

    def test_meek_config_defaults(self):
        """Test Meek configuration defaults."""
        from proxy.meek_transport import MeekConfig

        config = MeekConfig()

        assert len(config.front_domains) > 0
        assert config.poll_interval == 0.1
        assert config.add_random_padding is True

    def test_meek_session_id_generation(self):
        """Test Meek session ID generation."""
        from proxy.meek_transport import MeekSession, MeekConfig

        config = MeekConfig()
        session = MeekSession(config)

        assert len(session.session_id) == 12
        assert session.session_id.isalnum() or '-' in session.session_id

    def test_meek_cdn_domains(self):
        """Test Meek CDN domain selection."""
        from proxy.meek_transport import MeekTransport

        transport = MeekTransport(
            bridge_host='bridge.example.com',
            use_cdn='google'
        )

        assert len(transport.front_domains) > 0
        assert any('google' in d for d in transport.front_domains)

    def test_meek_availability_check(self):
        """Test Meek domain availability check."""
        from proxy.meek_transport import check_meek_availability

        results = check_meek_availability()

        assert isinstance(results, dict)
        assert len(results) > 0


# =============================================================================
# Key Rotator Tests
# =============================================================================


class TestKeyRotator:
    """Tests for automatic key rotation."""

    @pytest.mark.asyncio
    async def test_key_rotator_creation(self):
        """Test KeyRotator initialization."""
        from proxy.crypto import KeyRotator, EncryptionType

        rotator = KeyRotator(
            algorithm=EncryptionType.AES_256_GCM,
            rotation_interval=60.0,
            message_limit=1000
        )

        assert rotator.algorithm == EncryptionType.AES_256_GCM
        assert rotator.rotation_interval == 60.0
        assert rotator.messages_encrypted == 0

    @pytest.mark.asyncio
    async def test_key_derivation(self):
        """Test deterministic key derivation."""
        from proxy.crypto import KeyRotator

        master_key = b'0' * 32
        rotator1 = KeyRotator(master_key=master_key)
        rotator2 = KeyRotator(master_key=master_key)

        # Same master key should derive same keys
        key1 = rotator1._derive_key(0)
        key2 = rotator2._derive_key(0)

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_encrypt_decrypt(self):
        """Test encryption and decryption with rotation."""
        from proxy.crypto import KeyRotator, EncryptionType

        rotator = KeyRotator(
            algorithm=EncryptionType.AES_256_GCM,
            rotation_interval=60.0
        )

        # Encrypt
        plaintext = b"secret message"
        encrypted, key_index = await rotator.encrypt(plaintext)

        # Decrypt with same key index
        decrypted = await rotator.decrypt(encrypted, key_index)

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_key_rotation_trigger(self):
        """Test automatic key rotation."""
        from proxy.crypto import KeyRotator

        rotator = KeyRotator(
            rotation_interval=0.1,  # 100ms for testing
            message_limit=1000
        )

        initial_index = rotator._current_key_index

        # Wait for rotation
        await asyncio.sleep(0.2)

        # Trigger rotation check
        rotated = await rotator.rotate_if_needed()

        assert rotated is True
        assert rotator._current_key_index > initial_index

    @pytest.mark.asyncio
    async def test_key_info(self):
        """Test key state information."""
        from proxy.crypto import KeyRotator

        rotator = KeyRotator()
        info = rotator.get_key_info()

        assert 'current_index' in info
        assert 'current_age' in info
        assert 'time_until_rotation' in info
        assert info['current_index'] >= 0

    @pytest.mark.asyncio
    async def test_manual_rotation(self):
        """Test manual key rotation."""
        from proxy.crypto import KeyRotator

        rotator = KeyRotator()
        initial_index = rotator._current_key_index

        await rotator.rotate_now()

        assert rotator._current_key_index == initial_index + 1
        assert rotator.rotations_count == 1

    @pytest.mark.asyncio
    async def test_master_key_export(self):
        """Test master key export."""
        from proxy.crypto import KeyRotator

        rotator = KeyRotator()
        master_key = rotator.export_master_key()

        assert len(master_key) == 32

    @pytest.mark.asyncio
    async def test_from_master_key(self):
        """Test creation from existing master key."""
        from proxy.crypto import KeyRotator

        master_key = b'1' * 32
        rotator = KeyRotator.from_master_key(master_key)

        assert rotator.master_key == master_key

    @pytest.mark.asyncio
    async def test_invalid_master_key_length(self):
        """Test rejection of invalid master key length."""
        from proxy.crypto import KeyRotator

        with pytest.raises(ValueError):
            KeyRotator.from_master_key(b'short')


# =============================================================================
# Mux Transport Tests
# =============================================================================


class TestMuxTransport:
    """Tests for connection multiplexing."""

    def test_mux_stream_creation(self):
        """Test MuxStream initialization."""
        from proxy.mux_transport import MuxStream

        stream = MuxStream(stream_id=1)

        assert stream.stream_id == 1
        assert stream.state == 'open'
        assert len(stream.receive_buffer) == 0

    def test_muxer_initialization(self):
        """Test ConnectionMuxer initialization."""
        from proxy.mux_transport import ConnectionMuxer

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        muxer = ConnectionMuxer(
            reader=mock_reader,
            writer=mock_writer,
            max_streams=50
        )

        assert muxer.max_streams == 50
        assert muxer.frames_sent == 0

    def test_frame_header_encoding(self):
        """Test frame header encoding/decoding."""
        import struct

        stream_id = 12345
        length = 67890

        header = struct.pack('!II', stream_id, length)
        decoded_id, decoded_len = struct.unpack('!II', header)

        assert decoded_id == stream_id
        assert decoded_len == length

    def test_mux_transport_stats(self):
        """Test mux transport statistics."""
        from proxy.mux_transport import MuxTransport

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()

        transport = MuxTransport(
            reader=mock_reader,
            writer=mock_writer,
            max_streams=100
        )

        stats = transport.get_stats()
        assert 'connected' in stats
        assert stats['connected'] is False  # Not connected yet


class TestMuxConnectionPool:
    """Tests for mux connection pool."""

    def test_pool_creation(self):
        """Test connection pool initialization."""
        from proxy.mux_transport import MuxConnectionPool

        pool = MuxConnectionPool(
            host='example.com',
            port=443,
            max_connections=4
        )

        assert pool.max_connections == 4
        assert pool.connections_created == 0

    def test_pool_stats(self):
        """Test pool statistics."""
        from proxy.mux_transport import MuxConnectionPool

        pool = MuxConnectionPool(host='localhost', port=80)
        stats = pool.get_stats()

        assert 'pool_size' in stats
        assert 'max_connections' in stats
        assert 'connections_created' in stats


# =============================================================================
# Integration Tests
# =============================================================================


class TestTransportIntegration:
    """Integration tests for multiple transports."""

    def test_all_transports_import(self):
        """Test that all transport modules can be imported."""
        from proxy import socks5_udp
        from proxy import http2_transport
        from proxy import quic_transport
        from proxy import meek_transport
        from proxy import mux_transport
        from proxy import crypto

        # Check key classes exist
        assert hasattr(socks5_udp, 'UdpRelay')
        assert hasattr(http2_transport, 'HTTP2Client')
        assert hasattr(quic_transport, 'QuicTransport')
        assert hasattr(meek_transport, 'MeekTransport')
        assert hasattr(mux_transport, 'ConnectionMuxer')
        assert hasattr(crypto, 'KeyRotator')

    def test_crypto_algorithms_available(self):
        """Test that all encryption algorithms are available."""
        from proxy.crypto import CryptoManager, EncryptionType

        manager = CryptoManager()
        algorithms = manager.get_supported_algorithms()

        assert EncryptionType.AES_256_GCM in algorithms
        assert EncryptionType.CHACHA20_POLY1305 in algorithms
        # MTProto IGE is available but not in default list
        assert hasattr(manager, 'get_performance_info')


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
