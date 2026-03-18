# TG WS Proxy v1.3.0

## 📋 Описание

Локальный SOCKS5-прокси для Telegram Desktop, который перенаправляет трафик через WebSocket-соединения к указанным серверам, помогая ускорить работу Telegram.

## 🔧 Изменения в версии 1.3.0

- Обновлена версия приложения
- Улучшена кроссплатформенная поддержка
- Добавлены spec-файлы для сборки на Linux и macOS
- Обновлены зависимости

## 📦 Готовые бинарники

### Windows
- **TgWsProxy.exe** — основная версия для Windows 10/11
- Размер: ~24 MB

### Linux
Соберите самостоятельно:
```bash
pip install -r requirements-build.txt -r requirements.txt
pyinstaller packaging/linux.spec
```

### macOS
Соберите самостоятельно:
```bash
pip install -r requirements-build.txt -r requirements.txt
pyinstaller packaging/macos.spec
```

## 🚀 Быстрый старт

### Windows
1. Скачайте `TgWsProxy.exe`
2. Запустите приложение
3. ПКМ по иконке в трее → «Открыть в Telegram»

### Linux/macOS
```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск
python linux.py    # Linux
python macos.py    # macOS
```

## 📊 Статистика сборки

| Платформа | Файл | Размер | Python |
|-----------|------|--------|--------|
| Windows | TgWsProxy.exe | ~24 MB | 3.13 |
| Linux | TgWsProxy | ~ | 3.8+ |
| macOS | TgWsProxy.app | ~ | 3.8+ |

## 🔨 Сборка из исходников

```bash
# Установка зависимостей
pip install -r requirements-build.txt -r requirements.txt

# Windows
pyinstaller packaging/windows.spec

# Linux
pyinstaller packaging/linux.spec

# macOS
pyinstaller packaging/macos.spec
```

## 📝 Конфигурация

Приложение хранит настройки в:
- **Windows**: `%APPDATA%/TgWsProxy`
- **macOS**: `~/Library/Application Support/TgWsProxy`
- **Linux**: `~/.config/TgWsProxy`

## ⚠️ Важно

**Антивирусы**: Windows Defender может ложно определять приложение как угрозу (Wacatac). Это известная проблема PyInstaller. Добавьте приложение в исключения.

## 📄 Лицензия

MIT License

## 🔗 Ссылки

- [Исходный код](https://github.com/Flowseal/tg-ws-proxy)
- [Баги и предложения](https://github.com/Flowseal/tg-ws-proxy/issues)
