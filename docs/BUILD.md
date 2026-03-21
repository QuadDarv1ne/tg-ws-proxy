# TG WS Proxy — Сборка

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. Все права защищены.**

Краткое руководство по сборке для всех платформ.

---

## Требования

### Все платформы
- Python 3.9+
- pip

### Windows
- Windows 10/11

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

### iOS (только macOS)
- Node.js 18+
- Xcode 15+

---

## Быстрая сборка

### Desktop (текущая ОС)
```bash
pip install -r requirements-build.txt
python build_desktop.py
```

### Mobile
```bash
# Android
python build_mobile.py android

# iOS (macOS)
python build_mobile.py ios
```

---

## Подробная инструкция

### Windows Desktop

```bash
pip install -r requirements-build.txt -r requirements.txt -r requirements-dev.txt
python build_desktop.py windows
```

**Результат:** `dist/TgWsProxy.exe`, `dist/TgWsProxy-Windows.zip`

---

### Linux Desktop

```bash
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1
pip install -r requirements-build.txt -r requirements.txt -r requirements-dev.txt
python build_desktop.py linux
```

**Результат:** `dist/TgWsProxy`, `dist/TgWsProxy-Linux.tar.gz`

---

### macOS Desktop

```bash
xcode-select --install
pip install -r requirements-build.txt -r requirements.txt -r requirements-dev.txt rumps
python build_desktop.py macos
```

**Результат:** `dist/TgWsProxy.app`, `dist/TgWsProxy-macOS.tar.gz`

---

### Android APK

```bash
cd mobile-app
npm install
npx cap add android  # Только первый раз
npx cap sync android
python build_mobile.py android
```

**Результат:** `dist/TgWsProxy-Android.apk`

**Release-сборка (с подписью):**
```bash
# Создать ключ
keytool -genkey -v -keystore tg-ws-proxy.keystore -alias tg-ws-proxy -keyalg RSA -keysize 2048 -validity 10000

# Настроить mobile-app/android/gradle.properties
# Собрать
cd mobile-app/android && gradlew assembleRelease
```

---

### iOS (только macOS)

```bash
cd mobile-app
npm install
npx cap add ios  # Только первый раз
npx cap sync android
python build_mobile.py ios
```

**Далее в Xcode:**
1. Открыть `mobile-app/ios/App/App.xcworkspace`
2. Выбрать команду разработки
3. Product → Archive

**Результат:** `.xcarchive`

---

## PWA (Progressive Web App)

```bash
python run_web.py
```

Откройте `http://localhost:5000` и установите через браузер.

---

## Структура результатов сборки

```
dist/
├── TgWsProxy.exe              # Windows
├── TgWsProxy-Windows.zip
├── TgWsProxy                  # Linux
├── TgWsProxy-Linux.tar.gz
├── TgWsProxy.app              # macOS
├── TgWsProxy-macOS.tar.gz
├── TgWsProxy-Android.apk
└── TgWsProxy-iOS.xcarchive
```

---

## Устранение проблем

**PyInstaller не работает:**
```bash
pip install -r requirements-build.txt
rm -rf build dist __pycache__
```

**Android build fails:**
- Проверьте `ANDROID_HOME`
- `npx cap sync android`

**iOS build fails:**
```bash
sudo xcodebuild -license accept
```

---

## Версия

Обновляйте версию в:
- `pyproject.toml`
- `mobile-app/package.json`
- `proxy/web_dashboard.py`
