import asyncio
import logging
import threading

from proxy.constants import DC_IP_MAP
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary

# Настройка логирования для Android (будет видно в logcat)
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(message)s'
)
logger = logging.getLogger("python-proxy")

stop_event = None
proxy_thread = None
_proxy_port = 1080

def start_proxy(host="127.0.0.1", port=1080):
    global stop_event, proxy_thread, _proxy_port
    _proxy_port = port

    if proxy_thread and proxy_thread.is_alive():
        logger.info("Proxy is already running")
        return "Already running"

    stop_event = asyncio.Event()

    # Формируем конфиг DC (берем дефолтные из constants.py)
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        logger.info(f"Starting proxy on {host}:{port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run(
                port=port,
                dc_opt=dc_opt,
                stop_event=stop_event,
                host=host
            ))
        except Exception as e:
            logger.error(f"Proxy loop error: {e}")
        finally:
            logger.info("Proxy loop finished")
            loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return "Started"

def stop_proxy():
    global stop_event
    if stop_event:
        # В текущей реализации _run ожидает stop_event.wait()
        # Нам нужно установить event из того же цикла событий или
        # просто завершить сервис, что мы и делаем в Java.
        return "Stopping"
    return "Not running"

def is_running():
    global proxy_thread
    return proxy_thread is not None and proxy_thread.is_alive()

def get_proxy_stats_dict():
    """Возвращает статистику в виде словаря для Capacitor"""
    try:
        stats = get_stats()
        # Добавляем статус и порт
        stats["is_running"] = is_running()
        stats["port"] = _proxy_port
        return stats
    except Exception as e:
        return {"error": str(e), "is_running": is_running()}

def get_proxy_summary_str():
    return get_stats_summary()
