# TODO — TG WS Proxy

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
- [x] Unit-тесты (64 теста)
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
- [ ] Lazy initialization пула — отложенное создание

#### Тесты (v2.12.0) ✅
- [x] Integration tests для веб-панели — `tests/test_web_dashboard.py` ✅ (9 тестов)
- [ ] Load tests — сценарии нагрузки
- [ ] Coverage > 80% — текущее покрытие ~20%

### 🟢 Низкий приоритет

#### Интерфейс (v2.14.0)
- [ ] Компактный режим tray — `tray.py`
- [ ] Индикатор статуса в трее — цвет иконки
- [ ] Quick settings в меню — быстрый доступ

#### Уведомления (v2.14.0)
- [ ] Уведомление об ошибках подключения — `tray.py`
- [ ] Уведомление о низком качестве соединения — по latency
- [ ] Daily summary — статистика за день

---

## 🧹 Технический долг

### Требуется рефакторинг
- [ ] Объединить дублирование в mtproto_proxy.py и tg_ws_proxy.py
- [ ] Вынести общую логику в базовый класс
- [ ] Упростить _edit_config_dialog() — ещё больше

### Код-качество
- [x] Исправить ruff нарушения (682 → 0 ✅)
- [ ] Добавить type hints в profiler.py
- [ ] Увеличить coverage тестов (>80%)
- [ ] Пройти mypy без ошибок (11 ошибок — missing stubs)

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

### v2.12.0 (Выполнено)
- ✅ DNS кэширование
- ✅ TCP connection pooling
- ✅ Graceful shutdown
- ✅ Integration tests для веб-панели

### v2.13.0 (В разработке)
- Валидация конфигурации
- Recovery после сетевых сбоев
- Lazy initialization пула
- Load tests

### v2.14.0 (Планируется)
- Компактный режим tray
- Индикатор статуса
- Smart notifications

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
