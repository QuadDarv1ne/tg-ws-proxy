"""Tests for core logic in tg_ws_proxy.py."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

from proxy.mtproto_parser import (
    extract_dc_from_init,
    is_http_transport,
    is_telegram_ip,
    patch_init_dc,
)


class TestPacketParsing:
    """Tests for MTProto packet parsing and manipulation."""

    def test_is_telegram_ip(self):
        """Test Telegram IP detection."""
        # Known Telegram IPs
        assert is_telegram_ip("149.154.167.220") is True
        assert is_telegram_ip("91.108.4.5") is True

        # Non-Telegram IPs
        assert is_telegram_ip("8.8.8.8") is False
        assert is_telegram_ip("127.0.0.1") is False

    def test_is_http_transport(self):
        """Test detection of HTTP transport."""
        assert is_http_transport(b"GET / HTTP/1.1\r\n") is True
        assert is_http_transport(b"POST /api HTTP/1.1\r\n") is True
        assert is_http_transport(b"HEAD / HTTP/1.1\r\n") is True

        # MTProto init packet (should not be detected as HTTP)
        assert is_http_transport(b"\x00" * 64) is False

    def test_dc_from_init_invalid_size(self):
        """Test _dc_from_init with small data."""
        assert extract_dc_from_init(b"too small")[0] is None

    @patch("proxy.mtproto_parser.Cipher")
    def test_dc_from_init_success(self, mock_cipher):
        """Test successful DC extraction from init packet."""
        # Create 64-byte init packet
        data = bytearray(b'\x00' * 64)

        # Mock keystream - all zeros so XOR doesn't change values
        keystream = b"\x00" * 64
        mock_encryptor = MagicMock()
        mock_encryptor.update.return_value = keystream
        mock_encryptor.finalize.return_value = b""
        mock_cipher.return_value.encryptor.return_value = mock_encryptor

        # Set up key (offset 8, 32 bytes) and IV (offset 40, 16 bytes)
        # These are at correct positions per constants.py
        data[8:40] = b'\x00' * 32  # key
        data[40:56] = b'\x00' * 16  # iv

        # Prepare plain header at bytes 56:64
        # PROTO_OBFUSCATED = 0xefefefef
        # DC = 2 (positive = not media)
        proto = 0xefefefef
        dc_id = 2
        plain_header = struct.pack('<I', proto) + struct.pack('<h', dc_id) + b"\x00\x00"
        # Since keystream is zeros, data[56:64] = plain_header XOR 0 = plain_header
        data[56:64] = plain_header

        dc, is_media = extract_dc_from_init(bytes(data))

        assert dc == 2
        assert is_media is False

    @patch("proxy.mtproto_parser.Cipher")
    def test_patch_init_dc(self, mock_cipher):
        """Test patching DC in init packet."""
        # Create 64-byte init packet
        data = bytearray(b'\x00' * 64)

        # Set up key and IV
        data[8:40] = b'\x00' * 32  # key
        data[40:56] = b'\x00' * 16  # iv

        # Mock keystream - all zeros so XOR is identity
        keystream = b"\x00" * 64
        mock_encryptor = MagicMock()
        mock_encryptor.update.return_value = keystream
        mock_encryptor.finalize.return_value = b""
        mock_cipher.return_value.encryptor.return_value = mock_encryptor

        # Patching to DC 4
        patched = patch_init_dc(bytes(data), 4)

        # With zero keystream: patched[60] = ks[60] ^ new_dc[0] = 0 ^ 4 = 4
        # new_dc = struct.pack('<h', 4) = b'\x04\x00'
        assert patched[60] == 4
        assert patched[61] == 0
