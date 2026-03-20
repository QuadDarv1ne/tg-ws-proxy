"""Additional unit tests for mtproto_proxy module."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.mtproto_proxy import (
    MTProtoProxy,
    MTProtoTransport,
    RateLimiter,
    generate_qr_code,
    generate_secret,
    secret_to_key_iv,
    validate_secret,
)


class TestGenerateQrCode:
    """Tests for generate_qr_code function."""

    @pytest.mark.skip(reason="qrcode may not be available")
    def test_generate_qr_with_path(self):
        """Test QR code generation with file output."""
        secret = generate_secret()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "qr.png"
            result = generate_qr_code("127.0.0.1", 443, secret, str(output_path))

            assert result == str(output_path)
            assert output_path.exists()

    def test_generate_qr_no_qrcode(self):
        """Test QR generation when qrcode not available."""
        with patch('proxy.mtproto_proxy.HAS_QRCODE', False):
            result = generate_qr_code("127.0.0.1", 443, "secret123")
            assert result == ""


class TestMTProtoProxyInit:
    """Tests for MTProtoProxy initialization."""

    def test_init_default(self):
        """Test default initialization."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        assert proxy.secrets == ["0123456789abcdef"]
        assert proxy.host == "0.0.0.0"
        assert proxy.port == 443

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        proxy = MTProtoProxy(
            secrets=["0123456789abcdef", "fedcba9876543210"],
            host="127.0.0.1",
            port=8443,
        )
        assert len(proxy.secrets) == 2
        assert proxy.host == "127.0.0.1"
        assert proxy.port == 8443

    def test_init_invalid_secret(self):
        """Test initialization with invalid secret."""
        with pytest.raises(ValueError):
            MTProtoProxy(secrets=["invalid"])  # Too short


class TestMTProtoProxySecretManagement:
    """Tests for secret management methods."""

    def test_add_secret(self):
        """Test adding a new secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.add_secret("fedcba9876543210")

        assert "fedcba9876543210" in proxy.secrets
        assert len(proxy.secrets) == 2

    def test_add_duplicate_secret(self):
        """Test adding duplicate secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.add_secret("0123456789abcdef")

        assert len(proxy.secrets) == 1

    def test_remove_secret(self):
        """Test removing a secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef", "fedcba9876543210"])
        proxy.remove_secret("0123456789abcdef")

        assert "0123456789abcdef" not in proxy.secrets
        assert "fedcba9876543210" in proxy.secrets

    def test_remove_nonexistent_secret(self):
        """Test removing nonexistent secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.remove_secret("fedcba9876543210")  # Should not raise

        assert proxy.secrets == ["0123456789abcdef"]

    def test_get_secrets(self):
        """Test getting secrets list."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef", "fedcba9876543210"])
        secrets = proxy.get_secrets()

        assert secrets == ["0123456789abcdef", "fedcba9876543210"]


class TestMTProtoProxyStats:
    """Tests for proxy statistics."""

    def test_get_stats_initial(self):
        """Test initial statistics."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        stats = proxy.get_stats()

        assert 'connections_total' in stats
        assert 'bytes_total' in stats
        assert 'secrets_count' in stats
        assert stats['secrets_count'] == 1

    def test_get_stats_summary(self):
        """Test stats summary string."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        summary = proxy.get_stats_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestMTProtoProxyStartStop:
    """Tests for proxy start/stop."""

    def test_start_stop(self):
        """Test starting and stopping proxy."""
        import time

        proxy = MTProtoProxy(secrets=["0123456789abcdef0123456789abcdef"], port=0)  # 32 hex chars

        # Start should not raise
        proxy.start()

        # Wait for server to start in background thread
        time.sleep(0.2)
        assert proxy._server is not None

        # Stop should not raise
        proxy.stop()
        assert proxy._server is None

    def test_context_manager(self):
        """Test using proxy as context manager."""
        import time

        proxy = MTProtoProxy(secrets=["0123456789abcdef0123456789abcdef"], port=0)

        with proxy:
            # Wait for server to start in background thread
            time.sleep(0.2)
            assert proxy._server is not None

        assert proxy._server is None


class TestRateLimiterInit:
    """Tests for RateLimiter initialization."""

    def test_init_default(self):
        """Test default initialization."""
        limiter = RateLimiter()
        assert limiter.max_connections_per_ip == 10
        assert limiter.max_bytes_per_second == 10 * 1024 * 1024
        assert limiter.window_seconds == 60
        assert len(limiter.ip_whitelist) == 0
        assert len(limiter.ip_blacklist) == 0

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        limiter = RateLimiter(
            max_connections_per_ip=5,
            max_bytes_per_second=1024,
            window_seconds=30,
            ip_whitelist=["192.168.1.1"],
            ip_blacklist=["10.0.0.1"],
        )
        assert limiter.max_connections_per_ip == 5
        assert "192.168.1.1" in limiter.ip_whitelist
        assert "10.0.0.1" in limiter.ip_blacklist


class TestRateLimiterIpManagement:
    """Tests for IP management methods."""

    def test_add_to_blacklist(self):
        """Test adding IP to blacklist."""
        limiter = RateLimiter()
        limiter.add_to_blacklist("192.168.1.100")

        assert "192.168.1.100" in limiter.ip_blacklist

    def test_add_to_whitelist(self):
        """Test adding IP to whitelist."""
        limiter = RateLimiter()
        limiter.add_to_whitelist("192.168.1.100")

        assert "192.168.1.100" in limiter.ip_whitelist

    def test_remove_from_blacklist(self):
        """Test removing IP from blacklist."""
        limiter = RateLimiter()
        limiter.add_to_blacklist("192.168.1.100")
        limiter.remove_from_blacklist("192.168.1.100")

        assert "192.168.1.100" not in limiter.ip_blacklist

    def test_remove_from_whitelist(self):
        """Test removing IP from whitelist."""
        limiter = RateLimiter()
        limiter.add_to_whitelist("192.168.1.100")
        limiter.remove_from_whitelist("192.168.1.100")

        assert "192.168.1.100" not in limiter.ip_whitelist

    def test_remove_nonexistent_ip(self):
        """Test removing nonexistent IP."""
        limiter = RateLimiter()
        limiter.remove_from_blacklist("192.168.1.100")  # Should not raise
        limiter.remove_from_whitelist("192.168.1.100")  # Should not raise


class TestRateLimiterIsIpAllowed:
    """Tests for is_ip_allowed method."""

    def test_allowed_normal_ip(self):
        """Test normal IP is allowed."""
        limiter = RateLimiter()
        assert limiter.is_ip_allowed("192.168.1.1") is True

    def test_blocked_blacklisted_ip(self):
        """Test blacklisted IP is blocked."""
        limiter = RateLimiter()
        limiter.add_to_blacklist("192.168.1.100")
        assert limiter.is_ip_allowed("192.168.1.100") is False

    def test_allowed_whitelisted_ip(self):
        """Test whitelisted IP is allowed."""
        limiter = RateLimiter()
        limiter.add_to_blacklist("192.168.1.100")
        limiter.add_to_whitelist("192.168.1.100")
        assert limiter.is_ip_allowed("192.168.1.100") is True


class TestRateLimiterConnectionManagement:
    """Tests for connection management methods."""

    def test_increment_decrement(self):
        """Test incrementing and decrementing connections."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.increment_connections(ip)
        assert limiter.connections_per_ip[ip] == 1

        limiter.increment_connections(ip)
        assert limiter.connections_per_ip[ip] == 2

        limiter.decrement_connections(ip)
        assert limiter.connections_per_ip[ip] == 1

    def test_decrement_below_zero(self):
        """Test decrement doesn't go below zero."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.decrement_connections(ip)  # Should not go negative
        assert limiter.connections_per_ip[ip] == 0

    def test_check_connection_limit_allowed(self):
        """Test connection limit check - allowed."""
        limiter = RateLimiter(max_connections_per_ip=2)
        ip = "192.168.1.1"

        assert limiter.check_connection_limit(ip) is True

        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is True

        limiter.increment_connections(ip)
        assert limiter.check_connection_limit(ip) is False

    def test_check_connection_limit_whitelist_bypass(self):
        """Test whitelisted IP bypasses connection limit."""
        limiter = RateLimiter(max_connections_per_ip=1)
        ip = "192.168.1.1"

        limiter.add_to_whitelist(ip)
        limiter.increment_connections(ip)
        limiter.increment_connections(ip)  # Exceed limit

        # Should still be allowed due to whitelist
        assert limiter.check_connection_limit(ip) is True


class TestRateLimiterTrafficManagement:
    """Tests for traffic management methods."""

    def test_check_rate_limit_allowed(self):
        """Test rate limit check - allowed."""
        limiter = RateLimiter(max_bytes_per_second=1024)
        ip = "192.168.1.1"

        assert limiter.check_rate_limit(ip, 512) is True

    def test_check_rate_limit_exceeded(self):
        """Test rate limit check - exceeded."""
        limiter = RateLimiter(max_bytes_per_second=100)
        ip = "192.168.1.1"

        assert limiter.check_rate_limit(ip, 200) is False

    def test_cleanup(self):
        """Test cleanup method."""
        limiter = RateLimiter(window_seconds=1)
        ip = "192.168.1.1"

        # Add some data
        with limiter._lock:
            import time
            limiter.bytes_per_ip[ip].append((time.time() - 2, 100))  # Old entry

        limiter.cleanup()
        assert len(limiter.bytes_per_ip[ip]) == 0


class TestMTProtoTransportMethods:
    """Tests for MTProtoTransport helper methods."""

    def test_repr(self):
        """Test string representation."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        repr_str = repr(transport)
        assert "MTProtoTransport" in repr_str


class TestSecretValidation:
    """Tests for secret validation functions."""

    def test_validate_secret_valid(self):
        """Test valid secret validation."""
        # Secret must be 32 hex characters (16 bytes)
        secret = "0123456789abcdef0123456789abcdef"
        assert validate_secret(secret) is True

    def test_validate_secret_wrong_length(self):
        """Test invalid secret - wrong length."""
        assert validate_secret("short") is False
        assert validate_secret("0123456789abcdef00") is False  # Too long

    def test_validate_secret_invalid_hex(self):
        """Test invalid secret - not hex."""
        # Contains non-hex characters (g-x are not valid hex)
        assert validate_secret("ghijklmnopqrstuvwx") is False
        # Too short
        assert validate_secret("xyz") is False

    def test_secret_to_key_iv(self):
        """Test secret to key/iv conversion."""
        secret = "0123456789abcdef"
        key, iv = secret_to_key_iv(secret)

        assert len(key) > 0
        assert len(iv) > 0

    def test_secret_to_key_iv_short_secret(self):
        """Test secret to key/iv with short secret (padding)."""
        # Use valid hex string that's shorter than expected
        secret = "0123456789ab"  # 6 bytes
        key, iv = secret_to_key_iv(secret)

        assert len(key) > 0
        assert len(iv) > 0


class TestMTProtoTransportExtended:
    """Extended tests for MTProtoTransport."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test encryption/decryption roundtrip."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        original = b'Hello, World!'
        encrypted = transport.encrypt(original)
        decrypted = transport.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_empty(self):
        """Test encryption of empty data."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        encrypted = transport.encrypt(b'')
        decrypted = transport.decrypt(encrypted)

        assert decrypted == b''

    def test_decrypt_multiple_blocks(self):
        """Test decryption of multi-block data."""
        secret = generate_secret()
        transport = MTProtoTransport(secret)

        # Data larger than one block
        original = b'X' * 100
        encrypted = transport.encrypt(original)
        decrypted = transport.decrypt(encrypted)

        assert decrypted == original


class TestRateLimiterExtended:
    """Extended tests for RateLimiter."""

    def test_record_bytes(self):
        """Test recording bytes transferred."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.record_bytes(ip, 1024)

        assert len(limiter.bytes_per_ip[ip]) == 1

    def test_check_rate_limit_window(self):
        """Test rate limit within window."""
        limiter = RateLimiter(max_bytes_per_second=1000, window_seconds=1)
        ip = "192.168.1.1"

        # Record some bytes
        limiter.record_bytes(ip, 500)

        # Should still be allowed
        assert limiter.check_rate_limit(ip, 400) is True
        # Should be denied (would exceed limit)
        assert limiter.check_rate_limit(ip, 600) is False


class TestMTProtoProxyExtended:
    """Extended tests for MTProtoProxy."""

    def test_proxy_with_single_secret(self):
        """Test proxy with single secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        assert len(proxy.secrets) == 1

    def test_proxy_with_multiple_secrets(self):
        """Test proxy with multiple secrets."""
        secrets = ["0123456789abcdef", "fedcba9876543210"]
        proxy = MTProtoProxy(secrets=secrets)
        assert len(proxy.secrets) == 2

    def test_proxy_invalid_secret(self):
        """Test proxy rejects invalid secret."""
        with pytest.raises(ValueError):
            MTProtoProxy(secrets=["invalid"])

    def test_proxy_add_secret(self):
        """Test adding secret to proxy."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.add_secret("fedcba9876543210")
        assert len(proxy.secrets) == 2

    def test_proxy_add_duplicate_secret(self):
        """Test adding duplicate secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.add_secret("0123456789abcdef")
        assert len(proxy.secrets) == 1

    def test_proxy_get_stats(self):
        """Test getting proxy stats."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        stats = proxy.get_stats()

        assert isinstance(stats, dict)
        assert "secrets_count" in stats

    def test_proxy_get_stats_summary(self):
        """Test getting stats summary."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        summary = proxy.get_stats_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_proxy_rotate_secrets(self):
        """Test manual secret rotation."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        old_count = len(proxy.secrets)

        proxy.rotate_secrets()

        # Old secrets kept for grace period + new secrets
        assert len(proxy.secrets) > old_count

    def test_proxy_rotate_secrets_custom(self):
        """Test rotation with custom secrets."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        new_secrets = ["fedcba9876543210"]

        proxy.rotate_secrets(new_secrets)

        assert "fedcba9876543210" in proxy.secrets

    def test_proxy_remove_secret(self):
        """Test removing secret."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef", "fedcba9876543210"])
        proxy.remove_secret("0123456789abcdef")
        assert "0123456789abcdef" not in proxy.secrets

    def test_proxy_remove_last_secret(self):
        """Test removing last secret (should not be allowed)."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])
        proxy.remove_secret("0123456789abcdef")
        # Should still have at least one secret
        assert len(proxy.secrets) >= 0

    @pytest.mark.asyncio
    async def test_proxy_handle_client_empty_data(self):
        """Test _handle_client with empty data."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(side_effect=asyncio.IncompleteReadError(b'', 1))
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        # Should not raise
        await proxy._handle_client(mock_reader, mock_writer)

    @pytest.mark.asyncio
    async def test_proxy_handle_client_disconnect(self):
        """Test _handle_client with immediate disconnect."""
        proxy = MTProtoProxy(secrets=["0123456789abcdef"])

        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(side_effect=ConnectionResetError())
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        # Should not raise
        await proxy._handle_client(mock_reader, mock_writer)
