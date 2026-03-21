# План по улучшению Android-проекта (Capacitor) - СТАТУС: ВЫПОЛНЕНО (Циклы 1-3)

- [x] **Исправление критических ошибок (Sync Fix)**: Удален `flatDir`, настроен `fileTree`.
- [x] **Обновление зависимостей**: Версии в `variables.gradle` и `libs.versions.toml` обновлены.
- [x] **Оптимизация сборки (R8 / ProGuard)**: Включено сжатие кода и ресурсов в релизе.
- [x] **Переход на Gradle Version Catalog**: Создан `libs.versions.toml` и подключен к `:app`.
- [x] **Edge-to-Edge**: Добавлена поддержка в `MainActivity.java`.
- [x] **Интеграция Python (Chaquopy)**: Запуск ядра прокси на Python внутри Android процесса.
- [x] **Фоновый сервис (Foreground Service)**: Живое уведомление со статистикой и кнопкой остановки.
- [x] **Автозапуск и выживаемость**: `BootReceiver` и `AutoStartHelper` для обхода ограничений вендоров.
- [x] **Quick Settings Tile**: Плитка в шторке для быстрого управления прокси.
- [x] **App Shortcuts**: Ярлыки на рабочем столе для мгновенного управления.
- [x] **Система диагностики**: Проверка пинга до Telegram и real-time логирование.
- [x] **Энергопотребление**: Оптимизация батареи и использование `WakeLock`.
- [x] **Умные порты**: Автоматический поиск свободного порта при конфликтах.
- [x] **Модернизация корневого build.gradle**: Переход на современный синтаксис `plugins {}`.
- [x] **Обновление Target SDK**: Проект полностью переведен на SDK 35 (Android 15).
- [x] **Adaptive Icons**: Внедрена поддержка адаптивных иконок.
- [x] **Локализация**: Полный перевод на RU/EN.
- [x] **Package Visibility**: Решена проблема видимости пакетов на Android 11+.
- [x] **Log Sharing**: Добавлена возможность отправки логов из приложения.
- [x] **Status API Upgrade**: Реактивные события, Watchdog и Heartbeat.
- [x] **Data Backup**: Автоматическое резервное копирование настроек в облако.
- [x] **Encrypted Storage**: Защита секретов через security-crypto.
- [x] **Advanced DoH**: Поддержка Cloudflare/Google/Quad9 DNS.
- [x] **Background Refresh**: WorkManager для авто-обновления серверов.
- [x] **Handshake Diagnostics**: Глубокое логирование MTProto.
- [x] **Adaptive Pooling**: Динамический пул под тип сети.
- [x] **Native Splash API**: Современный запуск Android 12+.
- [x] **Structured Session Logs**: JSON-отчеты по каждой сессии.
- [x] **TCP Tuning**: Оптимизация сокетов для 4G/LTE.
- [x] **Config Profiles**: Поддержка наборов настроек.
- [x] **Security Hardening**: Root-детект и анти-отладка.
- [x] **Dynamic Best DC**: Авто-выбор лучшего сервера Telegram.
- [x] **Biometric Security**: Защита настроек отпечатком пальца.
- [x] **Advanced Analytics**: Подготовка данных для графиков в реальном времени.
- [x] **MTProto Listener**: Параллельная работа в режиме MTProto-прокси.
- [x] **System Theme Sync**: Синхронизация Dark/Light темы с ОС.
- [x] **Deep Link Import**: Импорт настроек по ссылке tg://.
- [x] **Network Whitelist**: Режим работы "Только Wi-Fi".
- [x] **Memory Leak Guard**: Очистка ресурсов при нехватке памяти.
- [x] **Multi-Session View**: Детали активных соединений.
- [x] **AI Log Analyzer**: Анализ ошибок через Gemini AI на русском языке.

## Новый план "Pro Connectivity & Enterprise":
1.  [ ] **Remote Web Dashboard**: Запуск веб-панели на локальном IP устройства для мониторинга с ПК.
2.  [ ] **Persistent Rolling Logs**: Сохранение логов в файлы на диске с ротацией.
3.  [ ] **Multiple MTProto Secrets**: Поддержка управления списком секретов в плагине.
4.  [ ] **Network Speed Limiter**: Возможность программного ограничения скорости.
5.  [ ] **Auto-Update Script**: Проверка и загрузка обновлений python-логики с GitHub.
6.  [ ] **IPv6 Stack Support**: Поддержка IPv6 для WebSocket и MTProto соединений.
7.  [ ] **Task Automation Intents**: Публичные Intent-ы для управления прокси через Tasker/MacroDroid.
8.  [ ] **SSL/TLS Hardening**: Поддержка кастомных сертификатов для туннелирования.
9.  [ ] **Memory Optimization (Chaquopy)**: Настройка исключения неиспользуемых модулей Python (std-lib).
10. [ ] **Export to CSV/Excel**: Выгрузка накопленной статистики трафика в табличный формат.
