"""
Web Dashboard for TG WS Proxy.

Provides a web interface to monitor proxy statistics and manage settings.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

try:
    from flask import Flask, jsonify, render_template_string, request, Response
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
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TG WS Proxy - Dashboard</title>
    <style>
        :root {
            --bg-gradient-start: #667eea;
            --bg-gradient-end: #764ba2;
            --card-bg: #ffffff;
            --text-primary: #333333;
            --text-secondary: #666666;
            --text-muted: #888888;
            --border-color: #e2e8f0;
            --table-bg: #f8f9fa;
            --input-bg: #ffffff;
            --code-bg: #f7fafc;
        }
        [data-theme="dark"] {
            --bg-gradient-start: #2d3748;
            --bg-gradient-end: #1a202c;
            --card-bg: #2d3748;
            --text-primary: #f7fafc;
            --text-secondary: #cbd5e0;
            --text-muted: #a0aec0;
            --border-color: #4a5568;
            --table-bg: #1a202c;
            --input-bg: #2d3748;
            --code-bg: #1a202c;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
            min-height: 100vh;
            padding: 20px;
            transition: background 0.3s ease;
        }
        .container {
            max-width: 1400px;
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
            background: var(--card-bg);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease, background 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }
        .stat-card h3 {
            color: var(--bg-gradient-start);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--text-primary);
        }
        .stat-card .unit {
            font-size: 1rem;
            color: var(--text-muted);
            margin-left: 5px;
        }
        .section {
            background: var(--card-bg);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: background 0.3s ease;
        }
        .section h2 {
            color: var(--bg-gradient-start);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }
        th {
            background: var(--table-bg);
            color: var(--bg-gradient-start);
            font-weight: 600;
        }
        tr:hover {
            background: var(--table-bg);
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        .status-online { background: #48bb78; }
        .status-degraded { background: #ed8936; }
        .status-offline { background: #f56565; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .btn {
            background: var(--bg-gradient-start);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s, transform 0.2s;
            text-decoration: none;
            display: inline-block;
            margin-left: 10px;
        }
        .btn:hover {
            background: #5568d3;
            transform: translateY(-2px);
        }
        .btn-secondary {
            background: #718096;
        }
        .btn-secondary:hover { background: #4a5568; }
        .btn-success { background: #48bb78; }
        .btn-success:hover { background: #38a169; }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }
        .header-actions {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .last-update {
            color: var(--text-muted);
            font-size: 0.9rem;
            display: flex;
            align-items: center;
        }
        .nav-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .nav-tab {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s;
        }
        .nav-tab:hover { background: rgba(255,255,255,0.3); }
        .nav-tab.active {
            background: white;
            color: var(--bg-gradient-start);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--bg-gradient-start);
            font-weight: 600;
        }
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 12px;
            background: var(--input-bg);
            color: var(--text-primary);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s, background 0.3s;
        }
        .form-group input:focus, .form-group textarea:focus {
            outline: none;
            border-color: var(--bg-gradient-start);
        }
        .form-group textarea {
            min-height: 100px;
            resize: vertical;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .checkbox-group input[type="checkbox"] { width: auto; }
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .alert-success {
            background: #c6f6d5;
            color: #22543d;
            border: 1px solid #9ae6b4;
        }
        .alert-error {
            background: #fed7d7;
            color: #742a2a;
            border: 1px solid #f56565;
        }
        .health-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .health-ok { background: #c6f6d5; color: #22543d; }
        .health-degraded { background: #feebc8; color: #7c2d12; }
        .theme-toggle {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1.2rem;
            transition: background 0.3s;
            margin-left: 10px;
        }
        .theme-toggle:hover { background: rgba(255,255,255,0.3); }
        code {
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            color: #e53e3e;
        }
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: 1fr; }
            .header {
                flex-direction: column;
                align-items: flex-start;
            }
            .header-actions {
                width: 100%;
                justify-content: flex-start;
            }
            .nav-tabs { justify-content: flex-start; }
            .btn { margin: 5px 0; }
            h1 { font-size: 1.8rem; }
            .stat-card .value { font-size: 2rem; }
        }
        @media (max-width: 480px) {
            body { padding: 10px; }
            .section { padding: 15px; }
            .stat-card { padding: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 TG WS Proxy Dashboard <button class="theme-toggle" onclick="toggleTheme()" title="Переключить тему">🌓</button></h1>

        <div class="header">
            <div class="last-update">
                <span class="status-indicator status-online" id="statusIndicator"></span>
                Обновлено: <span id="lastUpdate">-</span>
            </div>
            <div class="header-actions">
                <button class="btn" onclick="loadStats()">🔄 Обновить</button>
                <button class="btn btn-secondary" onclick="exportStats('json')">📥 JSON</button>
                <button class="btn btn-secondary" onclick="exportStats('csv')">📊 CSV</button>
                <button class="btn btn-success" onclick="checkHealth()">❤️ Health</button>
            </div>
        </div>

        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchTab('stats')">📊 Статистика</button>
            <button class="nav-tab" onclick="switchTab('dc')">🌐 DC Stats</button>
            <button class="nav-tab" onclick="switchTab('settings')">⚙️ Настройки</button>
        </div>

        <!-- Statistics Tab -->
        <div id="stats-tab" class="tab-content active">
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
        </div>

        <!-- DC Stats Tab -->
        <div id="dc-tab" class="tab-content">
            <div class="section">
                <h2>🌐 Статистика по Data Center</h2>
                <table>
                    <thead>
                        <tr>
                            <th>DC ID</th>
                            <th>Подключений</th>
                            <th>Ошибок</th>
                            <th>Задержка (ms)</th>
                            <th>Средняя задержка (ms)</th>
                        </tr>
                    </thead>
                    <tbody id="dcTable">
                        <tr><td colspan="5" style="text-align:center;">Загрузка...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Settings Tab -->
        <div id="settings-tab" class="tab-content">
            <div class="section">
                <h2>⚙️ Настройки прокси</h2>
                <div id="configAlert"></div>
                <form id="configForm" onsubmit="saveConfig(event)">
                    <div class="form-group">
                        <label for="proxyHost">Хост:</label>
                        <input type="text" id="proxyHost" name="host" value="127.0.0.1" placeholder="127.0.0.1">
                    </div>
                    <div class="form-group">
                        <label for="proxyPort">Порт:</label>
                        <input type="number" id="proxyPort" name="port" value="1080" min="1" max="65535">
                    </div>
                    <div class="form-group">
                        <label for="dcIp">DC IP (каждый с новой строки, формат: ID:IP):</label>
                        <textarea id="dcIp" name="dc_ip" placeholder="2:149.154.167.220&#10;4:149.154.167.220"></textarea>
                    </div>
                    <div class="form-group checkbox-group">
                        <input type="checkbox" id="verbose" name="verbose">
                        <label for="verbose">Подробное логирование (verbose)</label>
                    </div>
                    <button type="submit" class="btn btn-success">💾 Сохранить</button>
                </form>
            </div>
        </div>

        <div class="section">
            <h2>ℹ️ Информация о сервере</h2>
            <table>
                <tbody>
                    <tr><th>Версия</th><td id="version">-</td></tr>
                    <tr><th>Хост</th><td id="host">-</td></tr>
                    <tr><th>Порт</th><td id="port">-</td></tr>
                    <tr><th>Время работы</th><td id="uptime">-</td></tr>
                    <tr><th>Health Status</th><td id="healthStatus"><span class="health-badge health-ok">Unknown</span></td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let currentConfig = {};

        function formatBytes(bytes) {
            if (bytes === 0) return '0 MB';
            const mb = bytes / (1024 * 1024);
            return mb.toFixed(2) + ' MB';
        }

        function truncateSecret(secret) {
            return secret.substring(0, 8) + '...' + secret.substring(secret.length - 4);
        }

        function switchTab(tabName) {
            document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
            
            if (tabName === 'settings') {
                loadConfig();
            } else if (tabName === 'dc') {
                loadDCStats();
            }
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

                document.getElementById('version').textContent = data.version || '2.5.5';
                document.getElementById('host').textContent = data.host || '-';
                document.getElementById('port').textContent = data.port || '-';
                document.getElementById('uptime').textContent = data.uptime || '-';

                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('ru-RU');
                
                // Update status indicator
                const statusIndicator = document.getElementById('statusIndicator');
                if (data.ws_errors && data.ws_errors > 10) {
                    statusIndicator.className = 'status-indicator status-degraded';
                } else {
                    statusIndicator.className = 'status-indicator status-online';
                }
            } catch (error) {
                console.error('Failed to load stats:', error);
                document.getElementById('statusIndicator').className = 'status-indicator status-offline';
            }
        }

        async function loadDCStats() {
            try {
                const response = await fetch('/api/dc-stats');
                const data = await response.json();
                
                const dcTable = document.getElementById('dcTable');
                if (data.dc_stats && data.dc_stats.length > 0) {
                    dcTable.innerHTML = data.dc_stats.map(dc => `
                        <tr>
                            <td><strong>DC ${dc.dc_id}</strong></td>
                            <td>${dc.connections}</td>
                            <td>${dc.errors}</td>
                            <td>${dc.latency_ms !== null ? dc.latency_ms.toFixed(2) : 'N/A'}</td>
                            <td>${dc.avg_latency_ms !== null ? dc.avg_latency_ms.toFixed(2) : 'N/A'}</td>
                        </tr>
                    `).join('');
                } else {
                    dcTable.innerHTML = '<tr><td colspan="5" style="text-align:center;">Нет данных</td></tr>';
                }
            } catch (error) {
                console.error('Failed to load DC stats:', error);
                document.getElementById('dcTable').innerHTML = '<tr><td colspan="5" style="text-align:center;">Ошибка загрузки</td></tr>';
            }
        }

        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                if (response.ok) {
                    currentConfig = await response.json();
                    document.getElementById('proxyHost').value = currentConfig.host || '127.0.0.1';
                    document.getElementById('proxyPort').value = currentConfig.port || 1080;
                    document.getElementById('dc_ip').value = (currentConfig.dc_ip || []).join('\\n');
                    document.getElementById('verbose').checked = currentConfig.verbose || false;
                }
            } catch (error) {
                console.log('Config not available or not editable');
            }
        }

        async function saveConfig(event) {
            event.preventDefault();
            
            const config = {
                host: document.getElementById('proxyHost').value,
                port: parseInt(document.getElementById('proxyPort').value),
                dc_ip: document.getElementById('dc_ip').value.split('\\n').filter(line => line.trim()),
                verbose: document.getElementById('verbose').checked,
            };

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config),
                });
                
                const result = await response.json();
                const alertDiv = document.getElementById('configAlert');
                
                if (response.ok && result.status === 'success') {
                    alertDiv.innerHTML = '<div class="alert alert-success">✅ Настройки успешно сохранены!</div>';
                    setTimeout(() => alertDiv.innerHTML = '', 5000);
                } else {
                    alertDiv.innerHTML = '<div class="alert alert-error">❌ Ошибка: ' + (result.error || 'Неизвестная ошибка') + '</div>';
                }
            } catch (error) {
                document.getElementById('configAlert').innerHTML = '<div class="alert alert-error">❌ Ошибка соединения: ' + error + '</div>';
            }
        }

        async function exportStats(format) {
            window.location.href = '/api/stats/export?format=' + format;
        }

        async function checkHealth() {
            try {
                const response = await fetch('/api/health');
                const data = await response.json();

                const healthBadge = document.getElementById('healthStatus');
                if (data.status === 'ok') {
                    healthBadge.innerHTML = '<span class="health-badge health-ok">✓ OK</span>';
                } else if (data.status === 'degraded') {
                    healthBadge.innerHTML = '<span class="health-badge health-degraded">⚠ Degraded</span>';
                } else {
                    healthBadge.innerHTML = '<span class="health-badge" style="background:#fed7d7;color:#742a2a">✗ Unhealthy</span>';
                }

                alert('Health Check:\\n' +
                      'Status: ' + data.status + '\\n' +
                      'WS Errors: ' + (data.websocket?.ws_errors || 0) + '\\n' +
                      'Pool Hits: ' + (data.websocket?.pool_hits || 0) + '\\n' +
                      'Pool Misses: ' + (data.websocket?.pool_misses || 0));
            } catch (error) {
                alert('Health check failed: ' + error);
            }
        }

        function toggleTheme() {
            const html = document.documentElement;
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }

        // Load saved theme on page load
        (function() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);
        })();

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
        update_config_callback: Optional[Callable[[dict], bool]] = None,
        host: str = "127.0.0.1",
        port: int = 5000,
        debug: bool = False,
    ):
        if not HAS_FLASK:
            log.error("Flask not installed. Install with: pip install flask flask-cors")
            raise ImportError("Flask is required for web dashboard")

        self.get_stats = get_stats_callback
        self.update_config = update_config_callback
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
            stats['version'] = '2.5.5'
            stats['host'] = self.host
            stats['port'] = self.port
            stats['uptime'] = str(datetime.now() - self.start_time).split('.')[0]
            return jsonify(stats)

        @self.app.route('/api/stats/export')
        def api_stats_export():
            """Export statistics as JSON or CSV."""
            format_type = request.args.get('format', 'json')
            stats = self.get_stats()
            stats['exported_at'] = datetime.now().isoformat()
            
            if format_type == 'csv':
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Metric', 'Value'])
                
                # Basic stats
                for key, value in stats.items():
                    if isinstance(value, (int, float, str)):
                        writer.writerow([key, value])
                
                output.seek(0)
                return Response(
                    output.getvalue(),
                    mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=stats.csv'}
                )
            else:
                return jsonify(stats)

        @self.app.route('/api/config', methods=['GET'])
        def api_get_config():
            """Get current configuration."""
            if self.update_config is None:
                return jsonify({'error': 'Configuration updates not enabled'}), 403
            
            stats = self.get_stats()
            config = {
                'host': stats.get('host', '127.0.0.1'),
                'port': stats.get('port', 1080),
                'dc_ip': stats.get('dc_ip', []),
                'verbose': stats.get('verbose', False),
            }
            return jsonify(config)

        @self.app.route('/api/config', methods=['POST'])
        def api_update_config():
            """Update configuration."""
            if self.update_config is None:
                return jsonify({'error': 'Configuration updates not enabled'}), 403
            
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Invalid JSON'}), 400
                
                success = self.update_config(data)
                if success:
                    return jsonify({'status': 'success'})
                else:
                    return jsonify({'error': 'Failed to update configuration'}), 500
            except Exception as e:
                log.error(f"Config update error: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/health')
        def api_health():
            """Health check endpoint."""
            stats = self.get_stats()
            is_healthy = stats.get('connections_active', 0) >= 0  # Always healthy if running
            
            # Check WebSocket endpoints
            ws_health = {
                'status': 'ok' if stats.get('ws_errors', 0) < 10 else 'degraded',
                'ws_errors': stats.get('ws_errors', 0),
                'pool_hits': stats.get('pool_hits', 0),
                'pool_misses': stats.get('pool_misses', 0),
            }
            
            return jsonify({
                'status': 'ok' if is_healthy else 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'version': '2.5.5',
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'websocket': ws_health,
            })

        @self.app.route('/api/dc-stats')
        def api_dc_stats():
            """Get detailed DC statistics."""
            stats = self.get_stats()
            dc_stats = stats.get('dc_stats', {})
            
            # Format for frontend
            formatted = []
            for dc_id, dc_data in dc_stats.items():
                formatted.append({
                    'dc_id': dc_id,
                    'connections': dc_data.get('connections', 0),
                    'errors': dc_data.get('errors', 0),
                    'latency_ms': dc_data.get('latency_ms'),
                    'avg_latency_ms': dc_data.get('avg_latency_ms'),
                })
            
            return jsonify({'dc_stats': formatted})

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
    update_config_callback: Optional[Callable[[dict], bool]] = None,
    host: str = "127.0.0.1",
    port: int = 5000,
    open_browser: bool = True,
):
    """
    Run web dashboard for proxy monitoring.

    Args:
        get_stats_callback: Function that returns proxy statistics.
        update_config_callback: Optional function to update configuration.
        host: Host to bind to.
        port: Port to listen on.
        open_browser: Open browser automatically.
    """
    if not HAS_FLASK:
        log.error("Flask not installed. Install with: pip install flask flask-cors")
        return

    dashboard = WebDashboard(get_stats_callback, update_config_callback, host, port)
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
