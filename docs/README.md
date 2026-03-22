# 📚 Документация TG WS Proxy

## 📖 Основная документация (7 файлов)

| Файл | Описание | Размер |
|------|----------|--------|
| [QUICKSTART.md](QUICKSTART.md) | ⚡ Быстрый старт — установка и настройка за 5 минут | 6 KB |
| [CONFIGURATION.md](CONFIGURATION.md) | ⚙️ Полная справка по конфигурации | 7 KB |
| [GAMING_PROXY.md](GAMING_PROXY.md) | 🎮 Настройка PS4/PS5/Xbox/Switch + mobile | 8 KB |
| [SECURITY_ADVANCED.md](SECURITY_ADVANCED.md) | 🔒 Безопасность: шифрование, rate limiting, DPI bypass | 7 KB |
| [TESTING.md](TESTING.md) | 🧪 Тестирование и coverage | 6 KB |
| [CHANGELOG.md](CHANGELOG.md) | 📋 История изменений | 7 KB |
| [README.md](README.md) | 📖 Это оглавление | 3 KB |

## 🔗 Дополнительные ресурсы

| Ресурс | Описание |
|--------|----------|
| [README.md](../README.md) | 🏠 Главная страница проекта |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 🤝 Руководство для контрибьюторов |
| [SECURITY.md](../SECURITY.md) | 🛡️ Политика безопасности |
| [TODO.md](../todo.md) | 📝 План разработки |

---

## 📂 Итоговая структура проекта

```
tg-ws-proxy/
├── docs/                        # Документация (7 файлов, 44 KB)
│   ├── README.md               # Оглавление
│   ├── QUICKSTART.md           # Быстрый старт + Telegram + mobile
│   ├── CONFIGURATION.md        # Конфигурация
│   ├── GAMING_PROXY.md         # Игровые консоли + mobile
│   ├── SECURITY_ADVANCED.md    # Безопасность (объединяет 3 файла)
│   ├── TESTING.md              # Тестирование
│   └── CHANGELOG.md            # История изменений
│
├── proxy/                       # Исходный код (48 модулей)
├── tests/                       # Тесты (35 файлов)
├── scripts/                     # Скрипты
├── mobile-app/                  # Android приложение
└── ...                          # Конфигурационные файлы
```

---

## 🗂️ Оптимизация документации

**Было:** 15 файлов (60+ KB)  
**Стало:** 7 файлов (44 KB)  
**Сокращение:** 53% без потери информации

**Объединено:**
- `TELEGRAM_SETUP.md` → `QUICKSTART.md`
- `ENCRYPTION.md` + `RATE_LIMITING.md` + `DPI_BYPASS.md` → `SECURITY_ADVANCED.md`
- `RELEASE_NOTES.md` + `GITHUB_RELEASE.md` → `CHANGELOG.md`
- `INSTALL_MOBILE.md` → `GAMING_PROXY.md`
- `BUILD.md` → перенесён в основной README проекта
- `MONITORING.md` → удалён (устарел)
- `HTTP2_RESEARCH.md` → удалён (устарел)

---

## 🔗 Полезные ссылки

- [GitHub Repository](https://github.com/QuadDarv1ne/tg-ws-proxy)
- [Releases](https://github.com/QuadDarv1ne/tg-ws-proxy/releases)
- [Issues](https://github.com/QuadDarv1ne/tg-ws-proxy/issues)

---

**Последнее обновление:** 23.03.2026  
**Версия:** v2.57.0
