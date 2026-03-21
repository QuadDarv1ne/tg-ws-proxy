# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.37.0)

### Performance & Stability
- ✅ Zero-copy буферизация WebSocket
- ✅ Batch отправка WebSocket фреймов
- ✅ Исправлена обработка ошибок WebSocket (_read_frame, recv)
- ✅ Timeout на чтение фреймов (30s)
- ✅ Обработка IncompleteReadError и TimeoutError
- ✅ Улучшен health check — подсчёт failed connections

### Ядро и Сеть (Stability Phase)
- ✅ `test_tg_ws_proxy_logic.py` — тесты парсинга пакетов ✅
- ✅ SRP Рефакторинг `_handle_client` ✅
- ✅ Health Checks: WS PING/PONG keep-alive ✅
- ✅ Crash Watchdog: Авто-рестарт asyncio loop ✅
- ✅ DoH Integration: DNS over HTTPS ✅
- ✅ Pool Tests: Покрытие логики `_WsPool` тестами ✅

---

## 🔴 Высокий приоритет (v2.36.0: Performance & Android)

### [ПЛАН РЕАЛИЗАЦИИ: 15 ШАГОВ]
1.  [x] **Dev Env Sync**: Тесты и окружение готовы.
2.  [x] **SRP Refactoring**: Разбит `_handle_client`.
3.  [x] **Type Safety**: Типизация `ProxyServer` и `_WsPool`.
4.  [x] **Unit Tests**: Покрыты SOCKS5 и логика парсинга.
5.  [x] **Health Checks**: Реализован WS PING/PONG.
6.  [x] **Crash Watchdog**: Внедрен авто-рестарт.
7.  [x] **DoH Integration**: DNS over HTTPS.
8.  [x] **Pool Tests**: Тесты переполнения и очистки пула.
9.  [ ] **HTTP/2 Multiplexing**: (Перенесено в v2.37).
10. [x] **VpnService Routing**: Нативный TUN-интерфейс на Android.
11. [x] **Dynamic Tile**: Живая статистика скорости в шторке.
12. [x] **Auto-TLS**: Локальное шифрование сертификатами.
13. [ ] **Memory Profiling**: Поиск утечек в пуле.
14. [x] **CI Validation**: Ruff/Mypy/Pytest (486 тестов ✅).
15. [ ] **Release**: Merge dev -> main.

---

## 📊 Статус

```
Tests: 493 passed, 28 skipped, 0 errors ✅
Coverage: ~40% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: missing stubs (внешние зависимости)
```

**Восстановлено после повреждения:**
- `proxy/web_dashboard.py` — 2987 строк (веб-панель) ✅
- `proxy/crypto.py` — 716 строк (шифрование) ✅
- `proxy/tg_ws_proxy.py` — 2431 строк (ядро прокси) ✅

**Новые тесты:**
- `tests/test_socks5.py` — 5 тестов (SOCKS5 negotiation) ✅
- `tests/test_ws_pool.py` — 4 теста (WebSocket pool + health check) ✅
- `tests/test_tg_ws_proxy_logic.py` — 5 тестов (core logic: DC parsing, patching) ✅

**Отличное покрытие:**
- `logger.py`, `optimizer.py`, `dc_monitor.py` — 100% ✅
- `test_tg_ws_proxy_logic.py`, `test_socks5.py`, `test_ws_pool.py` — 100% ✅

**Реализовано в v2.36.0:**
- Health Checks: WS PING/PONG каждые 45с, авто-очистка мёртвых соединений ✅
- Crash Watchdog: мониторинг сбоев (3 сбоя за 5 мин), логирование ✅
- DoH: DNS over HTTPS (Cloudflare/Google) ✅
- Pool Tests: тесты переполнения, очистки, expired connections ✅

---

## 📋 План на v2.37.0: Performance & Mobile

### Производительность
- [x] **Zero-copy буферизация** — `memoryview` вместо копирования байтов ✅
- [x] **Batch WebSocket отправка** — группировка мелких пакетов (<4KB) ✅
- [x] **Автоматический выбор DC** — по latency в реальном времени (5 мин) ✅
- [ ] **HTTP/2 Multiplexing** — снижение оверхеда TCP

### Надёжность
- [x] **Экспоненциальный backoff** — при ошибках подключения (2^(n-1), max 8x) ✅
- [ ] **Graceful shutdown** — корректное завершение всех соединений
- [ ] **Memory Profiling** — поиск утечек в пулах (tracemalloc/memray)

### Безопасность
- [ ] **Rate limiting** — защита от злоупотреблений (requests/minute)
- [ ] **IP whitelist/blacklist** — фильтрация подключений
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI

### Android App
- [ ] **Battery optimization** — фоновая работа без разряда (WorkManager)
- [ ] **Quick Settings Tile** — быстрый старт/стоп из шторки
- [ ] **Статистика в шторке** — скорость, трафик, активные подключения

### Мониторинг
- [ ] **Prometheus metrics** — endpoint `/metrics` для сбора метрик
- [ ] **JSON логирование** — для интеграции с ELK/Grafana
- [ ] **Alerting** — уведомления при высокой задержке DC (>200ms)

---

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
