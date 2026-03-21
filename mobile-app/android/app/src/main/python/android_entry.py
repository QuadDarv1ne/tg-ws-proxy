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

def log_handshake_step(dc_id, step, success=True, error=None):
    """Глубокая диагностика рукопожатия (Task 4)"""
    status = "SUCCESS" if success else f"FAILED: {error}"
    logger.info(f"[DIAGNOSTICS] DC{dc_id} Handshake Step: {step} -> {status}")

def ping():
    global _last_heartbeat
    _last_heartbeat = time.time()
    return True

def update_dc_config_remote(url):
    """Task 3 - Background refresh function"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TGWSProxy-Android"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            if "dcs" in data:
                global _custom_dc_opt
                _custom_dc_opt = {int(k): v for k, v in data["dcs"].items()}
                logger.info("DC Config updated from remote source")
                return True
    except Exception as e:
        logger.error(f"Remote update failed: {e}")
    return False

def set_secure_dns(enabled, provider="google"):
    global _use_doh, _doh_provider
    _use_doh = enabled
    if provider in DOH_PROVIDERS: _doh_provider = provider
    return True

def start_proxy(host="127.0.0.1", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds
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
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        crash_file = os.path.join(os.environ.get("HOME", "."), "crash_log.txt")
        with open(crash_file, "a") as f: f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass
