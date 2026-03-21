# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.10.0 — v2.35.0)

### Сборка и Тесты
- ✅ Android APK сборка (Java 21 LTS, AGP 9.1.0)
- ✅ Исправлен `Windows PermissionError` в `tests/test_logger.py`
- ✅ `logger.py` — 100% покрытие ✅

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
13. [ ] **Memory Profiling**: Поиск утечек в пуле (В РАБОТЕ).
14. [ ] **CI Validation**: Ruff/Mypy/Pytest (100% успех).
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

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
