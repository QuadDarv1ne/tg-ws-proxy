"""Tests for SOCKS5 negotiation and request parsing."""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock
from proxy.tg_ws_proxy import ProxyServer

@pytest.fixture
def proxy_server():
    return ProxyServer(dc_opt={2: "149.154.167.220"})

@pytest.fixture
def mock_streams():
    reader = AsyncMock(spec=asyncio.StreamReader)
    writer = AsyncMock(spec=asyncio.StreamWriter)
    return reader, writer

class TestSocks5Negotiation:
    """Tests for Step 1: _negotiate_socks5."""

    @pytest.mark.asyncio
    async def test_negotiate_no_auth_success(self, proxy_server, mock_streams):
        reader, writer = mock_streams
        reader.readexactly.side_effect = [
            b'\x05\x01',  # SOCKS5, 1 method
            b'\x00'       # Method 0 (No Auth)
        ]
        
        result = await proxy_server._negotiate_socks5(reader, writer, "[TEST]")
        
        assert result is True
        writer.write.assert_called_with(b'\x05\x00')

    @pytest.mark.asyncio
    async def test_negotiate_wrong_version(self, proxy_server, mock_streams):
        reader, writer = mock_streams
        reader.readexactly.return_value = b'\x04\x01' # SOCKS4
        
        result = await proxy_server._negotiate_socks5(reader, writer, "[TEST]")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_negotiate_auth_required_success(self, mock_streams):
        server = ProxyServer(dc_opt={}, auth_required=True, 
                             auth_credentials={'username': 'user', 'password': 'pass'})
        reader, writer = mock_streams
        reader.readexactly.side_effect = [
            b'\x05\x01',  # SOCKS5, 1 method
            b'\x02',      # Method 2 (Username/Password)
            b'\x01',      # Auth version 1
            b'\x04',      # User length 4
            b'user',      # Username
            b'\x04',      # Pass length 4
            b'pass'       # Password
        ]
        
        result = await server._negotiate_socks5(reader, writer, "[TEST]")
        
        assert result is True
        # First write is method selection, second is auth result
        writer.write.assert_any_call(b'\x05\x02')
        writer.write.assert_any_call(b'\x01\x00')

class TestSocks5Request:
    """Tests for Step 2: _read_socks5_request."""

    @pytest.mark.asyncio
    async def test_read_request_ipv4(self, proxy_server, mock_streams):
        reader, writer = mock_streams
        reader.readexactly.side_effect = [
            b'\x05\x01\x00\x01', # VER=5, CMD=1 (CONNECT), RSV=0, ATYP=1 (IPv4)
            b'\x7f\x00\x00\x01', # 127.0.0.1
            b'\x04\x38'          # Port 1080
        ]
        
        dst, port = await proxy_server._read_socks5_request(reader, writer, "[TEST]")
        
        assert dst == "127.0.0.1"
        assert port == 1080

    @pytest.mark.asyncio
    async def test_read_request_domain(self, proxy_server, mock_streams):
        reader, writer = mock_streams
        reader.readexactly.side_effect = [
            b'\x05\x01\x00\x03', # ATYP=3 (Domain)
            b'\x0b',             # Length 11
            b'example.com',      # Domain
            b'\x00\x50'          # Port 80
        ]
        
        dst, port = await proxy_server._read_socks5_request(reader, writer, "[TEST]")
        
        assert dst == "example.com"
        assert port == 80
