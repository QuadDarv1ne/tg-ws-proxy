"""Unit tests for diagnostics module."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from proxy.diagnostics import (
    DC_DOMAINS,
    DC_IPS,
    DiagnosticResult,
    print_diagnostics_report,
    test_dns_resolve,
    test_tcp_connect,
    test_websocket_connect,
)


class TestDiagnosticResult:
    """Tests for DiagnosticResult dataclass."""

    def test_init_success(self):
        """Test successful result initialization."""
        result = DiagnosticResult(
            name="Test",
            success=True,
            latency_ms=50.5,
            details="OK"
        )
        assert result.name == "Test"
        assert result.success is True
        assert result.latency_ms == 50.5
        assert result.details == "OK"
        assert result.error is None

    def test_init_failure(self):
        """Test failed result initialization."""
        result = DiagnosticResult(
            name="Test",
            success=False,
            error="Connection failed"
        )
        assert result.name == "Test"
        assert result.success is False
        assert result.error == "Connection failed"
        assert result.latency_ms is None
        assert result.details is None

    def test_init_minimal(self):
        """Test minimal result initialization."""
        result = DiagnosticResult(name="Test", success=True)
        assert result.name == "Test"
        assert result.success is True
        assert result.latency_ms is None
        assert result.error is None
        assert result.details is None


@pytest.mark.asyncio
class TestTestTcpConnect:
    """Tests for test_tcp_connect function."""

    @patch('proxy.diagnostics.asyncio.open_connection')
    @patch('proxy.diagnostics.time.perf_counter')
    async def test_success(self, mock_time, mock_open):
        """Test successful TCP connection."""
        mock_time.side_effect = [0.0, 0.05]  # start, end (50ms)

        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.is_closing.return_value = False
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open.return_value = (mock_reader, mock_writer)

        result = await test_tcp_connect("127.0.0.1", 443)

        assert result.success is True
        assert result.name == "TCP 127.0.0.1:443"
        assert result.latency_ms is not None
        assert result.error is None

    @patch('proxy.diagnostics.asyncio.wait_for')
    async def test_timeout(self, mock_wait_for):
        """Test TCP connection timeout."""
        import asyncio
        mock_wait_for.side_effect = asyncio.TimeoutError()

        result = await test_tcp_connect("127.0.0.1", 443, timeout=0.001)

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.latency_ms is None

    @patch('proxy.diagnostics.asyncio.open_connection')
    async def test_connection_refused(self, mock_open):
        """Test TCP connection refused."""
        mock_open.side_effect = ConnectionRefusedError("Connection refused")

        result = await test_tcp_connect("127.0.0.1", 443)

        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
class TestTestDnsResolve:
    """Tests for test_dns_resolve function."""

    @patch('asyncio.get_event_loop')
    @patch('proxy.diagnostics.time.perf_counter')
    async def test_success(self, mock_time, mock_loop):
        """Test successful DNS resolution."""
        mock_time.side_effect = [0.0, 0.03]  # start, end (30ms)

        mock_resolver = AsyncMock()
        mock_resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('142.250.185.78', 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('142.250.185.79', 0)),
        ]
        mock_loop.return_value.getaddrinfo = mock_resolver

        result = await test_dns_resolve("google.com")

        assert result.success is True
        assert result.name == "DNS google.com"
        assert result.latency_ms is not None
        assert "142.250.185.78" in result.details

    @patch('asyncio.get_event_loop')
    async def test_failure(self, mock_loop):
        """Test failed DNS resolution."""
        mock_resolver = AsyncMock()
        mock_resolver.side_effect = socket.gaierror("Name or service not known")
        mock_loop.return_value.getaddrinfo = mock_resolver

        result = await test_dns_resolve("nonexistent.invalid")

        assert result.success is False
        assert result.error is not None


@pytest.mark.asyncio
class TestTestWebsocketConnect:
    """Tests for test_websocket_connect function."""

    @patch('proxy.diagnostics.asyncio.open_connection')
    @patch('proxy.diagnostics.time.perf_counter')
    async def test_success(self, mock_time, mock_open):
        """Test successful WebSocket connection."""
        mock_time.side_effect = [0.0, 0.1]  # start, end (100ms)

        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b'HTTP/1.1 101 Switching Protocols\r\n\r\n')
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open.return_value = (mock_reader, mock_writer)

        result = await test_websocket_connect("142.250.185.78", "test.domain.com")

        assert result.success is True
        assert result.name == "WS test.domain.com via 142.250.185.78"
        assert result.latency_ms is not None

    @patch('proxy.diagnostics.asyncio.open_connection')
    async def test_redirect_302(self, mock_open):
        """Test WebSocket 302 redirect."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b'HTTP/1.1 302 Found\r\n\r\n')
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open.return_value = (mock_reader, mock_writer)

        result = await test_websocket_connect("142.250.185.78", "test.domain.com")

        assert result.success is False
        assert "302" in result.error

    @patch('proxy.diagnostics.asyncio.open_connection')
    async def test_unexpected_response(self, mock_open):
        """Test unexpected WebSocket response."""
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(return_value=b'HTTP/1.1 404 Not Found\r\n\r\n')
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()
        mock_open.return_value = (mock_reader, mock_writer)

        result = await test_websocket_connect("142.250.185.78", "test.domain.com")

        assert result.success is False
        assert "Unexpected response" in result.error

    @patch('proxy.diagnostics.asyncio.wait_for')
    async def test_timeout(self, mock_wait_for):
        """Test WebSocket connection timeout."""
        import asyncio
        mock_wait_for.side_effect = asyncio.TimeoutError()

        result = await test_websocket_connect("142.250.185.78", "test.domain.com", timeout=0.001)

        assert result.success is False
        assert result.error == "Connection timeout"


class TestPrintDiagnosticsReport:
    """Tests for print_diagnostics_report function."""

    def test_print_empty(self, capsys):
        """Test printing empty results."""
        print_diagnostics_report([])
        captured = capsys.readouterr()
        assert "Diagnostics Report" in captured.out
        assert "No tests run" in captured.out

    def test_print_dns_results(self, capsys):
        """Test printing DNS results."""
        results = [
            DiagnosticResult(name="DNS test.com", success=True, latency_ms=30.5, details="1.2.3.4"),
        ]
        print_diagnostics_report(results)
        captured = capsys.readouterr()
        assert "DNS Resolution" in captured.out
        assert "✓" in captured.out
        assert "30.5" in captured.out

    def test_print_tcp_results(self, capsys):
        """Test printing TCP results."""
        results = [
            DiagnosticResult(name="TCP 1.2.3.4:443", success=True, latency_ms=50.0),
        ]
        print_diagnostics_report(results)
        captured = capsys.readouterr()
        assert "TCP Connectivity" in captured.out
        assert "✓" in captured.out

    def test_print_ws_results_success(self, capsys):
        """Test printing successful WebSocket results."""
        results = [
            DiagnosticResult(
                name="WS test.com via 1.2.3.4",
                success=True,
                latency_ms=100.0,
                details="Upgrade successful"
            ),
        ]
        print_diagnostics_report(results)
        captured = capsys.readouterr()
        assert "WebSocket Endpoints" in captured.out
        assert "✓" in captured.out
        assert "100.0" in captured.out

    def test_print_ws_results_failure(self, capsys):
        """Test printing failed WebSocket results."""
        results = [
            DiagnosticResult(
                name="WS test.com via 1.2.3.4",
                success=False,
                error="Connection refused"
            ),
        ]
        print_diagnostics_report(results)
        captured = capsys.readouterr()
        assert "WebSocket Endpoints" in captured.out
        assert "✗" in captured.out
        assert "Connection refused" in captured.out

    def test_print_mixed_results(self, capsys):
        """Test printing mixed results."""
        results = [
            DiagnosticResult(name="DNS test.com", success=True, latency_ms=30.0, details="1.2.3.4"),
            DiagnosticResult(name="TCP 1.2.3.4:443", success=False, error="Timeout"),
            DiagnosticResult(name="WS test.com via 1.2.3.4", success=True, latency_ms=100.0),
        ]
        print_diagnostics_report(results)
        captured = capsys.readouterr()
        assert "DNS Resolution" in captured.out
        assert "TCP Connectivity" in captured.out
        assert "WebSocket Endpoints" in captured.out
        assert "Summary:" in captured.out
        # 2/3 = 66.7%
        assert "66.7%" in captured.out


class TestDcConstants:
    """Tests for DC constants."""

    def test_dc_domains_structure(self):
        """Test DC_DOMAINS structure."""
        assert isinstance(DC_DOMAINS, dict)
        for dc_id in range(1, 6):
            assert dc_id in DC_DOMAINS
            assert isinstance(DC_DOMAINS[dc_id], list)
            assert len(DC_DOMAINS[dc_id]) >= 1

    def test_dc_ips_structure(self):
        """Test DC_IPS structure."""
        assert isinstance(DC_IPS, dict)
        for dc_id in range(1, 6):
            assert dc_id in DC_IPS
            assert isinstance(DC_IPS[dc_id], list)
            assert len(DC_IPS[dc_id]) >= 1
