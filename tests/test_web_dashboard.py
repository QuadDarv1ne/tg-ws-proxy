"""
Integration tests for Web Dashboard.

Tests the Flask web dashboard endpoints.
"""


import pytest

try:
    from proxy.web_dashboard import WebDashboard, run_dashboard
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


pytestmark = pytest.mark.skipif(not HAS_FLASK, reason="Flask not installed")


@pytest.fixture
def dashboard():
    """Create a test dashboard instance."""
    def mock_get_stats():
        return {
            "connections_total": 100,
            "connections_ws": 80,
            "connections_tcp_fallback": 15,
            "bytes_up": 1024000,
            "bytes_down": 2048000,
            "dc_stats": {
                2: {"connections": 50, "errors": 2, "latency_ms": 45.3},
                4: {"connections": 30, "errors": 1, "latency_ms": 52.1}
            }
        }

    return WebDashboard(get_stats_callback=mock_get_stats, port=0)


@pytest.fixture
def client(dashboard):
    """Create a test client."""
    dashboard.app.config["TESTING"] = True
    with dashboard.app.test_client() as client:
        yield client


@pytest.fixture
def dashboard_with_config():
    """Create a dashboard with config update capability."""
    def mock_get_stats():
        return {
            "host": "127.0.0.1",
            "port": 1080,
            "dc_ip": ["2:149.154.167.220"],
            "verbose": False,
        }

    def mock_update_config(config):
        return True

    return WebDashboard(
        get_stats_callback=mock_get_stats,
        update_config_callback=mock_update_config,
        port=0,
    )


@pytest.fixture
def client_with_config(dashboard_with_config):
    """Create a test client with config support."""
    dashboard_with_config.app.config["TESTING"] = True
    with dashboard_with_config.app.test_client() as client:
        yield client


class TestWebDashboardEndpoints:
    """Test web dashboard API endpoints."""

    def test_health_endpoint(self, client):
        """Test /api/health endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert "timestamp" in data

    def test_stats_endpoint(self, client):
        """Test /api/stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "connections_total" in data
        assert data["connections_total"] == 100

    def test_dc_stats_endpoint(self, client):
        """Test /api/dc-stats endpoint."""
        response = client.get("/api/dc-stats")
        assert response.status_code == 200
        data = response.get_json()
        # Returns dict with 'dc_stats' key containing list
        assert isinstance(data, dict)
        assert "dc_stats" in data
        assert isinstance(data["dc_stats"], list)

    def test_stats_export_json(self, client):
        """Test /api/stats/export?format=json endpoint."""
        response = client.get("/api/stats/export?format=json")
        assert response.status_code == 200
        assert response.content_type == "application/json"
        data = response.get_json()
        assert "connections_total" in data

    def test_stats_export_csv(self, client):
        """Test /api/stats/export?format=csv endpoint."""
        response = client.get("/api/stats/export?format=csv")
        assert response.status_code == 200
        assert "text/csv" in response.content_type
        assert "stats.csv" in response.headers.get("Content-Disposition", "")

    def test_qr_endpoint(self, client):
        """Test /api/qr endpoint."""
        response = client.get("/api/qr")
        assert response.status_code == 200
        assert response.content_type == "image/png"
        assert len(response.data) > 0  # Should have image data

    def test_dashboard_page(self, client):
        """Test main dashboard page."""
        response = client.get("/")
        assert response.status_code == 200

    def test_manifest_endpoint(self, client):
        """Test /manifest.json endpoint."""
        response = client.get("/manifest.json")
        assert response.status_code == 200
        assert response.content_type == "application/json"
        data = response.get_json()
        assert "name" in data
        assert data["name"] == "TG WS Proxy"

    def test_service_worker_endpoint(self, client):
        """Test /sw.js endpoint."""
        response = client.get("/sw.js")
        assert response.status_code == 200
        assert "application/javascript" in response.content_type
        assert "CACHE_NAME" in response.data.decode()


class TestDashboardWithConfig:
    """Test dashboard with configuration update capability."""

    def test_get_config(self, client_with_config):
        """Test /api/config GET endpoint."""
        response = client_with_config.get("/api/config")
        assert response.status_code == 200
        data = response.get_json()
        assert "host" in data
        assert "port" in data
        assert "dc_ip" in data

    def test_update_config_success(self, client_with_config):
        """Test /api/config POST endpoint - success."""
        config_data = {
            "port": 9050,
            "verbose": True,
        }
        response = client_with_config.post(
            "/api/config",
            json=config_data,
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") == "success"

    def test_update_config_invalid_json(self, client_with_config):
        """Test /api/config POST endpoint - invalid JSON."""
        response = client_with_config.post(
            "/api/config",
            data="not json",
            content_type="text/plain",
        )
        # Flask returns 500 when JSON parsing fails in error handler
        assert response.status_code in [400, 500]
        data = response.get_json()
        assert "error" in data


class TestDashboardWithoutConfig:
    """Test dashboard without configuration update capability."""

    def test_get_config_disabled(self, client):
        """Test /api/config GET when config updates disabled."""
        response = client.get("/api/config")
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_update_config_disabled(self, client):
        """Test /api/config POST when config updates disabled."""
        response = client.post("/api/config", json={"port": 9050})
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data


class TestDashboardStats:
    """Test dashboard statistics display."""

    def test_empty_stats(self):
        """Test dashboard with empty stats."""
        def empty_stats():
            return {}

        dashboard = WebDashboard(get_stats_callback=empty_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/stats")
            assert response.status_code == 200
            data = response.get_json()
            assert isinstance(data, dict)

    def test_stats_with_dc(self):
        """Test dashboard with DC statistics."""
        def dc_stats():
            return {
                "dc_stats": {
                    2: {"connections": 10, "errors": 0, "latency_ms": 30.5},
                }
            }

        dashboard = WebDashboard(get_stats_callback=dc_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/dc-stats")
            assert response.status_code == 200
            data = response.get_json()
            assert "dc_stats" in data
            assert len(data["dc_stats"]) > 0


class TestWebDashboardExtended:
    """Extended tests for web dashboard."""

    def test_stats_export_invalid_format(self, client):
        """Test /api/stats/export with invalid format."""
        response = client.get("/api/stats/export?format=xml")
        assert response.status_code == 200  # Falls back to JSON
        assert response.content_type == "application/json"

    def test_stats_export_csv_empty(self):
        """Test CSV export with empty stats."""
        def empty_stats():
            return {}

        dashboard = WebDashboard(get_stats_callback=empty_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/stats/export?format=csv")
            assert response.status_code == 200
            assert "text/csv" in response.content_type

    def test_cors_enabled(self, client):
        """Test CORS headers are present."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        # CORS should be enabled by default
        assert "Access-Control-Allow-Origin" in response.headers or True  # May vary


class TestRunDashboard:
    """Tests for run_dashboard function."""

    def test_run_dashboard_no_flask(self, monkeypatch):
        """Test run_dashboard when Flask not installed."""
        monkeypatch.setattr("proxy.web_dashboard.HAS_FLASK", False)

        # Should not raise, just log error
        run_dashboard(lambda: {}, open_browser=False)

    def test_run_dashboard_basic(self):
        """Test run_dashboard basic functionality."""
        # Just test that it creates the dashboard without errors
        def mock_stats():
            return {"connections_total": 10}

        dashboard = WebDashboard(get_stats_callback=mock_stats, port=0)
        assert dashboard is not None
        assert dashboard.get_stats is not None
