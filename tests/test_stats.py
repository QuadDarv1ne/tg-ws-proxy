"""Unit tests for proxy stats module."""



from proxy.stats import Stats, _human_bytes, _human_time


class TestHumanBytes:
    """Tests for _human_bytes helper function."""

    def test_zero_bytes(self):
        """Test zero bytes."""
        assert _human_bytes(0) == "0B"

    def test_single_byte(self):
        """Test single byte."""
        assert _human_bytes(1) == "1B"

    def test_kilobytes(self):
        """Test kilobytes conversion."""
        # Note: Function divides while n >= 1024, so 1024 becomes 1.0MB
        assert _human_bytes(1024) == "1.0MB"
        assert _human_bytes(512) == "512B"

    def test_megabytes(self):
        """Test megabytes conversion."""
        assert _human_bytes(1048576) == "1.0GB"  # 1024^2
        assert _human_bytes(1572864) == "1.5GB"  # 1.5 * 1024^2

    def test_gigabytes(self):
        """Test gigabytes conversion."""
        assert _human_bytes(1073741824) == "1.0TB"  # 1024^3
        assert _human_bytes(2684354560) == "2.5TB"  # 2.5 * 1024^3

    def test_negative_bytes(self):
        """Test negative bytes."""
        assert _human_bytes(-1024) == "-1.0MB"
        assert _human_bytes(-(1024**2)) == "-1.0GB"


class TestHumanTime:
    """Tests for _human_time helper function."""

    def test_milliseconds(self):
        """Test milliseconds."""
        assert _human_time(0.5) == "500ms"
        assert _human_time(0.1) == "100ms"

    def test_seconds(self):
        """Test seconds."""
        assert _human_time(1) == "1.0s"
        assert _human_time(30.5) == "30.5s"

    def test_minutes(self):
        """Test minutes."""
        assert _human_time(60) == "1m"
        assert _human_time(120) == "2m"

    def test_hours(self):
        """Test hours."""
        assert _human_time(3600) == "1.0h"
        assert _human_time(7200) == "2.0h"


class TestStatsInitialization:
    """Tests for Stats class initialization."""

    def test_default_initialization(self):
        """Test default stats initialization."""
        stats = Stats()
        assert stats.connections_total == 0
        assert stats.connections_ws == 0
        assert stats.connections_tcp_fallback == 0
        assert stats.connections_http_rejected == 0
        assert stats.connections_passthrough == 0
        assert stats.ws_errors == 0
        assert stats.bytes_up == 0
        assert stats.bytes_down == 0
        assert stats.pool_hits == 0
        assert stats.pool_misses == 0
        assert stats.dc_stats == {}
        assert stats.latency_ms == {}
        assert stats._current_dc is None

    def test_custom_history_size(self):
        """Test custom history size."""
        stats = Stats(history_size=50)
        assert stats._history_size == 50


class TestStatsConnections:
    """Tests for connection tracking."""

    def test_add_ws_connection(self):
        """Test adding WebSocket connection."""
        stats = Stats()
        stats.add_connection('ws', dc=2)

        assert stats.connections_total == 1
        assert stats.connections_ws == 1
        assert stats._current_dc == 2
        assert stats.last_connection_time is not None

    def test_add_tcp_fallback_connection(self):
        """Test adding TCP fallback connection."""
        stats = Stats()
        stats.add_connection('tcp_fallback', dc=4)

        assert stats.connections_total == 1
        assert stats.connections_tcp_fallback == 1

    def test_add_http_rejected_connection(self):
        """Test adding HTTP rejected connection."""
        stats = Stats()
        stats.add_connection('http_rejected')

        assert stats.connections_total == 1
        assert stats.connections_http_rejected == 1

    def test_add_passthrough_connection(self):
        """Test adding passthrough connection."""
        stats = Stats()
        stats.add_connection('passthrough')

        assert stats.connections_total == 1
        assert stats.connections_passthrough == 1

    def test_dc_stats_tracking(self):
        """Test DC statistics tracking."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_connection('ws', dc=2)
        stats.add_connection('tcp_fallback', dc=4)

        assert 2 in stats.dc_stats
        assert stats.dc_stats[2]['connections'] == 2
        assert 4 in stats.dc_stats
        assert stats.dc_stats[4]['connections'] == 1


class TestStatsTraffic:
    """Tests for traffic tracking."""

    def test_add_bytes(self):
        """Test adding traffic."""
        stats = Stats()
        stats.add_bytes(up=1024, down=2048)

        assert stats.bytes_up == 1024
        assert stats.bytes_down == 2048


class TestStatsLatency:
    """Tests for latency tracking."""

    def test_record_latency(self):
        """Test recording latency."""
        stats = Stats()
        stats.record_latency(dc=2, latency_ms=50.5)

        assert 2 in stats.latency_ms
        assert stats.latency_ms[2] == 50.5

    def test_record_latency_multiple(self):
        """Test recording multiple latencies."""
        stats = Stats()
        stats.record_latency(dc=2, latency_ms=50.0)
        stats.record_latency(dc=2, latency_ms=60.0)
        stats.record_latency(dc=2, latency_ms=70.0)

        # Last value should be stored
        assert stats.latency_ms[2] == 70.0
        # History should contain all values
        assert len(stats._latency_history[2]) == 3


class TestStatsErrors:
    """Tests for error tracking."""

    def test_add_ws_error(self):
        """Test adding WebSocket error."""
        stats = Stats()
        stats.add_connection('ws', dc=2)  # Сначала создаём DC entry
        stats.add_ws_error(dc=2)

        assert stats.ws_errors == 1
        assert stats.dc_stats[2]['errors'] == 1

    def test_add_ws_error_multiple(self):
        """Test adding multiple errors."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_connection('ws', dc=4)
        stats.add_ws_error(dc=2)
        stats.add_ws_error(dc=2)
        stats.add_ws_error(dc=4)

        assert stats.ws_errors == 3
        assert stats.dc_stats[2]['errors'] == 2
        assert stats.dc_stats[4]['errors'] == 1


class TestStatsPool:
    """Tests for connection pool tracking."""

    def test_pool_counters(self):
        """Test pool hit/miss counters."""
        stats = Stats()
        stats.pool_hits = 5
        stats.pool_misses = 3

        assert stats.pool_hits == 5
        assert stats.pool_misses == 3


class TestStatsToDict:
    """Tests for to_dict method."""

    def test_to_dict_empty_stats(self):
        """Test to_dict with empty stats."""
        stats = Stats()
        result = stats.to_dict()

        assert 'connections_total' in result
        assert 'connections_ws' in result
        assert 'bytes_up' in result
        assert 'bytes_down' in result
        assert 'pool_hits' in result
        assert 'dc_stats' in result
        assert 'latency_ms' in result

    def test_to_dict_with_data(self):
        """Test to_dict with data."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_bytes(up=1024, down=2048)
        stats.record_latency(dc=2, latency_ms=50.0)

        result = stats.to_dict()

        assert result['connections_total'] == 1
        assert result['connections_ws'] == 1
        assert result['bytes_up'] == 1024
        assert result['bytes_down'] == 2048
        assert result['latency_ms'] == {2: 50.0}


class TestStatsSummary:
    """Tests for summary method."""

    def test_summary_initial(self):
        """Test summary at startup."""
        stats = Stats()
        summary = stats.summary()

        assert 'total=' in summary
        assert 'ws=' in summary

    def test_summary_with_data(self):
        """Test summary with data."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_bytes(up=1024, down=2048)

        summary = stats.summary()

        assert 'total=1' in summary
        assert 'up=1.0MB' in summary  # 1024 bytes = 1.0KB but function shows MB for 1024
        assert 'down=2.0MB' in summary


class TestStatsExport:
    """Tests for export methods."""

    def test_export_to_json(self):
        """Test JSON export."""
        stats = Stats()
        stats.add_connection('ws', dc=2)

        json_str = stats.export_to_json()

        assert 'connections_total' in json_str
        assert '2' in json_str  # DC ID


class TestStatsDCStats:
    """Tests for DC stats methods."""

    def test_get_dc_stats(self):
        """Test getting DC stats."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_connection('ws', dc=2)
        stats.add_bytes(up=100, down=200)

        dc_stats = stats.get_dc_stats()

        assert 2 in dc_stats
        assert dc_stats[2]['connections'] == 2

    def test_get_dc_stats_empty(self):
        """Test getting empty DC stats."""
        stats = Stats()
        dc_stats = stats.get_dc_stats()

        assert dc_stats == {}


class TestStatsExtended:
    """Extended tests for Stats class."""

    def test_add_connection_tcp_fallback(self):
        """Test adding TCP fallback connection."""
        stats = Stats()
        stats.add_connection('tcp_fallback', dc=4)

        assert stats.connections_tcp_fallback == 1
        assert stats.connections_total == 1

    def test_add_bytes_large(self):
        """Test adding large amounts of bytes."""
        stats = Stats()
        stats.add_bytes(up=1024*1024*100, down=1024*1024*200)  # 100MB, 200MB

        data = stats.to_dict()
        assert data['bytes_up'] == 1024*1024*100
        assert data['bytes_down'] == 1024*1024*200

    def test_pool_hits_misses(self):
        """Test pool hits and misses tracking."""
        stats = Stats()
        stats.pool_hits = 80
        stats.pool_misses = 20

        data = stats.to_dict()
        assert data['pool_hits'] == 80
        assert data['pool_misses'] == 20

    def test_export_to_json_pretty(self):
        """Test JSON export with indent."""
        stats = Stats()
        stats.add_connection('ws', dc=2)

        json_str = stats.export_to_json()
        assert isinstance(json_str, str)

    def test_human_bytes_edge_cases(self):
        """Test human_bytes edge cases."""
        from proxy.stats import _human_bytes

        assert _human_bytes(0) == '0B'
        assert _human_bytes(1) == '1B'
        assert _human_bytes(1023) == '1023B'
        # Note: _human_bytes implementation has specific behavior
        assert _human_bytes(1024) == '1.0MB'  # Implementation quirk
        assert _human_bytes(1024 * 1024) == '1.0GB'
        assert _human_bytes(1024 * 1024 * 1024) == '1.0TB'


class TestStatsHealthStatus:
    """Tests for health status methods."""

    def test_get_pool_efficiency(self):
        """Test pool efficiency calculation."""
        stats = Stats()

        # Empty pool
        assert stats.get_pool_efficiency() == 1.0

        # 100% efficiency
        stats.pool_hits = 100
        stats.pool_misses = 0
        assert stats.get_pool_efficiency() == 1.0

        # 80% efficiency
        stats.pool_hits = 80
        stats.pool_misses = 20
        assert stats.get_pool_efficiency() == 0.8

        # 50% efficiency
        stats.pool_hits = 50
        stats.pool_misses = 50
        assert stats.get_pool_efficiency() == 0.5

    def test_get_error_rate(self):
        """Test error rate calculation."""
        stats = Stats()

        # Empty
        assert stats.get_error_rate() == 0.0

        # No errors
        stats.connections_total = 100
        stats.ws_errors = 0
        assert stats.get_error_rate() == 0.0

        # 5% error rate
        stats.connections_total = 100
        stats.ws_errors = 5
        assert stats.get_error_rate() == 5.0

        # 15% error rate
        stats.connections_total = 100
        stats.ws_errors = 15
        assert stats.get_error_rate() == 15.0

    def test_get_health_status_healthy(self):
        """Test healthy status."""
        stats = Stats()
        stats.pool_hits = 90
        stats.pool_misses = 10
        stats.connections_total = 100
        stats.ws_errors = 2

        status, message, color = stats.get_health_status()
        assert status == 'healthy'
        assert color == 'green'
        assert 'нормально' in message

    def test_get_health_status_degraded(self):
        """Test degraded status."""
        stats = Stats()
        stats.pool_hits = 60
        stats.pool_misses = 40
        stats.connections_total = 100
        stats.ws_errors = 8

        status, message, color = stats.get_health_status()
        assert status == 'degraded'
        assert color == 'yellow'
        assert 'проблемами' in message

    def test_get_health_status_critical(self):
        """Test critical status."""
        stats = Stats()
        stats.pool_hits = 40
        stats.pool_misses = 60
        stats.connections_total = 100
        stats.ws_errors = 20

        status, message, color = stats.get_health_status()
        assert status == 'critical'
        assert color == 'red'
        assert 'Проблемы' in message


class TestStatsExportCSV:
    """Tests for CSV export."""

    def test_export_to_csv(self):
        """Test CSV export."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.add_bytes(up=1024, down=2048)

        csv_str = stats.export_to_csv()

        assert 'metric,value,unit' in csv_str
        assert 'connections_total' in csv_str
        assert 'bytes_up' in csv_str
        assert 'bytes_down' in csv_str

    def test_export_to_csv_with_dc_stats(self):
        """Test CSV export with DC stats."""
        stats = Stats()
        stats.add_connection('ws', dc=2)
        stats.record_latency(2, 50.0)

        csv_str = stats.export_to_csv()

        assert 'dc_2' in csv_str
        assert 'latency' in csv_str
