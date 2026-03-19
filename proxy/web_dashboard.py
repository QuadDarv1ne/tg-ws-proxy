"""
Web Dashboard for TG WS Proxy.

Provides a web interface to monitor proxy statistics and manage settings.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import threading
import time
from datetime import datetime
from typing import Callable

try:
    from flask import Flask, Response, jsonify, render_template_string, request
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
        .chart-container {
            background: var(--card-bg);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: background 0.3s ease;
        }
        .chart-container h3 {
            color: var(--bg-gradient-start);
            margin-bottom: 15px;
            font-size: 1.1rem;
        }
        .chart {
            width: 100%;
            height: 200px;
            position: relative;
            overflow: hidden;
        }
        .chart-line {
            fill: none;
            stroke-width: 2.5;
            stroke-linecap: round;
            stroke-linejoin: round;
            transition: d 0.5s ease;
        }
        .chart-line-up {
            stroke: #48bb78;
        }
        .chart-line-down {
            stroke: #3182ce;
        }
        .chart-area {
            transition: d 0.5s ease;
        }
        .chart-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }
        .chart-legend {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            color: var(--text-primary);
        }
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 2px;
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
            <button class="nav-tab" onclick="switchTab('logs')">📜 Live Логи</button>
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

            <div class="chart-container">
                <h3>📈 Трафик в реальном времени</h3>
                <div class="chart-legend">
                    <div class="legend-item">
                        <div class="legend-color" style="background:#48bb78"></div>
                        <span>Вверх</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background:#3182ce"></div>
                        <span>Вниз</span>
                    </div>
                </div>
                <svg class="chart" id="trafficChart" viewBox="0 0 600 200" preserveAspectRatio="none">
                </svg>
                <div class="chart-labels">
                    <span>60с назад</span>
                    <span>Сейчас</span>
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

        <!-- Live Logs Tab -->
        <div id="logs-tab" class="tab-content">
            <div class="section">
                <h2>📜 Live Логи подключений</h2>
                <div style="margin-bottom: 15px; display: flex; gap: 10px; align-items: center;">
                    <button onclick="clearLogs()" class="btn btn-secondary">🗑️ Очистить</button>
                    <button onclick="toggleAutoRefresh()" class="btn btn-secondary" id="autoRefreshBtn">⏸️ Пауза</button>
                    <span id="logCount" style="color: var(--text-muted); margin-left: auto;">Записей: 0</span>
                </div>
                <div id="liveLogs" style="
                    background: var(--table-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    padding: 15px;
                    max-height: 500px;
                    overflow-y: auto;
                    font-family: 'Courier New', monospace;
                    font-size: 0.85rem;
                ">
                    <div style="color: var(--text-muted); text-align: center; padding: 20px;">
                        Загрузка логов...
                    </div>
                </div>
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

            <div class="section">
                <h2>📱 QR-код для Telegram Mobile</h2>
                <p style="margin-bottom: 15px; color: var(--text-secondary);">
                    Отсканируйте QR-код через Telegram Mobile для автоматической настройки прокси:
                </p>
                <div style="text-align: center; padding: 20px;">
                    <img id="qrCode" src="/api/qr" alt="QR Code" style="max-width: 256px; border: 2px solid var(--border-color); border-radius: 12px; padding: 10px; background: white;">
                    <br>
                    <button onclick="downloadQR()" class="btn btn-primary" style="margin-top: 15px;">⬇️ Скачать QR-код</button>
                    <button onclick="refreshQR()" class="btn btn-secondary" style="margin-top: 15px; margin-left: 10px;">🔄 Обновить</button>
                </div>
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
            } else if (tabName === 'logs') {
                loadLiveLogs();
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

                // Render traffic chart
                if (data.traffic_history) {
                    renderTrafficChart(data.traffic_history);
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

        function downloadQR() {
            const link = document.createElement('a');
            link.href = '/api/qr';
            link.download = 'tg-ws-proxy-qr.png';
            link.click();
        }

        function refreshQR() {
            const qrImg = document.getElementById('qrCode');
            qrImg.src = '/api/qr?t=' + Date.now();
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

                let wsStatus = 'OK';
                if (data.websocket?.status === 'degraded') wsStatus = '⚠ Degraded';
                else if (data.websocket?.status === 'unhealthy') wsStatus = '✗ Unhealthy';

                let dcStatus = '';
                if (data.dc_health && data.dc_health.length > 0) {
                    dcStatus = '\\n\\nDC Status:\\n' + data.dc_health.map(dc =>
                        `  DC${dc.dc_id}: ${dc.status === 'ok' ? '✓' : dc.status === 'degraded' ? '⚠' : '✗'} (${dc.error_rate_percent}% errors)`
                    ).join('\\n');
                }

                alert('Health Check:\\n' +
                      'Status: ' + data.status.toUpperCase() + '\\n' +
                      'WebSocket: ' + wsStatus + '\\n' +
                      'Pool Efficiency: ' + (data.websocket?.pool_efficiency_percent || 0) + '%\\n' +
                      'WS Errors: ' + (data.websocket?.ws_errors || 0) + '\\n' +
                      'Pool Hits/Misses: ' + (data.websocket?.pool_hits || 0) + '/' + (data.websocket?.pool_misses || 0) +
                      dcStatus);
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

        // Live Logs functionality
        let logsAutoRefresh = true;
        let logsInterval = null;
        let lastLogTime = 0;

        function clearLogs() {
            document.getElementById('liveLogs').innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">Логи очищены</div>';
            updateLogCount(0);
        }

        function toggleAutoRefresh() {
            logsAutoRefresh = !logsAutoRefresh;
            const btn = document.getElementById('autoRefreshBtn');
            btn.textContent = logsAutoRefresh ? '⏸️ Пауза' : '▶️ Старт';
            if (logsAutoRefresh) {
                startLogsRefresh();
            } else {
                stopLogsRefresh();
            }
        }

        function startLogsRefresh() {
            if (logsInterval) clearInterval(logsInterval);
            logsInterval = setInterval(loadLiveLogs, 2000);
        }

        function stopLogsRefresh() {
            if (logsInterval) clearInterval(logsInterval);
            logsInterval = null;
        }

        function updateLogCount(count) {
            document.getElementById('logCount').textContent = 'Записей: ' + count;
        }

        async function loadLiveLogs() {
            if (!logsAutoRefresh) return;

            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                const logsContainer = document.getElementById('liveLogs');

                // Get connection history from stats
                const history = data.connection_history || [];
                const newLogs = history.filter(log => log.time > lastLogTime);

                if (newLogs.length > 0) {
                    newLogs.sort((a, b) => a.time - b.time);

                    for (const log of newLogs) {
                        const time = new Date((log.time % 3600) * 1000).toISOString().substr(14, 8);
                        const type = log.type || 'unknown';
                        const dc = log.dc ? `DC${log.dc}` : '-';

                        let icon = '🔌';
                        let color = 'var(--text-primary)';

                        if (type === 'ws') { icon = '🟢'; color = '#48bb78'; }
                        else if (type === 'tcp_fallback') { icon = '🟡'; color = '#ed8936'; }
                        else if (type === 'http_rejected') { icon = '🔴'; color = '#f56565'; }
                        else if (type === 'passthrough') { icon = '🔵'; color = '#4299e1'; }

                        const logEntry = `[${time}] ${icon} ${type.toUpperCase().padEnd(15)} ${dc.padEnd(6)}`;

                        const div = document.createElement('div');
                        div.textContent = logEntry;
                        div.style.color = color;
                        div.style.padding = '4px 0';
                        div.style.borderBottom = '1px solid var(--border-color)';
                        logsContainer.appendChild(div);

                        lastLogTime = log.time;
                    }

                    // Auto-scroll to bottom
                    logsContainer.scrollTop = logsContainer.scrollHeight;
                    updateLogCount(logsContainer.children.length);
                } else if (logsContainer.children.length === 0 ||
                          (logsContainer.children.length === 1 && logsContainer.children[0].textContent.includes('Загрузка'))) {
                    logsContainer.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">Нет новых подключений</div>';
                    updateLogCount(0);
                }
            } catch (error) {
                console.error('Failed to load live logs:', error);
            }
        }

        function renderTrafficChart(trafficHistory) {
            const svg = document.getElementById('trafficChart');
            if (!trafficHistory || trafficHistory.length < 2) {
                svg.innerHTML = '<text x=\"300\" y=\"100\" text-anchor=\"middle\" fill=\"#888\" font-size=\"14\">Нет данных для отображения</text>';
                return;
            }

            const width = 600;
            const height = 200;
            const padding = 20;
            const chartHeight = height - padding * 2;

            // Find max value for scaling
            let maxValue = 0;
            trafficHistory.forEach(point => {
                if (point.bytes_up > maxValue) maxValue = point.bytes_up;
                if (point.bytes_down > maxValue) maxValue = point.bytes_down;
            });

            if (maxValue === 0) maxValue = 1;

            // Generate smooth path using bezier curves
            const generateSmoothPath = (key) => {
                if (trafficHistory.length < 2) return '';
                const points = trafficHistory.map((point, i) => {
                    const x = (i / (trafficHistory.length - 1)) * (width - padding * 2) + padding;
                    const y = height - padding - (point[key] / maxValue) * chartHeight;
                    return {x, y};
                });

                let path = `M ${points[0].x} ${points[0].y}`;
                for (let i = 1; i < points.length; i++) {
                    const prev = points[i - 1];
                    const curr = points[i];
                    const cpx = (prev.x + curr.x) / 2;
                    path += ` C ${cpx} ${prev.y}, ${cpx} ${curr.y}, ${curr.x} ${curr.y}`;
                }
                return path;
            };

            const generateArea = (key) => {
                const path = generateSmoothPath(key);
                const lastX = width - padding;
                const firstX = padding;
                const baseY = height - padding;
                return `${path} L ${lastX} ${baseY} L ${firstX} ${baseY} Z`;
            };

            const pathUp = generateSmoothPath('bytes_up');
            const pathDown = generateSmoothPath('bytes_down');

            svg.innerHTML = `
                <defs>
                    <linearGradient id=\"gradUp\" x1=\"0%\" y1=\"0%\" x2=\"0%\" y2=\"100%\">
                        <stop offset=\"0%\" style=\"stop-color:#48bb78;stop-opacity:0.4\" />
                        <stop offset=\"100%\" style=\"stop-color:#48bb78;stop-opacity:0.05\" />
                    </linearGradient>
                    <linearGradient id=\"gradDown\" x1=\"0%\" y1=\"0%\" x2=\"0%\" y2=\"100%\">
                        <stop offset=\"0%\" style=\"stop-color:#3182ce;stop-opacity:0.4\" />
                        <stop offset=\"100%\" style=\"stop-color:#3182ce;stop-opacity:0.05\" />
                    </linearGradient>
                </defs>
                <path class=\"chart-area\" fill=\"url(#gradUp)\" d=\"${generateArea('bytes_up')}\" />
                <path class=\"chart-area\" fill=\"url(#gradDown)\" d=\"${generateArea('bytes_down')}\" />
                <path class=\"chart-line chart-line-up\" d=\"${pathUp}\" />
                <path class=\"chart-line chart-line-down\" d=\"${pathDown}\" />
            `;
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
        update_config_callback: Callable[[dict], bool] | None = None,
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
        self._thread: threading.Thread | None = None

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

        @self.app.route('/api/qr')
        def api_generate_qr():
            """Generate QR code for Telegram Mobile configuration."""
            try:
                import qrcode

                stats = self.get_stats()
                host = stats.get('host', '127.0.0.1')
                port = stats.get('port', 1080)

                # Generate tg:// proxy URL
                proxy_url = f"tg://socks?server={host}&port={port}"

                # Generate QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(proxy_url)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                # Save to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)

                return Response(
                    img_bytes.getvalue(),
                    mimetype='image/png',
                    headers={'Content-Disposition': 'attachment; filename=tg-ws-proxy-qr.png'}
                )
            except ImportError:
                return jsonify({'error': 'qrcode library not installed'}), 500
            except Exception as e:
                log.error(f"QR generation error: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/health')
        def api_health():
            """Health check endpoint with detailed diagnostics."""
            stats = self.get_stats()

            # Determine overall health status
            ws_errors = stats.get('ws_errors', 0)
            pool_misses = stats.get('pool_misses', 0)
            pool_hits = stats.get('pool_hits', 0)

            # Calculate pool efficiency
            pool_total = pool_hits + pool_misses
            pool_efficiency = (pool_hits / pool_total * 100) if pool_total > 0 else 100

            # Determine status
            if ws_errors < 5 and pool_efficiency >= 80:
                status = 'ok'
            elif ws_errors < 15 and pool_efficiency >= 50:
                status = 'degraded'
            else:
                status = 'unhealthy'

            ws_health = {
                'status': 'ok' if ws_errors < 10 else 'degraded',
                'ws_errors': ws_errors,
                'pool_hits': pool_hits,
                'pool_misses': pool_misses,
                'pool_efficiency_percent': round(pool_efficiency, 1),
            }

            # DC health summary
            dc_stats = stats.get('dc_stats', {})
            dc_health = []
            for dc_id, dc_data in dc_stats.items():
                dc_errors = dc_data.get('errors', 0)
                dc_conns = dc_data.get('connections', 0)
                dc_error_rate = (dc_errors / dc_conns * 100) if dc_conns > 0 else 0
                dc_health.append({
                    'dc_id': dc_id,
                    'status': 'ok' if dc_error_rate < 10 else 'degraded' if dc_error_rate < 30 else 'unhealthy',
                    'error_rate_percent': round(dc_error_rate, 1),
                })

            return jsonify({
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'version': '2.5.5',
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'websocket': ws_health,
                'dc_health': dc_health,
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
    update_config_callback: Callable[[dict], bool] | None = None,
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
