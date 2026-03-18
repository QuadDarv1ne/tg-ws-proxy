"""
Integration tests for MTProto Proxy.

Tests MTProto protocol handling, rate limiting, and connection management.
"""

import pytest
import asyncio
import struct
from typing import List, Tuple

from proxy.mtproto_proxy import (
    MTProtoProxy,
    MTProtoTransport,
    MTProtoPacket,
    RateLimiter,
    generate_secret,
    validate_secret,
    secret_to_key_iv,
)
from proxy.constants import MTPROTO_SECRET_LENGTH


class TestMTProtoTransport:
    """Tests for MTProtoTransport encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted data can be decrypted."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        original_data = b'Hello, Telegram!'

        encrypted = transport.encrypt(original_data)
        decrypted = transport.decrypt(encrypted)

        assert decrypted == original_data

    def test_different_secrets_fail(self):
        """Test that decryption with wrong secret fails."""
        secret1 = generate_secret()
        secret2 = generate_secret()

        transport1 = MTProtoTransport(secret1)
        transport2 = MTProtoTransport(secret2)

        original_data = b'Test data'
        encrypted = transport1.encrypt(original_data)

        # Decryption with different secret should produce garbage
        decrypted = transport2.decrypt(encrypted)
        assert decrypted != original_data

    def test_padding(self):
        """Test that data is properly padded to block size."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        # Test various data lengths
        for length in [1, 15, 16, 17, 31, 32, 33, 100]:
            original_data = b'X' * length
            encrypted = transport.encrypt(original_data)

            # Encrypted data should be multiple of block size (16)
            assert len(encrypted) % 16 == 0

            # Decrypted should match original
            decrypted = transport.decrypt(encrypted)
            assert decrypted == original_data


class TestMTProtoPacket:
    """Tests for MTProto packet serialization."""

    def test_serialize_deserialize(self):
        """Test packet serialization roundtrip."""
        packet = MTProtoPacket(
            length=10,
            seq=123,
            data=b'0123456789'
        )

        serialized = packet.serialize()
        deserialized = MTProtoPacket.deserialize(serialized)

        assert deserialized is not None
        assert deserialized.length == packet.length
        assert deserialized.seq == packet.seq
        assert deserialized.data == packet.data

    def test_deserialize_incomplete(self):
        """Test deserialization of incomplete data."""
        # Create packet but truncate it
        packet = MTProtoPacket(length=10, seq=1, data=b'0123456789')
        serialized = packet.serialize()

        # Truncate to header only (8 bytes)
        truncated = serialized[:8]
        result = MTProtoPacket.deserialize(truncated)

        assert result is None

    def test_deserialize_empty(self):
        """Test deserialization of empty data."""
        result = MTProtoPacket.deserialize(b'')
        assert result is None


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_connection_limit(self):
        """Test connection limiting per IP."""
        limiter = RateLimiter(max_connections_per_ip=3)

        ip = "192.168.1.100"

        # First 3 connections should be allowed
        assert limiter.check_connection_limit(ip) is True
        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is True
        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is True
        limiter.increment_connections(ip)

        # 4th connection should be rejected
        assert limiter.check_connection_limit(ip) is False

    def test_connection_cleanup(self):
        """Test connection count decrement."""
        limiter = RateLimiter(max_connections_per_ip=2)
        ip = "192.168.1.100"

        limiter.increment_connections(ip)
        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is False

        limiter.decrement_connections(ip)
        assert limiter.check_connection_limit(ip) is True

    def test_ip_whitelist(self):
        """Test IP whitelist bypasses limits."""
        limiter = RateLimiter(
            max_connections_per_ip=1,
            ip_whitelist=["10.0.0.1"]
        )

        ip = "10.0.0.1"

        # Whitelisted IP should always be allowed
        assert limiter.is_ip_allowed(ip) is True
        limiter.increment_connections(ip)
        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is True  # Still allowed

    def test_ip_blacklist(self):
        """Test IP blacklist blocks all."""
        limiter = RateLimiter(
            ip_blacklist=["192.168.1.100"]
        )

        ip = "192.168.1.100"
        assert limiter.is_ip_allowed(ip) is False

        # Non-blacklisted should be allowed
        assert limiter.is_ip_allowed("192.168.1.101") is True


class TestSecretGeneration:
    """Tests for secret generation and validation."""

    def test_generate_secret_length(self):
        """Test generated secret has correct length."""
        secret = generate_secret()
        assert len(secret) == MTPROTO_SECRET_LENGTH

    def test_generate_secret_hex(self):
        """Test generated secret is valid hex."""
        secret = generate_secret()
        # Should not raise
        bytes.fromhex(secret)

    def test_validate_secret_valid(self):
        """Test validation of valid secrets."""
        secret = generate_secret()
        assert validate_secret(secret) is True

    def test_validate_secret_invalid_length(self):
        """Test validation rejects wrong length."""
        assert validate_secret("abc123") is False
        assert validate_secret("0" * 30) is False
        assert validate_secret("0" * 34) is False

    def test_validate_secret_invalid_chars(self):
        """Test validation rejects non-hex chars."""
        assert validate_secret("g" * 32) is False
        assert validate_secret("0123456789abcdef0123456789abcdeg") is False


class TestSecretToKeyIv:
    """Tests for secret to key/IV derivation."""

    def test_key_iv_length(self):
        """Test key and IV have correct lengths."""
        secret = generate_secret()
        key, iv = secret_to_key_iv(secret)

        assert len(key) == 32  # AES-256
        assert len(iv) == 32   # IGE mode IV

    def test_deterministic(self):
        """Test same secret produces same key/IV."""
        secret = "0123456789abcdef0123456789abcdef"
        key1, iv1 = secret_to_key_iv(secret)
        key2, iv2 = secret_to_key_iv(secret)

        assert key1 == key2
        assert iv1 == iv2


@pytest.mark.asyncio
class TestMTProtoProxyIntegration:
    """Integration tests for MTProtoProxy."""

    async def test_proxy_start_stop(self):
        """Test proxy can start and stop."""
        secret = generate_secret()
        proxy = MTProtoProxy(
            secrets=[secret],
            host="127.0.0.1",
            port=0,  # Let OS choose port
        )

        # Start server
        server_task = asyncio.create_task(proxy.start())

        # Give it time to start
        await asyncio.sleep(0.1)

        # Stop server
        proxy._server.close()
        await proxy._server.wait_closed()

        # Cancel the task
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    async def test_multiple_secrets(self):
        """Test proxy with multiple secrets."""
        secrets = [generate_secret() for _ in range(3)]
        proxy = MTProtoProxy(
            secrets=secrets,
            host="127.0.0.1",
            port=0,
        )

        # All secrets should have transports
        assert len(proxy.transports) == 3
        for secret in secrets:
            assert secret in proxy.transports

        # Stats should be initialized for all secrets
        for secret in secrets:
            assert secret in proxy.stats_per_secret

        # Cleanup
        if proxy._server:
            proxy._server.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
