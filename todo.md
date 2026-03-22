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

## ✅ Выполнено (v2.49.0: functional improvements)

### Надёжность
- ✅ **Health Check Enhancement** — агрессивная проверка мёртвых соединений
  - Интервал health check: 30с (нормальный), 15с (агрессивный режим)
  - Timeout адаптируется: 5с → 3с в агрессивном режиме
  - Обнаружение stale соединений (>2 минут без активности)
  - Трекинг последней активности для каждого соединения (`_last_activity`)
  - Трекинг consecutive failures для каждого DC
  - Автоматическое включение aggressive mode при >5 failures
  - Очистка старых failed connections (5 минут)
  - Статистика в `get_stats()`: aggressive_mode, consecutive_failures, failed_connections_recent

### Производительность
- ✅ **Adaptive Timeout Tuning** — адаптивные таймауты на основе latency
  - `tg_ws_proxy.py`: `_update_adaptive_timeout()`, `get_adaptive_timeout()`, `get_adaptive_timeout_stats()`
  - Динамический расчёт: timeout = max(base, min(max, avg_latency * multiplier))
  - Rolling window последних 100 замеров latency
  - Smooth transition (изменения только при >1s разнице)
  - Интеграция в `asyncio.open_connection` (TCP fallback и passthrough)
  - Статистика в `get_optimization_config()`: adaptive_timeout stats

### Безопасность
- ✅ **E2E Encryption** — локальное шифрование трафика между клиентом и прокси
  - `proxy/e2e_encryption.py` — новый модуль (470+ строк)
  - X25519 ECDH key exchange для сессионных ключей
  - HKDF key derivation (SHA256, 256-bit keys)
  - AES-256-GCM authenticated encryption
  - Replay attack protection (nonce tracking)
  - Session management с automatic key rotation (10000 messages)
  - Session timeout (1 hour) и cleanup
  - Handshake protocol с server signature verification
  - API: `get_e2e()`, `init_e2e()`, `E2EEncryption` класс

### Мониторинг
- ✅ **Diagnostic Report** — расширенная диагностика с экспортом
  - `proxy/diagnostics_advanced.py` — новый модуль (550+ строк)
  - Full connectivity testing: DNS, TCP, WebSocket
  - Health assessment: 5 уровней (EXCELLENT, GOOD, DEGRADED, CRITICAL, DOWN)
  - Automated recommendations engine
  - Export to JSON/CSV форматы
  - Historical data tracking (last 100 reports)
  - Network interface discovery
  - DC-specific testing с latency measurement
  - API: `get_diagnostics()`, `DiagnosticsAdvanced` класс

### Интеграция
- ✅ **Code Quality** — type annotations в `autotune.py`
  - Добавлены аннотации для `_current_pool_size`, `_current_timeout_ms`, `_current_max_retries`
  - Аннотации для `_tuning_applied_count`, `_running`

---

## 🟡 В процессе (v2.50.0: dashboard + stability)

### Производительность
- [ ] **HTTP/2 for Web Dashboard** — Quart + Hypercorn для API multiplexing
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI
- [ ] **Rate Limiting Improvements** — защита от DDoS и злоупотреблений

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 55% до 60%
- [ ] **Integration Tests** — сквозные тесты для основных сценариев

### Мониторинг
- [ ] **Real-time Dashboard** — улучшение веб-панели с live графиками
- [ ] **Metrics History** — хранение истории метрик за 30 дней

---

## 📊 Статус (23.03.2026 02:00)

```
Модулей: 37 в proxy/ ✅ (добавлены e2e_encryption.py, diagnostics_advanced.py)
Тестов: 33 файла в tests/ ✅
Tests: 642 passed, 7 skipped ✅
Coverage: ~57% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 0 ошибок ✅
RuntimeWarnings: 0 ✅
Version: v2.49.0 (Health Check ✅, Adaptive Timeout ✅, E2E ✅, Diagnostics ✅)
```

**Актуальная версия:** v2.49.0 (dev) — ✅ synced
**Следующая версия:** v2.50.0 (Dashboard + Rate Limiting)
**Последнее обновление:** 23.03.2026 (02:00)

---

## 📝 Заметки по Android (v2.38.1)
- Исправлена несовместимость с AGP 9.1.0 в Capacitor плагинах.
- Требуется нативный TUN двигатель (L3->L5) для полноценного VPN.
