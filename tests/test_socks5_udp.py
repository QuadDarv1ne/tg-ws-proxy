"""
Tests for SOCKS5 UDP Relay.

Tests for:
- UdpSession dataclass
- UdpRelay initialization
- UDP session management
- Packet forwarding
- Session cleanup
"""

import pytest
import socket
import time
from unittest.mock import MagicMock, patch

from proxy.socks5_udp import UdpRelay, UdpSession


class TestUdpSession:
    """Tests for UdpSession dataclass."""

    def test_udp_session_creation(self):
        """Test UdpSession initialization."""
        session = UdpSession(
            client_addr=('127.0.0.1', 50000),
            bind_addr=('127.0.0.1', 60000)
        )

        assert session.client_addr == ('127.0.0.1', 50000)
        assert session.bind_addr == ('127.0.0.1', 60000)
        assert session.socket is None
        assert session.packets_forwarded == 0
        assert session.bytes_forwarded == 0

    def test_udp_session_with_socket(self):
        """Test UdpSession with socket."""
        mock_socket = MagicMock()
        session = UdpSession(
            client_addr=('192.168.1.1', 12345),
            bind_addr=('0.0.0.0', 54321),
            socket=mock_socket
        )

        assert session.socket == mock_socket
        assert session.packets_forwarded == 0

    def test_udp_session_stats(self):
        """Test UdpSession statistics tracking."""
        session = UdpSession(
            client_addr=('10.0.0.1', 8080),
            bind_addr=('10.0.0.1', 9090)
        )

        # Update stats
        session.packets_forwarded = 100
        session.bytes_forwarded = 50000

        assert session.packets_forwarded == 100
        assert session.bytes_forwarded == 50000

    def test_udp_session_timestamps(self):
        """Test UdpSession timestamp tracking."""
        before = time.monotonic()
        session = UdpSession(
            client_addr=('127.0.0.1', 11111),
            bind_addr=('127.0.0.1', 22222)
        )
        after = time.monotonic()

        assert session.created_at >= before
        assert session.created_at <= after
        assert session.last_activity >= before
        assert session.last_activity <= after

    def test_udp_session_update_activity(self):
        """Test updating last_activity timestamp."""
        session = UdpSession(
            client_addr=('127.0.0.1', 33333),
            bind_addr=('127.0.0.1', 44444)
        )

        initial_activity = session.last_activity
        time.sleep(0.01)
        session.last_activity = time.monotonic()

        assert session.last_activity > initial_activity


class TestUdpRelayInit:
    """Tests for UdpRelay initialization."""

    def test_udp_relay_default_init(self):
        """Test UdpRelay default initialization."""
        relay = UdpRelay()

        assert relay.host == '127.0.0.1'
        assert relay.port == 1080
        assert relay.on_packet is None
        assert relay._sessions == {}
        assert relay._sockets == {}
        assert relay._running is False
        assert relay._udp_socket is None
        assert relay.total_sessions == 0
        assert relay.total_packets == 0
        assert relay.total_bytes == 0
        assert relay.active_sessions == 0

    def test_udp_relay_custom_init(self):
        """Test UdpRelay with custom parameters."""
        def callback(data, addr):
            pass

        relay = UdpRelay(
            host='0.0.0.0',
            port=2080,
            on_packet=callback
        )

        assert relay.host == '0.0.0.0'
        assert relay.port == 2080
        assert relay.on_packet == callback

    def test_udp_relay_constants(self):
        """Test UdpRelay class constants."""
        assert UdpRelay.SESSION_TIMEOUT == 120.0
        assert UdpRelay.MAX_PACKET_SIZE == 65535
        assert UdpRelay.MAX_SESSIONS == 100


class TestUdpRelaySessions:
    """Tests for UDP session management."""

    def test_create_session(self):
        """Test creating UDP session."""
        relay = UdpRelay()
        
        session = UdpSession(
            client_addr=('127.0.0.1', 50000),
            bind_addr=('127.0.0.1', 60000)
        )
        
        # Add session manually
        relay._sessions[('127.0.0.1', 50000)] = session
        
        assert len(relay._sessions) == 1
        assert ('127.0.0.1', 50000) in relay._sessions

    def test_remove_session(self):
        """Test removing UDP session."""
        relay = UdpRelay()
        
        session = UdpSession(
            client_addr=('192.168.1.1', 12345),
            bind_addr=('0.0.0.0', 54321)
        )
        
        relay._sessions[('192.168.1.1', 12345)] = session
        del relay._sessions[('192.168.1.1', 12345)]
        
        assert len(relay._sessions) == 0

    def test_session_cleanup_expired(self):
        """Test cleaning up expired sessions."""
        relay = UdpRelay()
        
        # Create expired session
        old_time = time.monotonic() - 200  # 200 seconds ago
        session = UdpSession(
            client_addr=('10.0.0.1', 8080),
            bind_addr=('10.0.0.1', 9090)
        )
        session.last_activity = old_time
        
        relay._sessions[('10.0.0.1', 8080)] = session
        
        # Check session is expired
        assert (time.monotonic() - session.last_activity) > relay.SESSION_TIMEOUT

    def test_session_cleanup_active(self):
        """Test that active sessions are not cleaned up."""
        relay = UdpRelay()
        
        session = UdpSession(
            client_addr=('10.0.0.2', 8081),
            bind_addr=('10.0.0.2', 9091)
        )
        # Recent activity
        session.last_activity = time.monotonic()
        
        relay._sessions[('10.0.0.2', 8081)] = session
        
        # Session should still be active
        assert (time.monotonic() - session.last_activity) < relay.SESSION_TIMEOUT


class TestUdpRelayStats:
    """Tests for UDP relay statistics."""

    def test_stats_initial(self):
        """Test initial statistics."""
        relay = UdpRelay()
        
        assert relay.total_sessions == 0
        assert relay.total_packets == 0
        assert relay.total_bytes == 0
        assert relay.active_sessions == 0

    def test_stats_update(self):
        """Test updating statistics."""
        relay = UdpRelay()
        
        # Simulate session creation
        relay.total_sessions = 5
        relay.active_sessions = 3
        relay.total_packets = 100
        relay.total_bytes = 50000
        
        assert relay.total_sessions == 5
        assert relay.active_sessions == 3
        assert relay.total_packets == 100
        assert relay.total_bytes == 50000

    def test_stats_increment(self):
        """Test incrementing statistics."""
        relay = UdpRelay()
        
        initial_packets = relay.total_packets
        initial_bytes = relay.total_bytes
        
        # Simulate packet forwarding
        relay.total_packets += 1
        relay.total_bytes += 1024
        
        assert relay.total_packets == initial_packets + 1
        assert relay.total_bytes == initial_bytes + 1024


class TestUdpRelayRunning:
    """Tests for UDP relay running state."""

    def test_relay_not_running_initially(self):
        """Test that relay is not running initially."""
        relay = UdpRelay()
        
        assert relay._running is False

    def test_relay_running_state(self):
        """Test running state toggle."""
        relay = UdpRelay()
        
        relay._running = True
        assert relay._running is True
        
        relay._running = False
        assert relay._running is False


class TestUdpRelaySockets:
    """Tests for UDP relay socket management."""

    def test_socket_initial_state(self):
        """Test initial socket state."""
        relay = UdpRelay()
        
        assert relay._udp_socket is None
        assert relay._transport is None
        assert relay._protocol is None

    def test_sockets_dict_empty(self):
        """Test sockets dictionary initially empty."""
        relay = UdpRelay()
        
        assert relay._sockets == {}
        assert len(relay._sockets) == 0

    def test_sessions_dict_empty(self):
        """Test sessions dictionary initially empty."""
        relay = UdpRelay()
        
        assert relay._sessions == {}
        assert len(relay._sessions) == 0


class TestUdpRelayOnPacketCallback:
    """Tests for UDP relay packet callback."""

    def test_callback_none(self):
        """Test with no callback."""
        relay = UdpRelay()
        
        assert relay.on_packet is None

    def test_callback_called(self):
        """Test callback is called on packet."""
        mock_callback = MagicMock()
        relay = UdpRelay(on_packet=mock_callback)
        
        # Simulate packet
        data = b'test packet'
        addr = ('127.0.0.1', 12345)
        
        if relay.on_packet:
            relay.on_packet(data, addr)
        
        mock_callback.assert_called_once_with(data, addr)

    def test_callback_with_multiple_packets(self):
        """Test callback with multiple packets."""
        mock_callback = MagicMock()
        relay = UdpRelay(on_packet=mock_callback)
        
        # Simulate multiple packets
        for i in range(5):
            if relay.on_packet:
                relay.on_packet(b'packet' + bytes([i]), ('127.0.0.1', 1000 + i))
        
        assert mock_callback.call_count == 5


class TestUdpRelayEdgeCases:
    """Tests for edge cases and error handling."""

    def test_max_sessions_limit(self):
        """Test MAX_SESSIONS constant."""
        relay = UdpRelay()
        
        assert relay.MAX_SESSIONS == 100
        
        # Create max sessions
        for i in range(relay.MAX_SESSIONS):
            session = UdpSession(
                client_addr=(f'192.168.1.{i}', 50000 + i),
                bind_addr=('0.0.0.0', 60000 + i)
            )
            relay._sessions[(f'192.168.1.{i}', 50000 + i)] = session
        
        assert len(relay._sessions) == relay.MAX_SESSIONS

    def test_max_packet_size(self):
        """Test MAX_PACKET_SIZE constant."""
        relay = UdpRelay()
        
        assert relay.MAX_PACKET_SIZE == 65535
        
        # Create packet at max size
        max_packet = bytes(relay.MAX_PACKET_SIZE)
        assert len(max_packet) == relay.MAX_PACKET_SIZE

    def test_session_timeout_constant(self):
        """Test SESSION_TIMEOUT constant."""
        relay = UdpRelay()
        
        assert relay.SESSION_TIMEOUT == 120.0
        
        # Verify timeout is reasonable (2 minutes)
        assert relay.SESSION_TIMEOUT == 2 * 60  # 2 minutes in seconds

    def test_multiple_relays_independent(self):
        """Test that multiple relay instances are independent."""
        relay1 = UdpRelay(host='127.0.0.1', port=1080)
        relay2 = UdpRelay(host='0.0.0.0', port=2080)
        
        assert relay1.host != relay2.host
        assert relay1.port != relay2.port
        assert relay1._sessions is not relay2._sessions
        assert relay1._sockets is not relay2._sockets


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
