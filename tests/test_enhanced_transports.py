"""
Comprehensive tests for enhanced transport modules.

Tests for:
- Transport Manager
- Obfsproxy Transport
- Post-Quantum Crypto
- Web Transport UI
- Integration tests

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# =============================================================================
# Transport Manager Tests
# =============================================================================


class TestTransportManager:
    """Tests for Transport Manager."""

    def test_transport_config_defaults(self):
        """Test TransportConfig default values."""
        from proxy.transport_manager import TransportConfig, TransportType

        config = TransportConfig()

        assert config.transport_type == TransportType.WEBSOCKET
        assert config.host == 'kws2.web.telegram.org'
        assert config.port == 443
        assert config.auto_select is True
        assert config.health_check_interval == 30.0

    def test_transport_type_enum(self):
        """Test TransportType enum values."""
        from proxy.transport_manager import TransportType

        assert TransportType.WEBSOCKET.name == 'WEBSOCKET'
        assert TransportType.HTTP2.name == 'HTTP2'
        assert TransportType.QUIC.name == 'QUIC'
        assert TransportType.MEEK.name == 'MEEK'
        assert TransportType.SHADOWSOCKS.name == 'SHADOWSOCKS'
        assert TransportType.TUIC.name == 'TUIC'
        assert TransportType.REALITY.name == 'REALITY'

    def test_transport_status_enum(self):
        """Test TransportStatus enum values."""
        from proxy.transport_manager import TransportStatus

        assert TransportStatus.DISCONNECTED.name == 'DISCONNECTED'
        assert TransportStatus.CONNECTING.name == 'CONNECTING'
        assert TransportStatus.CONNECTED.name == 'CONNECTED'
        assert TransportStatus.FAILED.name == 'FAILED'
        assert TransportStatus.DEGRADED.name == 'DEGRADED'

    def test_transport_health(self):
        """Test TransportHealth metrics."""
        from proxy.transport_manager import TransportHealth

        health = TransportHealth()

        assert health.latency_ms == 0.0
        assert health.packet_loss == 0.0
        assert health.consecutive_failures == 0
        assert health.success_rate == 1.0
        assert health.is_healthy is True

    def test_transport_health_unhealthy(self):
        """Test TransportHealth unhealthy conditions."""
        from proxy.transport_manager import TransportHealth

        health = TransportHealth()
        health.consecutive_failures = 5
        health.successful_requests = 5
        health.total_requests = 10

        assert health.is_healthy is False
        assert health.success_rate == 0.5

    def test_manager_initialization(self):
        """Test TransportManager initialization."""
        from proxy.transport_manager import TransportManager, TransportConfig

        config = TransportConfig()
        manager = TransportManager(config)

        assert manager.config == config
        assert manager._transport is None
        assert manager._status.value == 1  # DISCONNECTED

    def test_manager_fallback_chain(self):
        """Test fallback chain building."""
        from proxy.transport_manager import TransportManager, TransportConfig, TransportType

        config = TransportConfig()
        manager = TransportManager(config)

        chain = manager._build_fallback_chain()

        assert TransportType.QUIC in chain
        assert TransportType.HTTP2 in chain
        assert TransportType.WEBSOCKET in chain
        assert TransportType.MEEK in chain

    def test_manager_stats(self):
        """Test manager statistics."""
        from proxy.transport_manager import TransportManager

        manager = TransportManager()
        stats = manager.get_stats()

        assert 'status' in stats
        assert 'transport_type' in stats
        assert 'bytes_sent' in stats
        assert 'bytes_received' in stats
        assert 'health' in stats


# =============================================================================
# Obfsproxy Transport Tests
# =============================================================================


class TestObfsproxyTransport:
    """Tests for Obfsproxy transport."""

    def test_obfs_config_defaults(self):
        """Test ObfsConfig default values."""
        from proxy.obfsproxy_transport import ObfsConfig, ObfsProtocol

        config = ObfsConfig()

        assert config.protocol == ObfsProtocol.OBFSC4
        assert len(config.cert) == 32
        assert len(config.seed) == 32
        assert config.add_padding is True
        assert config.timing_jitter is True

    def test_obfs4_obfuscator_creation(self):
        """Test Obfs4Obfuscator initialization."""
        from proxy.obfsproxy_transport import Obfs4Obfuscator

        obfuscator = Obfs4Obfuscator()

        assert len(obfuscator.cert) == 32
        assert len(obfuscator.seed) == 32
        assert obfuscator._initialized is False

    def test_obfs4_handshake(self):
        """Test obfs4 handshake creation."""
        from proxy.obfsproxy_transport import Obfs4Obfuscator

        obfuscator = Obfs4Obfuscator()
        handshake = obfuscator.create_client_handshake()

        assert len(handshake) == obfuscator.CLIENT_HANDSHAKE_SIZE
        assert obfuscator._initialized is True

    def test_obfs4_obfuscate_deobfuscate(self):
        """Test obfs4 obfuscate/deobfuscate round-trip."""
        from proxy.obfsproxy_transport import Obfs4Obfuscator

        obfuscator = Obfs4Obfuscator()
        obfuscator.create_client_handshake()

        original = b"Hello, obfuscated world!"
        obfuscated = obfuscator.obfuscate(original)

        # Should be different from original
        assert obfuscated != original
        assert len(obfuscated) > len(original)  # Has length prefix

    def test_scramblesuit_obfuscator(self):
        """Test ScrambleSuit obfuscator."""
        from proxy.obfsproxy_transport import ScrambleSuitObfuscator

        obfuscator = ScrambleSuitObfuscator(password='test_password')

        original = b"Test data"
        obfuscated = obfuscator.obfuscate(original)

        assert obfuscated != original
        assert len(obfuscated) > len(original)  # Has padding and signature

    def test_meek_lite_obfuscator(self):
        """Test Meek-lite obfuscator."""
        from proxy.obfsproxy_transport import MeekLiteObfuscator

        obfuscator = MeekLiteObfuscator(front_domain='www.google.com')

        original = b"Test payload"
        obfuscated = obfuscator.obfuscate(original)

        assert b'www.google.com' in obfuscated
        assert b'HTTP/1.1' in obfuscated
        assert original in obfuscated

    def test_obfsproxy_transport_creation(self):
        """Test ObfsproxyTransport initialization."""
        from proxy.obfsproxy_transport import (
            ObfsproxyTransport,
            ObfsConfig,
            ObfsProtocol
        )

        mock_transport = AsyncMock()
        config = ObfsConfig(protocol=ObfsProtocol.OBFSC4)

        transport = ObfsproxyTransport(mock_transport, config)

        assert transport.transport == mock_transport
        assert transport.config == config
        assert transport.obfuscator is not None

    def test_obfs_availability_check(self):
        """Test obfuscation availability check."""
        from proxy.obfsproxy_transport import check_obfs_availability

        avail = check_obfs_availability()

        assert avail['obfs4_available'] is True
        assert 'obfs4' in avail['protocols']
        assert 'scramblesuit' in avail['protocols']
        assert 'meek-lite' in avail['protocols']


# =============================================================================
# Post-Quantum Crypto Tests
# =============================================================================


class TestPostQuantumCrypto:
    """Tests for Post-Quantum Cryptography."""

    def test_kyber_keypair_generation(self):
        """Test Kyber key pair generation."""
        from proxy.post_quantum_crypto import Kyber768

        kyber = Kyber768()
        keypair = kyber.generate_keypair()

        assert len(keypair.public_key) > 0
        assert len(keypair.secret_key) > 0
        assert keypair.algorithm == 'kyber768'

    def test_kyber_encapsulation(self):
        """Test Kyber encapsulation."""
        from proxy.post_quantum_crypto import Kyber768

        kyber = Kyber768()
        keypair = kyber.generate_keypair()

        ciphertext = kyber.encapsulate(keypair.public_key)

        assert len(ciphertext.ciphertext) > 0
        assert len(ciphertext.shared_secret) == 32

    def test_kyber_decapsulation(self):
        """Test Kyber decapsulation."""
        from proxy.post_quantum_crypto import Kyber768

        kyber = Kyber768()
        keypair = kyber.generate_keypair()

        ciphertext = kyber.encapsulate(keypair.public_key)
        shared = kyber.decapsulate(ciphertext, keypair.secret_key)

        assert shared is not None
        assert len(shared) == 32

    def test_hybrid_crypto_keypair(self):
        """Test Hybrid crypto key pair generation."""
        from proxy.post_quantum_crypto import HybridCrypto

        hybrid = HybridCrypto()
        public, secret = hybrid.generate_hybrid_keypair()

        # Hybrid = X25519 (32) + Kyber (64+)
        assert len(public) > 64
        assert len(secret) > 64

    def test_hybrid_encapsulation(self):
        """Test Hybrid encapsulation."""
        from proxy.post_quantum_crypto import HybridCrypto

        hybrid = HybridCrypto()
        public, secret = hybrid.generate_hybrid_keypair()

        ciphertext, shared = hybrid.hybrid_encapsulate(public)

        assert len(ciphertext) > 0
        assert len(shared) == 32

    def test_pq_key_manager(self):
        """Test PQKeyManager."""
        from proxy.post_quantum_crypto import PQKeyManager

        manager = PQKeyManager(use_hybrid=True)
        public_key = manager.generate_keys()

        assert len(public_key) > 0
        assert manager.keys_generated == 1

        info = manager.get_key_info()
        assert info['algorithm'] == 'hybrid_x25519_kyber768'
        assert info['use_hybrid'] is True

    def test_pq_convenience_functions(self):
        """Test PQ convenience functions."""
        from proxy.post_quantum_crypto import generate_pq_keys, pq_encapsulate

        public, secret = generate_pq_keys(hybrid=True)
        assert len(public) > 0

        ciphertext, shared = pq_encapsulate(public, hybrid=True)
        assert len(ciphertext) > 0
        assert len(shared) == 32

    def test_pq_availability_check(self):
        """Test PQ availability check."""
        from proxy.post_quantum_crypto import check_pq_availability

        avail = check_pq_availability()

        assert 'liboqs_available' in avail
        assert 'builtin_pq_available' in avail
        assert 'Kyber-768' in avail['algorithms'][0]


# =============================================================================
# Web Transport UI Tests
# =============================================================================


class TestWebTransportUI:
    """Tests for Web Transport UI."""

    def test_transport_api_routes_exist(self):
        """Test that transport API routes are defined."""
        from proxy.web_transport_ui import get_transport_api_routes

        routes = get_transport_api_routes()

        assert '/api/transport/status' in routes
        assert '/api/transport/config' in routes
        assert '/api/transport/switch' in routes
        assert '/api/transport/health' in routes

    def test_transport_settings_html_exists(self):
        """Test that transport settings HTML is defined."""
        from proxy.web_transport_ui import get_transport_settings_html

        html = get_transport_settings_html()

        assert 'transport-tab' in html
        assert 'transport-type' in html
        assert 'transport-health-list' in html

    def test_pq_api_routes_exist(self):
        """Test that PQ API routes are defined."""
        from proxy.web_transport_ui import get_transport_api_routes

        routes = get_transport_api_routes()

        assert '/api/pq/status' in routes
        assert '/api/pq/generate-keys' in routes


# =============================================================================
# Integration Tests
# =============================================================================


class TestEnhancedTransportsIntegration:
    """Integration tests for enhanced transports."""

    def test_all_transport_modules_import(self):
        """Test that all transport modules can be imported."""
        from proxy import transport_manager
        from proxy import obfsproxy_transport
        from proxy import post_quantum_crypto
        from proxy import web_transport_ui
        from proxy import http2_transport
        from proxy import quic_transport
        from proxy import meek_transport
        from proxy import shadowsocks_transport
        from proxy import tuic_transport
        from proxy import reality_transport

        # Check key classes exist
        assert hasattr(transport_manager, 'TransportManager')
        assert hasattr(obfsproxy_transport, 'ObfsproxyTransport')
        assert hasattr(post_quantum_crypto, 'PQKeyManager')
        assert hasattr(http2_transport, 'HTTP2Transport')
        assert hasattr(quic_transport, 'QuicTransport')
        assert hasattr(meek_transport, 'MeekTransport')

    def test_transport_manager_with_mock(self):
        """Test TransportManager with mocked transport."""
        from proxy.transport_manager import TransportManager, TransportConfig, TransportType

        config = TransportConfig(transport_type=TransportType.WEBSOCKET)
        manager = TransportManager(config)

        # Mock the _create_transport method
        mock_transport = AsyncMock()
        mock_transport.connect.return_value = True
        mock_transport.send.return_value = True
        mock_transport.recv.return_value = b'test'
        mock_transport.get_stats.return_value = {'connected': True}

        manager._transport = mock_transport
        manager._status = MagicMock()
        manager._status.name = 'CONNECTED'

        # Test send
        result = asyncio.run(manager.send(b'test'))
        assert result is True

        # Test stats
        stats = manager.get_stats()
        assert 'status' in stats

    def test_obfsproxy_with_mock_transport(self):
        """Test ObfsproxyTransport with mocked transport."""
        from proxy.obfsproxy_transport import ObfsproxyTransport, ObfsConfig, ObfsProtocol

        mock_transport = AsyncMock()
        mock_transport.connect.return_value = True
        mock_transport.send.return_value = True
        mock_transport.recv.return_value = b'test'

        config = ObfsConfig(protocol=ObfsProtocol.OBFSC4)
        transport = ObfsproxyTransport(mock_transport, config)

        # Test connect
        result = asyncio.run(transport.connect())
        assert result is True

        # Test send (should obfuscate)
        result = asyncio.run(transport.send(b'test'))
        assert result is True

    def test_full_stack_import(self):
        """Test full stack import of all enhanced features."""
        # Core
        from proxy.transport_manager import TransportManager, TransportType
        from proxy.crypto import KeyRotator

        # Transports
        from proxy.http2_transport import HTTP2Transport
        from proxy.quic_transport import QuicTransport
        from proxy.meek_transport import MeekTransport

        # Obfuscation
        from proxy.obfsproxy_transport import ObfsproxyTransport, ObfsProtocol

        # Post-quantum
        from proxy.post_quantum_crypto import PQKeyManager, HybridCrypto

        # Web UI
        from proxy.web_transport_ui import (
            get_transport_api_routes,
            get_transport_settings_html
        )

        # All imports successful
        assert True


# =============================================================================
# Performance Tests
# =============================================================================


class TestPerformance:
    """Performance tests for new features."""

    def test_obfs4_performance(self):
        """Test obfs4 obfuscation performance."""
        import time
        from proxy.obfsproxy_transport import Obfs4Obfuscator

        obfuscator = Obfs4Obfuscator()
        obfuscator.create_client_handshake()

        data = b'X' * 1000  # 1KB
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            obfuscator.obfuscate(data)
        elapsed = time.time() - start

        ops_per_second = iterations / elapsed
        assert ops_per_second > 100  # At least 100 ops/sec

    def test_kyber_performance(self):
        """Test Kyber key generation performance."""
        import time
        from proxy.post_quantum_crypto import Kyber768

        kyber = Kyber768()
        iterations = 100

        start = time.time()
        for _ in range(iterations):
            kyber.generate_keypair()
        elapsed = time.time() - start

        ops_per_second = iterations / elapsed
        assert ops_per_second > 10  # At least 10 keypairs/sec

    def test_hybrid_crypto_performance(self):
        """Test hybrid crypto performance."""
        import time
        from proxy.post_quantum_crypto import HybridCrypto

        hybrid = HybridCrypto()
        iterations = 50

        start = time.time()
        for _ in range(iterations):
            hybrid.generate_hybrid_keypair()
        elapsed = time.time() - start

        ops_per_second = iterations / elapsed
        assert ops_per_second > 5  # At least 5 keypairs/sec


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
