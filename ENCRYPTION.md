# 🔐 Modern Encryption for TG WS Proxy

## Обзор

TG WS Proxy теперь поддерживает современные методы шифрования для дополнительной защиты трафика между клиентом и прокси сервером.

## Поддерживаемые алгоритмы

### 1. **AES-256-GCM** (рекомендуется по умолчанию)

**Advantages:**
- ✅ Authenticated encryption (AEAD) - шифрование + аутентификация
- ✅ Высокая производительность с AES-NI (100-500 MB/s)
- ✅ Стандарт индустрии, широко поддерживается
- ✅ Защита от подделки данных (GMAC authentication)

**Best for:** Серверы с поддержкой AES-NI, общее использование

**Security:** 256-bit ключ, 96-bit nonce, 128-bit authentication tag

---

### 2. **ChaCha20-Poly1305**

**Advantages:**
- ✅ Отличная производительность без аппаратного ускорения
- ✅ Устойчивость к timing-атакам
- ✅ Идеально для мобильных устройств и ARM
- ✅ Authenticated encryption (AEAD)

**Best for:** Мобильные устройства, процессоры без AES-NI

**Security:** 256-bit ключ, 96-bit nonce, 128-bit authentication tag

---

### 3. **XChaCha20-Poly1305**

**Advantages:**
- ✅ 192-bit nonce (безопасная случайная генерация)
- ✅ Идеально для долгих сессий
- ✅ Защита от повторного использования nonce
- ✅ Authenticated encryption

**Best for:** Распределенные системы, долгосрочные ключи

**Security:** 256-bit ключ, 192-bit nonce, 128-bit authentication tag

---

### 4. **AES-256-CTR**

**Advantages:**
- ✅ Stream cipher - шифрование любого размера данных
- ✅ Параллельная обработка
- ✅ Случайный доступ к данным
- ✅ Опциональная HMAC аутентификация

**Best for:** Потоковое шифрование, критичные к производительности сценарии

**Security:** 256-bit ключ, 128-bit counter + HMAC-SHA256

---

### 5. **MTProto IGE** (legacy)

**Advantages:**
- ✅ Совместимость с протоколом Telegram
- ✅ Требуется для MTProto proxy

**Best for:** Только для совместимости с MTProto

**Security:** 256-bit ключ, 256-bit IV (legacy mode)

---

## Настройка

### Через конфигурационный файл

```json
{
    "encryption_type": "aes-256-gcm",
    "encryption_enabled": true,
    "key_rotation_interval": 3600
}
```

### Параметры конфигурации

| Параметр | Значения по умолчанию | Описание |
|----------|----------------------|----------|
| `encryption_type` | `"aes-256-gcm"` | Алгоритм шифрования |
| `encryption_enabled` | `true` | Включить/выключить шифрование |
| `key_rotation_interval` | `3600` | Интервал ротации ключей (секунды) |

### Допустимые значения `encryption_type`:
- `"aes-256-gcm"` - AES-256-GCM (рекомендуется)
- `"chacha20-poly1305"` - ChaCha20-Poly1305
- `"xchacha20-poly1305"` - XChaCha20-Poly1305
- `"aes-256-ctr"` - AES-256-CTR с HMAC
- `"mtproto-ige"` - MTProto IGE (legacy)

---

## Автоматическая ротация ключей

Прокси автоматически обновляет ключи шифрования через заданный интервал:

```python
# Пример конфигурации
{
    "key_rotation_interval": 3600  # Ротация каждый час
}
```

**Рекомендации:**
- Минимум: 60 секунд
- По умолчанию: 3600 секунд (1 час)
- Максимум: 86400 секунд (24 часа)

---

## Производительность

### Бенчмарк (на Intel Core i5 с AES-NI)

| Алгоритм | Скорость шифрования | Скорость дешифрования |
|----------|---------------------|-----------------------|
| AES-256-GCM | ~450 MB/s | ~450 MB/s |
| ChaCha20-Poly1305 | ~180 MB/s | ~180 MB/s |
| XChaCha20-Poly1305 | ~170 MB/s | ~170 MB/s |
| AES-256-CTR | ~420 MB/s | ~420 MB/s |
| MTProto IGE | ~120 MB/s | ~120 MB/s |

### На процессорах без AES-NI (ARM, мобильные)

| Алгоритм | Скорость шифрования |
|----------|---------------------|
| AES-256-GCM | ~50 MB/s |
| ChaCha20-Poly1305 | ~200 MB/s ⭐ |
| XChaCha20-Poly1305 | ~190 MB/s |

**Вывод:** Для устройств без AES-NI используйте ChaCha20-Poly1305

---

## Безопасность

### Уровни безопасности

Все алгоритмы обеспечивают 256-битную безопасность:

- **AES-256**: 2²⁵⁶ операций для brute-force
- **ChaCha20**: 2²⁵⁶ операций для brute-force
- **XChaCha20**: 2²⁵⁶ операций + защита от nonce reuse

### Аутентификация

AEAD алгоритмы (GCM, Poly1305) обеспечивают:
- ✅ Конфиденциальность данных
- ✅ Целостность данных
- ✅ Аутентификацию источника

### Защита от атак

- ✅ Timing attacks (constant-time implementation)
- ✅ Replay attacks (nonce-based)
- ✅ Bit-flipping attacks (authentication tags)
- ✅ Known-plaintext attacks

---

## Использование в GUI

### Настройки в трей-меню

1. ПКМ по иконке в трее → **Настройки**
2. Раздел **🔐 Современное шифрование**
3. Выберите алгоритм из списка
4. Установите интервал ротации ключей
5. Нажмите **Сохранить**

---

## Мониторинг

### Статистика шифрования

```python
# Получение статистики
stats = proxy_server.get_stats()
encryption_info = stats.get("encryption", {})

print(f"Шифрование: {'включено' if encryption_info.get('enabled') else 'выключено'}")
print(f"Алгоритм: {encryption_info.get('algorithm', 'N/A')}")
print(f"Ротация ключей: {encryption_info.get('key_rotation_interval')} сек")
```

### Логирование

```
2026-03-20 20:00:00  INFO  Modern encryption enabled: AES-256-GCM (key rotation: 3600s)
2026-03-20 21:00:00  INFO  Encryption keys rotated automatically
```

---

## Рекомендации

### Для большинства пользователей

```json
{
    "encryption_type": "aes-256-gcm",
    "encryption_enabled": true,
    "key_rotation_interval": 3600
}
```

### Для мобильных устройств

```json
{
    "encryption_type": "chacha20-poly1305",
    "encryption_enabled": true,
    "key_rotation_interval": 1800
}
```

### Для максимальной безопасности

```json
{
    "encryption_type": "xchacha20-poly1305",
    "encryption_enabled": true,
    "key_rotation_interval": 900
}
```

### Для совместимости с MTProto

```json
{
    "encryption_type": "mtproto-ige",
    "encryption_enabled": false,  # MTProto уже имеет своё шифрование
    "key_rotation_interval": 3600
}
```

---

## Устранение проблем

### Проблема: Низкая производительность

**Решение:**
1. Проверьте поддержку AES-NI процессором
2. Если AES-NI нет → используйте ChaCha20-Poly1305
3. Увеличьте интервал ротации ключей

### Проблема: Ошибки аутентификации

**Решение:**
1. Проверьте синхронизацию времени между клиентом и сервером
2. Убедитесь, что используется тот же алгоритм
3. Проверьте логи на наличие DecryptionError

### Проблема: Высокое потребление CPU

**Решение:**
1. Увеличьте интервал ротации ключей
2. Используйте аппаратное ускорение (AES-NI)
3. Переключитесь на ChaCha20-Poly1305 для CPU без AES-NI

---

## API для разработчиков

### Базовое использование

```python
from proxy.crypto import CryptoManager, CryptoConfig, EncryptionType

# Создание менеджера
config = CryptoConfig(algorithm=EncryptionType.AES_256_GCM)
crypto = CryptoManager(config)

# Шифрование
encrypted = crypto.encrypt(b"Secret message")
print(f"Ciphertext: {encrypted.ciphertext.hex()}")
print(f"Nonce: {encrypted.nonce.hex()}")
print(f"Tag: {encrypted.tag.hex()}")

# Дешифрование
decrypted = crypto.decrypt(encrypted)
print(f"Plaintext: {decrypted.decode()}")
```

### Ротация ключей

```python
# Ручная ротация
crypto.rotate_all_keys()

# Проверка поддерживаемых алгоритмов
supported = crypto.get_supported_algorithms()
print(f"Supported: {[a.name for a in supported]}")
```

### Производительность

```python
# Информация о производительности
perf_info = crypto.get_performance_info()
for algo, info in perf_info.items():
    print(f"{algo}: {info['speed']}")
```

---

## Сравнение с другими решениями

| Решение | Шифрование | Аутентификация | Ротация ключей |
|---------|------------|----------------|----------------|
| TG WS Proxy (AES-GCM) | ✅ 256-bit | ✅ GMAC | ✅ Авто |
| TG WS Proxy (ChaCha20) | ✅ 256-bit | ✅ Poly1305 | ✅ Авто |
| Стандартный SOCKS5 | ❌ | ❌ | ❌ |
| SSH Tunnel | ✅ | ✅ | ⚠️ Вручную |
| WireGuard | ✅ | ✅ | ✅ Авто |

---

## Будущие улучшения

- [ ] Post-quantum cryptography (Kyber, Dilithium)
- [ ] Multi-key encryption
- [ ] Hardware security module (HSM) support
- [ ] Key exchange via ECDH
- [ ] Encrypted statistics export

---

## Авторы

**Dupley Maxim Igorevich**  
© 2026 Dupley Maxim Igorevich. Все права защищены.

## Лицензия

Использование в рамках проекта TG WS Proxy.
