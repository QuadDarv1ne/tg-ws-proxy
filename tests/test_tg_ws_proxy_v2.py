from unittest.mock import MagicMock, patch

import pytest

from proxy.mtproto_parser import (
    extract_dc_from_init,
    is_telegram_ip,
    patch_init_dc,
)


@pytest.mark.parametrize("ip,expected", [
    ("149.154.167.220", True),
    ("91.108.56.100", True),
    ("8.8.8.8", False),
    ("127.0.0.1", False),
])
def test_is_telegram_ip(ip, expected):
    """Test Telegram IP detection logic."""
    assert is_telegram_ip(ip) == expected


class TestDcHandling:
    """Tests for DC detection and patching."""

    def test_dc_from_init_fail(self):
        """Test DC detection with invalid data."""
        assert extract_dc_from_init(b'too short') == (None, False)

    def test_patch_init_dc(self):
        """Test patching DC ID in init packet."""
        init_data = bytearray(b'A' * 64)

        with patch('proxy.mtproto_parser.Cipher') as mock_cipher:
            mock_enc = MagicMock()
            mock_cipher.return_value.encryptor.return_value = mock_enc
            # Mock keystream
            mock_enc.update.return_value = b'\x00' * 64

            patched = patch_init_dc(bytes(init_data), 2)

            # In our mock (keystream 0), patched bytes should be XORed with 2
            # Byte 60-61 are DC offset
            assert len(patched) == 64
            # We check if the function attempted to XOR the correct offsets
            assert patched[60] != init_data[60] or patched[61] != init_data[61]


class TestHandleClientIntegrated:
    """Integration tests for _handle_client SOCKS5 flow."""
    # Tests removed: implementation changed (no auth support in current version)
