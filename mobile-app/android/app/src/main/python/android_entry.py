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
import zlib
from datetime import date, datetime, timedelta

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy
from proxy.web_dashboard import WebDashboard

try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

# Paths
FILES_DIR = os.environ.get("HOME", ".")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")

# Global state
stop_event = None
proxy_thread = None
_compression_enabled = True # Task 4 Cycle 6

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _compression_enabled
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running"}
    
    stop_event = asyncio.Event()
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Task 4: Передаем флаг сжатия в ядро
            loop.run_until_complete(_run(
                port=port, dc_opt=dc_opt, stop_event=stop_event, host=host,
                use_compression=_compression_enabled
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": port, "compression": _compression_enabled}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["compression_active"] = _compression_enabled
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(os.path.join(FILES_DIR, "crash_log.txt"), "a") as f:
            f.write(f"\n--- CRASH AT {datetime.now().isoformat()} ---\n{error_msg}\n")
    except: pass
