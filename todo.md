# TODO — TG WS Proxy

**Правило:** не создавай документацию без запроса, только код и исправления.
**Правило:** дело не в количестве, а в качестве.
**Правило:** продолжай улучшать проект в dev, потом проверь и отправь в main.

---

## ✅ Выполнено (v2.48.1: build & compatibility)

### Android & Build System
- ✅ **AGP 9.1.0 Compatibility** — исправление ошибки `proguard-android.txt` is no longer supported.
  - Динамическая замена устаревшего файла на `proguard-android-optimize.txt` через root `build.gradle`.
  - Автоматическое исправление для всех Capacitor плагинов в `node_modules`.
- ✅ **Gradle Refactoring** — очистка root `build.gradle` от неэффективных конфигураций.

### Refactoring Complete ✅
- ✅ **mtproto_parser.py** — выделен парсинг MTProto пакетов
- ✅ **Модульность** — все 4 модуля выделены (socks5, websocket, pool, mtproto)

### Performance Optimization
- ✅ **Performance Profiler** — cProfile интеграция с optimization suggestions
- ✅ **DNS Resolver Aggressive Caching** — hit rate >90% target

### Monitoring & Observability
- ✅ **Prometheus metrics endpoint** — `/metrics` для сбора метрик
- ✅ **Circuit breaker** — защита от cascade failures (websocket, tcp, dns)

---

## ✅ Выполнено (v2.50.0: rate limiting + DDoS protection)

### Безопасность
- ✅ **Rate Limiting Improvements** — защита от DDoS и злоупотреблений
  - `proxy/rate_limiter.py` — расширенный rate limiter (+300 строк)
  
  **DDoS Detection:**
  • Детекция атак по RPS (threshold: 50 RPS)
  • Progressive ban duration (exponential backoff)
  • Max ban duration: 24 часа
  • Логирование critical событий
  • Конфигурация: ddos_detection_enabled, ddos_threshold_rps
  
  **Connection Flood Protection:**
  • Детекция по CPS (threshold: 50 CPS)
  • Ban duration: 10 минут с escalation
  • Отдельный счётчик flood_violations
  • Конфигурация: flood_detection_enabled, flood_threshold_connections
  
  **Geographic Rate Limiting:**
  • /24 subnet tracking для IPv4
  • Max connections per subnet: 20
  • Автоматическое отслеживание IP в subnet
  • Конфигурация: enable_ip_range_limiting, max_connections_per_subnet
  
  **Progressive Penalties:**
  • total_bans tracking per IP
  • last_ban_duration tracking
  • Escalation: ban duration удваивается
  • Конфигурация: progressive_ban_enabled, max_ban_duration
  
  **Расширенная статистика:**
  • Global: ddos_attacks_detected, flood_attacks_detected, subnets_active
  • Per-IP: ddos_violations, flood_violations, total_bans, subnet
  • connection_flood_rate (CPS)

---

## 🟡 В процессе (v2.51.0: dashboard + stability)

### Производительность
- [ ] **HTTP/2 for Web Dashboard** — Quart + Hypercorn для API multiplexing
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 55% до 60%
- [ ] **Integration Tests** — сквозные тесты для основных сценариев

### Мониторинг
- [ ] **Real-time Dashboard** — улучшение веб-панели с live графиками
- [ ] **Metrics History** — хранение истории метрик за 30 дней

---

## 📊 Статус (23.03.2026 02:30)

```
Модулей: 37 в proxy/ ✅
Тестов: 33 файла в tests/ ✅
Tests: 642 passed, 7 skipped ✅
Coverage: ~57% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 0 ошибок ✅
RuntimeWarnings: 0 ✅
Version: v2.50.0 (Rate Limiting ✅, DDoS Protection ✅)
```

**Актуальная версия:** v2.50.0 (dev) — ✅ synced
**Следующая версия:** v2.51.0 (Dashboard + Stability)
**Последнее обновление:** 23.03.2026 (02:30)

---

## 📝 Заметки по Android (v2.38.1)
- Исправлена несовместимость с AGP 9.1.0 в Capacitor плагинах.
- Требуется нативный TUN двигатель (L3->L5) для полноценного VPN.
