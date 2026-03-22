# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.39.0)

### Refactoring
- ✅ websocket_client.py — выделен RawWebSocket и WsHandshakeError
- ✅ socks5_handler.py — выделен SOCKS5 handler
- ✅ test_websocket_client.py — тесты WebSocket клиента
- ✅ test_socks5_handler.py — тесты SOCKS5 handler

### Performance & Stability
- ✅ Zero-copy буферизация WebSocket
- ✅ Batch отправка WebSocket фреймов
- ✅ Исправлена обработка ошибок WebSocket (_read_frame, recv)
- ✅ Timeout на чтение фреймов (30s)
- ✅ Обработка IncompleteReadError и TimeoutError
- ✅ Улучшен health check — подсчёт failed connections
- ✅ Memory Profiling — поиск утечек в пулах (tracemalloc, weakref)
- ✅ Graceful shutdown — корректное завершение всех соединений
- ✅ Автоматический выбор DC — по latency в реальном времени
- ✅ VpnService Routing — нативный TUN-интерфейс на Android

### Ядро и Сеть
- ✅ DNS Caching — TTL для DoH запросов
- ✅ Crash Watchdog — авто-рестарт asyncio loop
- ✅ Исправлена синхронизация версий в `proxy/__init__.py` и `pyproject.toml`
- ✅ Исправлен тест `test_profiler.py` (RuntimeError loop)

### Android App
- ✅ Quick Settings Tile — запуск/остановка из шторки
- ✅ Живая статистика в шторке — скорость и подключения
- ✅ Background Config Update — через WorkManager
- ✅ Splash API & Material 3
- ✅ Интеграция Chaquopy и asyncio мост

---

## 🟡 В процессе (v2.40.0: optimization & resilience)

### Производительность
- [ ] **HTTP/2 Multiplexing** — снижение оверхеда TCP (R&D)
- [ ] **QUIC/UDP Support** — для звонков и медиа через прокси
- [ ] **Connection Pooling Optimization** — динамическая настройка размера пула на основе нагрузки

### Надёжность
- [ ] **Circuit breaker** — защита от cascade failures
- [ ] **Retry Strategy** — умный повтор запросов при смене сети
- [ ] **Health Check Enhancement** — более агрессивная проверка мёртвых соединений

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI
- [ ] **E2E Encryption** — локальное шифрование трафика между клиентом и прокси
- [ ] **Rate Limiting Improvements** — защита от DDoS и злоупотреблений

### Мониторинг
- [ ] **Prometheus metrics** — endpoint `/metrics` для сбора метрик
- [ ] **Alerting** — уведомления при высокой задержке DC (>200ms)
- [ ] **Diagnostic Report** — экспорт детального отчета о состоянии сети
- [ ] **Real-time Dashboard** — улучшение веб-панели с live графиками

---

## 📊 Статус

```
Tests: 476 passed, 7 skipped, 0 errors ✅
Coverage: ~40% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 15 ошибок (type annotations, Any usage)
Version: v2.39.0 (sync complete ✅)
```

**Актуальная версия:** v2.39.0 (main) — ✅ merged
**Следующая версия:** v2.40.0 (planning)

---

## ⚠️ Технические долги

### Mypy type errors (15 ошибок)
- [ ] `proxy/service_windows.py` — missing type annotations (4 ошибки)
- [ ] `proxy/i18n.py` — Any return type, unused ignore (2 ошибки)
- [ ] `proxy/logger.py` — Any return, incompatible types (2 ошибки)
- [ ] `proxy/plugins.py` — missing type annotation (1 ошибка)
- [ ] `proxy/optimizer.py` — invalid "any" type (3 ошибки)

### RuntimeWarnings (18 предупреждений в тестах)
- [ ] `coroutine 'open_connection' was never awaited` — gc.collect() в profiler.py
- [ ] `coroutine 'Stats.start_realtime_monitoring` — не awaited в тестах

---

## 🔍 Анализ кодовой базы (22.03.2026)

### Архитектура
- **Ядро:** `proxy/tg_ws_proxy.py` (2600+ строк) — основной SOCKS5 прокси с WebSocket мостом
- **Модули:** 25 Python модулей в `proxy/`, хорошо структурированы
- **Тесты:** 24 тестовых файла в `tests/`, покрытие требует улучшения
- **Платформы:** Windows (tray.py), Linux (linux.py), macOS (macos.py), Android (mobile-app/)

### Сильные стороны
- ✅ Полная реализация SOCKS5 с MTProto поддержкой
- ✅ WebSocket пулинг с health checks
- ✅ DNS кэширование с TTL
- ✅ Rate limiting и защита от злоупотреблений
- ✅ Автоматический выбор DC по latency
- ✅ Memory profiling и leak detection
- ✅ Кроссплатформенность (Windows/Linux/macOS/Android)
- ✅ Веб-панель управления с Flask
- ✅ Encryption support (AES-GCM, ChaCha20, MTProto IGE)

### Области для улучшения
- ⚠️ **Тестирование:** Нет установленного pytest, требуется `pip install -r requirements-dev.txt`
- ⚠️ **Покрытие тестами:** ~40%, цель >80%
- ⚠️ **Документация:** Устаревший GITHUB_RELEASE.md (v1.3.0 вместо v2.38.0)
- ⚠️ **Зависимости:** aiodns не работает на Windows (условная установка)
- ⚠️ **Логирование:** Много debug логов, можно оптимизировать
- ⚠️ **Монолитность:** `tg_ws_proxy.py` слишком большой (2600+ строк), нужен рефакторинг

### Технический долг
1. **Рефакторинг tg_ws_proxy.py** — разбить на модули:
   - `socks5_handler.py` — SOCKS5 протокол
   - `websocket_client.py` — WebSocket клиент
   - `connection_pool.py` — пулинг соединений
   - `mtproto_parser.py` — парсинг MTProto пакетов

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

## 🔴 Высокий приоритет (v2.39.0: Refactoring & Testing)

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
11. [x] **Dynamic Tile**: Живая статистика скорости в шторке.
12. [x] **Auto-TLS**: Локальное шифрование сертификатами.
13. [x] **Memory Profiling**: Поиск утечек в пуле ✅
14. [x] **CI Validation**: Ruff/Mypy/Pytest (476 тестов ✅).
15. [x] **Release**: Merge dev -> main ✅ (v2.39.0).

### ✅ Исправлено v2.39.0
- [x] **websocket_client.py** — выделен RawWebSocket и WsHandshakeError
- [x] **socks5_handler.py** — выделен SOCKS5 handler
- [x] **test_websocket_client.py** — тесты WebSocket клиента
- [x] **test_socks5_handler.py** — тесты SOCKS5 handler
- [x] **ruff check** — 0 ошибок ✅
- [x] **Синхронизация версий** — pyproject.toml: 2.39.0, proxy/__init__.py: 2.39.0


---

## 🔴 Высокий приоритет (v2.39.0)

### 1. Рефакторинг tg_ws_proxy.py
**Проблема:** Монолитный файл 2600+ строк затрудняет поддержку
**Решение:** Разбить на модули:
- `proxy/socks5_handler.py` — SOCKS5 протокол и handshake
- `proxy/websocket_client.py` — RawWebSocket класс
- `proxy/connection_pool.py` — _WsPool и _TcpPool
- `proxy/mtproto_parser.py` — парсинг MTProto init пакетов

### 2. Увеличение покрытия тестами
**Текущее:** ~40% | **Цель:** >80%
**Приоритет:**
- Интеграционные тесты для SOCKS5 handshake
- Тесты для WebSocket reconnection logic
- Тесты для DC selection algorithm
- Performance тесты для connection pooling

### 3. Обновление документации
- [ ] Обновить `docs/GITHUB_RELEASE.md` до v2.38.0
- [ ] Добавить архитектурную диаграмму в README
- [ ] Документировать REST API веб-панели
- [ ] Создать CONTRIBUTING.md для контрибьюторов

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

### Метрики качества
- **Строк кода:** ~15,000 (Python)
- **Модулей:** 25 в `proxy/`
- **Тестов:** 24 файла в `tests/`
- **Покрытие:** ~40% (требуется улучшение)
- **Ruff:** 0 ошибок ✅
- **Платформы:** Windows, Linux, macOS, Android

---

## 🎯 Roadmap

### v2.39.0 (Q2 2026) — Refactoring & Testing
- Рефакторинг tg_ws_proxy.py
- Увеличение покрытия тестами до >80%
- CI/CD pipeline с GitHub Actions
- Обновление документации

### v2.40.0 (Q3 2026) — Performance & Monitoring
- HTTP/2 Multiplexing
- Prometheus metrics
- Grafana dashboard
- Performance benchmarks

### v3.0.0 (Q4 2026) — Next Generation
- HTTP/3 / QUIC support
- Plugin system
- Multi-proxy chains
- ML-based anomaly detection

---

**Последнее обновление:** 22.03.2026
**Автор:** Dupley Maxim Igorevich
