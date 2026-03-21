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
from proxy.web_dashboard import WebDashboard

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
dashboard_instance = None
_udp_supported = True
_proxy_port = 1080
_dashboard_port = 5000

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, dashboard_instance, _proxy_port
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running"}
    
    # Task 2 Cycle 6: Start Local PAC Server via Web Dashboard
    try:
        if not dashboard_instance:
            dashboard_instance = WebDashboard(get_stats_callback=get_stats, host="0.0.0.0", port=_dashboard_port)
            
            # Add PAC file route dynamically
            @dashboard_instance.app.route('/proxy.pac')
            def serve_pac():
                pac_content = f'function FindProxyForURL(url, host) {{ return "SOCKS5 {host}:{_proxy_port}; DIRECT"; }}'
                return pac_content, 200, {'Content-Type': 'application/x-ns-proxy-autoconfig'}
            
            dashboard_instance.start()
            logger.info(f"PAC Server active at http://0.0.0.0:{_dashboard_port}/proxy.pac")
    except Exception as e:
        logger.error(f"Failed to start PAC/Dashboard server: {e}")

    stop_event = asyncio.Event()
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run(
                port=port, dc_opt=dc_opt, stop_event=stop_event, host=host,
                udp_enabled=_udp_supported
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": port, "pac_url": f"http://localhost:{_dashboard_port}/proxy.pac"}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["pac_server_active"] = dashboard_instance is not None
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(CRASH_LOG, "a") as f:
            f.write(f"\n--- CRASH AT {datetime.now().isoformat()} ---\n{error_msg}\n")
    except: pass

def get_recent_logs(): return log_stream.getvalue()
def get_crash_logs():
    if os.path.exists(CRASH_LOG):
        with open(CRASH_LOG, "r") as f: return f.read()
    return "No crashes"

def clear_dns():
    try:
        _clear_dns_cache()
        return True
    except: return False
