# 🛡️ Rate Limiting в TG WS Proxy

## Обзор

Система rate limiting защищает прокси от перегрузки и злоупотреблений, ограничивая количество подключений и запросов от каждого клиента.

## Возможности

### Per-IP лимиты:
- **Requests per second**: Макс. запросов в секунду от одного IP
- **Requests per minute**: Макс. запросов в минуту от одного IP
- **Requests per hour**: Макс. запросов в час от одного IP
- **Max connections per IP**: Макс. одновременных подключений

### Глобальные лимиты:
- **Max concurrent connections**: Общее ограничение подключений
- **Global requests per minute**: Глобальный лимит запросов

### Защита:
- **Exponential backoff**: Задержка увеличивается при нарушениях
- **Automatic ban**: Бан при повторных нарушениях
- **Sliding window**: Точный подсчет запросов
- **Cleanup**: Автоматическая очистка старых данных

## Настройка

### В конфигурационном файле

```json
{
    "rate_limit_rps": 10.0,
    "rate_limit_rpm": 100,
    "rate_limit_max_conn": 500,
    "rate_limit_per_ip": 10,
    "rate_limit_ban_threshold": 5,
    "rate_limit_ban_duration": 300.0
}
```

### Параметры конфигурации

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `rate_limit_rps` | 10.0 | Запросов в секунду на IP |
| `rate_limit_rpm` | 100 | Запросов в минуту на IP |
| `rate_limit_max_conn` | 500 | Макс. одновременных подключений |
| `rate_limit_per_ip` | 10 | Макс. подключений на IP |
| `rate_limit_ban_threshold` | 5 | Нарушений до бана |
| `rate_limit_ban_duration` | 300.0 | Длительность бана (сек) |

## Алгоритм работы

### 1. Проверка подключений

```
Новое подключение от IP
         ↓
    IP забанен? ────Да──→ Отклонить
         ↓ Нет
    Глобальный лимит превышен? ────Да──→ Отклонить/Задержать
         ↓ Нет
    Лимит IP превышен? ────Да──→ Нарушение
         ↓ Нет
    Разрешить подключение
```

### 2. Обработка нарушений

```
Нарушение лимита
         ↓
    Увеличить счетчик нарушений
         ↓
    Нарушений >= порога? ────Да──→ Бан на N секунд
         ↓ Нет
    Рассчитать задержку (exponential backoff)
         ↓
    Задержать на N мс
```

### 3. Exponential Backoff

Формула расчета задержки:

```
delay_ms = min(initial_delay * (multiplier ^ (violations - 1)), max_delay)
```

Где:
- `initial_delay`: 100 мс (по умолчанию)
- `multiplier`: 2.0 (удвоение)
- `max_delay`: 5000 мс (5 секунд)

**Пример:**
- 1 нарушение: 100 мс
- 2 нарушения: 200 мс
- 3 нарушения: 400 мс
- 4 нарушения: 800 мс
- 5 нарушений: 1600 мс
- 6+ нарушений: Бан на 300 сек

## Рекомендации по настройке

### Для домашнего использования

```json
{
    "rate_limit_rps": 20.0,
    "rate_limit_rpm": 200,
    "rate_limit_max_conn": 100,
    "rate_limit_per_ip": 20,
    "rate_limit_ban_threshold": 10,
    "rate_limit_ban_duration": 600.0
}
```

### Для публичного прокси

```json
{
    "rate_limit_rps": 5.0,
    "rate_limit_rpm": 50,
    "rate_limit_max_conn": 500,
    "rate_limit_per_ip": 5,
    "rate_limit_ban_threshold": 3,
    "rate_limit_ban_duration": 900.0
}
```

### Для высокой нагрузки

```json
{
    "rate_limit_rps": 50.0,
    "rate_limit_rpm": 500,
    "rate_limit_max_conn": 2000,
    "rate_limit_per_ip": 50,
    "rate_limit_ban_threshold": 10,
    "rate_limit_ban_duration": 1800.0
}
```

## Мониторинг

### Статистика по IP

```python
from proxy.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
stats = limiter.get_ip_stats("192.168.1.100")

print(stats)
# {
#     "total_requests": 150,
#     "blocked_requests": 5,
#     "violations": 2,
#     "active_connections": 3,
#     "is_banned": False,
#     "ban_remaining": 0,
#     "requests_last_minute": 45
# }
```

### Глобальная статистика

```python
global_stats = limiter.get_global_stats()

print(global_stats)
# {
#     "total_active_connections": 45,
#     "unique_ips": 12,
#     "requests_last_minute": 350,
#     "banned_ips": 2,
#     "total_violations": 15
# }
```

## Логирование

### Примеры логов

```
2026-03-20 22:00:00  INFO  Rate limiter configured: 100 req/min, 500 max connections
2026-03-20 22:00:01  INFO  Rate limiter started
2026-03-20 22:01:15  WARNING  [C192.168.1.100:54321-1234] rate limit exceeded - rejected
2026-03-20 22:02:30  WARNING  IP 192.168.1.100 banned for 300 seconds (violations: 5)
2026-03-20 22:07:30  INFO  IP 192.168.1.100 unbanned after timeout
```

### Уровни логирования

| Уровень | Событие |
|---------|---------|
| INFO | Настройка, запуск, остановка |
| DEBUG | Задержки, проверки лимитов |
| WARNING | Превышение лимитов, баны |
| ERROR | Ошибки в работе |

## Управление вручную

### Бан IP

```python
from proxy.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()

# Забанить IP на 10 минут
limiter.ban_ip("192.168.1.100", duration=600)

# Забанить IP навсегда (до ручного разбана)
limiter.ban_ip("192.168.1.100", duration=999999999)
```

### Разбан IP

```python
# Разбанить IP
limiter.unban_ip("192.168.1.100")
```

### Сброс статистики IP

```python
# Сбросить счетчики нарушений
limiter.reset_ip("192.168.1.100")
```

## Интеграция

### В коде прокси

```python
from proxy.rate_limiter import RateLimiter, RateLimitConfig, RateLimitAction

# Создание
config = RateLimitConfig(
    requests_per_second=10,
    requests_per_minute=100,
    max_concurrent_connections=500,
)
limiter = RateLimiter(config)

# Проверка
action, delay = limiter.check_rate_limit(client_ip)

if action == RateLimitAction.ALLOW:
    limiter.add_connection(client_ip)
    # Разрешить подключение
elif action == RateLimitAction.DELAY:
    await asyncio.sleep(delay)
    # Повторить проверку
elif action == RateLimitAction.REJECT:
    # Отклонить подключение
    return
elif action == RateLimitAction.BAN:
    # IP забанен
    return

# Освобождение
limiter.remove_connection(client_ip)
```

## Производительность

### Бенчмарки

| Метрика | Значение |
|---------|----------|
| Проверка лимита | ~5-10 мкс |
| Добавление подключения | ~2-5 мкс |
| Очистка данных (1000 IP) | ~50 мс |
| Потребление памяти (10000 IP) | ~5 MB |

### Оптимизация

- **Sliding window**: Эффективный подсчет запросов
- **Периодическая очистка**: Раз в минуту
- **Словари вместо списков**: O(1) доступ
- **Async cleanup**: Фоновая очистка

## Безопасность

### Защита от атак

| Атака | Защита |
|-------|--------|
| DDoS | Глобальные лимиты |
| Brute force | Бан при нарушениях |
| IP spoofing | Per-IP лимиты |
| Resource exhaustion | Max connections |

### Рекомендации

1. **Включите rate limiting** для любого публичного прокси
2. **Настройте бан** для злостных нарушителей
3. **Мониторьте статистику** для выявления атак
4. **Используйте whitelist** для доверенных IP

## API для разработчиков

### Основные методы

```python
from proxy.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitAction,
    get_rate_limiter,
    check_rate_limit,
    add_connection,
    remove_connection,
)
```

### Классы

- `RateLimiter`: Основной класс
- `RateLimitConfig`: Конфигурация
- `RateLimitAction`: Действие (enum)
- `IPStats`: Статистика IP (dataclass)

### Эндоинты (для веб-панели)

```
GET /api/rate-limit/stats     - Глобальная статистика
GET /api/rate-limit/ip/{ip}   - Статистика по IP
POST /api/rate-limit/ban/{ip} - Бан IP
POST /api/rate-limit/unban/{ip} - Разбан IP
```

## Будущие улучшения

- [ ] Интеграция с fail2ban
- [ ] Гео-блокировка по странам
- [ ] Динамическая настройка лимитов
- [ ] Машинное обучение для аномалий
- [ ] Распределенный rate limiting

---

**Dupley Maxim Igorevich**  
© 2026 Dupley Maxim Igorevich. Все права защищены.
