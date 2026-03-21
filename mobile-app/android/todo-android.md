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

## План "Cycle 6: Pro Connectivity & Global Access":
1.  [ ] **UDP Associate Support**: Реализация поддержки UDP для корректной работы голосовых звонков в Telegram.
2.  [ ] **Local PAC Server**: Запуск локального HTTP-сервера для раздачи PAC-файла (автонастройка прокси для других устройств).
3.  [ ] **ZeroConf / mDNS**: Анонсирование прокси в локальной сети для автоматического обнаружения.
4.  [ ] **Tunnel Compression**: Опциональное сжатие данных (zlib) в WebSocket-туннеле для экономии трафика.
5.  [ ] **Sleep Timer**: Таймер автоматического выключения прокси.
6.  [ ] **Password Protected Config**: Шифрование экспортируемых JSON-конфигов паролем.
7.  [ ] **Proxy Chaining**: Поддержка каскадирования (использование внешнего SOCKS5 прокси как апстрима).
8.  [ ] **Battery Analytics**: Интеграция с системным API для отображения реального потребления энергии сервисом.
9.  [ ] **VpnService Routing**: Переход от прототипа к работающей маршрутизации трафика через TUN-интерфейс.
10. [ ] **AI Optimization**: Обновление модели Gemini и добавление предиктивного анализа сетевых сбоев.
