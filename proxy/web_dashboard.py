"""
Web Dashboard for TG WS Proxy.

Provides a web interface to monitor proxy statistics and manage settings.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable

try:
    from flask import Flask, jsonify, render_template_string, request
    from flask_cors import CORS
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    Flask = None  # type: ignore
    CORS = None  # type: ignore

log = logging.getLogger('tg-web-dashboard')

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TG WS Proxy - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-card h3 {
            color: #667eea;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 2.5rem;
            font-weight: bold;
            color: #333;
        }
        .stat-card .unit {
            font-size: 1rem;
            color: #888;
            margin-left: 5px;
        }
        .section {
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .section h2 {
            color: #667eea;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }
        th {
            background: #f8f9fa;
            color: #667eea;
            font-weight: 600;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-online {
            background: #48bb78;
        }
        .status-offline {
            background: #f56565;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
        }
        .refresh-btn:hover {
            background: #5568d3;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .last-update {
            color: #888;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 TG WS Proxy Dashboard</h1>

        <div class="header">
            <div class="last-update">
                <span class="status-indicator status-online"></span>
                Обновлено: <span id="lastUpdate">-</span>
            </div>
            <button class="refresh-btn" onclick="loadStats()">🔄 Обновить</button>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>📡 Всего подключений</h3>
                <div class="value" id="totalConnections">0</div>
            </div>
            <div class="stat-card">
                <h3>🟢 Активных сейчас</h3>
                <div class="value" id="activeConnections">0</div>
            </div>
            <div class="stat-card">
                <h3>📤 Трафик вверх</h3>
                <div class="value" id="bytesUp">0<span class="unit">MB</span></div>
            </div>
            <div class="stat-card">
                <h3>📥 Трафик вниз</h3>
                <div class="value" id="bytesDown">0<span class="unit">MB</span></div>
            </div>
        </div>

        <div class="section">
            <h2>📊 Статистика по секретам (MTProto)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Секрет</th>
                        <th>Подключений всего</th>
                        <th>Активных</th>
                        <th>Получено</th>
                        <th>Отправлено</th>
                    </tr>
                </thead>
                <tbody id="secretsTable">
                    <tr><td colspan="5" style="text-align:center;">Загрузка...</td></tr>
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>⚙️ Информация о сервере</h2>
            <table>
                <tbody>
                    <tr><th>Версия</th><td id="version">-</td></tr>
                    <tr><th>Хост</th><td id="host">-</td></tr>
                    <tr><th>Порт</th><td id="port">-</td></tr>
                    <tr><th>Время работы</th><td id="uptime">-</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function formatBytes(bytes) {
            if (bytes === 0) return '0 MB';
            const mb = bytes / (1024 * 1024);
            return mb.toFixed(2) + ' MB';
        }

        function truncateSecret(secret) {
            return secret.substring(0, 8) + '...' + secret.substring(secret.length - 4);
        }

        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();

                document.getElementById('totalConnections').textContent = data.connections_total || 0;
                document.getElementById('activeConnections').textContent = data.connections_active || 0;
                document.getElementById('bytesUp').innerHTML = formatBytes(data.bytes_received || 0).replace(' MB', '<span class="unit"> MB</span>');
                document.getElementById('bytesDown').innerHTML = formatBytes(data.bytes_sent || 0).replace(' MB', '<span class="unit"> MB</span>');

                // Update secrets table
                const secretsTable = document.getElementById('secretsTable');
                if (data.per_secret && Object.keys(data.per_secret).length > 0) {
                    secretsTable.innerHTML = Object.entries(data.per_secret).map(([secret, stats]) => `
                        <tr>
                            <td><code>${truncateSecret(secret)}</code></td>
                            <td>${stats.connections_total || 0}</td>
                            <td>${stats.connections_active || 0}</td>
                            <td>${formatBytes(stats.bytes_received || 0)}</td>
                            <td>${formatBytes(stats.bytes_sent || 0)}</td>
                        </tr>
                    `).join('');
                } else {
                    secretsTable.innerHTML = '<tr><td colspan="5" style="text-align:center;">Нет данных</td></tr>';
                }

                document.getElementById('version').textContent = data.version || '2.1.0';
                document.getElementById('host').textContent = data.host || '-';
                document.getElementById('port').textContent = data.port || '-';
                document.getElementById('uptime').textContent = data.uptime || '-';

                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('ru-RU');
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        }

        // Auto-refresh every 5 seconds
        setInterval(loadStats, 5000);
        loadStats();
    </script>
</body>
</html>
"""


class WebDashboard:
    """Web dashboard for proxy monitoring."""

    def __init__(
        self,
        get_stats_callback: Callable[[], dict],
        host: str = "127.0.0.1",
        port: int = 5000,
        debug: bool = False,
    ):
        if not HAS_FLASK:
            log.error("Flask not installed. Install with: pip install flask flask-cors")
            raise ImportError("Flask is required for web dashboard")

        self.get_stats = get_stats_callback
        self.host = host
        self.port = port
        self.debug = debug
        self.start_time = datetime.now()

        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24).hex()
        CORS(self.app)

        self._setup_routes()
        self._thread: Optional[threading.Thread] = None

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def dashboard():
            """Main dashboard page."""
            return render_template_string(DASHBOARD_HTML)

        @self.app.route('/api/stats')
        def api_stats():
            """API endpoint for statistics."""
            stats = self.get_stats()
            stats['version'] = '2.1.0'
            stats['host'] = self.host
            stats['port'] = self.port
            stats['uptime'] = str(datetime.now() - self.start_time).split('.')[0]
            return jsonify(stats)

        @self.app.route('/api/health')
        def api_health():
            """Health check endpoint."""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
            })

    def start(self):
        """Start the web dashboard in a background thread."""
        if self._thread and self._thread.is_alive():
            log.warning("Dashboard already running")
            return

        def run_app():
            log.info("Starting web dashboard on http://%s:%d", self.host, self.port)
            self.app.run(
                host=self.host,
                port=self.port,
                debug=self.debug,
                use_reloader=False,
                threaded=True,
            )

        self._thread = threading.Thread(target=run_app, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the web dashboard."""
        if self._thread and self._thread.is_alive():
            log.info("Stopping web dashboard")
            # Flask doesn't have a clean shutdown, thread will die with process
        self._thread = None


def run_dashboard(
    get_stats_callback: Callable[[], dict],
    host: str = "127.0.0.1",
    port: int = 5000,
    open_browser: bool = True,
):
    """
    Run web dashboard for proxy monitoring.

    Args:
        get_stats_callback: Function that returns proxy statistics.
        host: Host to bind to.
        port: Port to listen on.
        open_browser: Open browser automatically.
    """
    if not HAS_FLASK:
        log.error("Flask not installed. Install with: pip install flask flask-cors")
        return

    dashboard = WebDashboard(get_stats_callback, host, port)
    dashboard.start()

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")
        log.info("Opening dashboard in browser...")

    log.info("Dashboard running at http://%s:%d", host, port)
    log.info("Press Ctrl+C to stop")

    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Dashboard stopped")


if __name__ == '__main__':
    # Demo mode with mock stats
    def mock_stats():
        return {
            "connections_total": 150,
            "connections_active": 12,
            "bytes_received": 52428800,
            "bytes_sent": 104857600,
            "per_secret": {
                "0123456789abcdef0123456789abcdef": {
                    "connections_total": 80,
                    "connections_active": 7,
                    "bytes_received": 31457280,
                    "bytes_sent": 62914560,
                },
                "fedcba9876543210fedcba9876543210": {
                    "connections_total": 70,
                    "connections_active": 5,
                    "bytes_received": 20971520,
                    "bytes_sent": 41943040,
                },
            },
        }

    logging.basicConfig(level=logging.INFO)
    run_dashboard(mock_stats, open_browser=True)
