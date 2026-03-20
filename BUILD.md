# TG WS Proxy - Build Instructions

**Author:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. All rights reserved.**

This guide explains how to build TG WS Proxy for all supported platforms.

## Prerequisites

### All Platforms
- Python 3.9+
- pip package manager

### Windows
- Windows 10/11
- Visual C++ Redistributable (for some dependencies)

### Linux
- GCC and build essentials
- Python development headers
- For GTK tray: `libappindicator3-1`, `python3-pil`

```bash
# Ubuntu/Debian
sudo apt install python3-pil python3-pil.imagetk libappindicator3-1 build-essential

# Fedora/RHEL
sudo dnf install python3-pillow python3-pillow-tk libappindicator-gtk3
```

### macOS
- Xcode Command Line Tools
- For native menu bar: `pip install rumps`

```bash
xcode-select --install
pip install rumps
```

### Android
- Node.js 18+
- Android Studio with SDK
- JDK 17+

### iOS (macOS only)
- Node.js 18+
- Xcode 15+
- macOS 13+

---

## Quick Build

### Desktop (Current OS)
```bash
# Install build dependencies
pip install -r requirements-build.txt

# Build for current platform
python build_desktop.py
```

### Mobile
```bash
# Build Android APK
python build_mobile.py android

# Build iOS app (macOS only)
python build_mobile.py ios
```

---

## Detailed Build Instructions

### Windows Desktop

1. **Install dependencies:**
   ```bash
   pip install -r requirements-build.txt
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

2. **Build:**
   ```bash
   python build_desktop.py windows
   ```

3. **Output:** `dist/TgWsProxy.exe` and `dist/TgWsProxy-Windows.zip`

---

### Linux Desktop

1. **Install system dependencies:**
   ```bash
   sudo apt install python3-pil python3-pil.imagetk libappindicator3-1
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements-build.txt
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Build:**
   ```bash
   python build_desktop.py linux
   ```

4. **Output:** `dist/TgWsProxy` and `dist/TgWsProxy-Linux.tar.gz`

---

### macOS Desktop

1. **Install dependencies:**
   ```bash
   xcode-select --install
   pip install -r requirements-build.txt
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install rumps
   ```

2. **Build:**
   ```bash
   python build_desktop.py macos
   ```

3. **Output:** `dist/TgWsProxy.app` and `dist/TgWsProxy-macOS.tar.gz`

---

### Android Mobile App

1. **Install Node.js dependencies:**
   ```bash
   cd mobile-app
   npm install
   ```

2. **Add Android platform (first time only):**
   ```bash
   npx cap add android
   ```

3. **Build:**
   ```bash
   python build_mobile.py android
   ```

4. **For Release Build (with signing):**
   - Create a keystore:
     ```bash
     keytool -genkey -v -keystore tg-ws-proxy.keystore -alias tg-ws-proxy -keyalg RSA -keysize 2048 -validity 10000
     ```
   - Edit `mobile-app/android/gradle.properties` with keystore details
   - Run: `cd mobile-app/android && ./gradlew assembleRelease`

5. **Output:** `dist/TgWsProxy-Android.apk`

---

### iOS Mobile App

**Note:** iOS build requires macOS and Xcode.

1. **Install Node.js dependencies:**
   ```bash
   cd mobile-app
   npm install
   ```

2. **Add iOS platform (first time only):**
   ```bash
   npx cap add ios
   ```

3. **Build:**
   ```bash
   python build_mobile.py ios
   ```

4. **In Xcode:**
   - Select your development team
   - Choose "Product" → "Archive"
   - Export the .ipa file

5. **Output:** Xcode archive (`.xcarchive`)

---

## PWA (Progressive Web App)

The web dashboard includes PWA support. To use:

1. **Start the proxy with web dashboard:**
   ```bash
   python run_web.py
   ```

2. **Open in browser:** `http://127.0.0.1:5000`

3. **Install as PWA:**
   - Chrome/Edge: Click the install icon in the address bar
   - Safari: Tap "Share" → "Add to Home Screen"
   - Firefox: Click "Install" in the address bar

---

## Troubleshooting

### PyInstaller build fails
- Ensure all dependencies are installed: `pip install -r requirements-build.txt`
- Try cleaning build cache: `rm -rf build dist __pycache__`

### Android build fails
- Ensure `ANDROID_HOME` environment variable is set
- Check that Android SDK Build-Tools are installed
- Run `npx cap sync android` before building

### iOS build fails
- Ensure Xcode is installed and up to date
- Accept Xcode license: `sudo xcodebuild -license accept`
- Check that iOS deployment target is set correctly

### Module not found errors
- Install all dependencies: `pip install -r requirements.txt`
- For tray features: `pip install -r requirements-dev.txt`
- For macOS menu bar: `pip install rumps`

---

## Build Output Structure

```
dist/
├── TgWsProxy.exe              # Windows executable
├── TgWsProxy-Windows.zip      # Windows distribution
├── TgWsProxy                  # Linux binary
├── TgWsProxy-Linux.tar.gz     # Linux distribution
├── TgWsProxy.app              # macOS application
├── TgWsProxy-macOS.tar.gz     # macOS distribution
├── TgWsProxy-Android.apk      # Android APK
└── TgWsProxy-iOS.xcarchive    # iOS archive (if built)
```

---

## Version Information

The version is defined in `pyproject.toml` and should be updated before each release:

```toml
[project]
version = "2.10.0"
```

Update the version in:
- `pyproject.toml`
- `mobile-app/package.json`
- `proxy/web_dashboard.py` (stats version)
