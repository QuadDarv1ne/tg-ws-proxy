# 🧪 Тестирование TG WS Proxy

## 📋 Обзор

Проект использует `pytest` для тестирования с покрытием ~59% (цель >80%).

## 🚀 Быстрый старт

### Установка зависимостей

```bash
pip install -r requirements-dev.txt
```

### Запуск всех тестов

```bash
pytest tests/ -v
```

### Запуск с coverage

```bash
pytest tests/ --cov=proxy --cov-report=html
```

## 📁 Структура тестов

```
tests/
├── test_alerts.py              # Тесты alerting системы
├── test_circuit_breaker.py     # Circuit breaker тесты
├── test_config.py              # Конфигурация тесты
├── test_connection_pool.py     # Connection pool тесты
├── test_crypto.py              # Криптография тесты
├── test_dns_resolver.py        # DNS resolver тесты
├── test_dpi_bypass.py          # DPI bypass тесты
├── test_e2e_encryption.py      # E2E encryption тесты
├── test_metrics_history.py     # Metrics history тесты
├── test_mtproto_parser.py      # MTProto parser тесты
├── test_optimizer.py           # Optimizer тесты
├── test_performance_profiler.py # Profiler тесты
├── test_plugins.py             # Plugin system тесты
├── test_proxy_chain.py         # Proxy chain тесты
├── test_rate_limiter.py        # Rate limiter тесты
├── test_retry_strategy.py      # Retry strategy тесты
├── test_socks5_handler.py      # SOCKS5 handler тесты
├── test_websocket_client.py    # WebSocket client тесты
└── test_*.py                   # Другие тесты
```

## 🔧 Команды pytest

### Запуск конкретных тестов

```bash
# Запуск одного файла
pytest tests/test_rate_limiter.py -v

# Запуск по имени теста
pytest tests/test_rate_limiter.py::test_check_rate_limit -v

# Запуск по маркеру
pytest -m slow -v
```

### Фильтрация

```bash
# Запуск только быстрых тестов
pytest -m "not slow" -v

# Запуск проваленных тестов
pytest --lf -v

# Запуск новых тестов
pytest --nf -v
```

### Coverage

```bash
# HTML отчёт
pytest --cov=proxy --cov-report=html

# Terminal отчёт
pytest --cov=proxy --cov-report=term-missing

# Coverage с порогом
pytest --cov=proxy --cov-fail-under=60
```

## 📊 Покрытие

Текущее покрытие: ~59%  
Цель: >80%

### Проверка покрытия по модулям

```bash
pytest --cov=proxy --cov-report=term-missing | head -50
```

### Генерация отчёта

```bash
# HTML
pytest --cov=proxy --cov-report=html:htmlcov
open htmlcov/index.html  # macOS/Linux
start htmlcov\index.html  # Windows
```

## 🧪 Написание тестов

### Пример теста

```python
import pytest
from proxy.rate_limiter import RateLimiter, RateLimitConfig

def test_rate_limiter_basic():
    config = RateLimitConfig(requests_per_second=10)
    limiter = RateLimiter(config)
    
    action, delay = limiter.check_rate_limit("127.0.0.1")
    
    assert action == RateLimitAction.ALLOW
    assert delay == 0.0

@pytest.mark.asyncio
async def test_rate_limiter_async():
    config = RateLimitConfig()
    limiter = RateLimiter(config)
    
    await limiter.start()
    
    # Test rate limiting
    for i in range(100):
        action, delay = limiter.check_rate_limit("192.168.1.1")
    
    assert action in (RateLimitAction.DELAY, RateLimitAction.BAN)
    
    await limiter.stop()
```

### Фикстуры

```python
import pytest

@pytest.fixture
def rate_limiter():
    config = RateLimitConfig()
    limiter = RateLimiter(config)
    yield limiter
    # Cleanup

@pytest.fixture
def sample_config():
    return {
        "server": {"port": 1080},
        "websocket": {"pool_size": 4}
    }
```

### Маркеры

```python
@pytest.mark.slow
def test_slow_test():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.asyncio
async def test_async():
    pass
```

## 🔍 Отладка тестов

### Вывод логов

```bash
pytest -s -v  # Показать print()
pytest -l -v  # Показать локальные переменные
```

### Post-mortem debugging

```bash
pytest --pdb  # Запуск pdb при ошибке
```

### Coverage для отладки

```bash
pytest --cov --cov-report=term-missing:skip-covered
```

## 📈 CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10
      
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      
      - name: Run tests
        run: pytest tests/ -v --cov=proxy
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## 🐛 Известные проблемы

### Windows DNS тесты

Некоторые DNS тесты могут падать на Windows из-за отсутствия aiodns.

Решение:
```bash
pytest tests/test_dns_resolver.py -k "not async"
```

### Асинхронные тесты

Для async тестов требуется `pytest-asyncio`:

```bash
pip install pytest-asyncio
```

## 📚 Ресурсы

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
