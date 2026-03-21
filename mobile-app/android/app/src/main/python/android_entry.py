import asyncio
import logging
import threading
import socket
import io
import json
import urllib.request
import time
import os
import traceback
from datetime import date

from proxy.constants import DC_IP_MAP
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache

log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(message)s',
    handlers=[logging.StreamHandler(), log_handler]
)
logger = logging.getLogger("python-proxy")

stop_event = None
proxy_thread = None
_proxy_port = 1080
_custom_dc_opt = None
_use_doh = False
_auth_creds = None
_mtproto_secret = None
_traffic_limit_mb = 0
_is_wifi = True
_last_heartbeat = 0

def ping():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return True

def set_mtproto_secret(secret):
    """Устанавливает кастомный секрет MTProto (Task 8)"""
    global _mtproto_secret
    if secret and len(secret) == 32:
        _mtproto_secret = secret
        logger.info("Custom MTProto secret set")
        return True
    return False

def on_network_changed(is_wifi):
    global _is_wifi
    _is_wifi = is_wifi
    logger.info(f"Network type changed: {'WiFi' if is_wifi else 'Mobile'}")

def save_daily_stats():
    try:
        stats = get_stats()
        today = str(date.today())
        file_path = os.path.join(os.environ.get("HOME", "."), "daily_stats.json")
        data = {}
        if os.path.exists(file_path):
            with open(file_path, "r") as f: data = json.load(f)
        data[today] = {
            "up": stats.get("bytes_up", 0),
            "down": stats.get("bytes_down", 0),
            "last_update": time.ctime()
        }
        keys = sorted(data.keys())
        if len(keys) > 30:
            for k in keys[:-30]: del data[k]
        with open(file_path, "w") as f: json.dump(data, f)
    except: pass

def start_proxy(host="127.0.0.1", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds, _mtproto_secret
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run(
                port=_proxy_port, dc_opt=dc_opt, stop_event=stop_event, host=host,
                auth_required=_auth_creds is not None, auth_credentials=_auth_creds
            ))
        except Exception:
            write_crash_log(traceback.format_exc())
        finally:
            save_daily_stats()
            loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["port"] = _proxy_port
        stats["last_heartbeat"] = _last_heartbeat
        stats["mtproto_secret_active"] = _mtproto_secret is not None
        if int(time.time()) % 60 == 0: save_daily_stats()
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(os.path.join(os.environ.get("HOME", "."), "crash_log.txt"), "a") as f:
            f.write(f"\n--- CRASH AT {time.ctime()} ---\n{error_msg}\n")
    except: pass
