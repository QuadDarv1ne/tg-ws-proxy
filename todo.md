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

## 🟡 В процессе (v2.54.0: stability + security)

### Производительность
- [ ] **HTTP/2 for Web Dashboard** — Quart + Hypercorn для API multiplexing
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 55% до 60%
- [ ] **Integration Tests** — сквозные тесты для основных сценариев

### Мониторинг
- ✅ **Real-time Dashboard** — улучшение веб-панели с live графиками
  - `proxy/web_dashboard.py` — SSE stream + Metrics History API
  - Rate Limiter API: stats, metrics, ban, unban
  - Metrics History API: history, summary, trend, export
  - Prometheus metrics export

---

## 📊 Статус (23.03.2026 04:30)

```
Модулей: 38 в proxy/ ✅
Тестов: 34 файла в tests/ ✅
Tests: 678 passed, 7 skipped ✅
Coverage: ~59% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 0 ошибок ✅
RuntimeWarnings: 0 ✅
Version: v2.53.1 (Dashboard Metrics ✅, Prometheus Export ✅)
```

**Актуальная версия:** v2.53.1 (dev) — ✅ synced
**Следующая версия:** v2.54.0 (HTTP/2 + Stability)
**Последнее обновление:** 23.03.2026 (04:30)

---

## 📝 Заметки по Android (v2.38.1)
- Исправлена несовместимость с AGP 9.1.0 в Capacitor плагинах.
- Требуется нативный TUN двигатель (L3->L5) для полноценного VPN.
