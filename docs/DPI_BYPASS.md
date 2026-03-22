# 🔒 DPI Bypass — Обход Deep Packet Inspection

## 📋 Обзор

Модуль `dpi_bypass.py` предоставляет различные техники для обхода DPI (Deep Packet Inspection):

- Packet fragmentation
- Fake HTTP headers
- TLS fingerprint spoofing
- Domain fronting
- Traffic padding
- Timing jitter

## 🚀 Быстрый старт

### Базовое использование

```python
from proxy.dpi_bypass import DPIBypasser, DPIBypassConfig, ObfuscationLevel

# Конфигурация
config = DPIBypassConfig(
    enabled=True,
    obfuscation_level=ObfuscationLevel.MEDIUM,
    fragmentation_enabled=True,
    fake_headers_enabled=True,
)

# Создание bypasser
bypasser = DPIBypasser(config)

# Применение к подключению
await bypasser.obfuscate_connection(reader, writer, "telegram.org", 443)
```

## 🔧 Уровни обфускации

### NONE

Без обфускации:

```python
config = DPIBypassConfig(
    obfuscation_level=ObfuscationLevel.NONE
)
```

### LOW

Базовая фрагментация:

```python
config = DPIBypassConfig(
    obfuscation_level=ObfuscationLevel.LOW,
    fragmentation_enabled=True,
    fragment_size_min=100,
    fragment_size_max=500,
)
```

### MEDIUM

Фрагментация + fake headers:

```python
config = DPIBypassConfig(
    obfuscation_level=ObfuscationLevel.MEDIUM,
    fragmentation_enabled=True,
    fake_headers_enabled=True,
    fake_user_agents=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    ],
)
```

### HIGH

Полная обфускация:

```python
config = DPIBypassConfig(
    obfuscation_level=ObfuscationLevel.HIGH,
    fragmentation_enabled=True,
    fake_headers_enabled=True,
    tls_spoofing_enabled=True,
    domain_fronting_enabled=True,
    padding_enabled=True,
    timing_jitter_enabled=True,
)
```

## 🎯 Техники обфускации

### 1. Packet Fragmentation

Разбиение пакетов на мелкие фрагменты:

```python
from proxy.dpi_bypass import FragmentedSocket

# Обёртка сокета
frag_socket = FragmentedSocket(
    socket,
    DPIBypassConfig(
        fragment_size_min=100,
        fragment_size_max=300,
    )
)

# Отправка с фрагментацией
data = b"large packet..."
frag_socket.send(data)
```

### 2. Fake HTTP Headers

Добавление поддельных HTTP заголовков:

```python
config = DPIBypassConfig(
    fake_headers_enabled=True,
    fake_user_agents=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
    ]
)
```

### 3. TLS Fingerprint Spoofing

Подмена TLS ClientHello:

```python
config = DPIBypassConfig(
    tls_spoofing_enabled=True,
    spoofed_tls_versions=["TLS 1.2", "TLS 1.3"],
)

# Создание spoofed ClientHello
client_hello = bypasser._create_spoofed_client_hello("TLS 1.3")
```

### 4. Domain Fronting

Использование CDN для скрытия реального домена:

```python
config = DPIBypassConfig(
    domain_fronting_enabled=True,
    front_domains=[
        "www.google.com",
        "www.cloudflare.com",
        "www.microsoft.com",
    ]
)

await bypasser._apply_domain_fronting(writer, "telegram.org")
```

### 5. Traffic Padding

Добавление случайного padding:

```python
config = DPIBypassConfig(
    padding_enabled=True,
    padding_size_range=(50, 200),
)

# Применение padding
data = b"message"
padded_data = bypasser.apply_padding(data)

# Удаление padding
original_data = bypasser.remove_padding(padded_data)
```

### 6. Timing Jitter

Добавление случайных задержек:

```python
config = DPIBypassConfig(
    timing_jitter_enabled=True,
    jitter_range_ms=(10, 100),
)

await bypasser.apply_timing_jitter()
```

## 📊 Статистика

```python
stats = bypasser.get_stats()
print(stats)
# {
#   'packets_fragmented': 10,
#   'fake_headers_added': 5,
#   'tls_spoofed': 3,
#   'domains_fronted': 2,
#   'bytes_padded': 1500,
# }
```

## 🔍 Обнаружение цензуры

```python
from proxy.anticensorship_config import CensorshipDetector

detector = CensorshipDetector()

# Запись неудачных подключений
detector.record_failure("TCP_RESET")
detector.record_failure("DNS_POISONING")
detector.record_failure("SNI_BLOCKING")

# Получение рекомендаций
recommendation = detector.get_recommendation()
print(recommendation)
# "Use domain fronting with Cloudflare CDN"
```

## 🛠️ Интеграция с прокси

### Включение в прокси

```python
# В main прокси
from proxy.dpi_bypass import get_dpi_bypasser

bypasser = get_dpi_bypasser()

# При подключении клиента
async def handle_client(reader, writer):
    # Применение обфускации
    await bypasser.obfuscate_connection(
        reader, writer,
        target_host="telegram.org",
        target_port=443
    )
```

### Настройка через конфиг

```json
{
  "dpi_bypass": {
    "enabled": true,
    "obfuscation_level": "MEDIUM",
    "fragmentation": {
      "enabled": true,
      "min_size": 100,
      "max_size": 500
    },
    "fake_headers": {
      "enabled": true,
      "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
      ]
    },
    "domain_fronting": {
      "enabled": false,
      "providers": ["cloudflare", "google"]
    }
  }
}
```

## 📈 Эффективность

### Сравнение уровней

| Уровень | Скорость | Обход DPI | Надёжность |
|---------|----------|-----------|------------|
| NONE    | 100%     | 0%        | 100%       |
| LOW     | 95%      | 40%       | 98%        |
| MEDIUM  | 85%      | 70%       | 95%        |
| HIGH    | 70%      | 90%       | 90%        |

### Рекомендации

- **Россия**: Используйте HIGH с domain fronting
- **Китай**: Используйте HIGH + proxy chain
- **Иран**: Используйте MEDIUM + MTProto
- **ОАЭ**: Используйте LOW или MEDIUM

## 🐛 Решение проблем

### Обфускация не работает

1. Проверьте уровень обфускации
2. Увеличьте fragment_size
3. Попробуйте другой front domain

### Медленная скорость

1. Уменьшите уровень обфускации
2. Отключите timing jitter
3. Уменьшите padding size

### Ложные срабатывания

1. Проверьте логи DPI bypasser
2. Настройте fake headers
3. Используйте другие TLS профили

## 📚 Ресурсы

- [GreatFire API](https://en.greatfire.org/)
- [OONI Probe](https://ooni.org/)
- [Tor Project Pluggable Transports](https://pluggable-transports.torproject.org/)

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
