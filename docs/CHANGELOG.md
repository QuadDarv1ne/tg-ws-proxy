# Changelog

Все изменения проекта TG WS Proxy.

## [v2.57.0] - 2026-03-23

### Добавлено
- **Gaming Console Proxy** — поддержка игровых консолей
  - PS4/PS5 настройка прокси
  - Xbox конфигурация
  - Nintendo Switch поддержка
  - UPnP port forwarding
  - Автоматическая генерация инструкций
- **setup_gaming_proxy.py** — скрипт настройки консолей
- **docs/GAMING_PROXY.md** — документация для консолей

### Изменено
- Улучшена структура документации
- Обновлён todo.md

## [v2.56.0] - 2026-03-23

### Добавлено
- **Proxy Chain** — цепочки прокси
  - Multi-hop routing
  - Протоколы: SOCKS5, HTTP, WebSocket, MTProto, Shadowsocks, VMESS
  - Automatic failover
  - Latency-based selection
- **proxy/proxy_chain.py** — менеджер цепочек прокси

### Изменено
- Обновлена документация

## [v2.55.0] - 2026-03-23

### Добавлено
- **DPI Bypass** — обход Deep Packet Inspection
  - Packet fragmentation
  - Fake HTTP headers
  - TLS fingerprint spoofing
  - Domain fronting
  - Traffic padding
  - Timing jitter
- **proxy/dpi_bypass.py** — DPI bypass engine
- **proxy/mtproxy.py** — MTProxy protocol support
  - MTProto 1.0/2.0
  - DD-Tags для обхода блокировок
  - Secret generation
  - QR code generation
- **proxy/cloudflare_warp.py** — Cloudflare WARP integration
  - WARP SOCKS proxy
  - Cloudflare Tunnel
  - Domain fronting
  - Routing rules
- **proxy/windows_proxy.py** — Windows system proxy
  - Registry proxy settings
  - WinHTTP configuration
  - PAC support

### Изменено
- 47 модулей в proxy/
- Улучшена документация

## [v2.54.0] - 2026-03-23

### Добавлено
- **Pluggable Transports** — транспорта для обхода блокировок
  - Obfs4 obfuscation
  - WebSocket fragmentation
  - TLS fingerprint spoofing
  - Domain fronting
  - Shadowsocks encryption
- **HTTP/2 Transport** — HTTP/2 поддержка
  - Multiplexing
  - HPACK compression
  - Flow control
- **Anti-censorship Config** — конфигурация обхода цензуры

### Изменено
- 42 модуля в proxy/
- Улучшена документация обхода блокировок

## [v2.53.1] - 2026-03-23

### Добавлено
- **Rate Limiter Prometheus Metrics** — 10 метрик для экспорта
  - active_connections
  - unique_ips
  - banned_ips
  - total_violations
  - ddos_attacks_total
  - flood_attacks_total
  - suspicious_ips
  - subnets_active
  - requests_per_minute
  - flood_rate

### Изменено
- Интеграция с /metrics endpoint

## [v2.53.0] - 2026-03-23

### Добавлено
- **Dashboard Metrics History API**
  - GET /api/metrics/history — история метрик
  - GET /api/metrics/history/export — экспорт JSON/CSV
  - GET /api/metrics/trend — анализ трендов
- **Summary statistics** — min, max, avg, p50, p95, p99
- **Trend analysis** — direction, slope, change%

### Изменено
- Улучшена веб-панель

## [v2.52.1] - 2026-03-23

### Добавлено
- **Metrics History Integration** в Rate Limiter
  - rate_limiter_rps — requests per second
  - rate_limiter_cps — connections per second
  - rate_limiter_violations — нарушения
  - rate_limiter_bans — баны
  - rate_limiter_ddos_detected — DDoS атаки
  - rate_limiter_flood_detected — flood атаки

## [v2.52.0] - 2026-03-23

### Добавлено
- **Metrics History** — хранение истории метрик
  - SQLite backend
  - 30-day retention
  - Агрегации (p50, p95, p99)
  - Trend analysis
  - Export to JSON/CSV
- **proxy/metrics_history.py** — новый модуль (670+ строк)

### Изменено
- 38 модулей в proxy/

## [v2.51.0] - 2026-03-23

### Добавлено
- **Real-time Dashboard SSE** — Server-Sent Events
  - GET /api/stream — real-time stream
  - Обновления каждые 2 секунды
  - Auto-reconnect
- **Metrics History API endpoints**

### Изменено
- Улучшена веб-панель

## [v2.50.1] - 2026-03-23

### Добавлено
- **Token Bucket Algorithm** в Rate Limiter
- **API Rate Limiting** — для web dashboard
- **Connection Scoring** — детекция подозрительной активности

### Изменено
- Улучшен rate limiter

## [v2.50.0] - 2026-03-23

### Добавлено
- **Rate Limiting Improvements**
  - DDoS Detection (50 RPS threshold)
  - Connection Flood Protection (50 CPS)
  - Geographic Rate Limiting (/24 subnet)
  - Progressive Penalties
- **proxy/rate_limiter.py** — расширенный rate limiter

### Изменено
- Улучшена защита от злоупотреблений

## [v2.49.0] - 2026-03-23

### Добавлено
- **Health Check Enhancement**
  - Агрессивная проверка (15с интервал)
  - Stale connection detection
  - Consecutive failures tracking
- **Adaptive Timeout Tuning**
  - Динамические таймауты на основе latency
  - Rolling window (100 замеров)
- **E2E Encryption**
  - X25519 ECDH key exchange
  - AES-256-GCM encryption
  - Replay attack protection
- **Diagnostic Report**
  - Full connectivity testing
  - Health assessment (5 уровней)
  - Export to JSON/CSV

### Изменено
- 37 модулей в proxy/

## [v2.48.1] - 2026-03-23

### Исправлено
- **AGP 9.1 Compatibility** — исправление ошибки proguard-android.txt
- **Gradle Refactoring** — очистка build.gradle

## [v2.48.0] - 2026-03-22

### Добавлено
- **Configuration System**
  - JSON/YAML загрузка
  - Environment overrides (TGWS_*)
  - Hot reload
  - Dataclasses для настроек
- **proxy/config.py** — система конфигурации

### Изменено
- 642 теста passed
- Ruff: 0 ошибок
- Mypy: 0 ошибок

---

**Формат:** Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
**Версионирование:** [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
