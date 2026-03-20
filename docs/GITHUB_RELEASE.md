## TG WS Proxy v1.3.0

Локальный SOCKS5-прокси для Telegram Desktop, который перенаправляет трафик через WebSocket-соединения.

### 📌 Изменения

- Обновлена версия приложения до 1.3.0
- Улучшена кроссплатформенная поддержка (Windows, Linux, macOS)
- Добавлены spec-файлы для сборки на всех платформах
- Обновлены зависимости и улучшена стабильность

### 📥 Установка

#### Windows
Скачайте `TgWsProxy.exe` и запустите. Приложение свернётся в системный трей.

#### Linux
```bash
pip install -r requirements.txt
python linux.py
```

#### macOS
```bash
pip install -r requirements.txt
python macos.py
```

### 🔨 Сборка из исходников

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

### 📖 Документация

Полная документация доступна в [README.md](https://github.com/Flowseal/tg-ws-proxy/blob/main/README.md)

### ⚠️ Антивирусы

Windows Defender может ложно определять приложение как угрозу. Это известная проблема PyInstaller. Добавьте приложение в исключения.

### 📄 Лицензия

MIT License

---

**Полный список изменений**: [CHANGELOG](https://github.com/Flowseal/tg-ws-proxy/blob/main/RELEASE_NOTES.md)
