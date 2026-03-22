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

## ✅ Выполнено (v2.49.0: health check + autotune integration)

### Надёжность
- ✅ **Health Check Enhancement** — агрессивная проверка мёртвых соединений
  - Интервал health check уменьшен с 45с до 30с (нормальный режим)
  - Агрессивный режим: 15с интервал при обнаружении проблем
  - Timeout адаптируется: 5с → 3с в агрессивном режиме
  - Обнаружение stale соединений (>2 минут без активности)
  - Трекинг последней активности для каждого соединения
  - Трекинг consecutive failures для каждого DC
  - Автоматическое включение aggressive mode при >5 failures
  - Очистка старых failed connections (5 минут)

### Производительность
- ✅ **Connection Timeout Tuning** — интеграция с AutoTuner
  - `proxy/autotune.py` — авто-тюнинг на основе latency
  - Адаптивные таймауты для health check (на основе tuned timeout)
  - Синхронизация pool optimization с autotuner
  - Запись performance samples в autotuner
  - Статистика autotune в `get_stats()`
  - Запуск autotuner при старте сервера (BALANCED mode)
  - Корректная остановка autotuner при shutdown

### Интеграция
- ✅ **AutoTuner + ConnectionPool** — полная интеграция
  - `connection_pool.py` использует `get_autotuner()`
  - Адаптивный timeout для health check (50% от tuned timeout, cap 10s)
  - Performance samples записываются при оптимизации пула
  - Статистика autotune доступна в pool stats

---

## 🟡 В процессе (v2.49.0: integration tests + coverage)

### Производительность
- [ ] **HTTP/2 for Web Dashboard** — Quart + Hypercorn для API multiplexing
- [ ] **QUIC/UDP Research** — для звонков и медиа через прокси (v3.0.0)

### Безопасность
- [ ] **Аудит зависимостей** — `pip-audit` интеграция в CI
- [ ] **E2E Encryption** — локальное шифрование трафика между клиентом и прокси

### Тестирование
- [ ] **Coverage Improvement** — увеличение покрытия с 55% до 60%
- [ ] **Integration Tests** — сквозные тесты для основных сценариев

---

## 📊 Статус (23.03.2026 01:30)

```
Модулей: 35 в proxy/ ✅
Тестов: 33 файла в tests/ ✅
Tests: 642 passed, 7 skipped ✅
Coverage: ~57% (цель >80%)
Ruff: 0 ошибок ✅
Mypy: 0 ошибок ✅
RuntimeWarnings: 0 ✅
Version: v2.49.0 (Health Check ✅, AutoTune ✅)
```

**Актуальная версия:** v2.49.0 (dev) — ✅ synced
**Следующая версия:** v2.50.0 (E2E Encryption + Security)
**Последнее обновление:** 23.03.2026 (01:30)

---

## 📝 Заметки по Android (v2.38.1)
- Исправлена несовместимость с AGP 9.1.0 в Capacitor плагинах.
- Требуется нативный TUN двигатель (L3->L5) для полноценного VPN.
