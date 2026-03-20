#!/usr/bin/env python
"""
Запуск веб-панели управления TG WS Proxy.

Автор: Dupley Maxim Igorevich
© 2026 Dupley Maxim Igorevich. Все права защищены.

Откройте в браузере: http://localhost:8080
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from proxy.web_dashboard import WebDashboard
from proxy.stats import Stats

# Create stats instance
stats = Stats()

# Create and run web dashboard
# Bind to 0.0.0.0 to allow access from local network
dashboard = WebDashboard(get_stats_callback=stats.to_dict, host='0.0.0.0', port=8080)
dashboard.start()

print("Веб-панель запущена: http://localhost:8080")
print("Для доступа с телефона используйте: http://192.168.31.227:8080")
print("Нажмите Ctrl+C для остановки")

try:
    # Keep main thread alive
    import time
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nОстановка веб-панели...")
    dashboard.stop()
