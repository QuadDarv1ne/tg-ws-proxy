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

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache

# DoH Providers
DOH_PROVIDERS = {
    "google": "https://dns.google/resolve",
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "quad9": "https://dns.quad9.net/dns-query"
}

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
_doh_provider = "google"
_auth_creds = None
_traffic_limit_mb = 0
_is_wifi = True
_last_heartbeat = 0
_current_pool_size = WS_POOL_SIZE
_session_id = None

def tune_tcp_socket(sock):
    """Низкоуровневая настройка TCP для мобильных сетей (Task 8)"""
    try:
        # Включаем Keep-Alive
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        
        # Настройка параметров Keep-Alive для Android
        # (интервал проверки при простое)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        
        # Увеличиваем буферы для компенсации лагов мобильной сети
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 128 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128 * 1024)
        
        logger.debug("TCP Socket tuned for mobile network")
    except Exception as e:
        logger.error(f"Failed to tune socket: {e}")

def start_session_logging():
    global _session_id
    _session_id = int(time.time())
    logger.info(f"New Proxy Session started: {_session_id}")

def save_session_report():
    try:
        stats = get_stats()
        report = {
            "session_id": _session_id,
            "duration_sec": time.time() - _session_id if _session_id else 0,
            "final_stats": stats,
            "timestamp": time.ctime()
        }
        file_path = os.path.join(os.environ.get("HOME", "."), f"session_{_session_id}.json")
        with open(file_path, "w") as f: json.dump(report, f)
        path = os.environ.get("HOME", ".")
        reports = sorted([f for f in os.listdir(path) if f.startswith("session_")])
        for r in reports[:-5]: os.remove(os.path.join(path, r))
    except: pass

def start_proxy(host="127.0.0.1", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    
    start_session_logging()
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
            save_session_report()
            loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["port"] = _proxy_port
        stats["tcp_tuning"] = True
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        crash_file = os.path.join(os.environ.get("HOME", "."), "crash_log.txt")
        with open(crash_file, "a") as f: f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass
