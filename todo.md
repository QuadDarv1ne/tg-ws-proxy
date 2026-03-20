# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## 🔴 Высокий приоритет (v2.18.0)

### ✅ Выполнено
- [x] Исправлены ruff предупреждения (W291, W293, F401, F402)
- [x] Установлены missing stubs: types-psutil, types-qrcode, types-Flask-Cors, types-pyperclip
- [x] Исправлены mypy ошибки в tg_ws_proxy.py, mtproto_proxy.py, web_dashboard.py, crypto.py
- [x] Mypy: 1 ошибка (rich.typing stubs не существует)

### Тесты и покрытие
- [ ] Покрытие tg_ws_proxy.py: 19% → 60%
  - [ ] Тесты для `_handle_client()`
  - [ ] Тесты для WebSocket pool
  - [ ] Тесты для TCP fallback логики
  - [ ] Тесты для callbacks уведомлений
- [ ] Load tests (100+ одновременных подключений)
- [ ] Coverage > 80% (текущее ~46%)

---

## 🟡 Средний приоритет (v2.18.0)

### Покрытие тестами
- [ ] web_dashboard.py: 60% → 80%
- [ ] mtproto_proxy.py: 49% → 80%
- [ ] dashboard.py: 57% → 80%

### Производительность
- [ ] Async DNS resolver (aiodns)
- [ ] HTTP/2 для WebSocket
- [ ] Оптимизация memory footprint

---

## 🟢 Низкий приоритет (v2.19.0)

### Документация (без запроса не менять)
- [ ] Скриншоты интерфейса в README
- [ ] Video-гайд по настройке
- [ ] API docs (Sphinx)

### Новые функции
- [ ] Графики трафика в веб-панели (Chart.js)
- [ ] История подключений
- [ ] Экспорт статистики (CSV/JSON)
- [ ] Push уведомления
- [ ] Настройки прокси в UI
- [ ] Многоязычность (i18n)

---

## ✅ Выполнено (v2.17.0)

### Интерфейс
- [x] Трей с темной/светлой темой
- [x] Всплывающие подсказки к пунктам меню
- [x] Горячие клавиши для быстрых DC (Ctrl+1, Ctrl+2...)
- [x] Новый современный UI веб-панели
- [x] PWA поддержка (manifest, service worker, иконки)
- [x] Мобильная версия UI
- [x] Тёмная тема в веб-панели
- [x] Индикаторы статуса системы
- [x] Быстрые действия (копирование конфига, QR-код)
- [x] PWA Install Prompt
- [x] Автообновление статистики (5 сек)
- [x] Toast уведомления

### Мобильные приложения
- [x] Capacitor проект для Android/iOS
- [x] PWA иконки (192x192, 512x512)
- [x] Сборка Android APK
- [x] Сборка iOS через Xcode
- [x] Инструкции по установке

### Сборка
- [x] Универсальный скрипт сборки Desktop
- [x] Универсальный скрипт сборки Mobile
- [x] Spec-файлы обновлены (Flask, PWA)
- [x] Windows сборка работает
- [x] Генерация иконок

### Документация
- [x] BUILD.md — руководство по сборке
- [x] INSTALL_MOBILE.md — установка на телефон
- [x] Обновление author во всех файлах
- [x] Организация docs/

---

## ✅ Выполнено (v2.14.0 — v2.16.0)

### Ядро
- [x] Callback для уведомлений об ошибках подключения
- [x] Callback для уведомлений о высоком latency
- [x] Мониторинг latency с cooldown (5 мин)
- [x] Graceful shutdown
- [x] DNS кэширование (5 мин TTL)
- [x] TCP connection pooling (max 4 conn, max age 60s)
- [x] Rate limiting, IP фильтрация
- [x] JSON конфигурация с валидацией

### Интерфейс
- [x] Компактный режим tray
- [x] Индикатор статуса в трее (цветная точка + текст)
- [x] Quick DC presets submenu
- [x] Daily summary при закрытии

### Код-качество
- [x] Ruff нарушения исправлены (682 → 0)
- [x] Type hints в proxy-модулях
- [x] Coverage: 20% → 46%
- [x] Mypy ошибки: 146 → ~30

---

## 📊 Статус тестов

```
Tests: 236 passed, 3 skipped, 0 errors
Coverage: ~46% (цель >80%)
```

**Проблемные зоны:**
- `tg_ws_proxy.py` — 19% (872 строки пропущено)
- `mtproto_proxy.py` — 49%
- `dashboard.py` — 57%
- `web_dashboard.py` — 61%

**Исправлено в v2.18.0:**
- ✅ Переименованы функции в `diagnostics.py`: `test_*` → `check_*`
- ✅ Обновлены импорты и вызовы в `test_diagnostics.py`
- ✅ Тесты запускаются без ошибок (236 passed, 3 skipped, 0 errors)
- ✅ Mypy ошибки: ~30 → 1 (rich.typing stubs не существует)
- ✅ Ruff предупреждения: исправлены все
- ✅ Установлены missing stubs

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

---

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
