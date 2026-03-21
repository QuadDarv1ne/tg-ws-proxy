> [!CAUTION]
> ### Реакция антивирусов
> Windows Defender может ошибочно помечать приложение как **Wacatac** (ложное срабатывание).
> Решение: добавьте приложение в исключения или скачайте версию win7.
> **Всегда проверяйте файлы через VirusTotal.**

# TG WS Proxy

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. Все права защищены.**

Локальный SOCKS5-прокси для Telegram Desktop, перенаправляющий трафик через WebSocket-соединения для ускорения загрузки файлов, сообщений и медиа.

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

**API:**
- `GET /api/stats` — статистика
- `GET /api/dc-stats` — статистика по DC
- `GET /api/qr` — QR-код для Telegram Mobile
- `GET /api/health` — проверка здоровья
- `POST /api/config` — обновление конфига

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
| [docs/RELEASE_NOTES.md](docs/RELEASE_NOTES.md) | История версий

---

## Лицензия

[MIT License](LICENSE)
