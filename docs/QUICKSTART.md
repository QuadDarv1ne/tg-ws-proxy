# ⚡ Быстрый старт TG WS Proxy

## 🎯 Что это?

TG WS Proxy — локальный SOCKS5 прокси для ускорения Telegram Desktop через WebSocket подключения к серверам Telegram.

**Как это работает:**
```
Telegram Desktop → SOCKS5 (127.0.0.1:1080) → TG WS Proxy → WSS (kws*.web.telegram.org) → Telegram DC
```

---

## 📦 Установка

### Windows (готовый exe) — РЕКОМЕНДУЕТСЯ

1. Скачайте [TgWsProxy.exe](https://github.com/QuadDarv1ne/tg-ws-proxy/releases)
2. Запустите приложение
3. Иконка появится в трее
4. ПКМ → **Открыть в Telegram**

### Windows (из исходников)

```bash
git clone https://github.com/QuadDarv1ne/tg-ws-proxy.git
cd tg-ws-proxy
pip install -r requirements.txt
python tray.py
```

### Linux

```bash
sudo apt install python3-pip python3-tk libappindicator3-1
git clone https://github.com/QuadDarv1ne/tg-ws-proxy.git
cd tg-ws-proxy
pip3 install -r requirements.txt
python3 linux.py
```

### macOS

```bash
git clone https://github.com/QuadDarv1ne/tg-ws-proxy.git
cd tg-ws-proxy
pip3 install -r requirements.txt
pip3 install rumps
python3 macos.py
```

### Консольный режим (все платформы)

```bash
python proxy/tg_ws_proxy.py --port 1080 --dc-ip 2:149.154.167.220 -v
```

---

## ⚙️ Настройка Telegram

### Автоматическая настройка

1. Запустите прокси (tray.py, linux.py, macos.py, или TgWsProxy.exe)
2. ПКМ по иконке в трее
3. **Открыть в Telegram**
4. Telegram автоматически применит настройки

### Ручная настройка

#### Windows/macOS/Linux

1. Откройте **Telegram Desktop**
2. **Настройки** → **Продвинутые** → **Тип подключения**
3. **Использовать прокси** → **SOCKS5**
4. Введите:
   ```
   Хост: 127.0.0.1
   Порт: 1080
   Логин: (оставьте пустым)
   Пароль: (оставьте пустым)
   ```
5. ✅ **Сохранить**

#### Мобильные устройства

**Android:**
1. Установите **Proxy Droid** или **Postern**
2. Настройте SOCKS5: `IP_компьютера:1080`
3. Включите прокси
4. Telegram автоматически использует системный прокси

**iOS:**
1. Установите **Potatso** или **Shadowrocket**
2. Добавьте конфигурацию SOCKS5
3. Включите в системных настройках

---

## 🎮 Игровые консоли

### PS4/PS5

```bash
python setup_gaming_proxy.py --console PS5 --port 1080
```

**Настройка консоли:**
1. Settings → Network → Network Settings
2. Set Up Internet Connection → Custom
3. DNS: Manual (1.1.1.1 / 1.0.0.1)
4. Proxy Server: Use
   - Server: `<IP_КОМПЬЮТЕРА>`
   - Port: 1080

### Nintendo Switch

```bash
python setup_gaming_proxy.py --console SWITCH --port 1081
```

**Настройка консоли:**
1. System Settings → Internet → Internet Settings
2. Выберите сеть → Change Settings
3. Proxy Settings → On
   - Server: `<IP_КОМПЬЮТЕРА>`
   - Port: 1081

### Xbox

⚠️ Xbox не поддерживает прокси напрямую. Используйте:
- Настройку прокси на роутере
- PC как мост (Internet Connection Sharing)

---

## ✅ Проверка работы

1. Откройте Telegram Desktop
2. Отправьте сообщение в **Избранное**
3. Проверьте что сообщения отправляются
4. Попробуйте скачать файл

**Тест подключения:**
```bash
python setup_gaming_proxy.py --test --ip 192.168.1.100
```

---

## 🔧 Конфигурация

Файл: `config.default.json`

**Основные параметры:**
```json
{
  "server": {
    "host": "0.0.0.0",
    "socks_port": 1080,
    "max_connections": 500
  },
  "websocket": {
    "pool_size": 4,
    "pool_max_size": 8
  },
  "dns": {
    "enable_cache": true,
    "cache_ttl": 300.0
  }
}
```

**Переменные окружения:**
```bash
export TGWS_SERVER_SOCKS_PORT=1080
export TGWS_WEBSOCKET_POOL_SIZE=8
```

---

## 🛠️ Решение проблем

### Прокси не запускается

1. Проверьте что порт 1080 не занят:
   ```bash
   netstat -ano | findstr :1080
   ```
2. Запустите от имени администратора
3. Проверьте брандмауэр

### Telegram не подключается

1. Проверьте настройки прокси в Telegram
2. Убедитесь что прокси запущен
3. Перезапустите прокси (Ctrl+R)

### Антивирус блокирует

Windows Defender может ложно срабатывать:
1. Добавьте в исключения
2. Или используйте версию win7

### Медленная загрузка

1. Проверьте скорость интернета
2. Попробуйте другой DC в настройках прокси
3. Включите compression в конфиге

---

## 📚 Документация

- [Конфигурация](CONFIGURATION.md)
- [Безопасность](SECURITY_ADVANCED.md)
- [Тестирование](TESTING.md)
- [Игровые консоли](GAMING_PROXY.md)

---

**Версия:** v2.57.0  
**Последнее обновление:** 23.03.2026
