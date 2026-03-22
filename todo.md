# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.48.1: build & compatibility)

### Android & Build System
- ✅ **AGP 9.1.0 Compatibility** — исправление ошибки `proguard-android.txt` is no longer supported.
  - Динамическая замена устаревшего файла на `proguard-android-optimize.txt` через root `build.gradle`.
  - Автоматическое исправление для всех Capacitor плагинов в `node_modules`.
- ✅ **Gradle Refactoring** — очистка root `build.gradle` от неэффективных конфигураций.

### Refactoring Complete ✅
- ✅ **mtproto_parser.py** — выделен парсинг MTProto пакетов
- ✅ **Модульность** — все 4 модуля выделены (socks5, websocket, pool, mtproto)

### Performance Optimization
- ✅ **Performance Profiler** — cProfile интеграция с optimization suggestions
- ✅ **DNS Resolver Aggressive Caching** — hit rate >90% target

### Monitoring & Observability
- ✅ **Prometheus metrics endpoint** — `/metrics` для сбора метрик
- ✅ **Circuit breaker** — защита от cascade failures (websocket, tcp, dns)

---

## ✅ Выполнено (v2.50.0: rate limiting + DDoS protection)

### Безопасность
- ✅ **Rate Limiting Improvements** — защита от DDoS и злоупотреблений
  - `proxy/rate_limiter.py` — расширенный rate limiter (+300 строк)

  **Token Bucket Algorithm:**
  • Более эффективный алгоритм (O(1) vs O(n) sliding window)
  • token_bucket_capacity: 20 tokens
  • token_bucket_refill_rate: 10 tokens/second
  • Автоматическое refill при check_rate_limit
  • Конфигурация: token_bucket_enabled, token_bucket_capacity

  **API Rate Limiting:**
  • Отдельный token bucket для API запросов (web dashboard)
  • api_requests_per_second: 5.0
  • api_burst_size: 10 requests
  • Метод: check_api_rate_limit(ip)
  • Конфигурация: api_rate_limit_enabled, api_burst_size

  **Connection Scoring:**
  • suspicious_score tracking per IP
  • score_decay_per_second: 1.0
  • suspicious_score_threshold: 100 (auto-ban)
  • Метод: record_suspicious_activity(ip, delta)
  • Auto-ban при превышении threshold
  • Конфигурация: connection_scoring_enabled, suspicious_score_threshold

  **DDoS Detection:**
  • Детекция атак по RPS (threshold: 50 RPS)
  • Progressive ban duration (exponential backoff)
  • Max ban duration: 24 часа
  • Логирование critical событий
  • Конфигурация: ddos_detection_enabled, ddos_threshold_rps

  **Connection Flood Protection:**
  • Детекция по CPS (threshold: 50 CPS)
  • Ban duration: 10 минут с escalation
  • Отдельный счётчик flood_violations
  • Конфигурация: flood_detection_enabled, flood_threshold_connections

  **Geographic Rate Limiting:**
  • /24 subnet tracking для IPv4
  • Max connections per subnet: 20
  • Автоматическое отслеживание IP в subnet
  • Конфигурация: enable_ip_range_limiting, max_connections_per_subnet

  **Progressive Penalties:**
  • total_bans tracking per IP
  • last_ban_duration tracking
  • Escalation: ban duration удваивается
  • Конфигурация: progressive_ban_enabled, max_ban_duration

  **Prometheus Metrics Integration:**
  • get_metrics_for_prometheus() метод
  • 9 метрик для экспорта:
    - rate_limiter_active_connections
    - rate_limiter_unique_ips
    - rate_limiter_banned_ips
    - rate_limiter_total_violations
    - rate_limiter_ddos_attacks
    - rate_limiter_flood_attacks
    - rate_limiter_suspicious_ips
    - rate_limiter_requests_per_minute
    - rate_limiter_flood_rate

  **Расширенная статистика:**
  • Global: ddos_attacks_detected, flood_attacks_detected, subnets_active, suspicious_ips
  • Per-IP: ddos_violations, flood_violations, total_bans, subnet, tokens_remaining, suspicious_score
  • connection_flood_rate (CPS)
  • API tokens remaining

---

## ✅ Выполнено (v2.52.0: metrics history + monitoring)

### Мониторинг
- ✅ **Metrics History** — хранение истории метрик за 30 дней
  - `proxy/metrics_history.py` — новый модуль (670+ строк)
  
  **Возможности:**
  • SQLite backend для персистентности
  • 30-day retention policy с авто-очисткой
  • WAL mode для лучшей конкурентности
  • In-memory cache (1000 recent metrics)
  
  **Функции:**
  • record_metric() — запись отдельной метрики
  • record_metrics_batch() — пакетная запись
  • get_metric_summary() — summary (min, max, avg, p50, p95, p99)
  • get_metric_history() — история с разрешением (raw/minute/hour)
  • get_trend() — анализ тренда (direction, slope, change%)
  • export_to_json() — экспорт в JSON
  • export_to_csv() — экспорт в CSV
  
  **Агрегации:**
  • p50, p95, p99 percentiles
  • min, max, avg, count
  • linear regression slope
  
  **Индексы:**
  • idx_metrics_name_time — для queries по имени + времени
  • idx_metrics_time — для time-range queries
  • idx_hourly_name_time — для hourly summaries

- ✅ **Rate Limiter Integration** — запись метрик в history
  - rate_limiter_rps — requests per second per IP
  - rate_limiter_cps — connections per second per IP
  - rate_limiter_violations — нарушения rate limiting
  - rate_limiter_bans — баны IP
  - rate_limiter_ddos_detected — DDoS атаки
  - rate_limiter_flood_detected — flood атаки
  
  **Labels:**
  • ip: IP адрес нарушителя
  • type: тип нарушения
  • rps/cps: значения метрик
  • duration: длительность бана

---

## ✅ Выполнено (v2.53.0: dashboard metrics + prometheus)

### Мониторинг
- ✅ **Dashboard Metrics History API** — API для работы с историей метрик
  - `GET /api/metrics/history` — история метрик с фильтрацией
    • metric: имя метрики (default: rate_limiter_rps)
    • hours: временной диапазон (default: 24)
    • resolution: raw/minute/hour/auto
    • Response: history, summary (min/max/avg/p50/p95/p99), trend
  
  - `GET /api/metrics/history/export` — экспорт данных
    • format: json/csv
    • Response: file download
  
  - `GET /api/metrics/trend` — анализ трендов
    • multiple metrics support
    • Response: trends per metric
  
- ✅ **Prometheus Metrics Export** — экспорт метрик rate limiter
  - `get_prometheus_metrics()` метод
  - 10 метрик для экспорта:
    • rate_limiter_active_connections (gauge)
    • rate_limiter_unique_ips (gauge)
    • rate_limiter_banned_ips (gauge)
    • rate_limiter_total_violations (counter)
    • rate_limiter_ddos_attacks_total (counter)
    • rate_limiter_flood_attacks_total (counter)
    • rate_limiter_suspicious_ips (gauge)
    • rate_limiter_subnets_active (gauge)
    • rate_limiter_requests_per_minute (gauge)
    • rate_limiter_flood_rate (gauge)
  - HELP и TYPE аннотации для каждой метрики
  - Совместимость с Prometheus exposition format

---

## ✅ Выполнено (v2.54.0: anti-censorship + pluggable transports)

### Обход блокировок
- ✅ **Pluggable Transports** — технологии обфускации трафика
  - `proxy/pluggable_transports.py` — новый модуль (850+ строк)

  **Obfs4-like Obfuscation:**
  • XOR-шифрование с HMAC-DRBG keystream
  • Client/server handshake (1968/1948 bytes)
  • Симметричное шифрование с ключами из shared secret
  • Методы: create_client_handshake(), obfuscate(), deobfuscate()

  **WebSocket Fragmentation:**
  • Разбиение фреймов на фрагменты 64-256 байт
  • Рандомизация размеров фрагментов
  • Методы: fragment(), reassemble()
  • Настройки: fragment_min_size, fragment_max_size

  **TLS Fingerprint Spoofing (JA3):**
  • Подмена ClientHello под браузеры
  • Профили: chrome_120, firefox_121, safari_17
  • Подмена cipher suites и extensions
  • Метод: create_ssl_context()

  **Domain Fronting:**
  • CDN providers: Cloudflare, Google, Azure, Amazon
  • SNI spoofing с подменой Host header
  • Метод: wrap_connection()
  • Настройки: fronting_provider

  **Shadowsocks-style Encryption:**
  • Шифры: aes-256-gcm, chacha20-ietf-poly1305, aes-128-gcm
  • PBKDF2 key derivation (100000 iterations)
  • Nonce-based encryption
  • Методы: encrypt(), decrypt()

  **Traffic Shaping:**
  • Random jitter (10-100ms)
  • Random padding (10% ratio)
  • Методы: apply_jitter(), add_padding(), remove_padding()

  **Censorship Detection:**
  • Детекция: TCP reset, DNS poisoning, SNI blocking, timeout, DPI
  • Анализ паттернов за 5 минут
  • Рекомендации по countermeasures
  • Методы: record_failure(), get_recommendation(), is_blocked()

  **Obfuscation Pipeline:**
  • Комбинация всех техник
  • Настраиваемые слои
  • Методы: obfuscate(), deobfuscate(), get_ssl_context()

- ✅ **Bridge/Relay Routing** — маршрутизация через релеи
  - `proxy/bridge_relay.py` — новый модуль (650+ строк)

  **RelayNode Configuration:**
  • ID, host, port, protocol
  • Country, city, latency, success_rate
  • Domain fronting support
  • Shadowsocks config
  • Priority scoring

  **Bridge Protocol:**
  • Magic: TGWP, Version: 0x01
  • Message types: CONNECT, DATA, CLOSE, PING, PONG, AUTH, ERROR
  • Framing: 9-byte header + payload
  • Методы: encode_*, decode_messages()

  **BridgeClient:**
  • Async connect с SSL/TLS
  • Domain fronting support
  • Obfuscation integration
  • Методы: connect(), send(), recv(), ping(), close()

  **RelayManager:**
  • Public relays: EU (DE, NL), Asia (SG), US (East, West)
  • Fronting relays: Cloudflare, Google
  • Health checks
  • Best relay selection (scoring algorithm)
  • Stats tracking (latency, success_rate)
  • Методы: select_best_relay(), check_relay_health(), update_relay_stats()

- ✅ **HTTP/2 Transport** — альтернатива WebSocket
  - `proxy/http2_transport.py` — новый модуль (550+ строк)

  **HTTP/2 Connection:**
  • Framing layer implementation
  • SETTINGS, HEADERS, DATA, PING, GOAWAY frames
  • HPACK-like header encoding (simplified)
  • Flow control (WINDOW_UPDATE)
  • Методы: connect(), create_stream(), send_data(), recv_data(), ping()

  **HTTP/2Transport:**
  • Wrapper для Telegram traffic
  • TLS с ALPN (h2)
  • Obfuscation integration
  • Методы: connect(), send(), recv(), close()

  **Fallback Logic:**
  • enable_fallback: true (default)
  • prefer_http2: false (default)
  • http2_only: false (default)
  • Auto-fallback при блокировке WebSocket

- ✅ **Cloudflare Integration** — обход блокировок через Cloudflare
  - `proxy/cloudflare_tunnel.py` — Cloudflare Tunnel (550+ строк)
  - `proxy/cloudflare_warp.py` — Cloudflare WARP (440+ строк)

  **CloudflareTunnel:**
  • cloudflared binary management (auto-download)
  • Tunnel configuration and lifecycle
  • Automatic reconnection and health monitoring
  • SOCKS5/HTTP proxy via tunnel
  • Metrics and monitoring support

  **CloudflareWARP:**
  • WARP SOCKS proxy interface (port 40000)
  • Cloudflare Zero Trust team support
  • Domain fronting through Cloudflare CDN
  • WARP routing configuration
  • License key and access credentials

- ✅ **MTProxy Protocol** — поддержка MTProto
  - `proxy/mtproxy.py` — новый модуль (536 строк)

  **MTProto Support:**
  • MTProto 1.0 и 2.0
  • Secret generation and parsing
  • DD-Tags for anti-censorship
  • TLS obfuscation (disguise as telegram.org)
  • Proxy link format (tg://proxy)
  • Upstream proxy chain support

- ✅ **System Proxy Integration** — системные прокси
  - `proxy/system_proxy.py` — кроссплатформенный (345 строк)
  - `proxy/windows_proxy.py` — Windows-specific (510 строк)

  **SystemProxy:**
  • Windows Registry proxy settings
  • WinHTTP proxy configuration
  • Proxy enable/disable with rollback
  • Cross-platform support (Win/Linux/macOS)

  **WindowsProxy:**
  • WinHTTP proxy settings
  • Internet Explorer/Edge proxy settings
  • PAC (Proxy Auto-Config) support
  • Automatic proxy detection (WPAD)
  • Bypass list configuration

- ✅ **Anti-censorship Configuration** — гибкая конфигурация
  - `proxy/anticensorship_config.py` — новый модуль (300+ строк)

  **ObfuscationConfig:**
  • enable_obfs4, enable_shadowsocks
  • enable_fragmentation, fragment_min/max_size
  • enable_traffic_shaping, traffic_jitter_ms, traffic_padding_ratio
  • enable_tls_spoof, browser_profile
  • enable_domain_fronting, fronting_provider

  **RelayConfig:**
  • enabled, auto_select
  • preferred_relay, preferred_region
  • require_fronting
  • custom_relays

  **HTTP2Config:**
  • enable_fallback, prefer_http2, http2_only
  • path, timeout

  **CensorshipDetectionConfig:**
  • enabled, auto_switch
  • failure_threshold, failure_window, check_interval

  **AntiCensorshipConfig:**
  • Master enabled switch
  • Preset modes: default, aggressive, stealth, custom
  • apply_preset() method
  • to_dict(), from_dict() serialization

- ✅ **Tray Menu Integration** — UI для обхода блокировок
  - `tray.py` — расширенное меню (120+ строк новых)

  **Menu Items:**
  • 🛡 Обход блокировок: Вкл/Выкл
  • Режим обфускации (submenu):
    - Обычный (default preset)
    - Агрессивный (aggressive preset)
    - Стеелс (stealth preset)
  • Domain Fronting: Вкл/Выкл
  • HTTP/2 Fallback: Вкл/Выкл
  • Мониторинг блокировок (status dialog)

  **Callbacks:**
  • _on_toggle_obfuscation()
  • _on_obfuscation_preset()
  • _on_toggle_domain_fronting()
  • _on_toggle_http2_fallback()
  • _on_show_censorship_status()

- ✅ **Constants Update** — конфигурация по умолчанию
  - `proxy/constants.py` — DEFAULT_CONFIG расширен

  **Anticensorship Defaults:**
  • enabled: False (user opt-in)
  • preset: "default"
  • Full obfuscation config
  • Full relay config
  • Full http2 config
  • Full censorship_detection config

### Производительность
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Безопасность
- ✅ **Аудит зависимостей** — `pip-audit` интеграция в CI
  - `.github/workflows/ci.yml` — enhanced security workflow
  - `scripts/security_audit.py` — локальный аудит безопасности
  - `SECURITY.md` — security policy документ

  **CI/CD Security:**
  • pip-audit + safety dual checking
  • JSON report generation (30-day retention)
  • Dev requirements auditing
  • Artifact upload for security reports

  **Local Security Audit:**
  • pip-audit integration с JSON отчётом
  • safety check для дополнительной проверки
  • Автоматическая установка инструментов
  • Поддержка multiple requirements файлов
  • Report generation (security-audit-report.json)

  **Security Policy:**
  • Vulnerability reporting guidelines (48h response)
  • Security best practices для пользователей и разработчиков
  • Automated scanning instructions
  • Dependency management policy (Critical: 24h, High: 7d)
  • Security checklist для релизов

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 41% до 60%
  - ✅ rate_limiter.py: 33 теста (Token Bucket, API Limiting, Connection Scoring, Ban/Unban, Subnet)
  - [ ] metrics_history.py: требует доработки тестов (сейчас 32% coverage)
  - [ ] web_dashboard.py: 16 errors — исправить импорты
  - [ ] connection_pool.py: 39% coverage — добавить тесты
  - [ ] tg_ws_proxy.py: 22% coverage — критично низкое покрытие

- [ ] **Integration Tests** — сквозные тесты для основных сценариев

### Мониторинг
- ✅ **Real-time Dashboard** — улучшение веб-панели с live графиками
  - `proxy/web_dashboard.py` — SSE stream + Metrics History API
  - Rate Limiter API: stats, metrics, ban, unban
  - Metrics History API: history, summary, trend, export
  - Prometheus metrics export

---

## 📊 Статус (23.03.2026 16:00)

```
Модулей: 47 в proxy/ ✅
Тестов: 35 файлов в tests/ ✅
Tests: 678 passed, 7 skipped ✅
Coverage: ~59% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 0 ошибок ✅
RuntimeWarnings: 0 ✅
Version: v2.55.0 (Cloudflare ✅, MTProxy ✅, System Proxy ✅)
```

**Актуальная версия:** v2.55.0 (dev) — ✅ synced
**Следующая версия:** v2.56.0 (Integration Tests + Coverage Improvement)
**Последнее обновление:** 23.03.2026 (16:00)

---

## 📝 Заметки по Android (v2.38.1)
- Исправлена несовместимость с AGP 9.1.0 в Capacitor плагинах.
- Требуется нативный TUN двигатель (L3->L5) для полноценного VPN.
