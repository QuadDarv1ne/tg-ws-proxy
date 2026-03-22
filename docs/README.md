# 📚 Документация TG WS Proxy

## 📖 Основная документация

| Файл | Описание |
|------|----------|
| [QUICKSTART.md](QUICKSTART.md) | ⚡ Быстрый старт — установка и настройка за 5 минут |
| [CONFIGURATION.md](CONFIGURATION.md) | ⚙️ Полная справка по конфигурации |
| [GAMING_PROXY.md](GAMING_PROXY.md) | 🎮 Настройка PS4/PS5/Xbox/Switch |
| [SECURITY_ADVANCED.md](SECURITY_ADVANCED.md) | 🔒 Безопасность: шифрование, rate limiting, DPI bypass |
| [TESTING.md](TESTING.md) | 🧪 Тестирование и coverage |
| [CHANGELOG.md](CHANGELOG.md) | 📋 История изменений |

## 🔗 Дополнительные ресурсы

| Ресурс | Описание |
|--------|----------|
| [README.md](../README.md) | 🏠 Главная страница проекта |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | 🤝 Руководство для контрибьюторов |
| [SECURITY.md](../SECURITY.md) | 🛡️ Политика безопасности |
| [TODO.md](../todo.md) | 📝 План разработки |

## 📂 Структура проекта

```
tg-ws-proxy/
├── docs/                    # Документация (6 основных файлов)
│   ├── README.md           # Оглавление
│   ├── QUICKSTART.md       # Быстрый старт + Telegram настройка
│   ├── CONFIGURATION.md    # Конфигурация
│   ├── GAMING_PROXY.md     # Игровые консоли + Mobile
│   ├── SECURITY_ADVANCED.md # Безопасность (объединяет 3 файла)
│   ├── TESTING.md          # Тестирование
│   └── CHANGELOG.md        # История изменений
├── proxy/                   # Исходный код (48 модулей)
├── tests/                   # Тесты (35 файлов)
├── scripts/                 # Скрипты
├── mobile-app/              # Android приложение
└── ...                      # Конфигурационные файлы
```

## 🗂️ Оптимизация документации

**Объединено:**
- `TELEGRAM_SETUP.md` → `QUICKSTART.md`
- `ENCRYPTION.md` + `RATE_LIMITING.md` + `DPI_BYPASS.md` → `SECURITY_ADVANCED.md`
- `RELEASE_NOTES.md` + `GITHUB_RELEASE.md` → `CHANGELOG.md`
- `INSTALL_MOBILE.md` → `GAMING_PROXY.md`
- `HTTP2_RESEARCH.md` → удалён (устарел)
- `BUILD.md` → перенесён в основной README

**Удалено:** 9 дублирующихся файлов

---

## 🔗 Полезные ссылки

- [GitHub Repository](https://github.com/QuadDarv1ne/tg-ws-proxy)
- [Releases](https://github.com/QuadDarv1ne/tg-ws-proxy/releases)
- [Issues](https://github.com/QuadDarv1ne/tg-ws-proxy/issues)

---

**Последнее обновление:** 23.03.2026  
**Версия:** v2.57.0
