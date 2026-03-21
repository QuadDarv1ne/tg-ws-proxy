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

### Тесты
- ✅ Tests: 463 passed, 7 skipped (было 255 passed)
- ✅ Добавлены тесты для i18n, updater, whitelist
- ✅ Покрытие web_dashboard.py: 61% → 74%
- ✅ Исправлены тесты config_backup (Windows permissions)
- ✅ Создана fixtures для Windows (tmp_path_safe)
- ✅ Добавлены тесты для rate_limiter.py (14 тестов)
- ✅ Исправлены все ruff ошибки (I001, F401, W293)
- ✅ Ruff: 0 ошибок во всех файлах

### Документация
- ✅ Очистка документации от дублирования
- ✅ README.md сокращён (352 → ~150 строк)
- ✅ BUILD.md — краткая инструкция
- ✅ INSTALL_MOBILE.md — PWA и APK
- ✅ RELEASE_NOTES.md — ключевые версии

---

## ✅ Выполнено (v2.22.0 — v2.31.0)

### Новые модули
- ✅ `proxy/optimizer.py` — авто-оптимизация производительности
- ✅ `proxy/logger.py` — расширенное логирование (JSON, rotation)
- ✅ `proxy/plugins.py` — система плагинов
- ✅ `proxy/dc_monitor.py` — мониторинг здоровья DC
- ✅ `proxy/notifications.py` — уведомления (Telegram, Discord, Email)
- ✅ `proxy/connection_cache.py` — LRU кэш соединений
- ✅ `proxy/client_stats.py` — per-client статистика
- ✅ `proxy/config_backup.py` — авто-бэкап конфигурации

### Улучшения веб-панели
- ✅ `/api/optimizer/stats` — статистика оптимизатора
- ✅ `/api/optimizer/config` — настройка оптимизатора
- ✅ `/api/plugins/stats` — статистика плагинов
- ✅ `/api/plugins/list` — список плагинов
- ✅ `/api/traffic-history` — история трафика
- ✅ `/api/performance-history` — история производительности

### Тесты
- ✅ test_optimizer.py: 17 тестов
- ✅ test_plugins.py: 14 тестов
- ✅ test_dc_monitor.py: 30 тестов
- ✅ test_notifications.py: 29 тестов
- ✅ test_connection_cache.py: 27 тестов
- ✅ test_client_stats.py: 39 тестов
- ✅ test_config_backup.py: 24 тестов
- ✅ test_rate_limiter.py: 14 тестов
- ✅ Итого: 463 passed, 7 skipped

### Android
- ✅ ProxyForegroundService — улучшена стабильность (watchdog, proxyThread)
- ✅ MainActivity — улучшения
- ✅ shortcuts.xml — добавлены ярлыки
- ✅ AndroidManifest — обновления
- ✅ strings.xml — English локализация (values-en)
- ✅ backup_rules.xml — правила бэкапа
- ✅ data_extraction_rules.xml — правила извлечения данных

---

## 🔴 Высокий приоритет (v2.32.0)

### Тесты и покрытие
- [ ] Покрытие tg_ws_proxy.py: 13% → 60%
  - [ ] Тесты для `_handle_client()` (интеграционные)
  - [ ] Тесты для WebSocket pool
  - [ ] Тесты для TCP fallback логики
- [ ] Load tests (100+ одновременных подключений)
- [ ] Coverage > 80% (текущее ~35%)

### Покрытие тестами
- [ ] rate_limiter.py: 14 тестов → 80% coverage
- [ ] crypto.py: 25% → 80%
- [ ] alerts.py: 40% → 80%
- [ ] logger.py: 9 тестов (fix Windows PermissionError) → 80%

### Производительность
- [ ] HTTP/2 для WebSocket
- [ ] Профилирование memory usage
- [ ] Оптимизация WebSocket pool

---

## 🟢 Низкий приоритет (v2.33.0)

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

---

## 📊 Статус

```
Tests: 463 passed, 7 skipped, 0 errors
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

**Новые модули (отличное покрытие):**
- `optimizer.py` — 100% (17 тестов)
- `plugins.py` — 100% (14 тестов)
- `dc_monitor.py` — 100% (30 тестов)
- `notifications.py` — 85% (29 тестов, 4 skipped)
- `connection_cache.py` — 100% (27 тестов)
- `client_stats.py` — 100% (39 тестов)
- `config_backup.py` — 100% (24 тестов)

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
