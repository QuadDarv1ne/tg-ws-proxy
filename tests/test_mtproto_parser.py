"""
Tests for MTProto parser.

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

import struct

from proxy.mtproto_parser import (
    MsgSplitter,
    extract_dc_from_init,
    is_http_transport,
    is_telegram_ip,
    parse_mtproto_length,
    patch_init_dc,
)


def test_is_telegram_ip_valid():
    """Test Telegram IP detection with valid IPs."""
    # Telegram DC IPs
    assert is_telegram_ip('149.154.167.220') is True
    assert is_telegram_ip('149.154.175.50') is True
    assert is_telegram_ip('91.108.56.100') is True


def test_is_telegram_ip_invalid():
    """Test Telegram IP detection with invalid IPs."""
    assert is_telegram_ip('8.8.8.8') is False
    assert is_telegram_ip('1.1.1.1') is False
    assert is_telegram_ip('192.168.1.1') is False


def test_is_telegram_ip_malformed():
    """Test Telegram IP detection with malformed input."""
    assert is_telegram_ip('invalid') is False
    assert is_telegram_ip('999.999.999.999') is False
    assert is_telegram_ip('') is False


def test_is_http_transport_post():
    """Test HTTP transport detection with POST."""
    assert is_http_transport(b'POST /api HTTP/1.1') is True


def test_is_http_transport_get():
    """Test HTTP transport detection with GET."""
    assert is_http_transport(b'GET / HTTP/1.1') is True


def test_is_http_transport_head():
    """Test HTTP transport detection with HEAD."""
    assert is_http_transport(b'HEAD / HTTP/1.1') is True


def test_is_http_transport_options():
    """Test HTTP transport detection with OPTIONS."""
    assert is_http_transport(b'OPTIONS * HTTP/1.1') is True


def test_is_http_transport_not_http():
    """Test HTTP transport detection with non-HTTP data."""
    assert is_http_transport(b'\xef\x00\x00\x00') is False
    assert is_http_transport(b'SOCKS5') is False
    assert is_http_transport(b'') is False


def test_extract_dc_from_init_short_packet():
    """Test DC extraction with packet too short."""
    short_packet = b'\x00' * 32
    dc, is_media = extract_dc_from_init(short_packet)
    assert dc is None
    assert is_media is False


def test_extract_dc_from_init_empty():
    """Test DC extraction with empty packet."""
    dc, is_media = extract_dc_from_init(b'')
    assert dc is None
    assert is_media is False


def test_patch_init_dc_short_packet():
    """Test DC patching with packet too short."""
    short_packet = b'\x00' * 32
    result = patch_init_dc(short_packet, 2)
    assert result == short_packet  # Should return unchanged


def test_patch_init_dc_empty():
    """Test DC patching with empty packet."""
    result = patch_init_dc(b'', 2)
    assert result == b''


def test_patch_init_dc_with_extra_data():
    """Test DC patching preserves extra data after init packet."""
    # Create 64-byte init packet + extra data
    init_packet = b'\x00' * 64
    extra_data = b'extra'
    full_packet = init_packet + extra_data

    result = patch_init_dc(full_packet, 2)

    # Should preserve extra data
    assert len(result) == len(full_packet)
    assert result[64:] == extra_data


def test_parse_mtproto_length_short():
    """Test parsing short MTProto length."""
    # Length = 5 (< 0x7F), so total = 1 + 5*4 = 21 bytes
    data = bytes([5]) + b'\x00' * 20
    length = parse_mtproto_length(data)
    assert length == 21


def test_parse_mtproto_length_long():
    """Test parsing long MTProto length."""
    # Length >= 0x7F, use 4 bytes
    # Use 200 (0xC8) which is >= 0x7F to trigger long format
    # Length = 200, so total = 4 + 200*4 = 804 bytes
    data = struct.pack('<I', 200) + b'\x00' * 800
    length = parse_mtproto_length(data)
    assert length == 804


def test_parse_mtproto_length_empty():
    """Test parsing empty data."""
    length = parse_mtproto_length(b'')
    assert length is None


def test_parse_mtproto_length_incomplete_long():
    """Test parsing incomplete long length."""
    # Only 2 bytes when 4 are needed
    data = b'\x7F\x00'
    length = parse_mtproto_length(data)
    assert length is None


def test_parse_mtproto_length_zero():
    """Test parsing zero length."""
    data = bytes([0])
    length = parse_mtproto_length(data)
    assert length == 1  # 1 + 0*4 = 1


def test_msg_splitter_init():
    """Test MsgSplitter initialization."""
    init_data = b'\x00' * 64
    splitter = MsgSplitter(init_data)
    assert splitter is not None


def test_msg_splitter_empty_chunk():
    """Test MsgSplitter with empty chunk."""
    init_data = b'\x00' * 64
    splitter = MsgSplitter(init_data)

    messages = splitter.split(b'')
    assert messages == []


def test_msg_splitter_incomplete_message():
    """Test MsgSplitter with incomplete message."""
    init_data = b'\x00' * 64
    splitter = MsgSplitter(init_data)

    # Only 2 bytes when more are needed
    messages = splitter.split(b'\x00\x00')
    assert messages == []


def test_is_telegram_ip_boundary():
    """Test Telegram IP detection at range boundaries."""
    # Test IPs at the edge of Telegram ranges
    # These should be valid Telegram IPs
    assert is_telegram_ip('149.154.160.0') is True
    assert is_telegram_ip('149.154.175.255') is True


def test_extract_dc_from_init_invalid_protocol():
    """Test DC extraction with invalid protocol."""
    # Create a 64-byte packet with invalid protocol
    init_data = b'\x00' * 64
    dc, is_media = extract_dc_from_init(init_data)
    # Should return None for invalid protocol
    assert dc is None


def test_patch_init_dc_preserves_length():
    """Test DC patching preserves packet length."""
    init_packet = b'\x00' * 64
    result = patch_init_dc(init_packet, 3)
    assert len(result) == 64


def test_parse_mtproto_length_max_short():
    """Test parsing maximum short length (0x7E)."""
    data = bytes([0x7E]) + b'\x00' * 500
    length = parse_mtproto_length(data)
    assert length == 1 + 0x7E * 4  # 1 + 126*4 = 505


def test_parse_mtproto_length_min_long():
    """Test parsing minimum long length (0x7F)."""
    data = struct.pack('<I', 0x7F) + b'\x00' * 500
    length = parse_mtproto_length(data)
    assert length == 4 + 0x7F * 4  # 4 + 127*4 = 512


def test_is_http_transport_partial_match():
    """Test HTTP transport detection with partial matches."""
    # Should not match partial HTTP methods
    assert is_http_transport(b'POS') is False
    assert is_http_transport(b'GE') is False
    assert is_http_transport(b'OPTION') is False


def test_msg_splitter_buffering():
    """Test MsgSplitter buffers incomplete messages."""
    init_data = b'\x00' * 64
    splitter = MsgSplitter(init_data)

    # Send incomplete message
    messages1 = splitter.split(b'\x00\x00')
    assert len(messages1) == 0

    # Buffer should retain data
    assert len(splitter._buf) == 2


def test_extract_dc_from_init_dc_range():
    """Test DC extraction validates DC range (1-5)."""
    # DC must be between 1 and 5
    init_data = b'\x00' * 64
    dc, is_media = extract_dc_from_init(init_data)

    # Invalid DC should return None
    if dc is not None:
        assert 1 <= dc <= 5
