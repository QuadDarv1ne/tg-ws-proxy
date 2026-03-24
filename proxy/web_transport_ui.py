"""
Enhanced Web Dashboard API for Transport Management.

Provides REST API endpoints for:
- Transport selection and configuration
- Health status monitoring
- Transport statistics
- Auto-select settings

Author: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. All rights reserved.
"""

from __future__ import annotations

import logging

log = logging.getLogger('tg-web-transport-api')


# =============================================================================
# Transport API Endpoints (to be added to web_dashboard.py)
# =============================================================================

TRANSPORT_API_ROUTES = """
# Transport Management Endpoints

@app.route('/api/transport/status', methods=['GET'])
def get_transport_status():
    \"\"\"Get current transport status and health.\"\"\"
    from .transport_manager import TransportManager
    
    # Get transport manager instance (from global state)
    manager = getattr(get_transport_status, 'manager', None)
    
    if not manager:
        return jsonify({
            'error': 'Transport manager not initialized',
            'status': 'disconnected'
        }), 503
    
    stats = manager.get_stats()
    return jsonify(stats)


@app.route('/api/transport/config', methods=['GET'])
def get_transport_config():
    \"\"\"Get current transport configuration.\"\"\"
    manager = getattr(get_transport_config, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    config = manager.config
    return jsonify({
        'transport_type': config.transport_type.name,
        'host': config.host,
        'port': config.port,
        'path': config.path,
        'auto_select': config.auto_select,
        'health_check_interval': config.health_check_interval,
        'meek_cdn': config.meek_cdn,
        'ss_method': config.ss_method,
        'reality_server_name': config.reality_server_name,
    })


@app.route('/api/transport/config', methods=['POST'])
def update_transport_config():
    \"\"\"Update transport configuration.\"\"\"
    manager = getattr(update_transport_config, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400
    
    # Update configuration
    try:
        from .transport_manager import TransportType
        
        if 'transport_type' in data:
            manager.config.transport_type = TransportType[data['transport_type'].upper()]
        
        if 'host' in data:
            manager.config.host = data['host']
        
        if 'port' in data:
            manager.config.port = data['port']
        
        if 'auto_select' in data:
            manager.config.auto_select = data['auto_select']
        
        if 'meek_cdn' in data:
            manager.config.meek_cdn = data['meek_cdn']
        
        if 'ss_method' in data:
            manager.config.ss_method = data['ss_method']
        
        if 'ss_password' in data:
            manager.config.ss_password = data['ss_password']
        
        if 'reality_sni' in data:
            manager.config.reality_server_name = data['reality_sni']
        
        # Reconnect with new config
        if data.get('reconnect', False):
            asyncio.run(manager.stop())
            asyncio.run(manager.start())
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated'
        })
    
    except Exception as e:
        log.error("Failed to update config: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/transport/switch', methods=['POST'])
def switch_transport():
    \"\"\"Switch to a different transport.\"\"\"
    manager = getattr(switch_transport, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    data = request.get_json()
    if not data or 'transport_type' not in data:
        return jsonify({'error': 'transport_type required'}), 400
    
    try:
        from .transport_manager import TransportType
        transport_type = TransportType[data['transport_type'].upper()]
        
        # Switch transport
        success = asyncio.run(manager._connect_transport(transport_type))
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Switched to {transport_type.name}'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to connect with {transport_type.name}'
            }), 500
    
    except Exception as e:
        log.error("Failed to switch transport: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/transport/health', methods=['GET'])
def get_transport_health():
    \"\"\"Get health status for all transports.\"\"\"
    manager = getattr(get_transport_health, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    health_data = {
        transport.name: {
            'latency_ms': health.latency_ms,
            'success_rate': health.success_rate,
            'is_healthy': health.is_healthy,
            'consecutive_failures': health.consecutive_failures,
        }
        for transport, health in manager._health.items()
    }
    
    return jsonify(health_data)


@app.route('/api/transport/measure', methods=['POST'])
def measure_transport_latency():
    \"\"\"Measure latency for a specific transport.\"\"\"
    manager = getattr(measure_transport_latency, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    data = request.get_json()
    if not data or 'transport_type' not in data:
        return jsonify({'error': 'transport_type required'}), 400
    
    try:
        from .transport_manager import TransportType
        transport_type = TransportType[data['transport_type'].upper()]
        
        latency = asyncio.run(manager._measure_transport_latency(transport_type))
        
        return jsonify({
            'transport_type': transport_type.name,
            'latency_ms': latency,
            'available': latency > 0
        })
    
    except Exception as e:
        log.error("Failed to measure latency: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/transport/reconnect', methods=['POST'])
def reconnect_transport():
    \"\"\"Force reconnect.\"\"\"
    manager = getattr(reconnect_transport, 'manager', None)
    
    if not manager:
        return jsonify({'error': 'Not initialized'}), 503
    
    try:
        success = asyncio.run(manager.reconnect())
        
        if success:
            return jsonify({'success': True, 'message': 'Reconnected'})
        else:
            return jsonify({'success': False, 'message': 'Reconnection failed'}), 500
    
    except Exception as e:
        log.error("Failed to reconnect: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/pq/status', methods=['GET'])
def get_pq_status():
    \"\"\"Get post-quantum cryptography status.\"\"\"
    from .post_quantum_crypto import check_pq_availability
    
    status = check_pq_availability()
    return jsonify(status)


@app.route('/api/pq/generate-keys', methods=['POST'])
def generate_pq_keys():
    \"\"\"Generate new post-quantum key pair.\"\"\"
    from .post_quantum_crypto import PQKeyManager
    
    data = request.get_json() or {}
    use_hybrid = data.get('hybrid', True)
    
    manager = PQKeyManager(use_hybrid=use_hybrid)
    public_key = manager.generate_keys()
    
    return jsonify({
        'public_key': public_key.hex(),
        'algorithm': 'hybrid_x25519_kyber768' if use_hybrid else 'kyber768',
        'key_info': manager.get_key_info()
    })
"""


# =============================================================================
# HTML Template for Transport Settings Tab
# =============================================================================

TRANSPORT_SETTINGS_HTML = """
<!-- Transport Settings Tab -->
<div id="transport-tab" class="tab-content" style="display: none;">
    <div class="dashboard-grid">
        <!-- Current Transport Status -->
        <div class="card">
            <div class="card-header">
                <span class="card-icon">📡</span>
                <h3>Текущий транспорт</h3>
            </div>
            <div class="card-body">
                <div class="stat-row">
                    <span class="stat-label">Тип:</span>
                    <span class="stat-value" id="current-transport">-</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Статус:</span>
                    <span class="stat-value" id="transport-status">-</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Хост:</span>
                    <span class="stat-value" id="transport-host">-</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Порт:</span>
                    <span class="stat-value" id="transport-port">-</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Auto-select:</span>
                    <span class="stat-value" id="transport-auto">-</span>
                </div>
            </div>
        </div>

        <!-- Transport Health -->
        <div class="card">
            <div class="card-header">
                <span class="card-icon">💚</span>
                <h3>Health Status</h3>
            </div>
            <div class="card-body">
                <div id="transport-health-list">
                    <div class="loading">Загрузка...</div>
                </div>
            </div>
        </div>

        <!-- Transport Selection -->
        <div class="card full-width">
            <div class="card-header">
                <span class="card-icon">🔄</span>
                <h3>Выбор транспорта</h3>
            </div>
            <div class="card-body">
                <div class="form-group">
                    <label for="transport-type">Тип транспорта:</label>
                    <select id="transport-type" class="form-control">
                        <option value="auto">Auto (рекомендуется)</option>
                        <option value="websocket">WebSocket</option>
                        <option value="http2">HTTP/2</option>
                        <option value="quic">QUIC/HTTP/3</option>
                        <option value="meek">Meek (CDN)</option>
                        <option value="shadowsocks">Shadowsocks</option>
                        <option value="tuic">Tuic</option>
                        <option value="reality">Reality</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="transport-host">Хост:</label>
                    <input type="text" id="transport-host" class="form-control" 
                           placeholder="kws2.web.telegram.org">
                </div>

                <div class="form-group">
                    <label for="transport-port">Порт:</label>
                    <input type="number" id="transport-port" class="form-control" 
                           value="443">
                </div>

                <div class="form-group">
                    <label for="meek-cdn">Meek CDN:</label>
                    <select id="meek-cdn" class="form-control">
                        <option value="cloudflare">Cloudflare</option>
                        <option value="google">Google</option>
                        <option value="amazon">Amazon</option>
                        <option value="microsoft">Microsoft</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="ss-method">Shadowsocks метод:</label>
                    <select id="ss-method" class="form-control">
                        <option value="chacha20-ietf-poly1305">ChaCha20-Poly1305</option>
                        <option value="aes-256-gcm">AES-256-GCM</option>
                        <option value="aes-128-gcm">AES-128-GCM</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="ss-password">Shadowsocks пароль:</label>
                    <input type="password" id="ss-password" class="form-control" 
                           placeholder="Введите пароль">
                </div>

                <div class="form-group">
                    <label for="reality-sni">Reality SNI:</label>
                    <input type="text" id="reality-sni" class="form-control" 
                           value="www.microsoft.com">
                </div>

                <div class="form-actions">
                    <button class="btn btn-primary" onclick="saveTransportConfig()">
                        💾 Сохранить
                    </button>
                    <button class="btn btn-success" onclick="switchTransport()">
                        🔄 Переключить
                    </button>
                    <button class="btn btn-warning" onclick="reconnectTransport()">
                        🔁 Переподключить
                    </button>
                    <button class="btn btn-secondary" onclick="measureAllLatencies()">
                        📏 Замерить latency
                    </button>
                </div>
            </div>
        </div>

        <!-- Post-Quantum Crypto -->
        <div class="card full-width">
            <div class="card-header">
                <span class="card-icon">🔐</span>
                <h3>Post-Quantum Cryptography</h3>
            </div>
            <div class="card-body">
                <div class="stat-row">
                    <span class="stat-label">liboqs доступен:</span>
                    <span class="stat-value" id="pq-liboqs">-</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Алгоритмы:</span>
                    <span class="stat-value" id="pq-algorithms">-</span>
                </div>
                <button class="btn btn-secondary" onclick="checkPQStatus()">
                    🔍 Проверить статус
                </button>
                <button class="btn btn-primary" onclick="generatePQKeys()">
                    🔑 Сгенерировать ключи
                </button>
                <div id="pq-keys-result" class="code-block" style="display: none;"></div>
            </div>
        </div>
    </div>
</div>

<script>
// Transport Management Functions

async function loadTransportConfig() {
    try {
        const response = await fetch('/api/transport/config');
        const config = await response.json();
        
        document.getElementById('current-transport').textContent = config.transport_type || '-';
        document.getElementById('transport-host').textContent = config.host || '-';
        document.getElementById('transport-port').textContent = config.port || '-';
        document.getElementById('transport-auto').textContent = config.auto_select ? '✅' : '❌';
        
        // Populate form
        document.getElementById('transport-type').value = config.transport_type?.toLowerCase() || 'auto';
        document.getElementById('transport-host').value = config.host || '';
        document.getElementById('transport-port').value = config.port || 443;
        document.getElementById('meek-cdn').value = config.meek_cdn || 'cloudflare';
        document.getElementById('ss-method').value = config.ss_method || 'chacha20-ietf-poly1305';
        document.getElementById('reality-sni').value = config.reality_server_name || 'www.microsoft.com';
        
    } catch (error) {
        console.error('Failed to load transport config:', error);
    }
}

async function loadTransportHealth() {
    try {
        const response = await fetch('/api/transport/health');
        const health = await response.json();
        
        const list = document.getElementById('transport-health-list');
        list.innerHTML = '';
        
        for (const [transport, data] of Object.entries(health)) {
            const statusClass = data.is_healthy ? 'status-ok' : 'status-warning';
            const statusText = data.is_healthy ? '✅' : '⚠️';
            
            const item = document.createElement('div');
            item.className = 'health-item';
            item.innerHTML = `
                <div class="health-row">
                    <span class="health-label">${transport}:</span>
                    <span class="health-status ${statusClass}">${statusText}</span>
                </div>
                <div class="health-row">
                    <span class="health-label">Latency:</span>
                    <span class="health-value">${data.latency_ms.toFixed(1)} ms</span>
                </div>
                <div class="health-row">
                    <span class="health-label">Success Rate:</span>
                    <span class="health-value">${(data.success_rate * 100).toFixed(1)}%</span>
                </div>
            `;
            list.appendChild(item);
        }
    } catch (error) {
        console.error('Failed to load health:', error);
    }
}

async function saveTransportConfig() {
    const config = {
        transport_type: document.getElementById('transport-type').value,
        host: document.getElementById('transport-host').value,
        port: parseInt(document.getElementById('transport-port').value),
        meek_cdn: document.getElementById('meek-cdn').value,
        ss_method: document.getElementById('ss-method').value,
        ss_password: document.getElementById('ss-password').value,
        reality_sni: document.getElementById('reality-sni').value,
        reconnect: false
    };
    
    try {
        const response = await fetch('/api/transport/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Конфигурация сохранена', 'success');
            loadTransportConfig();
        } else {
            showNotification('Ошибка: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

async function switchTransport() {
    const transportType = document.getElementById('transport-type').value;
    
    try {
        const response = await fetch('/api/transport/switch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({transport_type: transportType})
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Переключено на ' + transportType, 'success');
            setTimeout(() => loadTransportConfig(), 1000);
        } else {
            showNotification('Ошибка переключения: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

async function reconnectTransport() {
    try {
        const response = await fetch('/api/transport/reconnect', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Переподключено', 'success');
            setTimeout(() => loadTransportConfig(), 1000);
        } else {
            showNotification('Ошибка: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

async function measureAllLatencies() {
    const transports = ['websocket', 'http2', 'quic', 'meek', 'shadowsocks'];
    const results = [];
    
    showNotification('Замер latency...', 'info');
    
    for (const transport of transports) {
        try {
            const response = await fetch('/api/transport/measure', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({transport_type: transport})
            });
            
            const result = await response.json();
            results.push(`${transport}: ${result.latency_ms > 0 ? result.latency_ms.toFixed(1) + ' ms' : '❌'}`);
        } catch (error) {
            results.push(`${transport}: ❌`);
        }
    }
    
    showNotification('Результаты:\\n' + results.join('\\n'), 'info');
}

async function checkPQStatus() {
    try {
        const response = await fetch('/api/pq/status');
        const status = await response.json();
        
        document.getElementById('pq-liboqs').textContent = status.liboqs_available ? '✅' : '❌';
        document.getElementById('pq-algorithms').textContent = status.algorithms.join(', ');
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

async function generatePQKeys() {
    try {
        const response = await fetch('/api/pq/generate-keys', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({hybrid: true})
        });
        
        const result = await response.json();
        
        const resultDiv = document.getElementById('pq-keys-result');
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `
            <strong>Public Key:</strong><br>
            <code>${result.public_key}</code><br><br>
            <strong>Algorithm:</strong> ${result.algorithm}<br>
            <strong>Key Index:</strong> ${result.key_info.key_index}
        `;
        
        showNotification('Ключи сгенерированы', 'success');
    } catch (error) {
        showNotification('Ошибка: ' + error.message, 'error');
    }
}

// Load on tab switch
document.addEventListener('DOMContentLoaded', () => {
    // Add transport tab to navigation
    const nav = document.querySelector('.tab-navigation');
    if (nav) {
        const transportTab = document.createElement('button');
        transportTab.className = 'tab-button';
        transportTab.innerHTML = '📡 Транспорт';
        transportTab.onclick = () => showTab('transport');
        nav.appendChild(transportTab);
    }
    
    // Auto-refresh health every 30 seconds
    setInterval(loadTransportHealth, 30000);
});
</script>

<style>
.health-item {
    padding: 12px;
    margin: 8px 0;
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
    border: 1px solid var(--border);
}

.health-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
}

.health-label {
    color: var(--text-secondary);
    font-weight: 500;
}

.health-status {
    font-weight: 700;
}

.status-ok {
    color: var(--success);
}

.status-warning {
    color: var(--warning);
}

.code-block {
    background: var(--bg-secondary);
    padding: 16px;
    border-radius: var(--radius-sm);
    font-family: 'Courier New', monospace;
    font-size: 12px;
    overflow-x: auto;
    margin-top: 12px;
    border: 1px solid var(--border);
}
</style>
"""


def get_transport_api_routes() -> str:
    """Get transport API routes as string."""
    return TRANSPORT_API_ROUTES


def get_transport_settings_html() -> str:
    """Get transport settings HTML."""
    return TRANSPORT_SETTINGS_HTML
