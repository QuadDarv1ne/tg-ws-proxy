"""Tests for client_stats.py module."""

from __future__ import annotations

import time

from proxy.client_stats import (
    ClientInfo,
    ClientSession,
    ClientStatistics,
    ClientStatus,
    ClientType,
    detect_client_type,
    get_client_statistics,
)


class TestClientType:
    """Tests for ClientType enum."""

    def test_client_type_values(self):
        """Test ClientType enum values."""
        assert ClientType.TELEGRAM_DESKTOP.value == 1
        assert ClientType.TELEGRAM_ANDROID.value == 2
        assert ClientType.TELEGRAM_IOS.value == 3
        assert ClientType.TELEGRAM_WEB.value == 4
        assert ClientType.UNKNOWN.value == 5


class TestClientStatus:
    """Tests for ClientStatus enum."""

    def test_client_status_values(self):
        """Test ClientStatus enum values."""
        assert ClientStatus.CONNECTING.value == 1
        assert ClientStatus.ACTIVE.value == 2
        assert ClientStatus.IDLE.value == 3
        assert ClientStatus.DISCONNECTED.value == 4
        assert ClientStatus.BLOCKED.value == 5


class TestClientInfo:
    """Tests for ClientInfo dataclass."""

    def test_client_info_init(self):
        """Test ClientInfo initialization."""
        client = ClientInfo(ip='192.168.1.1', port=8080)

        assert client.ip == '192.168.1.1'
        assert client.port == 8080
        assert len(client.client_id) == 16
        assert client.client_type == ClientType.UNKNOWN
        assert client.status == ClientStatus.CONNECTING
        assert client.bytes_sent == 0
        assert client.bytes_received == 0

    def test_client_info_custom(self):
        """Test ClientInfo with custom values."""
        client = ClientInfo(
            ip='192.168.1.1',
            port=8080,
            client_type=ClientType.TELEGRAM_DESKTOP,
            dc_id=2,
        )

        assert client.client_type == ClientType.TELEGRAM_DESKTOP
        assert client.dc_id == 2

    def test_client_info_session_duration(self):
        """Test session_duration property."""
        client = ClientInfo(ip='192.168.1.1', port=8080)
        time.sleep(0.1)

        assert client.session_duration >= 0.1

    def test_client_info_idle_time(self):
        """Test idle_time property."""
        client = ClientInfo(ip='192.168.1.1', port=8080)
        time.sleep(0.1)

        assert client.idle_time >= 0.1

    def test_client_info_total_bytes(self):
        """Test total_bytes property."""
        client = ClientInfo(
            ip='192.168.1.1',
            port=8080,
            bytes_sent=100,
            bytes_received=200,
        )

        assert client.total_bytes == 300

    def test_client_info_is_active(self):
        """Test is_active property."""
        client = ClientInfo(ip='192.168.1.1', port=8080)

        assert client.is_active is True

    def test_client_info_is_active_false(self):
        """Test is_active property for idle client."""
        client = ClientInfo(ip='192.168.1.1', port=8080)
        # Manually set last_activity to past
        client.last_activity = time.time() - 600

        assert client.is_active is False

    def test_client_info_to_dict(self):
        """Test to_dict method."""
        client = ClientInfo(ip='192.168.1.1', port=8080)

        result = client.to_dict()

        assert result['ip'] == '192.168.1.1'
        assert result['port'] == 8080
        assert 'client_id' in result
        assert 'client_type' in result


class TestClientSession:
    """Tests for ClientSession dataclass."""

    def test_client_session_init(self):
        """Test ClientSession initialization."""
        session = ClientSession(client_id='test_id', start_time=time.time())

        assert session.client_id == 'test_id'
        assert session.end_time is None
        assert session.bytes_transferred == 0
        assert session.error_count == 0

    def test_client_session_duration(self):
        """Test duration property."""
        session = ClientSession(client_id='test_id', start_time=time.time())
        time.sleep(0.1)

        assert session.duration >= 0.1

    def test_client_session_duration_completed(self):
        """Test duration for completed session."""
        start = time.time()
        time.sleep(0.1)
        end = time.time()

        session = ClientSession(
            client_id='test_id',
            start_time=start,
            end_time=end,
        )

        assert session.duration >= 0.1

    def test_client_session_is_active(self):
        """Test is_active property."""
        session = ClientSession(client_id='test_id', start_time=time.time())

        assert session.is_active is True

    def test_client_session_is_active_false(self):
        """Test is_active for completed session."""
        session = ClientSession(
            client_id='test_id',
            start_time=time.time() - 100,
            end_time=time.time(),
        )

        assert session.is_active is False

    def test_client_session_to_dict(self):
        """Test to_dict method."""
        session = ClientSession(
            client_id='test_id',
            start_time=time.time(),
            dc_id=2,
        )

        result = session.to_dict()

        assert result['client_id'] == 'test_id'
        assert result['dc_id'] == 2
        assert 'is_active' in result


class TestClientStatistics:
    """Tests for ClientStatistics class."""

    def test_client_statistics_init(self):
        """Test ClientStatistics initialization."""
        stats = ClientStatistics()

        assert stats.max_clients == 1000
        assert stats.max_history == 100
        assert stats.total_connections == 0
        assert stats.peak_concurrent_clients == 0

    def test_register_client(self):
        """Test registering a client."""
        stats = ClientStatistics()

        client = stats.register_client('192.168.1.1', 8080)

        assert client is not None
        assert client.ip == '192.168.1.1'
        assert stats.total_connections == 1

    def test_register_client_existing(self):
        """Test registering existing client."""
        stats = ClientStatistics()
        
        stats.register_client('192.168.1.1', 8080)
        # Same IP:port should be treated as same client
        client = stats.get_client('192.168.1.1', 8080)
        
        # Client exists with initial values
        assert client is not None
        assert client.ip == '192.168.1.1'

    def test_unregister_client(self):
        """Test unregistering a client."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.unregister_client('192.168.1.1', 8080)

        assert stats.total_disconnections == 1

    def test_update_client_activity(self):
        """Test updating client activity."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.update_client_activity(
            '192.168.1.1',
            8080,
            bytes_sent=100,
            bytes_received=200,
        )

        client = stats.get_client('192.168.1.1', 8080)
        assert client.bytes_sent == 100
        assert client.bytes_received == 200

    def test_update_client_dc(self):
        """Test updating client DC."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.update_client_dc('192.168.1.1', 8080, 2)

        client = stats.get_client('192.168.1.1', 8080)
        assert client.dc_id == 2

    def test_record_client_error(self):
        """Test recording client error."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.record_client_error('192.168.1.1', 8080, 'Test error')

        sessions = stats.get_client_sessions('192.168.1.1:8080')
        assert sessions[-1].error_count == 1

    def test_get_client(self):
        """Test getting client."""
        stats = ClientStatistics()
        stats.register_client('192.168.1.1', 8080)

        client = stats.get_client('192.168.1.1', 8080)

        assert client is not None
        assert client.ip == '192.168.1.1'

    def test_get_client_missing(self):
        """Test getting missing client."""
        stats = ClientStatistics()

        client = stats.get_client('192.168.1.1', 8080)

        assert client is None

    def test_get_all_clients(self):
        """Test getting all clients."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.register_client('192.168.1.2', 8081)

        clients = stats.get_all_clients()

        assert len(clients) == 2

    def test_get_active_clients(self):
        """Test getting active clients."""
        stats = ClientStatistics()
        
        stats.register_client('192.168.1.1', 8080)
        stats.register_client('192.168.1.2', 8081)
        
        active = stats.get_active_clients()
        
        assert len(active) >= 1

    def test_get_statistics(self):
        """Test getting overall statistics."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.update_client_activity('192.168.1.1', 8080, bytes_sent=100)

        result = stats.get_statistics()

        assert result['total_clients'] == 1
        assert result['total_connections'] == 1
        assert result['total_bytes_sent'] == 100

    def test_get_top_clients_by_traffic(self):
        """Test getting top clients by traffic."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        stats.register_client('192.168.1.2', 8081)

        stats.update_client_activity('192.168.1.1', 8080, bytes_sent=1000)
        stats.update_client_activity('192.168.1.2', 8081, bytes_sent=500)

        top = stats.get_top_clients(limit=2, by='traffic')

        assert top[0].ip == '192.168.1.1'
        assert top[1].ip == '192.168.1.2'

    def test_get_top_clients_by_duration(self):
        """Test getting top clients by duration."""
        stats = ClientStatistics()

        stats.register_client('192.168.1.1', 8080)
        time.sleep(0.1)
        stats.register_client('192.168.1.2', 8081)

        top = stats.get_top_clients(limit=2, by='duration')

        # First client has longer duration
        assert top[0].ip == '192.168.1.1'

    def test_cleanup_inactive(self):
        """Test cleaning up inactive clients."""
        stats = ClientStatistics()

        client = stats.register_client('192.168.1.1', 8080)
        client.last_activity = time.time() - 7200  # 2 hours ago
        client.status = ClientStatus.DISCONNECTED

        removed = stats.cleanup_inactive(max_idle_seconds=3600)

        assert removed == 1


class TestGetClientStatistics:
    """Tests for get_client_statistics function."""

    def test_get_client_statistics_singleton(self):
        """Test get_client_statistics returns singleton."""
        stats1 = get_client_statistics()
        stats2 = get_client_statistics()

        assert stats1 is stats2

    def test_get_client_statistics_custom_max(self):
        """Test get_client_statistics with custom max."""
        import proxy.client_stats as cs_mod
        cs_mod._client_stats = None

        stats = get_client_statistics(max_clients=500)

        assert stats.max_clients == 500


class TestDetectClientType:
    """Tests for detect_client_type function."""

    def test_detect_client_type_none(self):
        """Test detection with None user agent."""
        result = detect_client_type(None)

        assert result == ClientType.UNKNOWN

    def test_detect_client_type_empty(self):
        """Test detection with empty user agent."""
        result = detect_client_type('')

        assert result == ClientType.UNKNOWN

    def test_detect_client_type_android(self):
        """Test detection of Android client."""
        result = detect_client_type('TelegramAndroid/1.0')

        assert result == ClientType.TELEGRAM_ANDROID

    def test_detect_client_type_ios(self):
        """Test detection of iOS client."""
        result = detect_client_type('Telegram-iOS/1.0')

        assert result == ClientType.TELEGRAM_IOS

    def test_detect_client_type_desktop(self):
        """Test detection of Desktop client."""
        result = detect_client_type('TelegramDesktop/1.0')

        assert result == ClientType.TELEGRAM_DESKTOP

    def test_detect_client_type_web(self):
        """Test detection of Web client."""
        result = detect_client_type('TelegramWeb/1.0')

        assert result == ClientType.TELEGRAM_WEB
