# 🚀 Обход блокировок TG WS Proxy

## Обзор

TG WS Proxy предоставляет комплексный набор инструментов для обхода интернет-цензуры и блокировок:

| Транспорт | Протокол | Обход DPI | Скорость | Рекомендация |
|-----------|----------|-----------|----------|--------------|
| **WebSocket** | WS/WSS | ⚠️ Частично | ⚡⚡⚡⚡⚡ | По умолчанию |
| **HTTP/2** | H2 | ✅ Хорошо | ⚡⚡⚡⚡ | Для строгих сетей |
| **QUIC/HTTP/3** | UDP | ✅ Отлично | ⚡⚡⚡⚡⚡ | При блокировке TCP |
| **Meek** | HTTPS + CDN | ✅✅ Максимально | ⚡⚡⚡ | Для сложных случаев |
| **MTProto** | TCP | ✅ Хорошо | ⚡⚡⚡⚡⚡ | Для Telegram Mobile |

---

## 1. Настройка транспортов

### 1.1 WebSocket (по умолчанию)

```python
from proxy.tg_ws_proxy import run_proxy_server

run_proxy_server(
    port=1080,
    dc_ip={2: "149.154.167.220"},
    use_websocket=True
)
```

**Преимущества:**
- Высокая скорость
- Низкая задержка
- Поддержка compression

**Недостатки:**
- Может блокироваться по WebSocket fingerprinting

---

### 1.2 HTTP/2 Transport

```python
from proxy.http2_transport import HTTP2Transport, create_http2_tunnel

# Создание HTTP/2 туннеля
transport = await create_http2_tunnel(
    host="kws2.web.telegram.org",
    port=443,
    path="/api",
    on_data=callback_function
)

# Отправка данных
await transport.send(b"telegram data")
data = await transport.recv()
```

**Конфигурация:**

```json
{
  "transport": "http2",
  "host": "kws2.web.telegram.org",
  "port": 443,
  "path": "/api",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
  "enable_compression": true
}
```

**Преимущества:**
- Маскировка под обычный HTTPS
- Multiplexing нескольких потоков
- HPACK сжатие заголовков

---

### 1.3 QUIC/HTTP/3 Transport

```python
from proxy.quic_transport import QuicTransport, create_quic_transport

# Автоматический выбор QUIC или HTTP/2 fallback
transport = await create_quic_transport(
    host="kws2.web.telegram.org",
    port=443,
    use_quic=True,
    fallback_to_http2=True
)

# Проверка поддержки QUIC
from proxy.quic_transport import check_quic_support
support = check_quic_support()
print(f"QUIC available: {support['quic_capable']}")
```

**Установка зависимостей:**
```bash
pip install aioquic
```

**Преимущества:**
- 0-RTT handshakes (быстрое подключение)
- Обход блокировок по TCP fingerprinting
- Улучшенная производительность на lossy сетях

---

### 1.4 Meek Transport (Domain Fronting)

```python
from proxy.meek_transport import MeekTransport, create_meek_transport

# Создание meek транспорта через CDN
transport = await create_meek_transport(
    bridge_host="your-bridge-server.com",
    bridge_port=443,
    use_cdn="cloudflare"  # или google, amazon, microsoft
)

# Отправка данных
await transport.send(b"telegram data")
data = await transport.recv()
```

**Настройка CDN:**

```python
# Выбор CDN провайдера
cdn_options = {
    "cloudflare": [
        "www.cloudflare.com",
        "cdn.cloudflare.com"
    ],
    "google": [
        "www.google.com",
        "www.gstatic.com"
    ],
    "amazon": [
        "www.amazon.com",
        "cloudfront.net"
    ]
}
```

**Преимущества:**
- Трафик выглядит как обращение к CDN
- Обход IP-based блокировок
- Обход DPI анализа

---

## 2. UDP Relay для звонков

### 2.1 Включение UDP поддержки

```python
from proxy.socks5_udp import UdpRelay

# Создание UDP relay
udp_relay = UdpRelay(host='127.0.0.1', port=1080)
bind_addr = await udp_relay.start()

print(f"UDP relay listening on {bind_addr}")
```

### 2.2 Настройка Telegram для звонков

1. Откройте настройки Telegram
2. Перейдите в **Advanced** → **Connection Type**
3. Выберите **Custom Proxy**
4. Включите **Use UDP for calls**
5. Введите SOCKS5 proxy: `127.0.0.1:1080`

---

## 3. Автоматическая ротация ключей

### 3.1 Настройка KeyRotator

```python
from proxy.crypto import KeyRotator, EncryptionType

# Создание ротатора
rotator = KeyRotator(
    algorithm=EncryptionType.AES_256_GCM,
    rotation_interval=300.0,  # 5 минут
    message_limit=10000,       # или 10000 сообщений
    transition_period=30.0     # 30 секунд overlap
)

# Шифрование
encrypted, key_index = await rotator.encrypt(b"secret data")

# Расшифровка
decrypted = await rotator.decrypt(encrypted, key_index)

# Информация о ключах
info = rotator.get_key_info()
print(f"Current key index: {info['current_index']}")
print(f"Rotation in: {info['time_until_rotation']:.0f}s")
```

### 3.2 Интеграция с прокси

```python
# В tg_ws_proxy.py
encryption_config = {
    'enabled': True,
    'algorithm': 'aes-256-gcm',
    'key_rotation': {
        'enabled': True,
        'interval_seconds': 300,
        'message_limit': 10000
    }
}

run_proxy_server(
    port=1080,
    encryption_config=encryption_config
)
```

---

## 4. Мультиплексирование соединений

### 4.1 Использование MuxTransport

```python
from proxy.mux_transport import create_muxed_connection, MuxConnectionPool

# Создание мультиплексированного соединения
mux = await create_muxed_connection(
    host="kws2.web.telegram.org",
    port=443,
    max_streams=100
)

# Создание пула соединений
pool = await create_mux_pool(
    host="kws2.web.telegram.org",
    port=443,
    max_connections=4,
    max_streams_per_conn=50
)

# Получение транспорта из пула
transport = await pool.get_transport()
await transport.send(b"data")
```

---

## 5. Комплексная настройка

### 5.1 Конфигурация для строгих сетей

```json
{
  "proxy": {
    "port": 1080,
    "host": "127.0.0.1"
  },
  "transport": {
    "primary": "quic",
    "fallback": ["http2", "websocket"],
    "quic": {
      "enabled": true,
      "timeout": 10.0
    },
    "http2": {
      "enabled": true,
      "user_agent": "Mozilla/5.0",
      "path": "/api"
    },
    "meek": {
      "enabled": true,
      "cdn": "cloudflare",
      "bridge_host": "bridge.example.com"
    }
  },
  "encryption": {
    "algorithm": "aes-256-gcm",
    "key_rotation": {
      "enabled": true,
      "interval": 300,
      "message_limit": 10000
    }
  },
  "udp_relay": {
    "enabled": true,
    "port": 1080
  },
  "multiplexing": {
    "enabled": true,
    "max_connections": 4,
    "max_streams": 100
  }
}
```

### 5.2 Запуск с полной конфигурацией

```python
from proxy.tg_ws_proxy import run_proxy_server

config = {
    'port': 1080,
    'dc_ip': {2: "149.154.167.220"},
    
    # Транспорт
    'transport_config': {
        'use_quic': True,
        'use_http2': True,
        'use_meek': True,
        'meek_cdn': 'cloudflare'
    },
    
    # Шифрование
    'encryption_config': {
        'algorithm': 'aes-256-gcm',
        'key_rotation': True,
        'rotation_interval': 300
    },
    
    # UDP для звонков
    'enable_udp': True,
    
    # Мультиплексирование
    'enable_muxing': True,
    'mux_max_connections': 4
}

run_proxy_server(**config)
```

---

## 6. Диагностика и мониторинг

### 6.1 Проверка доступности транспортов

```python
from proxy.quic_transport import check_quic_support
from proxy.meek_transport import check_meek_availability

# QUIC поддержка
quic_status = check_quic_support()
print(f"QUIC: {quic_status['recommendation']}")

# Meek CDN доступность
meek_status = check_meek_availability()
for domain, status in meek_status.items():
    print(f"{domain}: {'✅' if status['available'] else '❌'}")
```

### 6.2 Статистика транспортов

```python
# HTTP/2 статистика
h2_stats = transport.get_stats()
print(f"HTTP/2 frames: {h2_stats['frames_sent']}")

# QUIC статистика
quic_stats = transport.get_stats()
print(f"QUIC RTT: {quic_stats['rtt_ms']:.1f}ms")

# Meek статистика
meek_stats = transport.get_stats()
print(f"Meek overhead: {meek_stats['bytes_overhead']} bytes")

# Mux статистика
mux_stats = pool.get_stats()
print(f"Mux connections: {mux_stats['pool_size']}")
```

---

## 7. Решение проблем

### Проблема: QUIC не подключается

**Решение:**
1. Проверьте поддержку: `check_quic_support()`
2. Установите aioquic: `pip install aioquic`
3. Проверьте UDP connectivity
4. Используйте HTTP/2 fallback

### Проблема: Meek слишком медленный

**Решение:**
1. Выберите другой CDN: `use_cdn="google"` вместо `"cloudflare"`
2. Уменьшите `poll_interval` в конфигурации
3. Увеличьте `max_poll_size`
4. Используйте прямой транспорт если возможен

### Проблема: UDP звонки не работают

**Решение:**
1. Проверьте, что UDP relay запущен
2. Включите UDP в настройках Telegram
3. Проверьте firewall правила
4. Используйте UDP-over-TCP fallback

---

## 8. Производительность

### Сравнение транспортов

| Транспорт | Latency | Throughput | Overhead | CPU |
|-----------|---------|------------|----------|-----|
| WebSocket | 20ms | 50 MB/s | 2% | Low |
| HTTP/2 | 25ms | 40 MB/s | 5% | Medium |
| QUIC | 15ms | 60 MB/s | 3% | Medium |
| Meek | 100ms | 5 MB/s | 30% | High |
| MTProto | 20ms | 50 MB/s | 2% | Low |

### Рекомендации по оптимизации

1. **Используйте QUIC** для мобильных сетей
2. **Включите muxing** для множества подключений
3. **Настройте key rotation** для безопасности
4. **Используйте UDP relay** для звонков
5. **Meek только при необходимости** (медленнее)

---

**Версия:** v2.58.0
**Обновлено:** 23.03.2026
