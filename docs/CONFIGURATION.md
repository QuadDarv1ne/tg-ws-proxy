# ⚙️ Конфигурация TG WS Proxy

## 📄 Файл конфигурации

Основной файл: `config.default.json`

Также поддерживаются:
- `config.json` (пользовательский)
- `config.yaml` (YAML формат)
- Переменные окружения `TGWS_*`

## 🔧 Основные разделы

### Server

Настройки сервера:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "socks_port": 1080,
    "max_connections": 500,
    "connection_timeout": 30.0
  }
}
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `host` | string | `0.0.0.0` | Хост для прослушивания |
| `port` | int | `8080` | Порт веб-панели |
| `socks_port` | int | `1080` | Порт SOCKS5 прокси |
| `max_connections` | int | `500` | Максимум подключений |
| `connection_timeout` | float | `30.0` | Таймаут подключения |

### WebSocket

Настройки WebSocket:

```json
{
  "websocket": {
    "pool_size": 4,
    "pool_max_size": 8,
    "pool_max_age": 120.0,
    "enable_compression": false,
    "ping_interval": 30.0,
    "ping_timeout": 10.0,
    "reconnect_delay": 5.0,
    "max_reconnect_attempts": 10
  }
}
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `pool_size` | int | `4` | Начальный размер пула |
| `pool_max_size` | int | `8` | Максимальный размер пула |
| `pool_max_age` | float | `120.0` | Макс возраст подключения (с) |
| `enable_compression` | bool | `false` | Сжатие WebSocket |
| `ping_interval` | float | `30.0` | Интервал ping (с) |
| `ping_timeout` | float | `10.0` | Таймаут ping (с) |

### DNS

Настройки DNS:

```json
{
  "dns": {
    "enable_cache": true,
    "cache_ttl": 300.0,
    "aggressive_ttl": true,
    "use_async_dns": true,
    "timeout": 5.0
  }
}
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `enable_cache` | bool | `true` | Включить кэширование |
| `cache_ttl` | float | `300.0` | TTL кэша (с) |
| `aggressive_ttl` | bool | `true` | Агрессивный TTL |
| `use_async_dns` | bool | `true` | Async DNS resolver |

### Security

Настройки безопасности:

```json
{
  "security": {
    "auth_required": false,
    "auth_username": "",
    "auth_password": "",
    "ip_whitelist": [],
    "ip_blacklist": [],
    "rate_limit_enabled": false,
    "rate_limit_requests": 100,
    "rate_limit_window": 60.0,
    "enable_encryption": false,
    "encryption_key": ""
  }
}
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `auth_required` | bool | `false` | Требовать авторизацию |
| `auth_username` | string | `""` | Имя пользователя |
| `auth_password` | string | `""` | Пароль |
| `ip_whitelist` | array | `[]` | Белый список IP |
| `ip_blacklist` | array | `[]` | Чёрный список IP |
| `rate_limit_enabled` | bool | `false` | Rate limiting |
| `rate_limit_requests` | int | `100` | Запросов в окно |
| `rate_limit_window` | float | `60.0` | Окно (с) |

### Performance

Настройки производительности:

```json
{
  "performance": {
    "enable_connection_pooling": true,
    "enable_auto_dc_selection": true,
    "enable_dns_cache": true,
    "tcp_nodelay": true,
    "recv_buffer_size": 65536,
    "send_buffer_size": 65536,
    "enable_profiling": false,
    "profiling_interval": 60.0
  }
}
```

### Logging

Настройки логирования:

```json
{
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "",
    "max_size_mb": 10,
    "backup_count": 3
  }
}
```

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `level` | string | `INFO` | Уровень логов |
| `format` | string | `...` | Формат логов |
| `file` | string | `""` | Файл логов |
| `max_size_mb` | int | `10` | Макс размер файла |
| `backup_count` | int | `3` | Кол-во резервных копий |

### Monitoring

Настройки мониторинга:

```json
{
  "monitoring": {
    "enable_metrics": true,
    "metrics_port": 9090,
    "enable_prometheus": true,
    "prometheus_path": "/metrics",
    "enable_alerts": true,
    "alert_dc_latency_warning": 150.0,
    "alert_dc_latency_critical": 200.0,
    "alert_cooldown": 120.0
  }
}
```

### DC Override

Переопределение DC:

```json
{
  "dc_override": {
    "1": "149.154.175.50",
    "2": "149.154.167.220",
    "3": "149.154.175.100",
    "4": "149.154.167.91",
    "5": "91.108.56.100"
  }
}
```

## 🌍 Переменные окружения

Все настройки можно переопределить через переменные:

```bash
export TGWS_SERVER_HOST=0.0.0.0
export TGWS_SERVER_SOCKS_PORT=1080
export TGWS_WEBSOCKET_POOL_SIZE=8
export TGWS_DNS_CACHE_TTL=600
```

Формат: `TGWS_<SECTION>_<KEY>=<VALUE>`

## 📝 Примеры конфигураций

### Минимальная

```json
{
  "server": {
    "socks_port": 1080
  }
}
```

### Для игровой консоли

```json
{
  "server": {
    "host": "0.0.0.0",
    "socks_port": 1080,
    "max_connections": 100
  },
  "websocket": {
    "pool_size": 8,
    "pool_max_size": 16
  }
}
```

### С авторизацией

```json
{
  "security": {
    "auth_required": true,
    "auth_username": "myuser",
    "auth_password": "mypassword"
  }
}
```

### С rate limiting

```json
{
  "security": {
    "rate_limit_enabled": true,
    "rate_limit_requests": 50,
    "rate_limit_window": 60.0
  }
}
```

## 🔧 Горячая перезагрузка

Конфигурация перезагружается автоматически при изменении файла.

Или отправьте сигнал:
- Linux/macOS: `kill -HUP <pid>`
- Windows: ПКМ по иконке → Перезапустить

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
