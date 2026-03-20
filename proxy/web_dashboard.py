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
    Flask = None  # type: ignore[assignment, misc]
    CORS = None  # type: ignore[assignment, misc]

log = logging.getLogger('tg-web-dashboard')

# PWA Manifest template
PWA_MANIFEST = """
{
    "name": "TG WS Proxy",
    "short_name": "TG Proxy",
    "description": "Local SOCKS5 proxy for Telegram Desktop",
    "author": "Dupley Maxim Igorevich",
    "copyright": "© 2026 Dupley Maxim Igorevich. All rights reserved.",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#667eea",
    "theme_color": "#667eea",
    "orientation": "portrait-primary",
    "icons": [
        {
            "src": "/static/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "/static/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ],
    "categories": ["utilities", "productivity"],
    "shortcuts": [
        {
            "name": "Статистика",
            "url": "/?tab=stats",
            "description": "Просмотр статистики прокси"
        },
        {
            "name": "Настройки",
            "url": "/?tab=settings",
            "description": "Настройка прокси"
        }
    ]
}
"""

# Service Worker template
SERVICE_WORKER = """
const CACHE_NAME = 'tg-ws-proxy-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/manifest.json',
    '/api/stats',
    '/api/dc-stats',
    '/api/health',
    '/api/config'
];

// Install event - cache assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
            );
        })
    );
    self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip API calls that modify data
    if (event.request.url.includes('/api/config') && event.request.method === 'POST') {
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                // Cache successful GET responses
                if (networkResponse && networkResponse.status === 200 && event.request.method === 'GET') {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return networkResponse;
            }).catch(() => {
                // Return cached response if network fails
                return cachedResponse;
            });

            return cachedResponse || fetchPromise;
        })
    );
});

// Push notification event (for future use)
self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'TG WS Proxy';
    const options = {
        body: data.body || 'Уведомление от прокси',
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        }
    };
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});
"""

# HTML template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ru" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#667eea">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="TG Proxy">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="author" content="Dupley Maxim Igorevich">
    <meta name="copyright" content="© 2026 Dupley Maxim Igorevich. Все права защищены.">
    <meta name="description" content="Local SOCKS5 proxy for Telegram Desktop">
    <meta name="format-detection" content="telephone=no">
    <!-- Allow HTTP connections for local network -->
    <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests; block-all-mixed-content; default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: http: https:; connect-src 'self' http: https:;">
    <title>TG WS Proxy — Панель управления</title>
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <link rel="icon" type="image/png" sizes="192x192" href="/static/icon-192.png">
    <link rel="icon" type="image/png" sizes="512x512" href="/static/icon-512.png">
    <style>
        :root {
            --primary: #667eea;
            --primary-dark: #5568d3;
            --primary-light: #7c8cf0;
            --secondary: #764ba2;
            --success: #10b981;
            --success-bg: #d1fae5;
            --warning: #f59e0b;
            --warning-bg: #fef3c7;
            --danger: #ef4444;
            --danger-bg: #fee2e2;
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --bg-card: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
            --border: #e2e8f0;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            --radius: 16px;
            --radius-sm: 8px;
            --radius-lg: 24px;
        }

        [data-theme="dark"] {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --border: #334155;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
            --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh;
            color: var(--text-primary);
            padding: env(safe-area-inset-top) 0 env(safe-area-inset-bottom) 0;
            transition: all 0.3s ease;
        }

        .app-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            margin-bottom: 30px;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .logo {
            width: 50px;
            height: 50px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
            box-shadow: var(--shadow);
        }

        .header-title h1 {
            color: white;
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }

        .header-title p {
            color: rgba(255, 255, 255, 0.8);
            font-size: 14px;
        }

        .header-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        /* Theme Toggle */
        .theme-toggle {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: none;
            color: white;
            font-size: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: var(--shadow);
        }

        .theme-toggle:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: scale(1.05);
        }

        .theme-toggle:active {
            transform: scale(0.95);
        }

        /* Status Bar */
        .status-bar {
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: var(--shadow-lg);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 15px;
        }

        .status-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-indicator.online { background: var(--success); }
        .status-indicator.degraded { background: var(--warning); }
        .status-indicator.offline { background: var(--danger); }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.1); }
        }

        .status-text {
            font-weight: 600;
            font-size: 16px;
        }

        .status-subtext {
            color: var(--text-secondary);
            font-size: 13px;
        }

        .refresh-btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .refresh-btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: var(--shadow);
        }

        .refresh-btn:active {
            transform: translateY(0);
        }

        .refresh-btn.spinning svg {
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .stat-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
        }

        .stat-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-xl);
        }

        .stat-icon {
            width: 48px;
            height: 48px;
            border-radius: var(--radius-sm);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            margin-bottom: 16px;
        }

        .stat-icon.blue { background: #dbeafe; color: #3b82f6; }
        .stat-icon.green { background: #d1fae5; color: #10b981; }
        .stat-icon.purple { background: #e9d5ff; color: #8b5cf6; }
        .stat-icon.orange { background: #fed7aa; color: #f97316; }

        [data-theme="dark"] .stat-icon.blue { background: #1e3a5f; }
        [data-theme="dark"] .stat-icon.green { background: #064e3b; }
        [data-theme="dark"] .stat-icon.purple { background: #4c1d95; }
        [data-theme="dark"] .stat-icon.orange { background: #7c2d12; }

        .stat-label {
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1;
        }

        .stat-unit {
            font-size: 14px;
            color: var(--text-muted);
            margin-left: 4px;
        }

        .stat-change {
            display: flex;
            align-items: center;
            gap: 4px;
            margin-top: 12px;
            font-size: 13px;
            font-weight: 600;
        }

        .stat-change.positive { color: var(--success); }
        .stat-change.negative { color: var(--danger); }

        /* Section */
        .section {
            background: var(--bg-card);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: var(--shadow);
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .section-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* DC List */
        .dc-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .dc-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
            background: var(--bg-secondary);
            border-radius: var(--radius-sm);
            transition: all 0.3s ease;
        }

        .dc-item:hover {
            background: var(--bg-primary);
            transform: translateX(4px);
        }

        .dc-left {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .dc-id {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: var(--primary);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
        }

        .dc-info h4 {
            font-weight: 600;
            font-size: 15px;
            margin-bottom: 4px;
        }

        .dc-info p {
            color: var(--text-secondary);
            font-size: 13px;
        }

        .dc-status {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-badge.ok { background: var(--success-bg); color: var(--success); }
        .status-badge.degraded { background: var(--warning-bg); color: var(--warning); }
        .status-badge.error { background: var(--danger-bg); color: var(--danger); }

        /* Action Buttons */
        .action-buttons {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            margin-top: 20px;
        }

        .action-btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 16px 24px;
            border-radius: var(--radius-sm);
            border: none;
            font-weight: 600;
            font-size: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
        }

        .action-btn.primary {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
        }

        .action-btn.primary:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .action-btn.secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 2px solid var(--border);
        }

        .action-btn.secondary:hover {
            background: var(--bg-primary);
            border-color: var(--primary);
        }

        /* Install Prompt */
        .install-prompt {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: var(--bg-card);
            padding: 20px 24px;
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 1000;
            animation: slideUp 0.3s ease forwards;
            max-width: calc(100vw - 40px);
        }

        @keyframes slideUp {
            to { transform: translateX(-50%) translateY(0); }
        }

        .install-prompt-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            color: white;
        }

        .install-prompt-text {
            flex: 1;
        }

        .install-prompt-text h4 {
            font-weight: 700;
            margin-bottom: 4px;
        }

        .install-prompt-text p {
            color: var(--text-secondary);
            font-size: 13px;
        }

        .install-prompt-actions {
            display: flex;
            gap: 8px;
        }

        .install-btn {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: var(--radius-sm);
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .install-btn:hover {
            background: var(--primary-dark);
        }

        .install-dismiss {
            background: transparent;
            color: var(--text-muted);
            border: none;
            padding: 8px;
            cursor: pointer;
            font-size: 20px;
            transition: all 0.3s ease;
        }

        .install-dismiss:hover {
            color: var(--text-primary);
        }

        /* Loading State */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            color: white;
        }

        .loading-spinner {
            width: 48px;
            height: 48px;
            border: 4px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 16px;
        }

        .loading-text {
            font-size: 16px;
            opacity: 0.9;
        }

        /* Error State */
        .error-state {
            background: var(--danger-bg);
            border: 1px solid var(--danger);
            border-radius: var(--radius);
            padding: 24px;
            text-align: center;
            margin: 20px 0;
        }

        .error-state h3 {
            color: var(--danger);
            margin-bottom: 12px;
            font-size: 18px;
        }

        .error-state p {
            color: var(--text-secondary);
            margin-bottom: 16px;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .app-container {
                padding: 16px;
            }

            .header {
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }

            .header-actions {
                width: 100%;
                justify-content: flex-end;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }

            .status-bar {
                flex-direction: column;
                align-items: flex-start;
            }

            .refresh-btn {
                width: 100%;
                justify-content: center;
            }

            .install-prompt {
                flex-direction: column;
                text-align: center;
                bottom: 10px;
            }

            .install-prompt-actions {
                width: 100%;
                justify-content: center;
            }
        }

        /* Safe area for notched devices */
        @supports (padding: max(0px)) {
            body {
                padding-left: max(0px, env(safe-area-inset-left));
                padding-right: max(0px, env(safe-area-inset-right));
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <!-- Header -->
        <header class="header">
            <div class="header-left">
                <div class="logo">🔒</div>
                <div class="header-title">
                    <h1>TG WS Proxy</h1>
                    <p>Панель управления</p>
                </div>
            </div>
            <div class="header-actions">
                <button class="theme-toggle" onclick="toggleTheme()" aria-label="Переключить тему">
                    🌙
                </button>
            </div>
        </header>

        <!-- Loading State -->
        <div id="loading" class="loading">
            <div class="loading-spinner"></div>
            <p class="loading-text">Загрузка статистики...</p>
        </div>

        <!-- Main Content -->
        <div id="app" style="display: none;">
            <!-- Status Bar -->
            <div class="status-bar">
                <div class="status-left">
                    <span class="status-indicator" id="status-indicator"></span>
                    <div>
                        <div class="status-text" id="status-text">Работает нормально</div>
                        <div class="status-subtext" id="status-subtext">Все системы в норме</div>
                    </div>
                </div>
                <button class="refresh-btn" onclick="refreshStats()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M23 4v6h-6M1 20v-6h6"/>
                        <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
                    </svg>
                    Обновить
                </button>
            </div>

            <!-- Stats Grid -->
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-icon blue">📡</div>
                    <div class="stat-label">Всего подключений</div>
                    <div class="stat-value" id="total-connections">0</div>
                    <div class="stat-change positive" id="connections-change">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 15l-6-6-6 6"/>
                        </svg>
                        <span>+0%</span>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon green">⚡</div>
                    <div class="stat-label">WebSocket</div>
                    <div class="stat-value" id="ws-connections">0</div>
                    <div class="stat-change positive">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                        <span>Активно</span>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon purple">📊</div>
                    <div class="stat-label">Pool Efficiency</div>
                    <div class="stat-value" id="pool-efficiency">0%</div>
                    <div class="stat-change" id="pool-change">
                        <span>—</span>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-icon orange">📈</div>
                    <div class="stat-label">Трафик</div>
                    <div class="stat-value" id="traffic-total">0 B</div>
                    <div class="stat-change" id="traffic-change">
                        <span>Обновляется</span>
                    </div>
                </div>
            </div>

            <!-- Traffic Section -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">
                        📶 Трафик
                    </h2>
                </div>
                <div class="stats-grid" style="margin-bottom: 0;">
                    <div class="stat-card" style="box-shadow: none; border: 1px solid var(--border);">
                        <div class="stat-label">Входящий</div>
                        <div class="stat-value" id="bytes-up">0 <span class="stat-unit">B</span></div>
                    </div>
                    <div class="stat-card" style="box-shadow: none; border: 1px solid var(--border);">
                        <div class="stat-label">Исходящий</div>
                        <div class="stat-value" id="bytes-down">0 <span class="stat-unit">B</span></div>
                    </div>
                </div>
            </div>

            <!-- Data Centers Section -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">
                        🌍 Data Centers
                    </h2>
                </div>
                <div class="dc-list" id="dc-list">
                    <!-- DC items will be inserted here -->
                </div>
            </div>

            <!-- Actions Section -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">
                        ⚡ Быстрые действия
                    </h2>
                </div>
                <div class="action-buttons">
                    <a href="tg://socks?server=127.0.0.1&port=1080" class="action-btn primary">
                        🔓 Открыть в Telegram
                    </a>
                    <button class="action-btn secondary" onclick="copyProxyConfig()">
                        📋 Копировать конфиг
                    </button>
                    <button class="action-btn secondary" onclick="showQRCode()">
                        📱 QR-код
                    </button>
                </div>
            </div>

            <!-- Info Section -->
            <div class="section">
                <div class="section-header">
                    <h2 class="section-title">
                        ℹ️ Информация
                    </h2>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                    <div>
                        <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 4px;">Версия</div>
                        <div style="font-weight: 600;" id="version">2.10.0</div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 4px;">Время работы</div>
                        <div style="font-weight: 600;" id="uptime">—</div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 4px;">Сервер</div>
                        <div style="font-weight: 600;" id="server-info">127.0.0.1:8080</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="footer">
            <p>© 2026 Dupley Maxim Igorevich. Все права защищены.</p>
        </footer>
    </div>

    <!-- Install Prompt -->
    <div id="install-prompt" class="install-prompt" style="display: none;">
        <div class="install-prompt-icon">📲</div>
        <div class="install-prompt-text">
            <h4>Установить приложение</h4>
            <p>Добавьте TG WS Proxy на главный экран</p>
        </div>
        <div class="install-prompt-actions">
            <button class="install-btn" onclick="installApp()">Установить</button>
            <button class="install-dismiss" onclick="dismissInstallPrompt()">✕</button>
        </div>
    </div>

    <script>
        // State
        let deferredPrompt = null;
        let previousStats = null;
        let autoRefreshInterval = null;

        // Theme management
        function toggleTheme() {
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            document.querySelector('.theme-toggle').textContent = next === 'dark' ? '☀️' : '🌙';
        }

        // Load saved theme
        (function() {
            const saved = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', saved);
            document.querySelector('.theme-toggle').textContent = saved === 'dark' ? '☀️' : '🌙';
        })();

        // Format bytes
        function humanBytes(n) {
            const units = ['B', 'KB', 'MB', 'GB', 'TB'];
            let i = 0;
            while (Math.abs(n) >= 1024 && i < units.length - 1) {
                n /= 1024;
                i++;
            }
            return n.toFixed(1) + ' ' + units[i];
        }

        // Copy proxy config
        function copyProxyConfig() {
            const config = 'SOCKS5 127.0.0.1 1080';
            navigator.clipboard.writeText(config).then(() => {
                showToast('✅ Конфигурация скопирована!');
            }).catch(() => {
                showToast('❌ Не удалось скопировать');
            });
        }

        // Show QR code
        function showQRCode() {
            const url = window.location.origin;
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(url)}`;
            
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 2000;
                animation: fadeIn 0.3s ease;
            `;
            
            modal.innerHTML = `
                <div style="background: white; padding: 30px; border-radius: 24px; text-align: center; max-width: 400px; margin: 20px;">
                    <h3 style="margin-bottom: 20px; color: #1e293b;">📱 QR-код для подключения</h3>
                    <img src="${qrUrl}" alt="QR Code" style="width: 100%; max-width: 300px; border-radius: 12px;">
                    <p style="margin-top: 20px; color: #64748b; font-size: 14px;">Отсканируйте для быстрого доступа</p>
                    <button onclick="this.closest('div[style*=fixed]').remove()" style="margin-top: 20px; padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer;">Закрыть</button>
                </div>
            `;
            
            document.body.appendChild(modal);
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        }

        // Toast notification
        function showToast(message) {
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(-100px);
                background: var(--bg-card);
                padding: 16px 24px;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                z-index: 3000;
                animation: slideDown 0.3s ease forwards;
                font-weight: 600;
            `;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }

        // Load statistics
        async function loadStats() {
            const refreshBtn = document.querySelector('.refresh-btn');
            refreshBtn?.classList.add('spinning');

            try {
                const response = await fetch('/api/stats', { 
                    method: 'GET',
                    headers: { 'Accept': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const stats = await response.json();
                
                // Update connection stats
                const totalConn = stats.connections_total || 0;
                document.getElementById('total-connections').textContent = totalConn.toLocaleString();
                
                const wsConn = stats.connections_ws || 0;
                document.getElementById('ws-connections').textContent = wsConn.toLocaleString();
                
                // Pool efficiency
                const poolTotal = (stats.pool_hits || 0) + (stats.pool_misses || 0);
                const efficiency = poolTotal > 0 ? Math.round((stats.pool_hits || 0) / poolTotal * 100) : 100;
                document.getElementById('pool-efficiency').textContent = efficiency + '%';
                
                // Traffic
                const totalTraffic = (stats.bytes_up || 0) + (stats.bytes_down || 0);
                document.getElementById('traffic-total').textContent = humanBytes(totalTraffic);
                document.getElementById('bytes-up').innerHTML = `${humanBytes(stats.bytes_up || 0)} <span class="stat-unit">↑</span>`;
                document.getElementById('bytes-down').innerHTML = `${humanBytes(stats.bytes_down || 0)} <span class="stat-unit">↓</span>`;
                
                // Update info
                document.getElementById('version').textContent = stats.version || '2.10.0';
                document.getElementById('uptime').textContent = stats.uptime || '—';
                document.getElementById('server-info').textContent = `${stats.host || '127.0.0.1'}:${stats.port || '8080'}`;
                
                // Calculate changes
                if (previousStats) {
                    const connChange = totalConn - (previousStats.connections_total || 0);
                    const connPercent = previousStats.connections_total > 0 ? 
                        Math.round((connChange / previousStats.connections_total) * 100) : 0;
                    
                    const changeEl = document.getElementById('connections-change');
                    if (changeEl) {
                        changeEl.className = `stat-change ${connChange >= 0 ? 'positive' : 'negative'}`;
                        changeEl.querySelector('span').textContent = `${connChange >= 0 ? '+' : ''}${connPercent}%`;
                    }
                }
                
                previousStats = stats;
                
                // Load DC stats
                await loadDcStats();
                
                // Update status
                updateHealthStatus(stats);
                
                // Show app, hide loading
                document.getElementById('loading').style.display = 'none';
                document.getElementById('app').style.display = 'block';
                
            } catch (error) {
                console.error('Failed to load stats:', error);
                document.getElementById('loading').innerHTML = `
                    <div class="error-state">
                        <h3>❌ Ошибка подключения</h3>
                        <p>Не удалось подключиться к прокси.<br>Убедитесь, что прокси запущен.</p>
                        <button onclick="location.reload()" class="action-btn primary" style="margin: 0 auto;">Попробовать снова</button>
                    </div>
                `;
            } finally {
                refreshBtn?.classList.remove('spinning');
            }
        }

        // Update health status
        function updateHealthStatus(stats) {
            const wsErrors = stats.ws_errors || 0;
            const indicator = document.getElementById('status-indicator');
            const text = document.getElementById('status-text');
            const subtext = document.getElementById('status-subtext');
            
            if (wsErrors < 5) {
                indicator.className = 'status-indicator online';
                text.textContent = 'Работает нормально';
                subtext.textContent = 'Все системы в норме';
            } else if (wsErrors < 15) {
                indicator.className = 'status-indicator degraded';
                text.textContent = 'Работает с проблемами';
                subtext.textContent = `${wsErrors} ошибок WebSocket`;
            } else {
                indicator.className = 'status-indicator offline';
                text.textContent = 'Проблемы с подключением';
                subtext.textContent = `${wsErrors} ошибок WebSocket`;
            }
        }

        // Load DC statistics
        async function loadDcStats() {
            try {
                const response = await fetch('/api/dc-stats', {
                    method: 'GET',
                    headers: { 'Accept': 'application/json' }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                const list = document.getElementById('dc-list');
                list.innerHTML = '';
                
                (data.dc_stats || []).forEach(dc => {
                    const connections = dc.connections || 0;
                    const errors = dc.errors || 0;
                    const errorRate = connections > 0 ? (errors / connections * 100) : 0;
                    
                    let statusClass = 'ok';
                    let statusText = 'OK';
                    if (errorRate > 30) {
                        statusClass = 'error';
                        statusText = 'Ошибка';
                    } else if (errorRate > 10) {
                        statusClass = 'degraded';
                        statusText = 'Проблемы';
                    }
                    
                    const item = document.createElement('div');
                    item.className = 'dc-item';
                    item.innerHTML = `
                        <div class="dc-left">
                            <div class="dc-id">${dc.dc_id}</div>
                            <div class="dc-info">
                                <h4>DC ${dc.dc_id}</h4>
                                <p>${connections} подключений, ${errors} ошибок</p>
                            </div>
                        </div>
                        <div class="dc-status">
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                    `;
                    list.appendChild(item);
                });
                
            } catch (error) {
                console.error('Failed to load DC stats:', error);
            }
        }

        // Refresh stats
        function refreshStats() {
            const refreshBtn = document.querySelector('.refresh-btn');
            refreshBtn?.classList.add('spinning');
            setTimeout(() => {
                loadStats();
                setTimeout(() => refreshBtn?.classList.remove('spinning'), 1000);
            }, 500);
        }

        // Install prompt
        function showInstallPrompt() {
            const prompt = document.getElementById('install-prompt');
            if (prompt && !isStandalone()) {
                prompt.style.display = 'flex';
                setTimeout(() => {
                    prompt.style.animation = 'slideUp 0.3s ease forwards';
                }, 10000);
            }
        }

        function dismissInstallPrompt() {
            const prompt = document.getElementById('install-prompt');
            if (prompt) {
                prompt.style.animation = 'slideUp 0.3s ease reverse';
                setTimeout(() => prompt.style.display = 'none', 300);
            }
            localStorage.setItem('install-prompt-dismissed', 'true');
        }

        async function installApp() {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            await deferredPrompt.userChoice;
            dismissInstallPrompt();
            deferredPrompt = null;
        }

        // Check if standalone
        function isStandalone() {
            return window.matchMedia('(display-mode: standalone)').matches ||
                   window.navigator.standalone === true;
        }

        // Auto-refresh
        function startAutoRefresh() {
            autoRefreshInterval = setInterval(loadStats, 5000);
        }

        // PWA Install event
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            if (!localStorage.getItem('install-prompt-dismissed')) {
                showInstallPrompt();
            }
        });

        // Initialize
        let loadTimeout = null;
        document.addEventListener('DOMContentLoaded', () => {
            // Set timeout for initial load
            loadTimeout = setTimeout(() => {
                const loading = document.getElementById('loading');
                if (loading && document.getElementById('app').style.display === 'none') {
                    loading.innerHTML = `
                        <div class="error-state">
                            <h3>⚠️ Превышено время ожидания</h3>
                            <p>Сервер не отвечает. Проверьте:<br>1. Подключение к интернету<br>2. URL адрес<br>3. Брандмауэр</p>
                            <button onclick="location.reload()" class="action-btn primary" style="margin: 0 auto;">Обновить страницу</button>
                        </div>
                    `;
                }
            }, 15000); // 15 seconds timeout
            
            loadStats().then(() => {
                if (loadTimeout) clearTimeout(loadTimeout);
            });
            startAutoRefresh();
        });
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

        # Get the directory where web_dashboard.py is located
        self.static_folder = os.path.join(os.path.dirname(__file__), 'static')
        os.makedirs(self.static_folder, exist_ok=True)

        self.app = Flask(__name__, static_folder=self.static_folder)
        self.app.config['SECRET_KEY'] = os.urandom(24).hex()
        CORS(self.app)

        self._setup_routes()
        self._thread: threading.Thread | None = None

    def _setup_routes(self) -> None:
        """Setup Flask routes."""

        @self.app.route('/')
        def dashboard() -> str:
            """Main dashboard page."""
            return render_template_string(DASHBOARD_HTML)

        @self.app.route('/api/stats')
        def api_stats() -> Response:
            """API endpoint for statistics."""
            stats = self.get_stats()
            stats['version'] = '2.5.5'
            stats['host'] = self.host
            stats['port'] = self.port
            stats['uptime'] = str(datetime.now() - self.start_time).split('.')[0]
            return jsonify(stats)

        @self.app.route('/api/stats/export')
        def api_stats_export() -> Response:
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
        def api_get_config() -> Response | tuple[Response, int]:
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
        def api_update_config() -> Response | tuple[Response, int]:
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
        def api_generate_qr() -> Response | tuple[Response, int]:
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
        def api_health() -> Response:
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
        def api_dc_stats() -> Response:
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

        @self.app.route('/manifest.json')
        def manifest() -> Response:
            """Serve PWA manifest."""
            return Response(PWA_MANIFEST, mimetype='application/json')

        @self.app.route('/sw.js')
        def service_worker() -> Response:
            """Serve Service Worker."""
            return Response(SERVICE_WORKER, mimetype='application/javascript')

    def start(self) -> None:
        """Start the web dashboard in a background thread."""
        if self._thread and self._thread.is_alive():
            log.warning("Dashboard already running")
            return

        def run_app() -> None:
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

    def stop(self) -> None:
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
) -> None:
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
    def mock_stats() -> dict:
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
