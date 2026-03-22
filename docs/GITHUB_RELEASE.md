## TG WS Proxy v2.38.0

Локальный SOCKS5-прокси для Telegram Desktop, который перенаправляет трафик через WebSocket-соединения для ускорения загрузки файлов, сообщений и медиа.

### 📌 Изменения

#### Performance & Stability
- Zero-copy буферизация WebSocket для снижения CPU нагрузки
- Batch отправка WebSocket фреймов (до 30% быстрее)
- Улучшена обработка ошибок WebSocket с timeout защитой
- Memory profiling и leak detection (tracemalloc + weakref)
- Graceful shutdown с корректным завершением соединений
- Автоматический выбор DC по latency в реальном времени

#### Networking
- DNS кэширование с TTL (5 минут)
- Crash watchdog с авто-рестартом asyncio loop
- WebSocket health checks с PING/PONG
- Connection pooling с динамической оптимизацией

#### Security & Monitoring
- Rate limiting для защиты от злоупотреблений
- Encryption support (AES-GCM, ChaCha20, MTProto IGE)
- Веб-панель управления с live статистикой
- Diagnostic tools для проверки подключений

#### Mobile
- Android VpnService с нативным TUN-интерфейсом
- Quick Settings Tile с живой статистикой
- PWA поддержка для установки на телефон

### 📥 Установка

#### Windows
Скачайте `TgWsProxy.exe` и запустите. Приложение свернётся в системный трей.

**Из исходников:**
```bash
pip install -r requirements.txt
python tray.py
```

#### Linux
```bash
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1
pip install -r requirements.txt
python linux.py
```

#### macOS
```bash
pip install -r requirements.txt
pip install rumps
python macos.py
```

#### Консольный режим (все платформы)
```bash
python proxy/tg_ws_proxy.py --port 1080 --dc-ip 2:149.154.167.220 -v
```

### 🔨 Сборка из исходников

```bash
# Установка зависимостей
pip install -r requirements-build.txt

# Windows
python build_desktop.py windows

# Linux
python build_desktop.py linux

# macOS
python build_desktop.py macos

# Все платформы
python build_desktop.py all
```

**Mobile (Android/iOS):**
```bash
python build_mobile.py android
python build_mobile.py ios
```

### 📖 Документация

- [README.md](https://github.com/Flowseal/tg-ws-proxy/blob/main/README.md) — основная документация
- [BUILD.md](https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/BUILD.md) — инструкции по сборке
- [INSTALL_MOBILE.md](https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/INSTALL_MOBILE.md) — установка на мобильные
- [RELEASE_NOTES.md](https://github.com/Flowseal/tg-ws-proxy/blob/main/docs/RELEASE_NOTES.md) — история версий

### 🌐 Веб-панель

Откройте `http://localhost:8080` для доступа к панели управления с:
- 📊 Статистика подключений и трафика
- 🌐 Задержки по дата-центрам
- 📜 Live логи в реальном времени
- ⚙️ Настройки и QR-коды для мобильных

### ⚠️ Антивирусы

Windows Defender может ошибочно помечать приложение как **Wacatac** (ложное срабатывание PyInstaller).

**Решение:**
1. Добавьте приложение в исключения Windows Defender
2. Скачайте версию win7 (без упаковки UPX)
3. Проверьте файл через [VirusTotal](https://www.virustotal.com/)

Это известная проблема PyInstaller — все исходники открыты для проверки.

### 📄 Лицензия

MIT License

---

**Полный список изменений**: [CHANGELOG](https://github.com/Flowseal/tg-ws-proxy/blob/main/RELEASE_NOTES.md)
