# 📊 Система Мониторинга и Уведомлений

## Обзор

TG WS Proxy включает продвинутую систему мониторинга в реальном времени с автоматическими уведомлениями о критических событиях.

## Компоненты

### 1. **Stats Module** (`proxy/stats.py`)

Собирает и анализирует метрики производительности:
- Подключения (total, active, per minute)
- Трафик (bytes up/down, per minute)
- Ошибки (WebSocket errors, error rate)
- Производительность (CPU, memory)
- DC статистика (latency, connections)
- Pool эффективность (hits/misses)

### 2. **Alerts Module** (`proxy/alerts.py`)

Генерирует уведомления при превышении порогов:
- Мгновенные алерты
- История событий
- Уведомления по email
- Webhook интеграция (Telegram, Discord, Slack)

## Типы уведомлений

| Тип | Описание | Порог Warning | Порог Critical |
|-----|----------|---------------|----------------|
| **CONNECTION_SPIKE** | Резкий рост подключений | 100/мин | 500/мин |
| **ERROR_RATE_HIGH** | Высокий процент ошибок | 5% | 15% |
| **CPU_HIGH** | Высокая загрузка CPU | 70% | 90% |
| **MEMORY_HIGH** | Высокое потребление памяти | 70% | 90% |
| **WS_ERRORS** | Ошибки WebSocket | 10/мин | 50/мин |
| **TRAFFIC_LIMIT** | Превышение трафика | 50 GB/час | 100 GB/час |
| **DC_UNAVAILABLE** | DC недоступен | - | - |
| **SECURITY_EVENT** | Событие безопасности | - | - |
| **KEY_ROTATION** | Ротация ключей шифрования | Info | - |

## Настройка порогов

```python
from proxy.stats import Stats
from proxy import alerts

# Получить менеджер алертов
alert_mgr = alerts.get_alert_manager()

# Настроить пороги
alert_mgr.update_threshold(
    "connections_per_minute",
    warning=150,      # Warning при 150 подключений/мин
    critical=600,     # Critical при 600 подключений/мин
    enabled=True
)

# Настроить cooldown (мин. время между алертами)
alert_mgr.thresholds["error_rate_percent"].cooldown_seconds = 120
```

## Email уведомления

```python
from proxy import alerts

alert_mgr = alerts.get_alert_manager()

alert_mgr.configure_email(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="your_email@gmail.com",
    password="your_app_password",
    from_email="your_email@gmail.com",
    to_emails=["admin@example.com", "devops@example.com"],
)
```

## Webhook уведомления

### Telegram Bot

```python
from proxy import alerts

alert_mgr = alerts.get_alert_manager()

# Telegram Bot API
telegram_url = "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage"
alert_mgr.configure_webhook([telegram_url])
```

### Discord Webhook

```python
discord_url = "https://discord.com/api/webhooks/<WEBHOOK_ID>/<TOKEN>"
alert_mgr.configure_webhook([discord_url])
```

### Slack Webhook

```python
slack_url = "https://hooks.slack.com/services/<SLACK_WEBHOOK>"
alert_mgr.configure_webhook([slack_url])
```

## Мониторинг в реальном времени

### Автоматический запуск

Мониторинг запускается автоматически при старте прокси:

```python
# В ProxyServer.__init__
self.stats = Stats(enable_alerts=True)
self.stats.start_realtime_monitoring(check_interval=30.0)  # Проверка каждые 30 сек
```

### Ручное управление

```python
from proxy.stats import Stats

stats = Stats(enable_alerts=True)

# Запуск мониторинга
stats.start_realtime_monitoring(check_interval=10.0)  # Проверка каждые 10 сек

# Остановка мониторинга
stats.stop_realtime_monitoring()
```

## Получение статистики

### Текущая статистика

```python
from proxy.stats import Stats

stats = proxy_server.stats

# Получить всю статистику
all_stats = stats.to_dict()

# Получить состояние здоровья
health_status = stats.get_health_status()
# Returns: ('healthy'|'degraded'|'unhealthy', message, color)

# Получить производительность
perf = stats.get_performance_stats()
# Returns: {cpu_percent, memory_bytes, avg_cpu, avg_memory}

# Получить статистику по DC
dc_stats = stats.get_dc_stats()
```

### Статистика алертов

```python
from proxy import alerts

alert_mgr = alerts.get_alert_manager()

# Получить статистику
alert_stats = alert_mgr.get_statistics()
# Returns:
# {
#     "total_alerts": 150,
#     "alerts_last_hour": 5,
#     "alerts_last_day": 42,
#     "alerts_sent": 150,
#     "alerts_suppressed": 10,
#     "by_severity": {...},
#     "by_type": {...}
# }

# Получить последние алерты
recent = alert_mgr.get_recent_alerts(limit=50)

# Получить алерты по типу
ws_errors = alert_mgr.get_alerts_by_type(AlertType.WS_ERRORS)

# Получить критические алерты
critical = alert_mgr.get_alerts_by_severity(AlertSeverity.CRITICAL)
```

## Интеграция с веб-панелью

### API эндпоинты

```
GET /api/stats          - Получить статистику
GET /api/alerts         - Получить последние алерты
GET /api/alerts/stats   - Получить статистику алертов
POST /api/alerts/clear  - Очистить текущие алерты
```

### Пример ответа /api/stats

```json
{
    "connections_total": 1250,
    "connections_ws": 1200,
    "bytes_up": 524288000,
    "bytes_down": 10737418240,
    "ws_errors": 5,
    "pool_hits": 980,
    "pool_misses": 20,
    "connections_per_minute": 45.5,
    "performance": {
        "cpu_percent": 12.5,
        "memory_bytes": 52428800,
        "avg_cpu_percent": 11.2,
        "avg_memory_bytes": 50331648
    },
    "health": ["healthy", "Работает нормально", "green"],
    "alerts_enabled": true,
    "monitoring": {
        "enabled": true,
        "alert_manager": true,
        "monitor_task": true
    }
}
```

## Логирование

Алерты записываются в лог:

```
2026-03-20 21:15:00  WARNING  ALERT [CRITICAL] High error rate: 15.2%
2026-03-20 21:15:00  WARNING  Error rate is above acceptable level. Current: 15.2%
2026-03-20 21:16:00  INFO  ALERT [INFO] Encryption keys rotated: AES-256-GCM
```

## Примеры использования

### Мониторинг трафика

```python
from proxy.stats import Stats
from proxy import alerts

stats = Stats(enable_alerts=True)

# Установить лимит трафика
alert_mgr = alerts.get_alert_manager()
alert_mgr.update_threshold(
    "traffic_gb_per_hour",
    warning=30,    # 30 GB/час warning
    critical=80,   # 80 GB/час critical
)

# Отправить уведомление при достижении лимита
# (автоматически при превышении порога)
```

### Мониторинг ошибок

```python
# Автоматическое отслеживание ошибок
# (встроено в stats.add_ws_error())

# При добавлении ошибки автоматически проверяется порог
stats.add_ws_error(dc=2)

# Если ошибок > 10 в минуту -> отправляется алерт
```

### Кастомные алерты

```python
from proxy import alerts

# Отправить кастомный алерт
alerts.send_alert(
    alert_type=alerts.AlertType.SECURITY_EVENT,
    severity=alerts.AlertSeverity.WARNING,
    title="Подозрительная активность",
    message="Обнаружено множество подключений с одного IP",
    metadata={"ip": "192.168.1.100", "attempts": 50},
)
```

## Встроенные функции алертов

```python
from proxy import alerts

# Быстрые функции для распространенных алертов
alerts.alert_connection_spike(connections=150)
alerts.alert_error_rate(error_rate=12.5)
alerts.alert_ws_errors(count=25)
alerts.alert_traffic_limit(traffic_gb=75.5)
alerts.alert_key_rotation(algorithm="AES-256-GCM")
alerts.alert_security_event(
    event_type="Rate limit exceeded",
    details="IP 192.168.1.100 exceeded rate limit"
)
```

## Коoldown управление

Для предотвращения спама алертами используется cooldown:

```python
alert_mgr = alerts.get_alert_manager()

# Установить cooldown 5 минут для CPU алертов
alert_mgr.thresholds["cpu_percent"].cooldown_seconds = 300

# Проверить cooldown
now = time.time()
last_alert = alert_mgr._last_alert_time.get("cpu_percent", 0)
if now - last_alert < 300:
    print("Alert suppressed (cooldown)")
```

## Статистика мониторинга

### Метрики для сбора

1. **Доступность**: uptime, health status
2. **Производительность**: CPU, memory, latency
3. **Трафик**: bytes up/down, connections
4. **Ошибки**: error rate, WS errors
5. **Безопасность**: auth failures, rate limits

### Рекомендуемые интервалы проверки

| Метрика | Интервал проверки | Cooldown |
|---------|-------------------|----------|
| CPU | 10 сек | 600 сек |
| Memory | 10 сек | 600 сек |
| Connections | 30 сек | 300 сек |
| Error rate | 30 сек | 180 сек |
| Traffic | 60 сек | 3600 сек |

## Устранение проблем

### Проблема: Алерты не отправляются

**Решение:**
1. Проверьте `stats.enable_alerts = True`
2. Убедитесь, что `alerts_module` импортирован
3. Проверьте логи на наличие ошибок

### Проблема: Слишком много алертов

**Решение:**
1. Увеличьте `cooldown_seconds` для порогов
2. Увеличьте `check_interval` в `start_realtime_monitoring()`
3. Настройте более высокие пороги warning/critical

### Проблема: Email не отправляются

**Решение:**
1. Проверьте SMTP настройки
2. Для Gmail используйте App Password
3. Проверьте firewall для порта 587

## Будущие улучшения

- [ ] Интеграция с Prometheus/Grafana
- [ ] Экспорт метрик в InfluxDB
- [ ] Поддержка PagerDuty
- [ ] Машинное обучение для аномалий
- [ ] Прогнозирование трендов
- [ ] Автоматическое масштабирование

---

**Dupley Maxim Igorevich**  
© 2026 Dupley Maxim Igorevich. Все права защищены.
