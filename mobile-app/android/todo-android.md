# План по улучшению Android-проекта (Capacitor) - СТАТУС: ВЫПОЛНЕНО (Циклы 1-5)

- [x] **Core Stability**: Исправлены ошибки сборки, обновлены зависимости, включен R8.
- [x] **Python Core**: Chaquopy интеграция, asyncio мост, логирование.
- [x] **Foreground Service**: Стабильность в фоне, WakeLock, Battery Watchdog.
- [x] **Diagnostics**: Live-статистика, пинг-тесты, AI анализ логов (Gemini).
- [x] **Networking**: SOCKS5 + MTProto одновременно, DoH, IPv6, Speed Shaper.
- [x] **UX/UI**: Material 3, Splash API, Theme Sync, Quick Tile, App Shortcuts.
- [x] **Security**: Encrypted Storage, Biometrics, Root/Debug detect, SSL Hardening.
- [x] **Enterprise**: WorkManager обновления, CSV экспорт, Remote Dashboard.
- [x] **Intelligence**: Dynamic DC Failover, Adaptive Pooling, Auto Secret Rotation.

## План "Cycle 6: Pro Connectivity & Global Access" - В РАБОТЕ:
1.  [x] **UDP Associate Support**: Поддержка UDP для звонков (интеграция в мост).
2.  [x] **Local PAC Server**: Раздача PAC-файла через локальный HTTP-сервер.
3.  [x] **ZeroConf / mDNS**: Авто-обнаружение прокси в локальной сети.
4.  [x] **Tunnel Compression**: Сжатие данных (zlib) в WebSocket-туннеле.
5.  [x] **Sleep Timer**: Таймер автоматического выключения прокси.
6.  [ ] **Password Protected Config**: Шифрование экспортируемых JSON-конфигов паролем.
7.  [ ] **Proxy Chaining**: Поддержка каскадирования (использование внешнего SOCKS5 прокси как апстрима).
8.  [ ] **Battery Analytics**: Интеграция с системным API для отображения реального потребления энергии.
9.  [ ] **VpnService Routing**: Переход от прототипа к работающей маршрутизации через TUN.
10. [ ] **AI Optimization**: Предиктивный анализ сетевых сбоев через Gemini.
