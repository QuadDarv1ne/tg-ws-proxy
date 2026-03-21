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
from proxy.web_dashboard import WebDashboard

# Пути к файлам (Task 2)
FILES_DIR = os.environ.get("HOME", ".")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")

# Настройка Rolling Logs (Task 2)
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=1024*1024, backupCount=3
)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s'))

log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(message)s',
    handlers=[logging.StreamHandler(), log_handler, file_handler]
)
logger = logging.getLogger("python-proxy")

stop_event = None
proxy_thread = None
dashboard_instance = None
_proxy_port = 1080
_dashboard_port = 5000
_custom_dc_opt = None
_use_doh = False
_doh_provider = "google"
_auth_creds = None
_traffic_limit_mb = 0
_is_wifi = True
_last_heartbeat = 0
_current_best_dc = 2

async def monitor_best_dc():
    global _current_best_dc, _custom_dc_opt
    while not stop_event or not stop_event.is_set():
        try:
            dcs_to_check = _custom_dc_opt.keys() if _custom_dc_opt else DC_IP_MAP.keys()
            best_latency = float('inf')
            best_id = _current_best_dc
            for dc_id in dcs_to_check:
                latency, _ = await _measure_dc_ping(dc_id, timeout=2.0)
                if latency and latency < best_latency:
                    best_latency = latency
                    best_id = dc_id
            if best_id != _current_best_dc:
                _current_best_dc = best_id
        except: pass
        await asyncio.sleep(300)

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds, dashboard_instance
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    
    try:
        if not dashboard_instance:
            dashboard_instance = WebDashboard(get_stats_callback=get_stats, host="0.0.0.0", port=_dashboard_port)
            dashboard_instance.start()
    except Exception as e: logger.error(f"Dashboard error: {e}")

    _session_id = int(time.time())
    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(monitor_best_dc())
        try:
            loop.run_until_complete(_run(
                port=_proxy_port, dc_opt=dc_opt, stop_event=stop_event, host=host,
                auth_required=_auth_creds is not None, auth_credentials=_auth_creds
            ))
        except Exception:
            write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["port"] = _proxy_port
        stats["log_file_size"] = os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        crash_file = os.path.join(FILES_DIR, "crash_log.txt")
        with open(crash_file, "a") as f: f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass

def get_recent_logs(): return log_stream.getvalue()
def clear_dns():
    try:
        _clear_dns_cache()
        return True
    except: return False
