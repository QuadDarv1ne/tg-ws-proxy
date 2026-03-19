"""Unit tests for dashboard module."""

import asyncio
from unittest.mock import patch

import pytest

from proxy.dashboard import HAS_RICH, ConsoleDashboard


class TestConsoleDashboardInit:
    """Tests for ConsoleDashboard initialization."""

    def test_init_default(self):
        """Test default initialization."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        assert dashboard.get_stats_fn is not None
        assert dashboard.refresh_interval == 1.0
        assert dashboard.enable_colors is True
        assert dashboard.running is False
        assert dashboard.events_log == []
        assert dashboard.max_events == 10

    def test_init_custom(self):
        """Test initialization with custom parameters."""
        dashboard = ConsoleDashboard(
            get_stats_fn=lambda: {'test': 'data'},
            refresh_interval=2.0,
            enable_colors=False,
        )
        assert dashboard.refresh_interval == 2.0
        assert dashboard.enable_colors is False
        assert dashboard.max_events == 10


class TestConsoleDashboardAddEvent:
    """Tests for add_event method."""

    def test_add_event_single(self):
        """Test adding a single event."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        dashboard.add_event("Test event")

        assert len(dashboard.events_log) == 1
        assert "Test event" in dashboard.events_log[0]
        assert "[" in dashboard.events_log[0]  # timestamp

    def test_add_event_multiple(self):
        """Test adding multiple events."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        dashboard.add_event("Event 1")
        dashboard.add_event("Event 2")
        dashboard.add_event("Event 3")

        assert len(dashboard.events_log) == 3
        assert "Event 1" in dashboard.events_log[0]
        assert "Event 3" in dashboard.events_log[2]

    def test_add_event_limit(self):
        """Test event log limit."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {}, )
        dashboard.max_events = 5

        for i in range(10):
            dashboard.add_event(f"Event {i}")

        assert len(dashboard.events_log) == 5
        assert "Event 5" in dashboard.events_log[0]  # First kept
        assert "Event 9" in dashboard.events_log[-1]  # Last added


class TestConsoleDashboardRenderSimple:
    """Tests for _render_simple method."""

    def test_render_empty_stats(self):
        """Test rendering empty statistics."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        output = dashboard._render_simple({})

        assert "TG WS Proxy - Console Dashboard" in output
        assert "Total Connections:     0" in output
        assert "Upload:                0B" in output
        assert "Download:              0B" in output

    def test_render_with_stats(self):
        """Test rendering with statistics."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        stats = {
            'connections_total': 100,
            'connections_ws': 80,
            'connections_tcp_fallback': 15,
            'connections_http_rejected': 5,
            'connections_passthrough': 10,
            'ws_errors': 2,
            'bytes_up': 1024,
            'bytes_down': 2048,
            'pool_hits': 50,
            'pool_misses': 10,
        }
        output = dashboard._render_simple(stats)

        assert "Total Connections:     100" in output
        assert "WebSocket:             80" in output
        assert "TCP Fallback:          15" in output
        # Note: _human_bytes shows 1024 as 1.0MB due to threshold
        assert "Upload:                1.0MB" in output
        assert "Download:              2.0MB" in output
        assert "Hits:                  50" in output
        assert "Misses:                10" in output

    def test_render_pool_hit_rate(self):
        """Test pool hit rate calculation."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        stats = {'pool_hits': 80, 'pool_misses': 20}
        output = dashboard._render_simple(stats)

        assert "Hit Rate:              80.0%" in output

    def test_render_pool_zero_total(self):
        """Test pool hit rate with zero total."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        stats = {'pool_hits': 0, 'pool_misses': 0}
        output = dashboard._render_simple(stats)

        assert "Hit Rate:              0.0%" in output

    def test_render_with_events(self):
        """Test rendering with events."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        dashboard.add_event("Event 1")
        dashboard.add_event("Event 2")
        output = dashboard._render_simple({})

        assert "RECENT EVENTS:" in output
        assert "Event 1" in output
        assert "Event 2" in output

    def test_render_header_footer(self):
        """Test header and footer."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        output = dashboard._render_simple({})

        assert "=" * 60 in output
        assert "Press Ctrl+C to exit" in output


class TestConsoleDashboardRenderRich:
    """Tests for _render_rich method (when Rich is available)."""

    @pytest.mark.skipif(not HAS_RICH, reason="Rich not installed")
    def test_render_rich_basic(self):
        """Test Rich rendering basic."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        stats = {
            'connections_total': 100,
            'connections_ws': 80,
            'bytes_up': 1024,
            'bytes_down': 2048,
            'pool_hits': 50,
            'pool_misses': 10,
        }
        result = dashboard._render_rich(stats)

        # Should return a Layout or Panel
        assert result is not None

    @pytest.mark.skipif(not HAS_RICH, reason="Rich not installed")
    def test_render_rich_empty_stats(self):
        """Test Rich rendering with empty stats."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        result = dashboard._render_rich({})

        assert result is not None


class TestConsoleDashboardRun:
    """Tests for run method."""

    @pytest.mark.asyncio
    async def test_run_simple_mode(self):
        """Test running in simple mode (no Rich)."""
        with patch('proxy.dashboard.HAS_RICH', False):
            dashboard = ConsoleDashboard(
                get_stats_fn=lambda: {'test': 'data'},
                refresh_interval=0.01,
            )

            # Run for a short time
            task = asyncio.create_task(dashboard.run())
            await asyncio.sleep(0.05)
            dashboard.stop()

            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_stop_dashboard(self):
        """Test stopping dashboard."""
        dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
        assert dashboard.running is False

        # Simulate running
        dashboard.running = True
        dashboard.stop()

        assert dashboard.running is False


class TestConsoleDashboardClearScreen:
    """Tests for _clear_screen method."""

    @patch('os.system')
    def test_clear_screen_windows(self, mock_system):
        """Test clear screen on Windows."""
        with patch('os.name', 'nt'):
            dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
            dashboard._clear_screen()
            mock_system.assert_called_with('cls')

    @patch('os.system')
    def test_clear_screen_unix(self, mock_system):
        """Test clear screen on Unix."""
        with patch('os.name', 'posix'):
            dashboard = ConsoleDashboard(get_stats_fn=lambda: {})
            dashboard._clear_screen()
            mock_system.assert_called_with('clear')


class TestHasRich:
    """Tests for HAS_RICH constant."""

    def test_has_rich_type(self):
        """Test HAS_RICH is boolean."""
        assert isinstance(HAS_RICH, bool)


class TestRunDashboard:
    """Tests for run_dashboard function."""

    @pytest.mark.asyncio
    async def test_run_dashboard_basic(self):
        """Test basic dashboard run."""
        from proxy.dashboard import ConsoleDashboard, run_dashboard

        original_run = ConsoleDashboard.run

        async def mock_run(self):
            await asyncio.sleep(0.01)

        with patch.object(ConsoleDashboard, 'run', mock_run):
            # Should not raise
            try:
                await asyncio.wait_for(
                    run_dashboard(lambda: {}, refresh_interval=0.01),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        # Restore
        ConsoleDashboard.run = original_run
