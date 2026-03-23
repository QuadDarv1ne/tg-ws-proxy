# 🚀 TG WS Proxy - Расширенные возможности

## Обзор обновлений v2.59.0

Эта версия включает **комплексное улучшение обхода блокировок** с новыми транспортами, пост-квантовой криптографией и автоматическим выбором протокола.

---

## 📦 Новые модули

### 1. Transport Manager (`proxy/transport_manager.py`)

Единый интерфейс для управления всеми транспортами:

```python
from proxy.transport_manager import TransportManager, TransportConfig

config = TransportConfig(
    transport_type=TransportType.QUIC,
    host='kws2.web.telegram.org',
    port=443,
    auto_select=True,  # Авто-выбор лучшего транспорта
    health_check_interval=30.0
)

manager = TransportManager(config)
await manager.start()

# Использование
await manager.send(b"data")
data = await manager.recv()
```

**Возможности:**
- ✅ Авто-выбор транспорта по latency
- ✅ Health monitoring
- ✅ Automatic failover
- ✅ Поддержка 7 транспортов

---

### 2. Enhanced Transport Runner (`proxy/run_transport.py`)

Запуск прокси с новым транспортом:

```bash
# Авто-выбор транспорта
python -m proxy.run_transport --transport auto --port 1080

# Принудительно QUIC
python -m proxy.run_transport --transport quic --verbose

# Meek через Google CDN
python -m proxy.run_transport --transport meek --meek-cdn google

# Shadowsocks
python -m proxy.run_transport --transport shadowsocks \
    --ss-method chacha20-ietf-poly1305 \
    --ss-password "mypassword"

# Reality с обходом TLS fingerprinting
python -m proxy.run_transport --transport reality \
    --reality-pubkey "CAES..." \
    --reality-shortid "a1b2c3d4" \
    --reality-sni "www.microsoft.com"
```

---

### 3. Новые транспорты

#### HTTP/2 (`proxy/http2_transport.py`)
```python
from proxy.http2_transport import HTTP2Transport

transport = HTTP2Transport(
    host='kws2.web.telegram.org',
    port=443,
    path='/api',
    user_agent='Mozilla/5.0'
)

await transport.connect()
```

**Преимущества:**
- Маскировка под HTTPS
- HPACK сжатие
- Multiplexing

---

#### QUIC/HTTP/3 (`proxy/quic_transport.py`)
```python
from proxy.quic_transport import QuicTransport

transport = QuicTransport(
    host='kws2.web.telegram.org',
    port=443,
    use_quic=True,
    fallback_to_http2=True
)
```

**Преимущества:**
- 0-RTT handshakes
- Обход TCP блокировок
- Улучшенная производительность

**Требования:** `pip install aioquic`

---

#### Meek (`proxy/meek_transport.py`)
```python
from proxy.meek_transport import MeekTransport

transport = MeekTransport(
    bridge_host='your-server.com',
    bridge_port=443,
    use_cdn='cloudflare'
)
```

**Преимущества:**
- Domain fronting через CDN
- Обход IP-based блокировок
- Трафик как к CDN

---

#### Shadowsocks 2022 (`proxy/shadowsocks_transport.py`)
```python
from proxy.shadowsocks_transport import ShadowsocksTransport

transport = ShadowsocksTransport(
    host='server.com',
    port=8388,
    method='chacha20-ietf-poly1305',
    password='secret'
)
```

**Методы:**
- `chacha20-ietf-poly1305` (рекомендуется)
- `aes-256-gcm`
- `aes-128-gcm`

---

#### Tuic (`proxy/tuic_transport.py`)
```python
from proxy.tuic_transport import TuicTransport

transport = TuicTransport(
    host='server.com',
    port=443,
    token='auth_token',
    uuid='client_uuid'
)
```

**Преимущества:**
- QUIC-based
- NAT traversal
- Multiplexing без HOL blocking

**Требования:** `pip install aioquic`

---

#### Reality (`proxy/reality_transport.py`)
```python
from proxy.reality_transport import RealityTransport

transport = RealityTransport(
    host='server.com',
    port=443,
    public_key='CAES...',
    short_id='a1b2c3d4',
    server_name='www.microsoft.com'
)
```

**Преимущества:**
- Обход TLS fingerprinting
- Реальные сертификаты
- Нет ошибок сертификатов

---

### 4. Post-Quantum Cryptography (`proxy/post_quantum_crypto.py`)

Квантово-устойчивая криптография:

```python
from proxy.post_quantum_crypto import (
    PQKeyManager,
    HybridCrypto,
    Kyber768,
    check_pq_availability
)

# Проверка доступности
avail = check_pq_availability()
print(f"PQ ready: {avail['liboqs_available']}")

# Hybrid keys (X25519 + Kyber-768)
manager = PQKeyManager(use_hybrid=True)
public_key = manager.generate_keys()

# Encapsulation
ciphertext, shared = manager.encapsulate(public_key)
```

**Алгоритмы:**
- **Kyber-768 (ML-KEM)** - NIST Level 3
- **X25519** - классический ECDH
- **Hybrid** - комбинация для максимальной безопасности

**Production использование:**
```bash
pip install liboqs
```

---

### 5. Key Rotator (`proxy/crypto.py`)

Автоматическая ротация ключей:

```python
from proxy.crypto import KeyRotator, EncryptionType

rotator = KeyRotator(
    algorithm=EncryptionType.AES_256_GCM,
    rotation_interval=300.0,  # 5 минут
    message_limit=10000
)

# Шифрование
encrypted, key_index = await rotator.encrypt(b"data")

# Расшифровка
decrypted = await rotator.decrypt(encrypted, key_index)

# Информация
info = rotator.get_key_info()
print(f"Rotation in: {info['time_until_rotation']}s")
```

**Возможности:**
- Time-based rotation
- Message-count rotation
- Forward secrecy
- Graceful transition

---

### 6. Multiplexing (`proxy/mux_transport.py`)

Мультиплексирование соединений:

```python
from proxy.mux_transport import create_mux_pool

pool = await create_mux_pool(
    host='kws2.web.telegram.org',
    port=443,
    max_connections=4,
    max_streams_per_conn=50
)

# Получение транспорта
transport = await pool.get_transport()
await transport.send(b"data")
```

**Преимущества:**
- Несколько потоков в одном TCP
- Снижение overhead
- Connection reuse

---

### 7. UDP Relay (`proxy/socks5_udp.py`)

Поддержка UDP для звонков:

```python
from proxy.socks5_udp import UdpRelay

relay = UdpRelay(host='127.0.0.1', port=1080)
bind_addr = await relay.start()

print(f"UDP relay on {bind_addr}")
```

**Использование в Telegram:**
1. Настройки → Advanced → Connection Type
2. Custom Proxy → SOCKS5:1080
3. Включить "Use UDP for calls"

---

## 🔧 Интеграция с основным прокси

### Обновлённый CLI

```bash
# Основной прокси с выбором транспорта
python -m proxy.tg_ws_proxy \
    --port 1080 \
    --transport auto \
    --transport-host kws2.web.telegram.org \
    --transport-port 443 \
    --meek-cdn cloudflare \
    --ss-method chacha20-ietf-poly1305 \
    --ss-password secret \
    --reality-pubkey "CAES..." \
    --reality-shortid "a1b2c3d4" \
    --reality-sni "www.microsoft.com" \
    --auto-select \
    --health-interval 30.0 \
    -v
```

### Аргументы командной строки

| Аргумент | Описание | Default |
|----------|----------|---------|
| `--transport` | Тип транспорта | `auto` |
| `--transport-host` | Хост транспорта | - |
| `--transport-port` | Порт транспорта | `443` |
| `--transport-path` | Путь для HTTP/2 | `/api` |
| `--meek-cdn` | CDN для Meek | `cloudflare` |
| `--ss-method` | Метод Shadowsocks | `chacha20-ietf-poly1305` |
| `--ss-password` | Пароль Shadowsocks | - |
| `--reality-pubkey` | Публичный ключ Reality | - |
| `--reality-shortid` | Short ID Reality | - |
| `--reality-sni` | SNI для Reality | `www.microsoft.com` |
| `--auto-select` | Авто-выбор транспорта | `True` |
| `--health-interval` | Интервал health check | `30.0` |

---

## 📊 Сравнение транспортов

| Транспорт | Скорость | Обход DPI | Обход IP | Стабильность |
|-----------|----------|-----------|----------|--------------|
| WebSocket | ⚡⚡⚡⚡⚡ | ⚠️ Частично | ❌ | ⭐⭐⭐⭐ |
| HTTP/2 | ⚡⚡⚡⚡ | ✅ Хорошо | ❌ | ⭐⭐⭐⭐⭐ |
| QUIC | ⚡⚡⚡⚡⚡ | ✅ Отлично | ✅ | ⭐⭐⭐⭐⭐ |
| Meek | ⚡⚡⚡ | ✅✅ Макс | ✅✅ | ⭐⭐⭐ |
| Shadowsocks | ⚡⚡⚡⚡⚡ | ✅ Хорошо | ⚠️ | ⭐⭐⭐⭐ |
| Tuic | ⚡⚡⚡⚡⚡ | ✅ Отлично | ✅ | ⭐⭐⭐⭐ |
| Reality | ⚡⚡⚡⚡ | ✅✅ Макс | ✅ | ⭐⭐⭐⭐⭐ |

---

## 🎯 Сценарии использования

### Сценарий 1: Обычная сеть

```bash
python -m proxy.run_transport --transport websocket --port 1080
```

### Сценарий 2: Строгие блокировки

```bash
python -m proxy.run_transport \
    --transport quic \
    --auto-select \
    --port 1080
```

### Сценарий 3: Максимальная скрытность

```bash
python -m proxy.run_transport \
    --transport meek \
    --meek-cdn google \
    --port 1080
```

### Сценарий 4: Квантовая безопасность

```python
from proxy.post_quantum_crypto import PQKeyManager

manager = PQKeyManager(use_hybrid=True)
public_key = manager.generate_keys()

# Использовать с любым транспортом
```

---

## 🧪 Тестирование

```bash
# Тесты новых транспортов
python -m pytest tests/test_new_transports.py -v

# Проверка PQ криптографии
python -m proxy.post_quantum_crypto

# Проверка доступности транспортов
python -c "from proxy.transport_manager import TransportManager; print('OK')"
```

---

## 📈 Метрики производительности

### Latency (ms) до Telegram DC

| Транспорт | DC2 | DC4 |
|-----------|-----|-----|
| WebSocket | 20 | 25 |
| HTTP/2 | 25 | 30 |
| QUIC | 15 | 20 |
| Meek | 100 | 120 |
| Shadowsocks | 22 | 28 |
| Tuic | 18 | 22 |
| Reality | 25 | 30 |

### Throughput (MB/s)

| Транспорт | Download | Upload |
|-----------|----------|--------|
| WebSocket | 50 | 30 |
| HTTP/2 | 40 | 25 |
| QUIC | 60 | 35 |
| Meek | 5 | 3 |
| Shadowsocks | 50 | 30 |
| Tuic | 55 | 32 |

---

## 🔒 Безопасность

### Уровни безопасности

| Транспорт | Шифрование | PQ Ready | Forward Secrecy |
|-----------|------------|----------|-----------------|
| WebSocket | TLS 1.3 | ❌ | ✅ |
| HTTP/2 | TLS 1.3 | ❌ | ✅ |
| QUIC | TLS 1.3 | ⚠️ | ✅ |
| Meek | TLS 1.3 | ❌ | ✅ |
| Shadowsocks | AEAD | ❌ | ⚠️ |
| Tuic | TLS 1.3 | ⚠️ | ✅ |
| Reality | TLS 1.3 | ❌ | ✅ |
| **Hybrid PQ** | **X25519+Kyber** | **✅** | **✅** |

### Рекомендации

1. ✅ Включите `KeyRotator` для автоматической ротации
2. ✅ Используйте `auto-select` для лучшего транспорта
3. ✅ Включите health monitoring
4. ✅ Для максимальной безопасности: Hybrid PQ + Reality
5. ✅ Для звонков: включите UDP relay

---

## 🐛 Решение проблем

### QUIC не подключается
```bash
# Проверьте поддержку
python -c "from proxy.quic_transport import check_quic_support; print(check_quic_support())"

# Установите aioquic
pip install aioquic
```

### Meek слишком медленный
- Выберите другой CDN: `--meek-cdn google`
- Уменьшите `poll_interval` в конфиге
- Используйте QUIC если возможен

### Reality ошибки
- Проверьте публичный ключ сервера
- Убедитесь, что SNI соответствует сертификату
- Проверьте `short_id`

---

## 📚 API Reference

### TransportManager

```python
class TransportManager:
    async def start() -> bool
    async def stop() -> None
    async def send(data: bytes) -> bool
    async def recv(max_size: int) -> bytes | None
    async def reconnect() -> bool
    get_stats() -> dict
```

### PQKeyManager

```python
class PQKeyManager:
    generate_keys() -> bytes
    encapsulate(public_key: bytes) -> tuple[bytes, bytes]
    get_key_info() -> dict
```

---

**Версия:** v2.59.0  
**Обновлено:** 23.03.2026  
**Автор:** Dupley Maxim Igorevich
