# 🔒 Безопасность TG WS Proxy

## Обзор

Комплексная система безопасности включает:
- E2E шифрование трафика
- Rate limiting для защиты от DDoS
- DPI bypass для обхода цензуры
- Circuit breaker для защиты от cascade failures

---

## 1. E2E Шифрование

### Поддерживаемые алгоритмы

| Алгоритм | Ключ | Nonce | Auth | Производительность |
|----------|------|-------|------|-------------------|
| **AES-256-GCM** | 256-bit | 96-bit | 128-bit | 100-500 MB/s (AES-NI) |
| **ChaCha20-Poly1305** | 256-bit | 96-bit | 128-bit | Отлично на мобильных |
| **XChaCha20-Poly1305** | 256-bit | 192-bit | 128-bit | Для долгих сессий |
| **AES-256-CTR** | 256-bit | 128-bit | Нет | Быстро, но без auth |
| **MTProto IGE** | 256-bit | 128-bit | Нет | Legacy совместимость |

### Использование

```python
from proxy.crypto import CryptoManager, EncryptionType

# Инициализация
crypto = CryptoManager(
    algorithm=EncryptionType.AES_256_GCM,
    key_size=32,
    encryption_key=b'your-32-byte-key-here'
)

# Шифрование
encrypted = crypto.encrypt(b"secret message")

# Расшифровка
decrypted = crypto.decrypt(encrypted)
```

### E2E Encryption Module

```python
from proxy.e2e_encryption import E2EEncryption

e2e = E2EEncryption()

# Handshake
public_key, nonce, timestamp = e2e.create_handshake_request()
session = e2e.complete_handshake(response)

# Шифрование
ciphertext, nonce_int = e2e.encrypt(session_id, plaintext)
plaintext = e2e.decrypt(session_id, ciphertext, nonce_int)
```

**Особенности:**
- X25519/P256 ECDH key exchange
- HKDF key derivation
- Replay attack protection
- Automatic key rotation (10000 messages)
- Session timeout (1 hour)

---

## 2. Rate Limiting

### Защита от DDoS и злоупотреблений

| Параметр | Значение | Описание |
|----------|----------|----------|
| Requests per second | 10 | На один IP |
| Requests per minute | 100 | На один IP |
| Max connections | 500 | Глобально |
| Connections per IP | 10 | На один IP |
| Ban threshold | 5 | Нарушений до бана |
| Ban duration | 300s | Длительность бана |

### DDoS Detection

```python
from proxy.rate_limiter import RateLimiter, RateLimitConfig

config = RateLimitConfig(
    ddos_detection_enabled=True,
    ddos_threshold_rps=50,  # RPS для детекции
    ddos_ban_duration=3600,  # 1 час бан
)

limiter = RateLimiter(config)
action, delay = limiter.check_rate_limit(ip)
```

### Connection Flood Protection

- Threshold: 50 connections per second
- Progressive ban: 10min → 20min → 40min
- Flood violations tracking

### Geographic Rate Limiting

- /24 subnet tracking
- Max 20 connections per subnet
- Prevents distributed attacks

### Prometheus Metrics

```
rate_limiter_active_connections
rate_limiter_unique_ips
rate_limiter_banned_ips
rate_limiter_total_violations
rate_limiter_ddos_attacks_total
rate_limiter_flood_attacks_total
rate_limiter_suspicious_ips
rate_limiter_subnets_active
rate_limiter_requests_per_minute
rate_limiter_flood_rate
```

---

## 3. DPI Bypass

### Техники обхода Deep Packet Inspection

#### 3.1 Packet Fragmentation

```python
from proxy.dpi_bypass import DPIBypassConfig, ObfuscationLevel

config = DPIBypassConfig(
    obfuscation_level=ObfuscationLevel.MEDIUM,
    fragmentation_enabled=True,
    fragment_size_min=100,
    fragment_size_max=500,
)
```

#### 3.2 Fake HTTP Headers

```python
config = DPIBypassConfig(
    fake_headers_enabled=True,
    fake_user_agents=[
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)",
    ],
)
```

#### 3.3 TLS Fingerprint Spoofing

- Подмена ClientHello
- Chrome/Firefox/Safari профили
- JA3 fingerprint spoofing

#### 3.4 Domain Fronting

```python
config = DPIBypassConfig(
    domain_fronting_enabled=True,
    front_domains=[
        "www.google.com",
        "www.cloudflare.com",
        "www.microsoft.com",
    ],
)
```

#### 3.5 Traffic Padding

- Random padding (50-200 bytes)
- Prevents traffic analysis

#### 3.6 Timing Jitter

- Random delays (10-100ms)
- Prevents timing analysis

---

## 4. Circuit Breaker

### Защита от cascade failures

```python
from proxy.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=30.0,
    half_open_max_calls=3
)

cb = CircuitBreaker('websocket', config)

@cb.protected
async def connect():
    # Protected function
    pass
```

### Типы circuit breakers:

1. **WebSocket** — защита WS подключений
2. **TCP** — защита TCP подключений
3. **DNS** — защита DNS resolver

### Состояния:

- **CLOSED** — нормальная работа
- **OPEN** — circuit tripped, rejecting calls
- **HALF-OPEN** — testing recovery

---

## 5. Security Best Practices

### Для пользователей:

1. ✅ Используйте E2E encryption
2. ✅ Включите rate limiting
3. ✅ Настройте whitelist IP
4. ✅ Регулярно обновляйте ключи
5. ✅ Мониторьте метрики безопасности

### Для разработчиков:

1. ✅ Проверяйте зависимости (pip-audit)
2. ✅ Используйте type hints
3. ✅ Пишите тесты на security функции
4. ✅ Логируйте security события
5. ✅ Следуйте security policy

---

## 6. Security Policy

### Vulnerability Reporting

- **Response time:** 48 hours
- **Fix time:** 7 days for High/Critical
- **Disclosure:** Coordinated

### Dependency Management

- **Critical vulnerabilities:** 24h
- **High vulnerabilities:** 7d
- **Medium vulnerabilities:** 30d

### Security Checklist

Перед релизом:
- [ ] pip-audit check passed
- [ ] No critical/high vulnerabilities
- [ ] Security tests passed
- [ ] Documentation updated

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
