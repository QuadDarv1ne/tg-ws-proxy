import asyncio
import logging
import threading
import socket
import io

from proxy.constants import DC_IP_MAP
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping

# Буфер для хранения логов в памяти
log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(), # Оставляем вывод в stdout (Logcat)
        log_handler # Добавляем наш буфер
    ]
)
logger = logging.getLogger("python-proxy")

stop_event = None
proxy_thread = None
_proxy_port = 1080

def find_free_port(start_port=1080):
    """Находит свободный порт, начиная с указанного"""
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except socket.error:
                port += 1
    return start_port

def start_proxy(host="127.0.0.1", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port
    
    if auto_port:
        _proxy_port = find_free_port(port)
    else:
        _proxy_port = port

    if proxy_thread and proxy_thread.is_alive():
        logger.info("Proxy is already running")
        return {"status": "Already running", "port": _proxy_port}

    stop_event = asyncio.Event()
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        logger.info(f"Starting proxy on {host}:{_proxy_port}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run(
                port=_proxy_port,
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
    return {"status": "Started", "port": _proxy_port}

def stop_proxy():
    global stop_event
    if stop_event:
        return "Stopping"
    return "Not running"

def is_running():
    global proxy_thread
    return proxy_thread is not None and proxy_thread.is_alive()

def get_recent_logs():
    """Возвращает содержимое буфера логов и очищает его, если он слишком большой"""
    global log_stream
    logs = log_stream.getvalue()
    # Если логов больше 50кб, обрезаем, чтобы не перегружать память
    if len(logs) > 50000:
        log_stream.truncate(0)
        log_stream.seek(0)
        logger.info("Log buffer cleared (size limit)")
    return logs

def test_connection_to_tg():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        latency, error = loop.run_until_complete(_measure_dc_ping(2, timeout=5.0))
        loop.close()

        if latency is not None:
            return {"status": "ok", "latency": latency}
        else:
            return {"status": "error", "message": error or "Timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = is_running()
        stats["port"] = _proxy_port
        return stats
    except Exception as e:
        return {"error": str(e), "is_running": is_running(), "port": _proxy_port}

def get_proxy_summary_str():
    return get_stats_summary()
