# План по улучшению Android-проекта (Capacitor) - СТАТУС: ВЫПОЛНЕНО (Циклы 1-4)

- [x] **Core Stability**: Исправлены ошибки сборки, обновлены зависимости, включен R8.
- [x] **Python Core**: Chaquopy интеграция, asyncio мост, логирование.
- [x] **Foreground Service**: Стабильность в фоне, WakeLock, Battery Watchdog.
- [x] **Diagnostics**: Live-статистика, пинг-тесты, AI анализ логов (Gemini).
- [x] **Networking**: SOCKS5 + MTProto одновременно, DoH, IPv6, Speed Shaper.
- [x] **UX/UI**: Material 3, Splash API, Theme Sync, Quick Tile, App Shortcuts.
- [x] **Security**: Encrypted Storage, Biometrics, Root/Debug detect, SSL Hardening.
- [x] **Enterprise**: WorkManager обновления, CSV экспорт, Remote Dashboard.

## План "Cycle 5: Intelligence & Reliability" (В работе):
1.  [ ] **Dynamic DC Failover**: Автоматическое переключение на резервный DC при сбое основного.
2.  [ ] **Advanced Handshake Logging**: Детальное логирование процесса установки соединения MTProto.
3.  [ ] **Session Persistence**: Сохранение состояния активных сессий для восстановления после перезапуска.
4.  [ ] **Enhanced Gemini Analysis**: Улучшенные промпты для более точного анализа логов через ИИ.
5.  [ ] **VPN Mode Integration**: Интеграция VpnService с Python-ядром (экспериментально).
6.  [ ] **Certificate Pinning**: Защита обновлений конфига от MITM атак.
7.  [ ] **Configurable Battery Threshold**: Настройка порога отключения прокси пользователем.
8.  [ ] **Network Speed History**: Накопление данных о скорости для построения графиков производительности.
9.  [ ] **Auto Secret Rotation**: Логика периодической ротации секретов MTProto.
10. [ ] **Java Crash Reporting**: Запись нативных падений Java в тот же файл логов.
