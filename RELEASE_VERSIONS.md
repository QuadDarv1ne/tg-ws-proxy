# 📦 TG WS Proxy - Готовые версии

**Версия:** v2.59.0  
**Дата сборки:** 23.03.2026  
**Статус:** ✅ Готово к использованию

---

## 🎯 Готовые версии

### Windows

**Файл:** `dist/TgWsProxy-Windows.zip` (32.3 MB)  
**Файл:** `dist/TgWsProxy.exe` (32.6 MB)

**Запуск:**
```bash
# 1. Распакуйте архив
TgWsProxy-Windows.zip

# 2. Запустите
TgWsProxy.exe

# 3. Или с параметрами
TgWsProxy.exe --transport auto --port 1080
```

**Трей версия:**
```bash
python tray.py
```

---

### Linux

**Сборка:**
```bash
# На Linux системе
python quick_build.py linux
```

**Результат:**
- `dist/TgWsProxy-Linux.tar.gz`
- `dist/TgWsProxy` (binary)

**Запуск:**
```bash
./TgWsProxy --transport quic --port 1080
```

---

### macOS

**Сборка:**
```bash
# На macOS системе
python quick_build.py macos
```

**Результат:**
- `dist/TgWsProxy-macOS.tar.gz`
- `dist/TgWsProxy.app`

**Запуск:**
```bash
open dist/TgWsProxy.app
```

---

### Мобильные версии

#### Android APK

**Сборка:**
```bash
cd mobile-app
npm install
npm run sync
cd android
gradlew assembleDebug
```

**Результат:**
- `mobile-app/android/app/build/outputs/apk/debug/app-debug.apk`

#### iOS IPA

**Сборка:**
```bash
cd mobile-app
npm run sync
cd ios
xcodebuild -workspace App.xcworkspace -scheme App -configuration Release archive
```

**Результат:**
- `ios/App.xcarchive`

---

## 🚀 Быстрый старт

### 1. Windows (готовый .exe)

```bash
# Скачайте TgWsProxy.exe из dist/
# Запустите
TgWsProxy.exe --transport auto --port 1080

# Или с GUI
python tray.py
```

### 2. Консольный режим (все платформы)

```bash
# Авто-выбор транспорта
python -m proxy.run_transport --transport auto --port 1080

# QUIC
python -m proxy.run_transport --transport quic

# Meek
python -m proxy.run_transport --transport meek --meek-cdn google

# Shadowsocks
python -m proxy.run_transport --transport shadowsocks \
    --ss-method chacha20-ietf-poly1305 \
    --ss-password "mypassword"
```

### 3. PWA (веб-версия)

```bash
# Запуск веб-панели
python run_web.py --port 5000
```

**Откройте в браузере:**
- Desktop: `http://localhost:5000`
- Mobile: `http://ВАШ_IP:5000`

**Установите как PWA:**
1. Откройте в Chrome/Edge
2. Меню → "Установить приложение"
3. Готово!

---

## 📊 Сравнение версий

| Версия | Размер | Транспорт | GUI | Трей |
|--------|--------|-----------|-----|------|
| **Windows .exe** | 32 MB | ✅ Все | ❌ | ❌ |
| **tray.py** | - | ✅ Все | ✅ | ✅ |
| **Linux binary** | ~30 MB | ✅ Все | ❌ | ❌ |
| **macOS .app** | ~35 MB | ✅ Все | ✅ | ✅ |
| **Android APK** | ~20 MB | ✅ WebSocket | ✅ | N/A |
| **PWA** | ~5 MB | ✅ WebSocket | ✅ | N/A |

---

## 🔧 Конфигурация

### config.json (в %APPDATA%/TgWsProxy/)

```json
{
  "port": 1080,
  "host": "127.0.0.1",
  "transport": "auto",
  "transport_host": "kws2.web.telegram.org",
  "transport_port": 443,
  "meek_cdn": "cloudflare",
  "ss_method": "chacha20-ietf-poly1305",
  "ss_password": "",
  "auto_select": true,
  "health_interval": 30.0,
  "verbose": false
}
```

---

## 🧪 Проверка работоспособности

### 1. Проверка импорта

```bash
python -c "from proxy.transport_manager import TransportManager; print('✅ OK')"
```

### 2. Проверка транспортов

```bash
python -c "
from proxy.http2_transport import HTTP2Transport
from proxy.quic_transport import QuicTransport
from proxy.meek_transport import MeekTransport
print('✅ Все транспорты доступны')
"
```

### 3. Проверка PQ криптографии

```bash
python -c "
from proxy.post_quantum_crypto import generate_pq_keys
pub, priv = generate_pq_keys()
print(f'✅ PQ ключи: {pub.hex()[:32]}...')
"
```

### 4. Запуск тестов

```bash
python -m pytest tests/ -v --tb=short
```

**Ожидаемый результат:**
```
1125 passed, 8 skipped, 0 failed
```

---

## 📝 Логи сборки

**Файл:** `dist/build_log.txt`

Содержит:
- Дату и время сборки
- Версию Python
- Список установленных зависимостей
- Этапы сборки
- Ошибки (если есть)

---

## 🐛 Решение проблем

### Проблема: TgWsProxy.exe не запускается

**Решение:**
1. Проверьте антивирус (возможно ложное срабатывание)
2. Добавьте в исключения
3. Или используйте версию с `python tray.py`

### Проблема: QUIC не работает

**Решение:**
```bash
# Установите aioquic
pip install aioquic

# Или используйте HTTP/2 fallback
python -m proxy.run_transport --transport http2
```

### Проблема: Meek слишком медленный

**Решение:**
```bash
# Смените CDN
python -m proxy.run_transport --transport meek --meek-cdn google

# Или используйте QUIC
python -m proxy.run_transport --transport quic
```

---

## 📞 Поддержка

**Документация:**
- `README.md` — основная
- `docs/ENHANCED_TRANSPORTS.md` — транспорты
- `docs/ANTI_CENSORSHIP.md` — обход блокировок
- `docs/CHANGES_SUMMARY.md` — изменения

**Автор:** Dupley Maxim Igorevich  
**Лицензия:** MIT  
**Версия:** v2.59.0

---

## ✅ Чек-лист перед использованием

- [ ] Скачана последняя версия (v2.59.0)
- [ ] Проверена целостность файла
- [ ] Проверен хэш (опционально)
- [ ] Добавлено в исключения антивируса
- [ ] Протестирован запуск
- [ ] Настроен транспорт (auto/quic/meek)
- [ ] Проверена работа с Telegram

---

**Готово к использованию! 🎉**
