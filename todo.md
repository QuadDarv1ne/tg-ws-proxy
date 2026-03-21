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
Tests: 486 passed, 7 skipped, 0 errors ✅
Coverage: ~40% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: missing stubs (внешние зависимости)
```

**Актуальная версия:** v2.37.0 (dev + main синхронизированы) ✅

---

## 📋 План на v2.38.0: Stability & Monitoring

### Производительность
- [x] **Zero-copy буферизация** — `memoryview` вместо копирования байтов ✅
- [x] **Batch WebSocket отправка** — группировка мелких пакетов (<4KB) ✅
- [x] **Автоматический выбор DC** — по latency в реальном времени (5 мин) ✅
- [ ] **HTTP/2 Multiplexing** — снижение оверхеда TCP

### Надёжность
- [x] **Экспоненциальный backoff** — при ошибках подключения (2^(n-1), max 8x) ✅
- [x] **Graceful shutdown** — корректное завершение всех соединений ✅
- [x] **Memory Profiling** — поиск утечек в пулах (tracemalloc, weakref) ✅

### Безопасность
- [x] **Rate limiting** — защита от злоупотреблений (10 req/s, 100 req/min) ✅
- [x] **IP whitelist/blacklist** — фильтрация подключений (allow-list по умолчанию) ✅
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
