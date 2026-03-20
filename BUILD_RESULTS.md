# 🚀 TG WS Proxy - Руководство по сборке

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. Все права защищены.**

---

## ✅ Успешно собрано для Windows

**Результаты сборки:**
- `dist/TgWsProxy.exe` (33 МБ) - исполняемый файл
- `dist/TgWsProxy-Windows.zip` (32 МБ) - архив для распространения

---

## 📋 Поддерживаемые платформы

| Платформа | Статус | Файл сборки |
|-----------|--------|-------------|
| **Windows** | ✅ Готово | `TgWsProxy.exe` |
| **Linux** | 🟡 Требуется сборка | `TgWsProxy` |
| **macOS** | 🟡 Требуется сборка | `TgWsProxy.app` |
| **Android** | 🟡 Требуется сборка | `TgWsProxy-Android.apk` |
| **iOS** | 🟡 Требуется сборка | `TgWsProxy.xcarchive` |
| **PWA** | ✅ Готово | Веб-приложение |

---

## 🛠️ Быстрая сборка

### Windows (уже выполнено)
```bash
python build_desktop.py windows
```

### Linux
```bash
# Установка зависимостей
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1

# Сборка
python build_desktop.py linux
```

### macOS
```bash
# Установка зависимостей
pip install rumps

# Сборка
python build_desktop.py macos
```

### Android
```bash
# Требуется Node.js и Android Studio
cd mobile-app
npm install
npx cap add android
python ../build_mobile.py android
```

### iOS (только macOS)
```bash
# Требуется Node.js и Xcode
cd mobile-app
npm install
npx cap add ios
python ../build_mobile.py ios
```

---

## 📱 PWA (Progressive Web App)

Веб-приложение уже включено в сборку и доступно через встроенный веб-сервер.

**Использование:**
1. Запустите прокси с веб-панелью: `python run_web.py`
2. Откройте в браузере: `http://127.0.0.1:5000`
3. Установите как PWA:
   - **Chrome/Edge:** Нажмите на иконку установки в адресной строке
   - **Safari:** "Поделиться" → "На экран «Домой»"
   - **Firefox:** Нажмите "Установить" в адресной строке

---

## 📦 Структура проекта

```
tg-ws-proxy/
├── build_desktop.py          # Скрипт сборки для Desktop
├── build_mobile.py           # Скрипт сборки для Mobile
├── generate_pwa_icons.py     # Генерация иконок PWA
├── windows.py                # Windows приложение
├── linux.py                  # Linux приложение
├── macos.py                  # macOS приложение
├── proxy/
│   ├── web_dashboard.py      # Веб-панель с PWA
│   └── static/               # Статические файлы PWA
│       ├── icon-192.png
│       ├── icon-512.png
│       └── favicon.ico
├── mobile-app/
│   ├── www/                  # Веб-приложение для мобильных
│   │   ├── index.html
│   │   ├── manifest.json
│   │   └── sw.js
│   └── capacitor.config.json
├── packaging/
│   ├── windows.spec
│   ├── linux.spec
│   └── macos.spec
└── dist/                     # Результаты сборки
    ├── TgWsProxy.exe
    └── TgWsProxy-Windows.zip
```

---

## 🔧 Требования для сборки

### Общие
- Python 3.9+
- pip

### Windows
- Visual C++ Redistributable

### Linux
```bash
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1 build-essential
```

### macOS
```bash
xcode-select --install
pip install rumps
```

### Android
- Node.js 18+
- Android Studio с SDK
- JDK 17+

### iOS
- Node.js 18+
- Xcode 15+
- macOS 13+

---

## 🎯 Особенности PWA

Веб-приложение включает:

- ✅ **Автономная работа** - Service Worker кэширует ресурсы
- ✅ **Установка на устройство** - Добавление на домашний экран
- ✅ **Адаптивный дизайн** - Работа на всех размерах экрана
- ✅ **Тёмная тема** - Переключение светлая/тёмная
- ✅ **Статистика в реальном времени** - Автообновление каждые 5 сек
- ✅ **QR-код** - Быстрое подключение Telegram

---

## 📊 Статистика сборки

| Компонент | Размер | Примечание |
|-----------|--------|------------|
| Windows EXE | 33 МБ | Включает Python, Flask, GUI |
| Windows ZIP | 32 МБ | Сжатый архив |
| Linux Binary | ~30 МБ | Ожидается |
| macOS App | ~35 МБ | Ожидается |
| Android APK | ~25 МБ | Ожидается |

---

## 🐛 Устранение проблем

### PyInstaller ошибка
```bash
# Очистить кэш
rm -rf build dist __pycache__

# Переустановить зависимости
pip install -r requirements-build.txt --force-reinstall
```

### Android сборка
```bash
# Синхронизировать Capacitor
cd mobile-app
npx cap sync android

# Проверить ANDROID_HOME
echo $ANDROID_HOME
```

### iOS сборка
```bash
# Принять лицензию Xcode
sudo xcodebuild -license accept

# Открыть проект
open ios/App.xcworkspace
```

---

## 📝 Changelog сборки

**Версия 2.10.0**
- ✅ Добавлена поддержка PWA
- ✅ Добавлены иконки для всех платформ
- ✅ Обновлены spec-файлы для Flask
- ✅ Созданы скрипты build_desktop.py и build_mobile.py
- ✅ Создан mobile-app с Capacitor
- ✅ Добавлен Service Worker для автономной работы
- ✅ Создан BUILD.md с инструкциями

---

## 📞 Поддержка

- GitHub Issues: https://github.com/Flowseal/tg-ws-proxy/issues
- Документация: README.md, BUILD.md

---

**Собрано успешно! 🎉**
