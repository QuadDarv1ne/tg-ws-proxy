# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.10.0 — v2.22.0)

### Сборка и релиз
- ✅ Android APK сборка (Java 21 LTS)
- ✅ Desktop сборка (Windows, Linux, macOS)
- ✅ PWA иконки и manifest
- ✅ GitHub Actions workflow

### Ядро и производительность
- ✅ Async DNS resolver (aiodns)
- ✅ Оптимизация memory footprint (история 100→30)
- ✅ Автоматический экспорт статистики (JSON каждый час)
- ✅ Проверка обновлений GitHub
- ✅ Многоязычность (i18n) — русский/английский (80+ переводов)
- ✅ Whitelist IP — полная реализация с O(1) проверкой

### Код-качество
- ✅ Ruff: 127 → 0 ошибок
- ✅ Mypy: missing stubs (внешние зависимости)
- ✅ Новые модули: `proxy/i18n.py`, `proxy/updater.py`
- ✅ Python 3.14 совместимость (tray.py asyncio.run)
- ✅ diagnostics_advanced.py — расширенная диагностика

### Тесты
- ✅ Tests: 472 passed, 7 skipped, 0 errors (было 255 passed)
- ✅ Добавлены тесты для i18n, updater, whitelist
- ✅ Покрытие web_dashboard.py: 61% → 74%
- ✅ Исправлены тесты config_backup (Windows permissions)
- ✅ Создана fixtures для Windows (tmp_path_safe)
- ✅ Добавлены тесты для rate_limiter.py (14 тестов)
- ✅ Исправлены все ruff ошибки (I001, F401, W293, B007, F821)
- ✅ Ruff: 0 ошибок во всех файлах

### Документация
- ✅ Очистка документации от дублирования
- ✅ README.md сокращён (352 → ~150 строк)
- ✅ BUILD.md — краткая инструкция
- ✅ INSTALL_MOBILE.md — PWA и APK
- ✅ RELEASE_NOTES.md — ключевые версии

---

## ✅ Выполнено (v2.31.0 — v2.35.0)

### Улучшения ядра (v2.32.0)
- ✅ Умный выбор DC на основе latency и истории ошибок (`DCStats`)
- ✅ LRU кэширование соединений с TTL и автоматической очитокй
- ✅ Автоматическая блокировка проблемных DC (blacklist с expiry)
- ✅ Оптимизация памяти: история 100→30 записей
- ✅ Динамическая оптимизация pool size на основе hit/miss ratio

### Новые модули
- ✅ `proxy/diagnostics_advanced.py` — комплексная диагностика подключений
- ✅ `proxy/autotune.py` — автоматическая оптимизация производительности

### Исправления сборки и тестов (v2.35.0)
- ✅ Исправлена ошибка сборки Android (добавлен `pluginManagement` в `settings.gradle`)
- ✅ Исправлен `Windows PermissionError` в `tests/test_logger.py` (закрытие хендлеров)
- ✅ logger.py — 19 тестов passed, 0 errors (100% покрытие)

---

## 🔴 Высокий приоритет (v2.36.0)

### Тесты и покрытие
- [ ] Покрытие tg_ws_proxy.py: 13% → 60%
  - [ ] Тесты для `_handle_client()` (интеграционные)
  - [ ] Тесты для WebSocket pool
  - [ ] Тесты для TCP fallback логики
- [ ] Load tests (100+ одновременных подключений)
- [ ] Coverage > 80% (текущее ~35%)
- [ ] Добавить тесты для `diagnostics_advanced.py` (цель 80%)
- [ ] Добавить тесты для `autotune.py` (цель 80%)

### Производительность
- [ ] HTTP/2 для WebSocket (поддержка мультиплексирования)
- [ ] Профилирование memory usage (поиск утечек в pool)
- [ ] Оптимизация WebSocket pool (динамическое сжатие)

---

## 🟢 Низкий приоритет

### Android
- [ ] Улучшения стабильности VpnService (reconnect logic)
- [ ] Quick Settings Tile (быстрый доступ из шторки)
- [ ] Оптимизация энергопотребления (Battery Analytics интеграция)

### Безопасность
- [ ] TLS для локального прокси (self-signed certs)
- [ ] Улучшенная SOCKS5 аутентификация

---

## 📊 Статус

```
Tests: 472 passed, 7 skipped, 0 errors ✅
Coverage: ~38% (цель >80%)
Ruff: 0 ошибок
Mypy: missing stubs (внешние зависимости)
```

**Проблемные зоны:**
- `tg_ws_proxy.py` — 12% (Фокус v2.36.0)
- `rate_limiter.py` — ~40%
- `crypto.py` — 25%
- `alerts.py` — 40%
- `diagnostics_advanced.py` — требует тестов
- `autotune.py` — требует тестов

**Отличное покрытие:**
- `logger.py` — 100% (19 тестов) ✅
- `optimizer.py` — 100% (17 тестов) ✅
- `dc_monitor.py` — 100% (30 тестов) ✅
- `connection_cache.py` — 100% (27 тестов) ✅
- `client_stats.py` — 100% (39 тестов) ✅
- `config_backup.py` — 100% (24 тестов) ✅
- `plugins.py` — 100% (14 тестов) ✅
- `notifications.py` — 85% (29 тестов, 4 skipped) ✅

---

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
