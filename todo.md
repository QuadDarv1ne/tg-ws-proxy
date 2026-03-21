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

## ✅ Выполнено (v2.31.0 — v2.32.0)

### Улучшения ядра (v2.32.0)
- ✅ Умный выбор DC на основе latency и истории ошибок (`DCStats`)
- ✅ LRU кэширование соединений с TTL и автоматической очисткой
- ✅ Автоматическая блокировка проблемных DC (blacklist с expiry)
- ✅ Оптимизация памяти: история 100→30 записей
- ✅ Динамическая оптимизация pool size на основе hit/miss ratio

### Новые модули
- ✅ `proxy/diagnostics_advanced.py` — комплексная диагностика подключений
  - DNS resolution тесты
  - TCP connectivity проверки
  - WebSocket endpoint тесты
  - Автоматические рекомендации
- ✅ `proxy/autotune.py` — автоматическая оптимизация производительности
  - Adaptive pool sizing (2-16 соединений)
  - Dynamic timeout adjustment (3-30 секунд)
  - Smart retry logic (2-5 попыток)
  - 3 режима: CONSERVATIVE, BALANCED, AGGRESSIVE

### Улучшения веб-панели
- ✅ `/api/config/export` — экспорт конфигурации в JSON
- ✅ `/api/config/import` — импорт конфигурации из JSON файла
- ✅ `/api/settings/advanced` — расширенные настройки оптимизатора
- ✅ `/api/diagnostics/run` — запуск диагностики
- ✅ `/api/diagnostics/results` — получение результатов диагностики
- ✅ `/api/optimization/config` — настройки оптимизации (GET/POST)
- ✅ `/api/optimization/metrics` — метрики производительности
- ✅ `/api/optimization/dns/cache` — очистка DNS кэша
- ✅ `/api/autotune/status` — статус авто-тюнера
- ✅ `/api/autotune/config` — настройка авто-тюнера

### Улучшения оптимизатора
- ✅ `DCStats` — статистика по каждому DC (success rate, latency, errors)
- ✅ `record_dc_success()` / `record_dc_failure()` — трекинг подключений
- ✅ `get_best_dc()` — автоматический выбор лучшего DC
- ✅ LRU cache: `cache_get()`, `cache_put()`, `cache_remove()`
- ✅ Настройка через API: pool size, max connections, blacklist duration
- ✅ Thread-safe DNS кэширование с asyncio.Lock
- ✅ Конфигурируемые параметры (_OPTIMIZATION_CONFIG)
- ✅ Метрики оптимизации (DNS hits/misses, connection time)

### Rate Limiter
- ✅ Allow-list поддержка для доверенных IP
- ✅ Гибкая конфигурация через `RateLimitConfig`
- ✅ Exponential backoff для нарушений

### Тесты
- ✅ test_optimizer.py: 17 тестов (100% покрытие)
- ✅ Итого: **472 passed, 7 skipped, 0 errors**

---

## 🔴 Высокий приоритет (v2.36.0)

### Тесты и покрытие
- [ ] Покрытие tg_ws_proxy.py: 13% → 60%
  - [ ] Тесты для `_handle_client()` (интеграционные)
  - [ ] Тесты для WebSocket pool
  - [ ] Тесты для TCP fallback логики
- [ ] Load tests (100+ одновременных подключений)
- [ ] Coverage > 80% (текущее ~35%)
- [ ] Fix failed tests (9 errors → 0)

### Покрытие тестами
- [ ] rate_limiter.py: 14 тестов → 80% coverage
- [ ] crypto.py: 25% → 80%
- [ ] alerts.py: 40% → 80%
- [ ] logger.py: 9 тестов (fix Windows PermissionError) → 80%
- [ ] diagnostics_advanced.py: новый модуль → 80%

### Производительность
- [ ] HTTP/2 для WebSocket
- [ ] Профилирование memory usage
- [ ] Оптимизация WebSocket pool

---

## 🟢 Низкий приоритет (v2.35.0)

### Документация (без запроса не менять)
- [ ] Скриншоты интерфейса в README
- [ ] Video-гайд по настройке

### Новые функции
- [ ] Расширенная i18n (de, es, fr)

### Безопасность
- [ ] Улучшенная SOCKS5 аутентификация
- [ ] TLS для локального прокси

### Android
- [ ] Улучшения стабильности сервиса
- [ ] Оптимизация батареи
- [ ] Quick Settings Tile

### Производительность
- [ ] optimizer.py — авто-оптимизация (pool size, memory, DC selection)
- [ ] connection_cache.py — LRU кэш соединений

---

## 📊 Статус

```
Tests: 472 passed, 7 skipped, 0 errors
Coverage: ~35% (цель >80%)
Ruff: 0 ошибок
Mypy: missing stubs (внешние зависимости)
```

**Проблемные зоны:**
- `tg_ws_proxy.py` — 12%
- `rate_limiter.py` — 14 тестов, покрытие ~40%
- `crypto.py` — 25%
- `alerts.py` — 40%
- `logger.py` — 9 тестов (Windows PermissionError)
- `diagnostics_advanced.py` — новый модуль, требует тестов
- `autotune.py` — новый модуль, требует тестов

**Отличное покрытие:**
- `optimizer.py` — 100% (17 тестов) ✅
- `plugins.py` — 100% (14 тестов) ✅
- `dc_monitor.py` — 100% (30 тестов) ✅
- `notifications.py` — 85% (29 тестов, 4 skipped) ✅
- `connection_cache.py` — 100% (27 тестов) ✅
- `client_stats.py` — 100% (39 тестов) ✅
- `config_backup.py` — 100% (24 тестов) ✅

---

## 🛠 Workflow

```bash
# Dev branch
git checkout dev
git pull

# Сделать изменения
# ...

# Проверка
ruff check .
mypy proxy/ tray.py
pytest tests/ -v

# Commit
git add .
git commit -m "feat: описание"
git push origin dev

# После тестов — в main
git checkout main
git merge dev
git push origin main
```

**Python:** `C:\Users\maksi\AppData\Local\Python\bin\python.exe` (3.14)
**Java:** `C:\Program Files\Java\jdk-21.0.10` (21 LTS)
**Android SDK:** `%LOCALAPPDATA%\Android\Sdk`

---

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
