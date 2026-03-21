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
from datetime import date, datetime

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy, generate_secret
from proxy.web_dashboard import WebDashboard

# Paths and constants
FILES_DIR = os.environ.get("HOME", ".")
STATS_FILE = os.path.join(FILES_DIR, "daily_stats.json")
CSV_EXPORT_FILE = os.path.join(FILES_DIR, "traffic_report.csv")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")
PYTHON_DIR = os.path.join(FILES_DIR, "python_updates")
CRASH_LOG = os.path.join(FILES_DIR, "crash_log.txt")

if not os.path.exists(PYTHON_DIR):
    os.makedirs(PYTHON_DIR)

# Logging configuration
log_stream = io.StringIO()
log_handler = logging.StreamHandler(log_stream)
log_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s', datefmt='%H:%M:%S'))

file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s]: %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s: %(message)s',
    handlers=[logging.StreamHandler(), log_handler, file_handler]
)
logger = logging.getLogger("python-proxy")

# Global state
stop_event = None
proxy_thread = None
dashboard_instance = None
_proxy_port = 1080
_mtproto_port = 8888
_mtproto_secrets = []
_speed_limit_kbps = 0
_dashboard_port = 5000
_custom_dc_opt = None
_use_doh = False
_doh_provider = "google"
_auth_creds = None
_traffic_limit_mb = 0
_is_wifi = True
_last_heartbeat = 0
_current_pool_size = WS_POOL_SIZE
_session_id = None
_current_best_dc = 2
_failover_count = 0

async def monitor_best_dc():
    """Dynamic Best DC Selection & Failover (Task 1)"""
    global _current_best_dc, _custom_dc_opt, _failover_count
    while not stop_event or not stop_event.is_set():
        try:
            dcs_to_check = _custom_dc_opt.keys() if _custom_dc_opt else DC_IP_MAP.keys()
            best_latency = float('inf')
            best_id = _current_best_dc
            
            for dc_id in dcs_to_check:
                latency, error = await _measure_dc_ping(dc_id, timeout=2.0)
                if latency and latency < best_latency:
                    best_latency = latency
                    best_id = dc_id
                elif error:
                    logger.debug(f"DC{dc_id} ping failed: {error}")
            
            if best_id != _current_best_dc:
                logger.info(f"Dynamic DC Switch: DC{_current_best_dc} -> DC{best_id} (Ping: {best_latency:.1f}ms)")
                _current_best_dc = best_id
                _failover_count += 1
                
        except Exception as e:
            logger.debug(f"DC Monitoring error: {e}")
        await asyncio.sleep(300)

def log_handshake_step(dc_id, step, success=True, error=None):
    """Advanced Handshake Logging (Task 2)"""
    status = "SUCCESS" if success else f"FAILED: {error}"
    logger.info(f"[HANDSHAKE] DC{dc_id} | {step} | {status}")

def tune_tcp_socket(sock):
    """TCP Tuning for Android (Task 8 Cycle 3)"""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 128 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128 * 1024)
    except:
        pass

def save_daily_stats():
    """Daily Statistics Persistence (Task 5 Cycle 2)"""
    try:
        stats = get_stats()
        today = str(date.today())
        data = {}
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
        
        data[today] = {
            "up": stats.get("bytes_up", 0),
            "down": stats.get("bytes_down", 0),
            "last_update": datetime.now().isoformat()
        }
        
        # Keep last 30 days
        keys = sorted(data.keys())
        if len(keys) > 30:
            for k in keys[:-30]: del data[k]

        with open(STATS_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save daily stats: {e}")

def export_stats_to_csv():
    """Export Daily Stats to CSV (Task 10 Cycle 4)"""
    try:
        if not os.path.exists(STATS_FILE):
            return "No data to export"
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
        with open(CSV_EXPORT_FILE, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Upload (Bytes)", "Download (Bytes)", "Last Update"])
            for day in sorted(data.keys()):
                writer.writerow([day, data[day].get("up", 0), data[day].get("down", 0), data[day].get("last_update", "")])
        return CSV_EXPORT_FILE
    except Exception as e:
        return str(e)

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port, _custom_dc_opt, _auth_creds, dashboard_instance, _session_id
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive():
        return {"status": "Already running", "port": _proxy_port}

    # Dashboard logic
    try:
        if not dashboard_instance:
            dashboard_instance = WebDashboard(get_stats_callback=get_stats, host="0.0.0.0", port=_dashboard_port)
            dashboard_instance.start()
    except Exception as e:
        logger.error(f"Dashboard error: {e}")

    _session_id = int(time.time())
    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(monitor_best_dc())
        
        try:
            loop.run_until_complete(_run(
                port=_proxy_port,
                dc_opt=dc_opt,
                stop_event=stop_event,
                host=host,
                auth_required=_auth_creds is not None,
                auth_credentials=_auth_creds
            ))
        except Exception:
            err = traceback.format_exc()
            logger.error(f"FATAL: {err}")
            write_crash_log(err)
        finally:
            save_daily_stats()
            loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port}

def stop_proxy():
    global stop_event, dashboard_instance
    if stop_event:
        stop_event.set()
    if dashboard_instance:
        dashboard_instance.stop()
        dashboard_instance = None
    return "Stopping"

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["port"] = _proxy_port
        stats["best_dc"] = _current_best_dc
        stats["failover_count"] = _failover_count
        stats["session_id"] = _session_id
        if int(time.time()) % 60 == 0:
            save_daily_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(CRASH_LOG, "a") as f:
            f.write(f"\n--- CRASH AT {datetime.now().isoformat()} ---\n{error_msg}\n")
    except:
        pass

def get_recent_logs(): return log_stream.getvalue()

def get_crash_logs():
    if os.path.exists(CRASH_LOG):
        with open(CRASH_LOG, "r") as f:
            return f.read()
    return "No crashes"

def clear_dns():
    try:
        _clear_dns_cache()
        return True
    except:
        return False

def on_network_changed(is_wifi):
    global _is_wifi, _current_pool_size
    _is_wifi = is_wifi
    _current_pool_size = 6 if is_wifi else 2
    logger.info(f"Network changed: {'WiFi' if is_wifi else 'Mobile'}, Pool Size: {_current_pool_size}")
    return _current_pool_size
