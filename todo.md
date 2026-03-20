# TODO — TG WS Proxy

## ✅ Выполнено (v2.14.0)

### Интерфейс (v2.14.0) ✅
- [x] Компактный режим tray — `tray.py` ✅
- [x] Индикатор статуса в трее — цвет иконки + текст в меню ✅
- [x] Quick settings в меню — быстрые пресеты DC ✅

### Уведомления (v2.14.0) ✅
- [x] Уведомление об ошибках подключения — `tray.py` ✅
- [x] Уведомление о низком качестве соединения — по latency (>200ms) ✅
- [x] Daily summary — статистика за день при закрытии ✅

---

## ✅ Выполнено (v2.12.0)

### Ядро
- [x] Базовая функциональность SOCKS5-прокси
- [x] WebSocket relay к Telegram DC
- [x] TCP fallback при недоступности WS
- [x] MTProto proxy для мобильных
- [x] Rate limiting, IP фильтрация
- [x] JSON конфигурация
- [x] Type hints для публичного API
- [x] DNS кэширование (5 мин TTL, автоочистка)
- [x] TCP connection pooling (max 4 conn, max age 60s)

### Платформы
- [x] Tray-приложение (Windows, Linux, macOS)
- [x] GUI настройки (customtkinter)
- [x] Нативное меню macOS на rumps
- [x] Автозапуск (Windows, macOS, Linux)

### Мониторинг
- [x] Статистика в трее
- [x] Консольная панель управления (TUI)
- [x] Веб-панель (Flask)
- [x] Мониторинг производительности (CPU/RAM)
- [x] Проверка обновлений (GitHub API)

### Инфраструктура
- [x] CI/CD (GitHub Actions)
- [x] Unit-тесты (195 тестов, 1 пропущен, 3 ошибки в интеграционных)
- [x] Интеграционные тесты (MTProto)
- [x] Integration tests для веб-панели
- [x] RotatingFileHandler для логов (5MB, 3 backup)
- [x] Проверка порта перед запуском
- [x] IPv6 warning

---

## 🔴 Критические исправления

### ✅ Исправлено (v2.5.1 - v2.12.0)
- [x] **Статистика**: добавлен `pool_hits` в `Stats.to_dict()` (ошибка KeyError)
- [x] **tray.py**: исправлен запуск через `if __name__ == "__main__"`
- [x] **tray.py**: иконка создаётся до показа диалога первого запуска
- [x] **Python 3.14**: совместимость с новой версией
- [x] **cryptography>=42**: ручная IGE реализация
- [x] **RateLimiter**: исправлена проверка whitelist
- [x] **Удаление дублирования**: `_human_bytes`, `_format_bytes`
- [x] **Очистка констант**: объединение секций, удаление неиспользуемых
- [x] **Рефакторинг**: разбиение крупных функций на подметоды
- [x] **Упрощение**: wait_stop(), _handle_client()
- [x] **Защита от None**: _close_writer_safe()
- [x] **time.monotonic()**: замена time.time() в stats.py
- [x] **Thread-safe**: is_ip_allowed() в RateLimiter
- [x] **Graceful shutdown**: корректное закрытие соединений (v2.12.0)

---

## 📋 Актуальные задачи

### ✅ Выполнено (v2.15.0)

#### Ядро (v2.15.0) ✅
- [x] Callback для уведомлений об ошибках подключения — `tg_ws_proxy.py` ✅
- [x] Callback для уведомлений о высоком latency — `tg_ws_proxy.py` ✅
- [x] Мониторинг latency с cooldown (5 мин) — `tg_ws_proxy.py` ✅

#### Интерфейс (v2.15.0) ✅
- [x] Индикатор статуса в трее — цветная точка (зелёный/жёлтый/красный) — `tray.py` ✅
- [x] Текст статуса в меню — "🟢 Работает", "🔴 Ошибка", "⏳ Запуск..." — `tray.py` ✅
- [x] Компактный режим меню — только основные пункты — `tray.py` ✅
- [x] Quick DC presets —_submenu_ с выбором DC 1-5, все DC — `tray.py` ✅
- [x] Daily summary — статистика за день при закрытии — `tray.py` ✅

#### Уведомления (v2.15.0) ✅
- [x] Уведомление об ошибках WebSocket handshake/connect — `tray.py` ✅
- [x] Уведомление о высоком latency (>200ms) — `tray.py` ✅
- [x] Сохранение daily stats в `.daily_stats.json` — `tray.py` ✅

### 🔴 Высокий приоритет

#### Безопасность (v2.12.0) ✅
- [x] Белый список IP-адресов клиентов — `proxy/constants.py`, `tray.py` ✅
- [x] Поддержка логина/пароля для прокси — уже реализовано ✅
- [x] Валидация конфигурации при сохранении — `tray.py` ✅

#### Стабильность (v2.12.0) ✅
- [x] Обработка ошибок WebSocket — экспоненциальная задержка ✅
- [x] Graceful shutdown — корректное закрытие соединений ✅
- [x] Recovery после сетевых сбоев — авторебез без рестарта ✅

### 🟡 Средний приоритет

#### Оптимизация (v2.12.0) ✅
- [x] Кэширование DNS запросов — `proxy/tg_ws_proxy.py` ✅
- [x] Connection pooling для TCP fallback — `proxy/tg_ws_proxy.py` ✅
- [x] Lazy initialization пула — отложенное создание (`proxy/tg_ws_proxy.py`) ✅

#### Тесты (v2.12.0) ✅
- [x] Integration tests для веб-панели — `tests/test_web_dashboard.py` ✅ (9 тестов)
- [x] Unit-тесты для MTProtoProxy — `tests/test_mtproto_proxy.py` ✅ (32 теста)
- [x] Unit-тесты для tg_ws_proxy — `tests/test_proxy.py` ✅ (25 тестов)
- [x] Unit-тесты для profiler.py — `tests/test_profiler.py` ✅ (19 тестов)
- [x] Unit-тесты для stats.py — `tests/test_stats.py` ✅ (30 тестов)
- [x] Unit-тесты для dashboard.py — `tests/test_dashboard.py` ✅ (19 тестов)
- [ ] Load tests — сценарии нагрузки
- [ ] Coverage > 80% — текущее покрытие ~44%

### ✅ Выполнено (v2.16.0)

#### Рефакторинг (v2.16.0) ✅
- [x] Улучшение type hints в dashboard.py — добавлены аннотации типов ✅
- [x] Улучшение type hints в diagnostics.py — добавлены аннотации типов ✅
- [x] Улучшение type hints в mtproto_proxy.py — добавлены аннотации типов ✅
- [x] Улучшение type hints в tg_ws_proxy.py — добавлены аннотации типов ✅
- [x] Улучшение type hints в web_dashboard.py — добавлены аннотации типов ✅
- [x] Исправление mypy type: ignore — замена на конкретные коды ошибок ✅

### 🟢 Низкий приоритет

#### Интерфейс (v2.17.0)
- [ ] Трей с темной/светлой темой — адаптация под тему Windows
- [ ] Всплывающие подсказки к пунктам меню
- [ ] Горячие клавиши для быстрых DC (Ctrl+1, Ctrl+2...)

#### Уведомления (v2.17.0)
- [ ] Настройка порогов уведомлений — GUI
- [ ] Еженедельный отчёт — сводка за 7 дней
- [ ] Уведомление о доступности обновлений — с деталями changelog

---

## 🧹 Технический долг

### Требуется рефакторинг
- [ ] Объединить дублирование в mtproto_proxy.py и tg_ws_proxy.py
- [ ] Вынести общую логику в базовый класс
- [ ] Упростить _edit_config_dialog() — ещё больше

### Код-качество
- [x] Исправить ruff нарушения (682 → 0 ✅)
- [x] Добавить type hints в profiler.py ✅
- [x] Увеличить coverage тестов (20% → 46% ✅, цель >80%)
- [x] Исправить mypy ошибки (146 → ~30 ✅)
- [x] Улучшение type hints в proxy-модулях (v2.16.0) ✅
- [ ] Пройти mypy без ошибок (остались missing stubs: flask_cors, qrcode; сложные типы в dashboard.py, web_dashboard.py, tray.py, tg_ws_proxy.py)

### Документация (без запроса не менять)
- [ ] Скриншоты интерфейса — README.md
- [ ] Примеры для разных сценариев — уже в README
- [ ] API docs — автогенерация

---

## 📦 Зависимости

### Основные
```
cryptography>=46.0.5
psutil>=7.2.2
pystray>=0.19.5
customtkinter>=5.2.2
Pillow>=12.1.1
flask>=3.1.3
flask-cors>=6.0.2
qrcode>=8.2
rich>=14.3.3
```

### Разработка
```
pytest>=9.0.2
pytest-cov>=6.1.1
pytest-asyncio>=0.26.0
mypy>=1.19.1
ruff>=0.15.6
black>=26.3.1
pyinstaller>=5.0.0
```

---

## 🚀 Roadmap

### v2.14.0 (Выполнено)
- ✅ Компактный режим tray
- ✅ Индикатор статуса
- ✅ Smart notifications (ошибки, latency, daily summary)
- ✅ Quick DC presets в меню

### v2.15.0 (Выполнено)
- ✅ Callback уведомления об ошибках подключения
- ✅ Мониторинг latency с cooldown (5 мин)
- ✅ Индикатор статуса — цветная точка + текст
- ✅ Quick DC presets submenu
- ✅ Daily summary при закрытии

### v2.16.0 (В разработке)
- [x] Увеличение coverage тестов (44% → 46%)
- [x] Исправление mypy ошибок (частично, ~30 осталось)
- [x] Улучшение type hints в proxy-модулях
- [ ] Load tests — сценарии нагрузки
- [ ] Coverage > 80% — текущее покрытие ~46%
- [ ] Пройти mypy без ошибок (остались missing stubs и сложные типы)

### v2.17.0 (Планируется)
- Улучшение type hints — оставшиеся модули
- Адаптация под тему системы
- Настройка порогов уведомлений — GUI
- Еженедельный отчёт — сводка за 7 дней
- Уведомление о доступности обновлений — changelog

---

## 🛠 Разработка

### Workflow
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

### Python
- **Путь:** `C:\Users\maksi\AppData\Local\Python\bin\python.exe`
- **Версия:** Python 3.14
