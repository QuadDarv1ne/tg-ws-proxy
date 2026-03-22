# Мониторинг TG WS Proxy с Prometheus и Grafana

**Версия:** v2.40.0+  
**Дата:** 22.03.2026

---

## 📋 Обзор

TG WS Proxy предоставляет endpoint `/metrics` в формате Prometheus для сбора метрик производительности и мониторинга.

### Доступные метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `tg_ws_proxy_info` | Gauge | Информация о прокси (версия) |
| `tg_ws_proxy_connections_total` | Counter | Общее количество подключений |
| `tg_ws_proxy_connections_active` | Gauge | Активные подключения |
| `tg_ws_proxy_bytes_received_total` | Counter | Байт получено от клиентов |
| `tg_ws_proxy_bytes_sent_total` | Counter | Байт отправлено клиентам |
| `tg_ws_proxy_bytes_forwarded_total` | Counter | Байт перенаправлено в Telegram |
| `tg_ws_proxy_cpu_percent` | Gauge | Использование CPU (%) |
| `tg_ws_proxy_memory_mb` | Gauge | Использование памяти (MB) |
| `tg_ws_proxy_dc_latency_ms{dc_id}` | Gauge | Задержка до DC (ms) |
| `tg_ws_proxy_dc_errors_total{dc_id}` | Counter | Ошибки по DC |
| `tg_ws_proxy_circuit_breaker_state{name}` | Gauge | Состояние circuit breaker |
| `tg_ws_proxy_circuit_breaker_failures_total{name}` | Counter | Failures circuit breaker |
| `tg_ws_proxy_circuit_breaker_rejected_total{name}` | Counter | Отклонённые запросы |
| `tg_ws_proxy_dns_queries_total` | Counter | DNS запросов |
| `tg_ws_proxy_dns_cache_hits_total` | Counter | DNS cache hits |
| `tg_ws_proxy_dns_cache_misses_total` | Counter | DNS cache misses |
| `tg_ws_proxy_dns_cache_hit_rate` | Gauge | DNS cache hit rate |
| `tg_ws_proxy_plugins_loaded` | Gauge | Загружено плагинов |

---

## 🚀 Быстрый старт

### 1. Запуск Prometheus + Grafana

**Docker Compose:**

Создайте файл `docker-compose.monitoring.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

### 2. Конфигурация Prometheus

Создайте файл `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'tg-ws-proxy'
    static_configs:
      - targets: ['host.docker.internal:8080']
    metrics_path: '/metrics'
    scrape_interval: 10s
    
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

**Для Linux замените `host.docker.internal` на IP хоста:**
```yaml
targets: ['172.17.0.1:8080']
```

### 3. Запуск

```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

### 4. Доступ к панелям

- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3000 (admin/admin123)

---

## 📊 Настройка Grafana Dashboard

### 1. Добавление DataSource

1. Откройте Grafana
2. Configuration → Data Sources → Add data source
3. Выберите **Prometheus**
4. URL: `http://prometheus:9090`
5. Save & Test

### 2. Импорт дашборда

Создайте файл `grafana-dashboard.json` (см. ниже) и импортируйте:

1. Dashboards → Import
2. Upload JSON file
3. Выберите Prometheus datasource
4. Import

---

## 📈 Примеры PromQL запросов

### Общая статистика

```promql
# Активные подключения
tg_ws_proxy_connections_active

# Трафик (байт/сек)
rate(tg_ws_proxy_bytes_received_total[5m])
rate(tg_ws_proxy_bytes_sent_total[5m])

# CPU и память
tg_ws_proxy_cpu_percent
tg_ws_proxy_memory_mb
```

### DC метрики

```promql
# Latency по DC
tg_ws_proxy_dc_latency_ms

# Ошибки по DC
rate(tg_ws_proxy_dc_errors_total[5m])

# Top DC по ошибкам
topk(3, rate(tg_ws_proxy_dc_errors_total[1h]))
```

### Circuit Breaker

```promql
# Состояние circuit breaker (0=closed, 1=open, 2=half_open)
tg_ws_proxy_circuit_breaker_state

# Failures rate
rate(tg_ws_proxy_circuit_breaker_failures_total[5m])

# Rejected запросы
rate(tg_ws_proxy_circuit_breaker_rejected_total[5m])
```

### DNS метрики

```promql
# DNS запросов в секунду
rate(tg_ws_proxy_dns_queries_total[5m])

# Cache hit rate
tg_ws_proxy_dns_cache_hit_rate

# Cache hits vs misses
tg_ws_proxy_dns_cache_hits_total
tg_ws_proxy_dns_cache_misses_total
```

---

## 🎨 Grafana Dashboard JSON

Пример дашборда (сохраните как `grafana-dashboard.json`):

```json
{
  "dashboard": {
    "title": "TG WS Proxy Monitoring",
    "tags": ["telegram", "proxy"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Active Connections",
        "type": "timeseries",
        "targets": [
          {
            "expr": "tg_ws_proxy_connections_active",
            "legendFormat": "Active"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Traffic",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(tg_ws_proxy_bytes_received_total[5m])",
            "legendFormat": "Received"
          },
          {
            "expr": "rate(tg_ws_proxy_bytes_sent_total[5m])",
            "legendFormat": "Sent"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      },
      {
        "id": 3,
        "title": "CPU Usage",
        "type": "gauge",
        "targets": [
          {
            "expr": "tg_ws_proxy_cpu_percent",
            "legendFormat": "CPU %"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 50},
                {"color": "red", "value": 80}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "Memory Usage",
        "type": "gauge",
        "targets": [
          {
            "expr": "tg_ws_proxy_memory_mb",
            "legendFormat": "Memory MB"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 8}
      },
      {
        "id": 5,
        "title": "DC Latency",
        "type": "timeseries",
        "targets": [
          {
            "expr": "tg_ws_proxy_dc_latency_ms",
            "legendFormat": "DC {{dc_id}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      },
      {
        "id": 6,
        "title": "DNS Cache Hit Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "tg_ws_proxy_dns_cache_hit_rate",
            "legendFormat": "Hit Rate"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percentunit",
            "thresholds": {
              "steps": [
                {"color": "red", "value": null},
                {"color": "yellow", "value": 0.5},
                {"color": "green", "value": 0.8}
              ]
            }
          }
        },
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16}
      },
      {
        "id": 7,
        "title": "Circuit Breaker State",
        "type": "table",
        "targets": [
          {
            "expr": "tg_ws_proxy_circuit_breaker_state",
            "legendFormat": "{{name}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 6, "y": 16}
      }
    ],
    "refresh": "10s",
    "schemaVersion": 38,
    "version": 1
  }
}
```

---

## 🔔 Alerting

### Prometheus Alert Rules

Создайте файл `alerts.yml`:

```yaml
groups:
  - name: tg-ws-proxy-alerts
    rules:
      - alert: HighCPUsage
        expr: tg_ws_proxy_cpu_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is {{ $value }}% for more than 5 minutes"

      - alert: HighMemoryUsage
        expr: tg_ws_proxy_memory_mb > 500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is {{ $value }}MB for more than 5 minutes"

      - alert: DCHighLatency
        expr: tg_ws_proxy_dc_latency_ms > 200
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High DC latency detected"
          description: "DC {{ $labels.dc_id }} latency is {{ $value }}ms"

      - alert: CircuitBreakerOpen
        expr: tg_ws_proxy_circuit_breaker_state == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker is OPEN"
          description: "Circuit breaker {{ $labels.name }} is open"

      - alert: LowDNSCacheHitRate
        expr: tg_ws_proxy_dns_cache_hit_rate < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low DNS cache hit rate"
          description: "DNS cache hit rate is {{ $value | humanizePercentage }}"
```

Добавьте в `prometheus.yml`:

```yaml
rule_files:
  - /etc/prometheus/alerts.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: []
```

---

## 🧪 Тестирование

### Проверка endpoint

```bash
curl http://localhost:8080/metrics
```

Ожидаемый вывод:
```
# HELP tg_ws_proxy_info Proxy information
# TYPE tg_ws_proxy_info gauge
tg_ws_proxy_info{version="2.40.0"} 1
# HELP tg_ws_proxy_connections_total Total number of connections
# TYPE tg_ws_proxy_connections_total counter
tg_ws_proxy_connections_total 150
...
```

### Проверка scrape

Откройте http://localhost:9090/targets и убедитесь, что target `tg-ws-proxy` в статусе UP.

---

## 📝 Рекомендации

### Production настройка

1. **Scrape interval:** 10-30s для баланса между детализацией и нагрузкой
2. **Retention:** 15-30 дней истории метрик
3. **Alerting:** Настройте уведомления в Telegram/Email/Slack
4. **High Availability:** Репликация Prometheus для критичных систем

### Оптимизация

1. **Recording Rules:** Для сложных запросов
2. **Service Discovery:** Для динамических окружений
3. **Federation:** Для масштабирования

---

## 🔗 Полезные ссылки

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Tutorial](https://promlabs.com/promql-cheat-sheet/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)

---

**Автор:** Dupley Maxim Igorevich  
**© 2026 Dupley Maxim Igorevich. All rights reserved.**
