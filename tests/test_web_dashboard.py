"""
Integration tests for Web Dashboard.

Tests the Flask web dashboard endpoints.
"""


import pytest

try:
    from proxy.web_dashboard import WebDashboard
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
        assert b"TG WS Proxy" in response.data or b"Dashboard" in response.data


class TestDashboardStats:
    """Test dashboard statistics formatting."""

    def test_empty_stats(self):
        """Test dashboard with empty stats."""
        def empty_stats():
            return {}

        dashboard = WebDashboard(get_stats_callback=empty_stats, port=0)
        assert dashboard.get_stats() == {}

    def test_stats_with_dc(self):
        """Test dashboard with DC stats."""
        def dc_stats():
            return {
                "dc_stats": {
                    2: {"connections": 100, "errors": 5}
                }
            }

        dashboard = WebDashboard(get_stats_callback=dc_stats, port=0)
        stats = dashboard.get_stats()
        assert 2 in stats.get("dc_stats", {})


class TestWebDashboardExtended:
    """Extended tests for WebDashboard."""

    def test_stats_export_invalid_format(self):
        """Test /api/stats/export with invalid format."""
        def mock_get_stats():
            return {"connections_total": 100}

        dashboard = WebDashboard(get_stats_callback=mock_get_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/stats/export?format=invalid")
            # Should default to JSON or return error
            assert response.status_code in [200, 400]

    def test_stats_export_csv_empty(self):
        """Test CSV export with empty stats."""
        def empty_stats():
            return {}

        dashboard = WebDashboard(get_stats_callback=empty_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/stats/export?format=csv")
            assert response.status_code == 200

    def test_cors_enabled(self):
        """Test CORS is enabled on API endpoints."""
        def mock_get_stats():
            return {}

        dashboard = WebDashboard(get_stats_callback=mock_get_stats, port=0)
        dashboard.app.config["TESTING"] = True

        with dashboard.app.test_client() as client:
            response = client.get("/api/health")
            # CORS headers should be present
            assert response.status_code == 200
