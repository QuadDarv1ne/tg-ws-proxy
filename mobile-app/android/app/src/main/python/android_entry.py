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
from datetime import date

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy, generate_secret
from proxy.web_dashboard import WebDashboard

FILES_DIR = os.environ.get("HOME", ".")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")
CERT_FILE = os.path.join(FILES_DIR, "custom_cert.pem")

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
_use_custom_ssl = False

def set_custom_certificate(cert_content):
    """Task 8: Установка пользовательского SSL-сертификата"""
    try:
        with open(CERT_FILE, "w") as f:
            f.write(cert_content)
        global _use_custom_ssl
        _use_custom_ssl = True
        logger.info("Custom SSL certificate installed and enabled")
        return True
    except Exception as e:
        logger.error(f"Failed to save certificate: {e}")
        return False

def get_ssl_context():
    """Создает защищенный SSL контекст (Task 8)"""
    ctx = ssl.create_default_context()
    if _use_custom_ssl and os.path.exists(CERT_FILE):
        try:
            ctx.load_verify_locations(CERT_FILE)
            logger.info("Using custom SSL context for WebSocket")
        except Exception as e:
            logger.error(f"Error loading custom cert: {e}")
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    
    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Получаем настроенный SSL контекст (Task 8)
        ssl_ctx = get_ssl_context()
        
        try:
            loop.run_until_complete(_run(
                port=_proxy_port, dc_opt=dc_opt, stop_event=stop_event, 
                host=host, ssl_context=ssl_ctx,
                auth_required=_auth_creds is not None, auth_credentials=_auth_creds
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port, "ssl_custom": _use_custom_ssl}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["ssl_mode"] = "custom" if _use_custom_ssl else "default"
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(os.path.join(FILES_DIR, "crash_log.txt"), "a") as f:
            f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass
