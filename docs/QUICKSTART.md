# ⚡ Быстрый старт TG WS Proxy

## 🎯 Что это?

TG WS Proxy — локальный SOCKS5 прокси для ускорения Telegram Desktop через WebSocket подключения к серверам Telegram.

## 📦 Установка

### Windows (готовый exe)

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

## ⚙️ Настройка Telegram

### Автоматическая

1. Запустите прокси
2. ПКМ по иконке → **Открыть в Telegram**

### Ручная

1. Telegram → Настройки → Продвинутые
2. Тип подключения → Использовать прокси
3. SOCKS5: `127.0.0.1:1080`
4. Сохранить

## 🎮 Игровые консоли

```bash
python setup_gaming_proxy.py --console PS5 --port 1080
```

См. [GAMING_PROXY.md](GAMING_PROXY.md)

## ✅ Проверка

1. Откройте Telegram
2. Отправьте сообщение
3. Проверьте загрузку файлов

## 📚 Документация

- [Настройка Telegram](TELEGRAM_SETUP.md)
- [Конфигурация](CONFIGURATION.md)
- [Тестирование](TESTING.md)

---

**Версия:** v2.57.0
