import asyncio
import logging
import logging.handlers
import threading
import socket
import io
import json
import urllib.request
import time
import os
import traceback
from datetime import date

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy, generate_secret
from proxy.web_dashboard import WebDashboard

FILES_DIR = os.environ.get("HOME", ".")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")
PYTHON_DIR = os.path.join(FILES_DIR, "python_updates")

file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s'))

log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(
    level=logging.INFO, format='%(name)s: %(message)s',
    handlers=[logging.StreamHandler(), log_handler, file_handler]
)
logger = logging.getLogger("python-proxy")

stop_event = None
proxy_thread = None
dashboard_instance = None
_proxy_port = 1080
_use_ipv6 = True # Task 6: Включаем поддержку IPv6 по умолчанию

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds, dashboard_instance
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    
    try:
        if not dashboard_instance:
            dashboard_instance = WebDashboard(get_stats_callback=get_stats, host="0.0.0.0", port=_dashboard_port)
            dashboard_instance.start()
    except: pass

    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Настройка семейства адресов для Task 6
        family = socket.AF_UNSPEC if _use_ipv6 else socket.AF_INET
        
        try:
            loop.run_until_complete(_run(
                port=_proxy_port, dc_opt=dc_opt, stop_event=stop_event, 
                host="::" if _use_ipv6 else host, # Слушаем на всех IPv6/IPv4 интерфейсах
                auth_required=_auth_creds is not None, auth_credentials=_auth_creds
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port, "ipv6": _use_ipv6}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["ipv6_supported"] = socket.has_ipv6
        stats["ipv6_active"] = _use_ipv6
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(os.path.join(FILES_DIR, "crash_log.txt"), "a") as f:
            f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass
