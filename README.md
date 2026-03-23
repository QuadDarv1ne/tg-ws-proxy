> [!CAUTION]
> ### Реакция антивирусов
> Windows Defender может ошибочно помечать приложение как **Wacatac** (ложное срабатывание).
> Решение: добавьте приложение в исключения или скачайте версию win7.
> **Всегда проверяйте файлы через VirusTotal.**

# TG WS Proxy

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. Все права защищены.**

**Версия:** v2.59.0+ (Enhanced Transports)

Локальный SOCKS5-прокси для Telegram Desktop с **комплексным обходом блокировок**:
- 🚀 **7 транспортов**: WebSocket, HTTP/2, QUIC, Meek, Shadowsocks, Tuic, Reality
- 🔐 **Post-Quantum криптография**: Kyber-768 (ML-KEM)
- 🎭 **Obfsproxy**: obfs4, ScrambleSuit, Meek-lite
- ⚡ **Авто-выбор** лучшего транспорта по latency
- 📞 **UDP Relay** для звонков Telegram

---

## 📊 Сравнение с аналогами

| Функция | TG WS Proxy | Shadowsocks | V2Ray | AmneziaVPN |
|---------|-------------|-------------|-------|------------|
| SOCKS5 UDP | ✅ | ✅ | ✅ | ✅ |
| HTTP/2 | ✅ | ❌ | ✅ | ❌ |
| **QUIC/HTTP/3** | ✅ | ❌ | ✅ | ❌ |
| **Meek/Domain Fronting** | ✅ | ❌ | ⚠️ | ❌ |
| **Post-Quantum Crypto** | ✅ | ❌ | ❌ | ❌ |
| **Obfsproxy** | ✅ | ⚠️ | ✅ | ❌ |
| MTProto | ✅ | ❌ | ❌ | ✅ |
| Auto-select transport | ✅ | ❌ | ❌ | ❌ |

**TG WS Proxy — максимальный набор функций для обхода блокировок!**

## Как это работает

```
Telegram Desktop → SOCKS5 (127.0.0.1:1080) → TG WS Proxy → WSS (kws*.web.telegram.org) → Telegram DC
```

1. Локальный SOCKS5-прокси на `127.0.0.1:1080`
2. Перехват подключений к IP Telegram
3. Извлечение DC ID из MTProto init-пакета
4. WebSocket соединение через `kws{N}.web.telegram.org`
5. TCP fallback при недоступности WS

---

## 🚀 Быстрый старт

### Windows

**Готовый .exe (рекомендуется):**
1. Скачайте [TgWsProxy.exe](https://github.com/Flowseal/tg-ws-proxy/releases)
2. Запустите — приложение свернётся в трей
3. ПКМ по иконке → **Открыть в Telegram**

**Из исходников:**
```bash
pip install -r requirements.txt
python tray.py
```

### Linux

```bash
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1
pip install -r requirements.txt
python linux.py
```

### macOS

```bash
pip install -r requirements.txt
pip install rumps
python macos.py
```

### Консольный режим (все платформы)

```bash
python proxy/tg_ws_proxy.py --port 1080 --dc-ip 2:149.154.167.220 -v
```

### Расширенные транспорты (обход блокировок)

```bash
# Авто-выбор лучшего транспорта
python -m proxy.run_transport --transport auto --port 1080

# QUIC для обхода TCP блокировок
python -m proxy.run_transport --transport quic

# Meek через CDN (максимальная скрытность)
python -m proxy.run_transport --transport meek --meek-cdn google

# Shadowsocks 2022
python -m proxy.run_transport --transport shadowsocks \
    --ss-method chacha20-ietf-poly1305 \
    --ss-password "mypassword"

# Reality (TLS fingerprint obfuscation)
python -m proxy.run_transport --transport reality \
    --reality-pubkey "CAES..." \
    --reality-shortid "a1b2c3d4" \
    --reality-sni "www.microsoft.com"

# С обфускацией obfs4
python -m proxy.run_transport --transport quic --obfs obfs4
```

---

## 🔒 Post-Quantum Cryptography

Генерация квантово-устойчивых ключей:

```bash
# Проверка доступности
python -c "from proxy.post_quantum_crypto import check_pq_availability; print(check_pq_availability())"

# Генерация гибридных ключей (X25519 + Kyber-768)
python -c "from proxy.post_quantum_crypto import generate_pq_keys; pub, priv = generate_pq_keys(); print(f'Public: {pub.hex()[:64]}...')"
```

**Для production установки:**
```bash
pip install liboqs  # NIST-сертифицированная PQ библиотека
```

---

## ⚙️ Меню трея и горячие клавиши

**Меню:**
- **Открыть в Telegram** — авто-настройка прокси
- **Перезапустить прокси** — рестарт без выхода
- **Настройки** — GUI-редактор конфига
- **Статистика** — мониторинг подключений
- **Выход** — остановка прокси

**Горячие клавиши:**
- `Ctrl+R` — сохранить и перезапустить
- `Ctrl+Q` — отменить
- `Escape` — закрыть окно

---

## 🔧 Конфигурация

**Пути к конфигам:**
| Платформа | Путь |
|-----------|------|
| Windows | `%APPDATA%/TgWsProxy` |
| macOS | `~/Library/Application Support/TgWsProxy` |
| Linux | `~/.config/TgWsProxy` |

**Пример конфига:**
```json
{
  "port": 1080,
  "host": "127.0.0.1",
  "dc_ip": ["2:149.154.167.220", "4:149.154.167.220"],
  "verbose": false
}
```

**Параметры:**
- `port` — порт SOCKS5 (по умолчанию 1080)
- `dc_ip` — список DC для подключения
- `verbose` — подробное логирование

---

## 🌐 Веб-панель

Откройте `http://localhost:8080` для доступа к панели управления.

**Вкладки:**
- 📊 **Статистика** — подключения, трафик, CPU/memory
- 🌐 **DC Stats** — задержки по дата-центрам
- 📜 **Live Логи** — подключения в реальном времени
- ⚙️ **Настройки** — конфиг + QR-код для мобильных
- 📡 **Транспорты** — выбор и управление транспортами (NEW!)

**API:**
- `GET /api/stats` — статистика
- `GET /api/dc-stats` — статистика по DC
- `GET /api/qr` — QR-код для Telegram Mobile
- `GET /api/health` — проверка здоровья
- `POST /api/config` — обновление конфига
- `GET /api/transport/status` — статус транспорта (NEW!)
- `POST /api/transport/switch` — переключение транспорта (NEW!)
- `POST /api/pq/generate-keys` — генерация PQ ключей (NEW!)

---

## 📊 Транспорт: Сравнение

| Транспорт | Скорость | Обход DPI | Обход IP | Стабильность | Рекомендация |
|-----------|----------|-----------|----------|--------------|--------------|
| **WebSocket** | ⚡⚡⚡⚡⚡ | ⚠️ Частично | ❌ | ⭐⭐⭐⭐ | По умолчанию |
| **HTTP/2** | ⚡⚡⚡⚡ | ✅ Хорошо | ❌ | ⭐⭐⭐⭐⭐ | Строгие сети |
| **QUIC** | ⚡⚡⚡⚡⚡ | ✅ Отлично | ✅ | ⭐⭐⭐⭐⭐ | TCP блокировки |
| **Meek** | ⚡⚡⚡ | ✅✅ Макс | ✅✅ | ⭐⭐⭐ | Макс скрытность |
| **Shadowsocks** | ⚡⚡⚡⚡⚡ | ✅ Хорошо | ⚠️ | ⭐⭐⭐⭐ | Классика |
| **Tuic** | ⚡⚡⚡⚡⚡ | ✅ Отлично | ✅ | ⭐⭐⭐⭐ | QUIC-based |
| **Reality** | ⚡⚡⚡⚡ | ✅✅ Макс | ✅ | ⭐⭐⭐⭐⭐ | TLS fingerprint |

---

## 📱 Мобильные устройства

### PWA (рекомендуется)
1. Запустите `python run_web.py`
2. Откройте `http://ВАШ_IP:5000` на телефоне
3. Установите как PWA через меню браузера

### APK (Android)
Сборка через Android Studio:
```bash
cd mobile-app
npx cap sync android
cd android && gradlew assembleDebug
```

**Полная инструкция:** [docs/INSTALL_MOBILE.md](docs/INSTALL_MOBILE.md)

---

## 🔨 Сборка

**Desktop:**
```bash
pip install -r requirements-build.txt
python build_desktop.py [windows|linux|macos|all]
```

**Mobile:**
```bash
python build_mobile.py [android|ios]
```

**Полная инструкция:** [docs/BUILD.md](docs/BUILD.md)

---

## 📚 Документация

| Файл | Описание |
|------|----------|
| [docs/BUILD.md](docs/BUILD.md) | Сборка для всех платформ |
| [docs/INSTALL_MOBILE.md](docs/INSTALL_MOBILE.md) | Установка на телефон (PWA/APK) |
| [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) | История версий |
| [docs/ENHANCED_TRANSPORTS.md](docs/ENHANCED_TRANSPORTS.md) | **Расширенные транспорты** (NEW!) |
| [docs/ANTI_CENSORSHIP.md](docs/ANTI_CENSORSHIP.md) | **Обход блокировок** (NEW!) |

---

## 🧪 Тесты

```bash
# Все тесты
python -m pytest tests/ -v

# Тесты новых транспортов
python -m pytest tests/test_new_transports.py tests/test_enhanced_transports.py -v

# Тесты производительности
python -m pytest tests/test_enhanced_transports.py::TestPerformance -v
```

---

## 🤝 Contributing

Вклад в проект приветствуется! См. [CONTRIBUTING.md](CONTRIBUTING.md)

### Основные направления:

1. **Тесты** — улучшайте покрытие тестами
2. **Документация** — дополняйте документацию
3. **Безопасность** — сообщайте об уязвимостях
4. **Новые транспорты** — предлагайте новые протоколы

---

## 🔒 Security

### Vulnerability Reporting

- **Response time:** 48 hours
- **Fix time:** 7 days for High/Critical
- **Disclosure:** Coordinated

### Post-Quantum Security

Проект использует **Kyber-768 (ML-KEM)** — NIST стандартизированный пост-квантовый алгоритм.

Для production установки рекомендуется:
```bash
pip install liboqs  # Официальная OQS библиотека
```

---

## 📊 Статистика проекта

- **Строк кода:** ~15,000+
- **Модулей:** 50+
- **Тестов:** 1100+ passed
- **Транспортов:** 7
- **Алгоритмов шифрования:** 5+
- **Post-Quantum ready:** ✅

---

## Лицензия

[MIT License](LICENSE)

---

**Автор:** Dupley Maxim Igorevich  
**Версия:** v2.59.0+  
**Последнее обновление:** 23.03.2026
