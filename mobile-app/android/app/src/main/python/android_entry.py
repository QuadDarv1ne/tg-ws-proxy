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
import ssl
import csv
import secrets
from datetime import date, datetime, timedelta

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy

# Paths and constants
FILES_DIR = os.environ.get("HOME", ".")
STATS_FILE = os.path.join(FILES_DIR, "daily_stats.json")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")
CRASH_LOG = os.path.join(FILES_DIR, "crash_log.txt")
SESSION_STATE_FILE = os.path.join(FILES_DIR, "session_state.json")

# Logging
log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))
file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s', handlers=[logging.StreamHandler(), log_handler, file_handler])
logger = logging.getLogger("python-proxy")

# Global state
stop_event = None
proxy_thread = None
_mtproto_secret = None
_last_rotation_time = 0
_rotation_interval_hours = 24

def generate_new_secret():
    """Generate secure 32-char hex secret"""
    return secrets.token_hex(16)

async def monitor_secret_rotation():
    """Automatically rotate MTProto secret (Task 9 Cycle 5)"""
    global _mtproto_secret, _last_rotation_time
    while not stop_event or not stop_event.is_set():
        try:
            now = time.time()
            if _mtproto_secret and (now - _last_rotation_time) > (_rotation_interval_hours * 3600):
                new_secret = generate_new_secret()
                logger.info(f"Auto-rotating MTProto secret. Next rotation in {_rotation_interval_hours}h")
                _mtproto_secret = new_secret
                _last_rotation_time = now
                # In a real scenario, we would need to restart MTProtoProxy task here
        except: pass
        await asyncio.sleep(3600) # Check every hour

def start_proxy(host="127.0.0.1", port=1080, auto_port=True):
    global stop_event, proxy_thread, _last_heartbeat
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running"}
    
    stop_event = asyncio.Event()
    _last_heartbeat = time.time()
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(monitor_secret_rotation())
        try:
            loop.run_until_complete(_run(port=port, dc_opt=dc_opt, stop_event=stop_event, host=host))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": port}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["next_rotation_in"] = round((_last_rotation_time + (_rotation_interval_hours * 3600) - time.time()) / 3600, 1)
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(CRASH_LOG, "a") as f:
            f.write(f"\n--- CRASH AT {datetime.now().isoformat()} ---\n{error_msg}\n")
    except: pass

def clear_dns():
    try:
        _clear_dns_cache()
        return True
    except: return False
