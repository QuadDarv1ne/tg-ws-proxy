# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.10.0 — v2.19.0)

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
- ✅ Mypy: ~10 ошибок (только missing stubs)
- ✅ Новые модули: `proxy/i18n.py`, `proxy/updater.py`

### Тесты
- ✅ Tests: 243 → 255 passed
- ✅ Добавлены тесты для i18n, updater, whitelist
- ✅ Покрытие web_dashboard.py: 61% → 74%

### Документация
- ✅ Очистка документации от дублирования
- ✅ README.md сокращён (352 → ~150 строк)
- ✅ BUILD.md — краткая инструкция
- ✅ INSTALL_MOBILE.md — PWA и APK
- ✅ RELEASE_NOTES.md — ключевые версии

---

## 🔴 Высокий приоритет (v2.20.0)

### Тесты и покрытие
- [ ] Покрытие tg_ws_proxy.py: 23% → 60%
  - [ ] Тесты для `_handle_client()` (интеграционные)
  - [ ] Тесты для WebSocket pool
  - [ ] Тесты для TCP fallback логики
- [ ] Load tests (100+ одновременных подключений)
- [ ] Coverage > 80% (текущее ~42%)

### Покрытие тестами
- [ ] mtproto_proxy.py: 49% → 80%
- [ ] dashboard.py: 57% → 80%
- [ ] alerts.py: 40% → 80%

### Производительность
- [ ] HTTP/2 для WebSocket
- [ ] Профилирование memory usage
- [ ] Оптимизация WebSocket pool

---

## 🟢 Низкий приоритет (v2.21.0)

### Документация (без запроса не менять)
- [ ] Скриншоты интерфейса в README
- [ ] Video-гайд по настройке

### Новые функции
- [ ] Графики трафика в веб-панели (Chart.js)
- [ ] Push уведомления (Telegram bot, Discord webhook)
- [ ] Расширенная i18n (de, es, fr)

### Безопасность
- [ ] Улучшенная SOCKS5 аутентификация
- [ ] TLS для локального прокси

---

## 📊 Статус

```
Tests: 255 passed, 3 skipped
Coverage: ~42% (цель >80%)
```

**Проблемные зоны:**
- `tg_ws_proxy.py` — 23%
- `mtproto_proxy.py` — 49%
- `dashboard.py` — 57%
- `alerts.py` — 40%

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
