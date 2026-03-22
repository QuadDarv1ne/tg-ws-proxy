# План по улучшению Android-проекта (Capacitor) - СТАТУС: v2.38.0 РЕЛИЗ

- [x] **Core Stability**: Chaquopy 15.0.0, Python 3.11, R8 Full Mode.
- [x] **Python Core**: Исправлен рассинхрон версий, asyncio watchdog.
- [x] **Foreground Service**: Стабильный WakeLock, Battery Optimization Bypass.
- [x] **Diagnostics**: Пинг-тесты DC в реальном времени, JSON-логи.
- [x] **Networking**: DNS Cache TTL, IPv6 Support, TUN Interface Stub.
- [x] **UX/UI**: Material 3, Quick Settings Tile (Скорость/Статус).
- [x] **Enterprise**: Background Config Update через WorkManager.

## Текущий цикл: Cycle 7 - Quality & Resilience (v2.39.0 План)
1.  [ ] **TUN2SOCKS Engine**: Полноценная реализация пересылки трафика (L3 -> L5).
2.  [ ] **Memory Guard**: Автоматический перезапуск Python-процесса при утечках >150MB.
3.  [ ] **Network Switching**: Бесшовный переход Wi-Fi <-> 4G без обрыва WS-пула.
4.  [ ] **Deep Links v2**: Поддержка импорта зашифрованных JSON-конфигов.
5.  [ ] **Advanced Tile**: Переключение между DC прямо из шторки.

## Заметки по качеству (Review):
- ⚠️ **VPN**: Интерфейс создается, но пакеты "дропаются" (нужен нативный движок).
- ✅ **Version Sync**: Все файлы (gradle, init, toml) теперь на v2.38.0.
- 🛠 **Tests**: `test_profiler` исправлен для asyncio сред.
