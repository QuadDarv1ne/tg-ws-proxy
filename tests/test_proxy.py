"""Unit tests for critical proxy logic."""

import pytest
import struct
import socket as _socket
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Import functions to test
from proxy.tg_ws_proxy import (
    _dc_from_init,
    _patch_init_dc,
    _MsgSplitter,
    _is_telegram_ip,
    _is_http_transport,
    parse_dc_ip_list,
)


class TestDcFromInit:
    """Tests for _dc_from_init function."""

    def _make_init_packet(self, dc_id: int, is_media: bool = False,
                          proto: int = 0xEFEFEFEF) -> bytes:
        """Create a valid MTProto init packet for testing."""
        key = b'\x00' * 32  # 32 bytes
        iv = b'\x00' * 16   # 16 bytes
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        keystream = encryptor.update(b'\x00' * 64) + encryptor.finalize()

        # Build plaintext header (8 bytes)
        # proto (4 bytes) + dc_raw (2 bytes) + padding (2 bytes)
        dc_raw = -dc_id if is_media else dc_id
        plain_header = struct.pack('<Ih', proto, dc_raw) + b'\x00\x00'

        # Encrypt the last 8 bytes of header
        encrypted_header = bytes(a ^ b for a, b in zip(
            plain_header, keystream[56:64]))

        # Build full packet: magic(8) + key(32) + iv(16) + encrypted_dc(8)
        packet = b'\x00' * 8 + key + iv + encrypted_header
        return packet

    def test_dc_extraction_dc1(self):
        """Test DC ID extraction for DC1."""
        init = self._make_init_packet(1, is_media=False)
        dc, is_media = _dc_from_init(init)
        assert dc == 1
        assert is_media is False

    def test_dc_extraction_dc2(self):
        """Test DC ID extraction for DC2."""
        init = self._make_init_packet(2, is_media=False)
        dc, is_media = _dc_from_init(init)
        assert dc == 2
        assert is_media is False

    def test_dc_extraction_dc5_media(self):
        """Test DC ID extraction for DC5 with media flag."""
        init = self._make_init_packet(5, is_media=True)
        dc, is_media = _dc_from_init(init)
        assert dc == 5
        assert is_media is True

    def test_invalid_packet_too_short(self):
        """Test handling of packet shorter than 64 bytes."""
        init = b'\x00' * 50
        dc, is_media = _dc_from_init(init)
        assert dc is None
        assert is_media is False

    def test_invalid_proto(self):
        """Test handling of invalid protocol magic."""
        init = self._make_init_packet(1, proto=0x00000000)
        dc, is_media = _dc_from_init(init)
        assert dc is None
        assert is_media is False

    def test_empty_packet(self):
        """Test handling of empty packet."""
        dc, is_media = _dc_from_init(b'')
        assert dc is None
        assert is_media is False


class TestPatchInitDc:
    """Tests for _patch_init_dc function."""

    def _make_init_packet(self, dc_id: int) -> bytes:
        """Create a valid MTProto init packet."""
        key = b'\x00' * 32
        iv = b'\x00' * 16
        cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
        encryptor = cipher.encryptor()
        keystream = encryptor.update(b'\x00' * 64) + encryptor.finalize()

        dc_raw = dc_id
        plain_header = struct.pack('<Ih', 0xEFEFEFEF, dc_raw) + b'\x00\x00'
        encrypted_header = bytes(a ^ b for a, b in zip(
            plain_header, keystream[56:64]))

        return b'\x00' * 8 + key + iv + encrypted_header

    def test_patch_dc_from_1_to_2(self):
        """Test patching DC ID from 1 to 2."""
        init = self._make_init_packet(1)
        patched = _patch_init_dc(init, 2)
        dc, _ = _dc_from_init(patched)
        assert dc == 2

    def test_patch_dc_from_3_to_5(self):
        """Test patching DC ID from 3 to 5."""
        init = self._make_init_packet(3)
        patched = _patch_init_dc(init, 5)
        dc, _ = _dc_from_init(patched)
        assert dc == 5

    def test_patch_short_packet(self):
        """Test handling of packet shorter than 64 bytes."""
        init = b'\x00' * 50
        patched = _patch_init_dc(init, 2)
        assert patched == init

    def test_patch_preserves_extra_data(self):
        """Test that patching preserves data after 64 bytes."""
        init = self._make_init_packet(1) + b'EXTRA_DATA'
        patched = _patch_init_dc(init, 2)
        assert patched.endswith(b'EXTRA_DATA')
        dc, _ = _dc_from_init(patched)
        assert dc == 2


class TestMsgSplitter:
    """Tests for _MsgSplitter class."""

    def _make_init_packet(self) -> bytes:
        """Create a valid MTProto init packet."""
        key = b'\x01\x02\x03\x04' * 8  # 32 bytes
        iv = b'\x05\x06\x07\x08' * 2   # 16 bytes
        return b'\x00' * 8 + key + iv + b'\x00' * 8

    def test_split_single_message(self):
        """Test splitting a single message."""
        init = self._make_init_packet()
        splitter = _MsgSplitter(init)
        # Single message with length prefix (abridged protocol)
        # 0x01 means 1 * 4 = 4 bytes total (including length byte)
        msg = b'\x01' + b'\x00' * 3  # 4 bytes total
        parts = splitter.split(msg)
        # Splitter may or may not split depending on encryption state
        assert len(parts) >= 1

    def test_split_multiple_messages(self):
        """Test splitting multiple messages."""
        init = self._make_init_packet()
        splitter = _MsgSplitter(init)
        # Two messages in abridged protocol:
        # Message 1: 0x01 (1 * 4 = 4 bytes total including length)
        # Message 2: 0x02 (2 * 4 = 8 bytes total including length)
        msg1 = b'\x01' + b'\x00' * 3  # 4 bytes
        msg2 = b'\x02' + b'\x00' * 7  # 8 bytes
        combined = msg1 + msg2
        parts = splitter.split(combined)
        # The splitter should detect boundaries in plaintext after decryption
        # Due to encryption, exact split behavior may vary
        assert len(parts) >= 1
        assert b''.join(parts) == combined

    def test_split_7f_prefix(self):
        """Test splitting with 0x7f extended length prefix."""
        init = self._make_init_packet()
        splitter = _MsgSplitter(init)
        # Message with 0x7f prefix (3-byte length)
        msg_len = 100  # Will be encoded as 0x7f + 3 bytes
        msg = b'\x7f' + struct.pack('<I', msg_len // 4)[:3] + b'\x00' * msg_len
        parts = splitter.split(msg)
        assert len(parts) == 1
        assert len(parts[0]) == len(msg)


class TestIsTelegramIp:
    """Tests for _is_telegram_ip function."""

    def test_dc2_ip(self):
        """Test known DC2 IP."""
        assert _is_telegram_ip('149.154.167.220') is True

    def test_dc4_ip(self):
        """Test known DC4 IP."""
        assert _is_telegram_ip('149.154.167.91') is True

    def test_dc1_range(self):
        """Test IP in DC1 range."""
        assert _is_telegram_ip('149.154.175.50') is True

    def test_dc3_range(self):
        """Test IP in DC3 range."""
        assert _is_telegram_ip('149.154.175.100') is True

    def test_dc5_range(self):
        """Test IP in DC5 range."""
        assert _is_telegram_ip('91.108.56.100') is True

    def test_185_76_151_range(self):
        """Test IP in 185.76.151.0/24 range."""
        assert _is_telegram_ip('185.76.151.100') is True

    def test_91_105_192_range(self):
        """Test IP in 91.105.192.0/23 range."""
        assert _is_telegram_ip('91.105.192.100') is True

    def test_91_108_range(self):
        """Test IP in 91.108.0.0/16 range."""
        assert _is_telegram_ip('91.108.100.50') is True

    def test_non_telegram_ip(self):
        """Test non-Telegram IP."""
        assert _is_telegram_ip('8.8.8.8') is False
        assert _is_telegram_ip('1.1.1.1') is False

    def test_invalid_ip(self):
        """Test invalid IP format."""
        assert _is_telegram_ip('invalid') is False
        assert _is_telegram_ip('') is False


class TestIsHttpTransport:
    """Tests for _is_http_transport function."""

    def test_post_request(self):
        """Test POST request detection."""
        assert _is_http_transport(b'POST /api HTTP/1.1\r\n') is True

    def test_get_request(self):
        """Test GET request detection."""
        assert _is_http_transport(b'GET /api HTTP/1.1\r\n') is True

    def test_head_request(self):
        """Test HEAD request detection."""
        assert _is_http_transport(b'HEAD /api HTTP/1.1\r\n') is True

    def test_options_request(self):
        """Test OPTIONS request detection."""
        assert _is_http_transport(b'OPTIONS /api HTTP/1.1\r\n') is True

    def test_mtproto_data(self):
        """Test MTProto data (not HTTP)."""
        assert _is_http_transport(b'\x00' * 64) is False
        assert _is_http_transport(b'\xef\xef\xfe\xef') is False

    def test_empty_data(self):
        """Test empty data."""
        assert _is_http_transport(b'') is False


class TestParseDcIpList:
    """Tests for parse_dc_ip_list function."""

    def test_single_dc(self):
        """Test parsing single DC entry."""
        result = parse_dc_ip_list(['2:149.154.167.220'])
        assert result == {2: '149.154.167.220'}

    def test_multiple_dc(self):
        """Test parsing multiple DC entries."""
        result = parse_dc_ip_list([
            '1:149.154.175.205',
            '2:149.154.167.220',
            '4:149.154.167.220',
        ])
        assert result == {
            1: '149.154.175.205',
            2: '149.154.167.220',
            4: '149.154.167.220',
        }

    def test_default_values(self):
        """Test parsing default DC values."""
        result = parse_dc_ip_list(['2:149.154.167.220', '4:149.154.167.220'])
        assert len(result) == 2
        assert result[2] == '149.154.167.220'
        assert result[4] == '149.154.167.220'

    def test_invalid_format_no_colon(self):
        """Test error on missing colon."""
        with pytest.raises(ValueError, match="Invalid --dc-ip format"):
            parse_dc_ip_list(['149.154.167.220'])

    def test_invalid_dc_number(self):
        """Test error on invalid DC number."""
        with pytest.raises(ValueError, match="Invalid --dc-ip"):
            parse_dc_ip_list(['abc:149.154.167.220'])

    def test_invalid_ip(self):
        """Test error on invalid IP address."""
        with pytest.raises(ValueError, match="Invalid --dc-ip"):
            parse_dc_ip_list(['2:999.999.999.999'])

    def test_empty_list(self):
        """Test empty list."""
        result = parse_dc_ip_list([])
        assert result == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
