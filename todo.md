# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.43.0)

### Refactoring Complete ✅
- ✅ **mtproto_parser.py** — выделен парсинг MTProto пакетов
  - `is_telegram_ip()` — проверка IP Telegram
  - `is_http_transport()` — детекция HTTP транспорта
  - `extract_dc_from_init()` — извлечение DC ID из init пакета
  - `patch_init_dc()` — патчинг DC ID в init пакете
  - `MsgSplitter` — разбиение MTProto сообщений для WebSocket
  - `parse_mtproto_length()` — парсинг длины сообщения
- ✅ **test_mtproto_parser.py** — 30+ тестов для MTProto парсера
- ✅ **tg_ws_proxy.py** — уменьшен с 2600+ до ~1400 строк
- ✅ **Модульность** — все 4 модуля выделены (socks5, websocket, pool, mtproto)

### Performance Optimization
- ✅ **Performance Profiler** — cProfile интеграция с optimization suggestions
  - `proxy/performance_profiler.py` — профилирование CPU и памяти
  - `tests/test_performance_profiler.py` — 18 тестов
  - Автоматические рекомендации по оптимизации
- ✅ **DNS Resolver Aggressive Caching** — hit rate >90% target
  - Extended TTL для стабильных доменов (1 час для Telegram)
  - `_get_aggressive_ttl()` — умный выбор TTL на основе домена
  - Custom TTL поддержка в `_add_to_cache()`

### Monitoring & Observability
- ✅ **Prometheus metrics endpoint** — `/metrics` для сбора метрик
  - Connection metrics (total, active, bytes)
  - Performance metrics (CPU, memory)
  - DC latency and errors
  - Circuit breaker states
  - DNS resolver metrics
  - Plugin system metrics
- ✅ **Circuit breaker** — защита от cascade failures (websocket, tcp, dns)
- ✅ **CircuitBreakerRegistry** — управление circuit breakers
- ✅ **Интеграция в ProxyServer** — 3 circuit breakers

### Refactoring
- ✅ **websocket_client.py** — выделен RawWebSocket и WsHandshakeError
- ✅ **socks5_handler.py** — выделен SOCKS5 handler
- ✅ **test_websocket_client.py** — тесты WebSocket клиента
- ✅ **test_socks5_handler.py** — тесты SOCKS5 handler

### Performance & Stability
- ✅ **Zero-copy буферизация WebSocket**
- ✅ **Batch отправка WebSocket фреймов**
- ✅ **Исправлена обработка ошибок WebSocket** (_read_frame, recv)
- ✅ **Timeout на чтение фреймов** (30s)
- ✅ **Обработка IncompleteReadError и TimeoutError**
- ✅ **Улучшен health check** — подсчёт failed connections
- ✅ **Memory Profiling** — поиск утечек в пулах (tracemalloc, weakref)
- ✅ **Graceful shutdown** — корректное завершение всех соединений
- ✅ **Автоматический выбор DC** — по latency в реальном времени
- ✅ **VpnService Routing** — нативный TUN-интерфейс на Android

### Ядро и Сеть
- ✅ **DNS Caching** — TTL для DoH запросов
- ✅ **Crash Watchdog** — авто-рестарт asyncio loop
- ✅ **Исправлена синхронизация версий** в `proxy/__init__.py` и `pyproject.toml`
- ✅ **Исправлен тест** `test_profiler.py` (RuntimeError loop)

### Android App
- ✅ **Quick Settings Tile** — запуск/остановка из шторки
- ✅ **Живая статистика в шторке** — скорость и подключения
- ✅ **Background Config Update** — через WorkManager
- ✅ **Splash API & Material 3**
- ✅ **Интеграция Chaquopy и asyncio мост**

### R&D
- ✅ **HTTP/2 Multiplexing Research** — анализ применимости (docs/HTTP2_RESEARCH.md)
  - Вывод: HTTP/2 не применим к основному прокси потоку
  - Рекомендация: использовать для Web Dashboard (v2.42.0)
  - Перспектива: QUIC/HTTP/3 для mobile (v3.0.0)

### Производительность
- ✅ **WebSocket Compression** — permessage-deflate для снижения трафика на 30-50%
  - Реализовано в `proxy/websocket_client.py`
  - RFC 7692 permessage-deflate compression
  - Настройка через `enable_compression` в optimization config
  - Тесты: `test_websocket_client.py`

---

## 🟢 Выполнено (v2.44.0: alerts + stability)

### Производительность
- ✅ **Connection Pooling Optimization** — динамическая настройка размера пула
  - Адаптация на основе miss rate (>30% → increase, <5% → decrease)
  - Адаптация на основе latency (>100ms → increase, <30ms → decrease)
  - Интервал оптимизации: 30 секунд
  - Логирование изменений размера пула

### Надёжность
- ✅ **Alerting** — уведомления при высокой задержке DC
  - AlertType.DC_HIGH_LATENCY добавлен
  - Порог: 150ms (warning), 200ms (critical)
  - Cooldown: 2 минуты между алертами для одного DC
  - Интеграция в monitor_dc_latency()
  - Email/webhook уведомления (через AlertManager)
  - Тесты: test_alerts.py (8 passed)
- ✅ **metric_to_alert_type mapping** — корректное сопоставление метрик с AlertType

---

## 🟡 В процессе (v2.45.0: coverage + stability)

### Производительность
- [ ] **HTTP/2 for Web Dashboard** — Quart + Hypercorn для API multiplexing
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Надёжность
- [ ] **Retry Strategy** — умный повтор запросов при смене сети
- [ ] **Health Check Enhancement** — более агрессивная проверка мёртвых соединений
- [ ] **Connection Timeout Tuning** — адаптивные таймауты на основе latency

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI
- [ ] **E2E Encryption** — локальное шифрование трафика между клиентом и прокси
- [ ] **Rate Limiting Improvements** — защита от DDoS и злоупотреблений

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 48% до 60%
- [ ] **Integration Tests** —端到端 тесты для основных сценариев
- [ ] **Performance Tests** — benchmark тесты производительности

### Мониторинг
- ✅ **Prometheus metrics endpoint** — `/metrics` endpoint реализован
  - Connection metrics (total, active, bytes)
  - Performance metrics (CPU, memory)
  - DC latency & errors
  - Circuit breaker states
  - DNS resolver metrics
  - Plugin system metrics
- ✅ **Grafana Dashboard** — документация и примеры дашбордов (docs/MONITORING.md)
  - Docker Compose конфигурация
  - Prometheus scrape config
  - Grafana dashboard JSON
  - Alert rules
- [ ] **Diagnostic Report** — экспорт детального отчета о состоянии сети
- [ ] **Real-time Dashboard** — улучшение веб-панели с live графиками
- [ ] **Metrics History** — хранение истории метрик за 30 дней

---

## 📊 Статус (22.03.2026 21:00)

```
Модулей: 33 в proxy/ ✅
Тестов: 31 файл в tests/ ✅
Tests: 547 passed, 7 skipped, 9 failed (performance_profiler) ⚠️
Coverage: ~50% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 17 ошибок (требуется исправление)
RuntimeWarnings: 0 ✅
Version: v2.44.0 (Alerting ✅, metric_to_alert_type ✅, Refactoring Complete ✅)
```

**Актуальная версия:** v2.44.0 (main/dev) — ✅ synced
**Следующая версия:** v2.45.0 (coverage improvement + mypy fix + profiler fix)
**Последнее обновление:** 22.03.2026 (21:00)

---

## ⚠️ Технические долги

### Mypy type errors — ИСПРАВЛЕНО ✅
- [x] **72 ошибки → 0 ошибок** — все type annotations добавлены
- [x] **proxy/service_windows.py** — добавлены type annotations
- [x] **proxy/optimizer.py** — any → Any (импорт из typing)
- [x] **proxy/notifications.py** — исправлен тип tasks для asyncio.gather
- [x] **proxy/logger.py** — добавлен type ignore для sum()
- [x] **proxy/tg_ws_proxy.py** — добавлены annotations, исправлен IncompleteReadError
- [x] **proxy/web_dashboard.py** — mypy disable-error-code для Flask специфичных ошибок

### RuntimeWarnings — ИСПРАВЛЕНО ✅
- [x] **18 предупреждений → 0** — все coroutines теперь awaited
- [x] `profiler.start()` и `profiler.stop()` — теперь async методы
- [x] `stats.start_realtime_monitoring()` и `stop_realtime_monitoring()` — теперь async
- [x] Перенесён вызов `start_realtime_monitoring` из `__init__` в `_run()`
- [x] Добавлен await для всех task.cancel() с обработкой CancelledError

---

## 🔍 Анализ кодовой базы (22.03.2026)

### Архитектура (обновлено 22.03.2026)
- **Ядро:** `proxy/tg_ws_proxy.py` (~1400 строк) — основной SOCKS5 прокси с WebSocket мостом
- **Модули:** 33 Python модуля в `proxy/`, отлично структурированы ✅
- **Тесты:** 31 тестовый файл в `tests/`, покрытие ~50%
- **Платформы:** Windows (tray.py), Linux (linux.py), macOS (macos.py), Android (mobile-app/)

### Новые модули (v2.43.0)
- ✅ `socks5_handler.py` — SOCKS5 протокол (350+ строк)
- ✅ `websocket_client.py` — WebSocket клиент (450+ строк)
- ✅ `connection_pool.py` — пулинг соединений (360+ строк)
- ✅ `mtproto_parser.py` — парсинг MTProto (280+ строк)
- ✅ `dns_resolver.py` — DNS resolver с метриками (350+ строк)
- ✅ `alerts.py` — система алертов (обновлён)
- ✅ `performance_profiler.py` — профилирование производительности
- ✅ `circuit_breaker.py` — защита от cascade failures

### Сильные стороны (v2.43.0)
- ✅ Полная реализация SOCKS5 с MTProto поддержкой
- ✅ WebSocket пулинг с health checks и динамической оптимизацией
- ✅ DNS кэширование с TTL и метриками (hit rate >90%)
- ✅ Rate limiting и защита от злоупотреблений
- ✅ Автоматический выбор DC по latency в реальном времени
- ✅ Memory profiling и leak detection (tracemalloc + weakref)
- ✅ Circuit breaker для защиты от cascade failures
- ✅ Alerting система с DC latency мониторингом
- ✅ Кроссплатформенность (Windows/Linux/macOS/Android)
- ✅ Веб-панель управления с Flask + Prometheus metrics
- ✅ Encryption support (AES-GCM, ChaCha20, MTProto IGE)
- ✅ Модульная архитектура (33 модуля, хорошо разделены)

### Области для улучшения (приоритеты v2.44.0)
- 🎯 **Покрытие тестами:** ~50% → цель >80% (HIGH PRIORITY)
- 🎯 **Интеграционные тесты:** Нужны end-to-end тесты (HIGH PRIORITY)
- ⚠️ **Документация:** Обновить GITHUB_RELEASE.md до v2.43.0
- ⚠️ **CI/CD:** GitHub Actions для автотестов + pip-audit
- ⚠️ **Логирование:** Оптимизировать debug логи (слишком много)
- ✅ **Монолитность:** ИСПРАВЛЕНО — tg_ws_proxy.py уменьшен на 46%

### Технический долг
1. **Рефакторинг tg_ws_proxy.py** — разбить на модули:
   - ✅ `socks5_handler.py` — SOCKS5 протокол
   - ✅ `websocket_client.py` — WebSocket клиент
   - ✅ `connection_pool.py` — пулинг соединений
   - ✅ `mtproto_parser.py` — парсинг MTProto пакетов
   - **Результат:** tg_ws_proxy.py уменьшен с 2600+ до ~1400 строк ✅

2. **Улучшение тестов:**
   - Добавить интеграционные тесты
   - Увеличить покрытие до >80%
   - Добавить performance тесты

3. **Документация:**
   - Обновить GITHUB_RELEASE.md до v2.38.0
   - Добавить архитектурную диаграмму
   - Документировать API веб-панели

4. **CI/CD:**
   - Добавить GitHub Actions для автотестов
   - Автоматическая сборка релизов
   - pip-audit для проверки зависимостей

---

## 🔴 Высокий приоритет (v2.40.0: Reliability & Resilience)

### [ПЛАН РЕАЛИЗАЦИИ: 15 ШАГОВ]
1.  [x] **Dev Env Sync**: Тесты и окружение готовы.
2.  [x] **SRP Refactoring**: Разбит `_handle_client`.
3.  [x] **Type Safety**: Типизация `ProxyServer` и `_WsPool`.
4.  [x] **Unit Tests**: Покрыты SOCKS5 и логика парсинга.
5.  [x] **Health Checks**: Реализован WS PING/PONG.
6.  [x] **Crash Watchdog**: Внедрен авто-рестарт.
7.  [x] **DoH Integration**: DNS over HTTPS.
8.  [x] **Pool Tests**: Тесты переполнения и очистки пула.
9.  [x] **WebSocket Client**: Выделен websocket_client.py ✅
10. [x] **SOCKS5 Handler**: Выделен socks5_handler.py ✅
11. [x] **Circuit Breaker**: Защита от cascade failures ✅
12. [x] **Dynamic Tile**: Живая статистика скорости в шторке.
13. [x] **Auto-TLS**: Локальное шифрование сертификатами.
14. [x] **Memory Profiling**: Поиск утечек в пуле ✅
15. [x] **Release**: Merge dev -> main ✅ (v2.40.0).

### ✅ Исправлено v2.40.0
- [x] **circuit_breaker.py** — CircuitBreaker, CircuitBreakerRegistry ✅
- [x] **test_circuit_breaker.py** — 18 тестов circuit breaker ✅
- [x] **Интеграция** — 3 circuit breakers в ProxyServer (websocket, tcp, dns) ✅
- [x] **ruff check** — 0 ошибок ✅


---

## 🔴 Высокий приоритет (v2.40.0)

### 1. Рефакторинг tg_ws_proxy.py
**Проблема:** Монолитный файл 2600+ строк затрудняет поддержку
**Решение:** Разбить на модули:
- `proxy/socks5_handler.py` — SOCKS5 протокол и handshake ✅
- `proxy/websocket_client.py` — RawWebSocket класс ✅
- `proxy/connection_pool.py` — _WsPool и _TcpPool ✅ (v2.42.0)
- `proxy/mtproto_parser.py` — парсинг MTProto init пакетов [ ]

### 2. Увеличение покрытия тестами
**Текущее:** ~40% | **Цель:** >80%
**Приоритет:**
- Интеграционные тесты для SOCKS5 handshake ✅
- Тесты для WebSocket reconnection logic ✅
- Тесты для DC selection algorithm [ ]
- Performance тесты для connection pooling [ ]

### 3. Обновление документации
- [x] Обновить `docs/GITHUB_RELEASE.md` до v2.39.0
- [x] Добавить CONTRIBUTING.md для контрибьюторов
- [ ] Добавить архитектурную диаграмму в README
- [ ] Документировать REST API веб-панели

### 4. CI/CD Pipeline
- [ ] GitHub Actions для автотестов (pytest + ruff + mypy)
- [ ] Автоматическая сборка релизов для Windows/Linux/macOS
- [ ] pip-audit для проверки уязвимостей в зависимостях
- [ ] Автоматический deploy документации

### 5. Performance Optimization
- [ ] Профилирование bottlenecks с помощью cProfile
- [ ] Оптимизация DNS resolver (кэш hit rate >90%)
- [ ] Уменьшение memory footprint (цель <100MB при 100 соединениях)
- [ ] Benchmark тесты для сравнения с предыдущими версиями

---

## 🟢 Средний приоритет (v2.40.0+)

### Новые фичи
- [ ] **HTTP/3 Support** — QUIC для низкой задержки
- [ ] **Multi-proxy Mode** — цепочка прокси для анонимности
- [ ] **Traffic Shaping** — QoS для приоритизации трафика
- [ ] **Plugin System** — расширяемость через плагины

### Улучшения UX
- [ ] **Desktop Notifications** — уведомления о событиях
- [ ] **Auto-update** — автоматическое обновление приложения
- [ ] **Config Profiles** — переключение между профилями
- [ ] **Dark/Light Theme** — темы для GUI

### Мониторинг и Аналитика
- [ ] **Grafana Dashboard** — визуализация метрик
- [ ] **Export to CSV/JSON** — экспорт статистики
- [ ] **Historical Data** — хранение истории за 30 дней
- [ ] **Anomaly Detection** — ML для обнаружения аномалий

---

## 📝 Заметки

### Зависимости
- `cryptography>=46.0.5` — шифрование
- `psutil>=7.2.2` — мониторинг системы
- `flask>=3.1.3` — веб-панель
- `aiodns>=3.2.0` — async DNS (не работает на Windows)

### Известные проблемы
1. **Windows Defender** — ложные срабатывания на PyInstaller exe
2. **aiodns** — не устанавливается на Windows (используется fallback)
3. **pytest** — требуется установка `pip install -r requirements-dev.txt`

### Метрики качества (v2.43.0)
- **Строк кода:** ~18,000 (Python) — увеличение за счёт новых модулей
- **Модулей:** 33 в `proxy/` (+8 новых модулей)
- **Тестов:** 31 файл в `tests/` (+7 новых тестовых файлов)
- **Покрытие:** ~50% (+10% за счёт новых тестов)
- **Ruff:** 0 ошибок ✅ (исправлено 29 ошибок форматирования)
- **Mypy:** 0 ошибок ✅
- **RuntimeWarnings:** 0 ✅
- **Платформы:** Windows, Linux, macOS, Android
- **Рефакторинг:** tg_ws_proxy.py уменьшен с 2600 до 1940 строк (-25%) ✅
- **Код качество:** Все проверки линтеров пройдены ✅

---

## 🎯 Roadmap (обновлено 22.03.2026)

### v2.44.0 (выполнено) — Alerts + Stability ✅
- ✅ Merge dev → main
- ✅ Alerting система для DC latency (test_alerts.py: 8 тестов)
- ✅ metric_to_alert_type mapping
- ✅ Ruff: 0 ошибок

### v2.45.0 (текущий спринт) — Coverage + Mypy Fix
- [ ] Исправить 9 failing тестов (performance_profiler)
- [ ] Исправить 17 ошибок mypy
- [ ] Увеличение покрытия тестами до >60%
- [ ] Интеграционные тесты для SOCKS5 + WebSocket
- [ ] Обновление GITHUB_RELEASE.md до v2.44.0

### v2.46.0 (следующий спринт) — Performance & Monitoring
- [ ] HTTP/2 для Web Dashboard (Quart + Hypercorn)
- [ ] Retry Strategy для сетевых ошибок
- [ ] Adaptive timeouts на основе latency
- [ ] Performance benchmarks

### v3.0.0 (Q4 2026) — Next Generation
- [ ] HTTP/3 / QUIC support
- [ ] Plugin system
- [ ] Multi-proxy chains
- [ ] ML-based anomaly detection

---

**Последнее обновление:** 22.03.2026 21:00
**Автор:** Dupley Maxim Igorevich
