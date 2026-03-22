# Contributing to TG WS Proxy

Спасибо за интерес к проекту! Мы рады любому вкладу — от исправления опечаток до новых фич.

## 🚀 Быстрый старт

### 1. Форк и клонирование

```bash
git clone https://github.com/YOUR_USERNAME/tg-ws-proxy.git
cd tg-ws-proxy
git checkout -b feature/my-feature
```

### 2. Установка зависимостей

```bash
# Основные зависимости
pip install -r requirements.txt

# Зависимости для разработки
pip install -r requirements-dev.txt
```

### 3. Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ --cov=proxy --cov-report=html

# Конкретный тест
pytest tests/test_socks5.py -v
```

### 4. Проверка кода

```bash
# Линтинг
ruff check proxy/ tests/

# Форматирование
black proxy/ tests/

# Типы
mypy proxy/
```

---

## 📋 Правила разработки

### Ветки

- `main` — стабильная версия для релизов
- `dev` — активная разработка
- `feature/*` — новые фичи
- `fix/*` — исправления багов
- `refactor/*` — рефакторинг кода

### Коммиты

Используйте [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавлена поддержка HTTP/2
fix: исправлена утечка памяти в WebSocket пуле
docs: обновлена документация API
refactor: разбит tg_ws_proxy.py на модули
test: добавлены тесты для SOCKS5 handshake
perf: оптимизирован DNS resolver
```

### Pull Requests

1. Создайте issue для обсуждения изменений
2. Работайте в отдельной ветке от `dev`
3. Добавьте тесты для новой функциональности
4. Убедитесь, что все тесты проходят
5. Обновите документацию при необходимости
6. Создайте PR в ветку `dev`

**Шаблон PR:**
```markdown
## Описание
Краткое описание изменений

## Тип изменений
- [ ] Исправление бага
- [ ] Новая фича
- [ ] Рефакторинг
- [ ] Документация

## Чеклист
- [ ] Тесты добавлены/обновлены
- [ ] Документация обновлена
- [ ] Код проверен линтером
- [ ] Все тесты проходят
```

---

## 🧪 Тестирование

### Структура тестов

```
tests/
├── test_socks5.py          # SOCKS5 протокол
├── test_ws_pool.py         # WebSocket пулинг
├── test_mtproto.py         # MTProto парсинг
├── test_stats.py           # Статистика
└── conftest.py             # Фикстуры
```

### Написание тестов

```python
import pytest
from proxy.tg_ws_proxy import ProxyServer

@pytest.mark.asyncio
async def test_socks5_handshake():
    """Test SOCKS5 handshake negotiation."""
    # Arrange
    server = ProxyServer(port=1080)
    
    # Act
    result = await server._negotiate_socks5(...)
    
    # Assert
    assert result is not None
```

### Покрытие

Цель: >80% покрытия кода

```bash
# Генерация отчета
pytest --cov=proxy --cov-report=html

# Просмотр
open htmlcov/index.html
```

---

## 🎨 Стиль кода

### Python

- **PEP 8** — базовый стиль
- **Black** — форматирование (line-length=88)
- **Ruff** — линтинг
- **Type hints** — обязательны для публичных функций

```python
# Хорошо ✅
async def connect_websocket(
    ip: str,
    domain: str,
    timeout: float = 10.0
) -> RawWebSocket | None:
    """Connect to WebSocket endpoint.
    
    Args:
        ip: Target IP address
        domain: Domain for SNI
        timeout: Connection timeout in seconds
        
    Returns:
        WebSocket instance or None on failure
    """
    pass

# Плохо ❌
async def connect_websocket(ip, domain, timeout=10.0):
    pass
```

### Документация

- Docstrings в формате Google Style
- Комментарии на русском или английском
- README и docs на русском

---

## 🏗️ Архитектура

### Модули

```
proxy/
├── tg_ws_proxy.py          # Основной прокси (требует рефакторинга)
├── stats.py                # Статистика
├── optimizer.py            # Оптимизация производительности
├── rate_limiter.py         # Rate limiting
├── crypto.py               # Шифрование
├── diagnostics.py          # Диагностика
└── web_dashboard.py        # Веб-панель
```

### Принципы

- **SRP** — один класс = одна ответственность
- **DRY** — избегайте дублирования
- **KISS** — простота важнее сложности
- **Async-first** — используйте asyncio где возможно

---

## 🐛 Отладка

### Логирование

```python
import logging
log = logging.getLogger('tg-ws-proxy')

# Уровни
log.debug("Детальная информация")
log.info("Общая информация")
log.warning("Предупреждение")
log.error("Ошибка")
```

### Запуск с verbose

```bash
python proxy/tg_ws_proxy.py -v  # Verbose логи
python tray.py                   # GUI с логами
```

### Профилирование

```python
from proxy.profiler import MemoryProfiler

profiler = MemoryProfiler()
await profiler.start()
# ... код ...
snapshot = profiler.take_snapshot()
```

---

## 📦 Релизы

### Версионирование

Используем [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH` (например, 2.38.0)
- `MAJOR` — breaking changes
- `MINOR` — новые фичи (обратно совместимые)
- `PATCH` — исправления багов

### Процесс релиза

1. Обновите версию в `pyproject.toml` и `proxy/__init__.py`
2. Обновите `docs/RELEASE_NOTES.md`
3. Создайте PR из `dev` в `main`
4. После мерджа создайте git tag
5. Соберите бинарники: `python build_desktop.py all`
6. Создайте GitHub Release

---

## 💡 Идеи для вклада

### Начинающим

- Исправление опечаток в документации
- Добавление комментариев к коду
- Написание тестов для существующего кода
- Улучшение сообщений об ошибках

### Средний уровень

- Рефакторинг `tg_ws_proxy.py` (разбить на модули)
- Увеличение покрытия тестами
- Оптимизация производительности
- Добавление новых метрик в статистику

### Продвинутым

- HTTP/2 multiplexing
- QUIC/UDP support
- Circuit breaker pattern
- Prometheus metrics endpoint
- Plugin system

---

## 📞 Связь

- **Issues** — для багов и предложений
- **Discussions** — для вопросов и обсуждений
- **Email** — maxim.dupley@example.com

---

## 📄 Лицензия

Внося вклад, вы соглашаетесь с лицензией [MIT License](LICENSE).

**© 2026 Dupley Maxim Igorevich. Все права защищены.**
