# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.38.0)

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

## 🟡 В процессе (v2.39.0: optimization & resilience)

### Производительность
- [ ] **HTTP/2 Multiplexing** — снижение оверхеда TCP (R&D)
- [ ] **QUIC/UDP Support** — для звонков и медиа через прокси

### Надёжность
- [ ] **Circuit breaker** — защита от cascade failures
- [ ] **Retry Strategy** — умный повтор запросов при смене сети

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI
- [ ] **E2E Encryption** — локальное шифрование трафика между клиентом и прокси

### Мониторинг
- [ ] **Prometheus metrics** — endpoint `/metrics` для сбора метрик
- [ ] **Alerting** — уведомления при высокой задержке DC (>200ms)
- [ ] **Diagnostic Report** — экспорт детального отчета о состоянии сети

---

## 📊 Статус

```
Tests: 476 passed, 7 skipped, 0 errors ✅
Coverage: ~40% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: missing stubs (внешние зависимости)
Version: v2.38.0 (sync complete ✅)
```

**Актуальная версия:** v2.38.0 (main) — ✅ merged
**Следующая версия:** v2.39.0 (planning)

---

## 🔴 Высокий приоритет (v2.38.0: Performance & Android)

### [ПЛАН РЕАЛИЗАЦИИ: 15 ШАГОВ]
1.  [x] **Dev Env Sync**: Тесты и окружение готовы.
2.  [x] **SRP Refactoring**: Разбит `_handle_client`.
3.  [x] **Type Safety**: Типизация `ProxyServer` и `_WsPool`.
4.  [x] **Unit Tests**: Покрыты SOCKS5 и логика парсинга.
5.  [x] **Health Checks**: Реализован WS PING/PONG.
6.  [x] **Crash Watchdog**: Внедрен авто-рестарт.
7.  [x] **DoH Integration**: DNS over HTTPS.
8.  [x] **Pool Tests**: Тесты переполнения и очистки пула.
9.  [ ] **HTTP/2 Multiplexing**: (Перенесено в v2.39).
10. [x] **VpnService Routing**: Нативный TUN-интерфейс на Android.
11. [x] **Dynamic Tile**: Живая статистика скорости в шторке.
12. [x] **Auto-TLS**: Локальное шифрование сертификатами.
13. [x] **Memory Profiling**: Поиск утечек в пуле ✅
14. [x] **CI Validation**: Ruff/Mypy/Pytest (476 тестов ✅).
15. [x] **Release**: Merge dev -> main ✅ (v2.38.0).

### ✅ Исправлено v2.38.0
- [x] **test_profiler.py::test_start_stop** — добавлен @pytest.mark.asyncio
- [x] **profiler.py stop()** — удалён get_event_loop().run_until_complete()
- [x] **Синхронизация версий** — pyproject.toml: 2.38.0, proxy/__init__.py: 2.38.0
