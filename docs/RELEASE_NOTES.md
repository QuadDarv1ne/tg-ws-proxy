# TG WS Proxy — Release Notes

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. Все права защищены.**

---

## v2.10.0 (Текущая)

**Основные изменения:**
- Оптимизация памяти: история 100→30 записей
- Async DNS resolver (aiodns) для ускорения
- Автоматический экспорт статистики (JSON каждый час)
- Проверка обновлений GitHub
- i18n: русский/английский (80+ переводов)
- Whitelist IP с O(1) проверкой
- Ruff: 0 ошибок, Mypy: ~10 предупреждений

---

## v2.5.5

**Улучшения:**
- Веб-панель: health check с диагностикой по DC
- Расширенная статистика: эффективность пула WebSocket
- Обработка ошибок в автостарте
- Проверка прав администратора для автозапуска
- Детальное логирование passthrough

---

## v2.5.3

**Рефакторинг:**
- Вынесена статистика в `proxy/stats.py`
- Обработка ошибок в `_handle_client()`
- Поддержка cryptography>=42
- RateLimiter: проверка whitelist
- Удаление дублирования `_human_bytes`
- Упрощение автостарта

---

## v2.5.2

**Новые функции:**
- Rate limiting для защиты от перегрузки
- IP фильтрация (whitelist/blacklist)
- JSON конфигурация с валидацией
- IPv6 warning
- RotatingFileHandler для логов (5MB, 3 backup)

**Исправления:**
- KeyError в `Stats.to_dict()`
- Запуск tray.py через `__main__`

---

## v2.5.0

**Базовая функциональность:**
- SOCKS5-прокси
- WebSocket relay к Telegram DC
- TCP fallback
- Tray-приложение (Windows, Linux, macOS)
- GUI настройки (customtkinter)
- Автозапуск
- Проверка обновлений GitHub
- Unit-тесты (55 тестов)
- MTProto proxy для мобильных

---

## v2.0.0

**Новые функции:**
- Веб-панель управления (Flask)
- Расширенная статистика по DC
- Система уведомлений
- SOCKS5 аутентификация
- IP whitelist

---

## v1.0.0

**Первый релиз:**
- Базовая функциональность прокси
- WebSocket relay
- TCP fallback
- Поддержка Windows

---

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
