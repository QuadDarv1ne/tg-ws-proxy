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
from proxy.mtproto_proxy import MTProtoProxy, generate_secret
from proxy.web_dashboard import WebDashboard

try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

# Paths and constants
FILES_DIR = os.environ.get("HOME", ".")
STATS_FILE = os.path.join(FILES_DIR, "daily_stats.json")
CSV_EXPORT_FILE = os.path.join(FILES_DIR, "traffic_report.csv")
LOG_FILE = os.path.join(FILES_DIR, "proxy_persistent.log")
PYTHON_DIR = os.path.join(FILES_DIR, "python_updates")
CRASH_LOG = os.path.join(FILES_DIR, "crash_log.txt")
SESSION_STATE_FILE = os.path.join(FILES_DIR, "session_state.json")

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
zc_instance = None
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
_use_ipv6 = True
_udp_supported = True
_compression_enabled = True
_speed_history_up = []
_speed_history_down = []
_last_bytes_up = 0
_last_bytes_down = 0

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def register_zeroconf(port):
    if not HAS_ZEROCONF: return None
    try:
        local_ip = get_local_ip()
        info = ServiceInfo(
            "_socks5._tcp.local.",
            f"TG WS Proxy ({socket.gethostname()})._socks5._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={'version': '2.10.0', 'vendor': 'Dupley'},
            server=f"{socket.gethostname()}.local.",
        )
        zc = Zeroconf(ip_version=IPVersion.V4Only)
        zc.register_service(info)
        logger.info(f"mDNS: Service registered on {local_ip}:{port}")
        return zc
    except Exception as e:
        logger.error(f"Zeroconf registration failed: {e}")
        return None

async def monitor_best_dc():
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
            if best_id != _current_best_dc:
                logger.info(f"DC Switch: DC{_current_best_dc} -> DC{best_id} ({best_latency:.1f}ms)")
                _current_best_dc = best_id
                _failover_count += 1
                save_session_state()
        except: pass
        await asyncio.sleep(300)

async def monitor_speed():
    global _last_bytes_up, _last_bytes_down, _speed_history_up, _speed_history_down
    while not stop_event or not stop_event.is_set():
        try:
            stats = get_stats()
            curr_up = stats.get("bytes_up", 0)
            curr_down = stats.get("bytes_down", 0)
            _speed_history_up.append(round((curr_up - _last_bytes_up) / 1024, 1))
            _speed_history_down.append(round((curr_down - _last_bytes_down) / 1024, 1))
            if len(_speed_history_up) > 60:
                _speed_history_up.pop(0)
                _speed_history_down.pop(0)
            _last_bytes_up, _last_bytes_down = curr_up, curr_down
        except: pass
        await asyncio.sleep(1)

def tune_tcp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"): sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 128 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 128 * 1024)
    except: pass

def save_daily_stats():
    try:
        stats = get_stats()
        today = str(date.today())
        data = {}
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r") as f: data = json.load(f)
        data[today] = {"up": stats.get("bytes_up", 0), "down": stats.get("bytes_down", 0), "last_update": datetime.now().isoformat()}
        keys = sorted(data.keys())
        if len(keys) > 30:
            for k in keys[:-30]: del data[k]
        with open(STATS_FILE, "w") as f: json.dump(data, f)
    except: pass

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, dashboard_instance, zc_instance, _proxy_port
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running", "port": _proxy_port}
    
    zc_instance = register_zeroconf(port)
    try:
        if not dashboard_instance:
            dashboard_instance = WebDashboard(get_stats_callback=get_stats, host="0.0.0.0", port=_dashboard_port)
            @dashboard_instance.app.route('/proxy.pac')
            def serve_pac():
                return f'function FindProxyForURL(url, host) {{ return "SOCKS5 {get_local_ip()}:{_proxy_port}; DIRECT"; }}', 200, {'Content-Type': 'application/x-ns-proxy-autoconfig'}
            dashboard_instance.start()
    except: pass

    _session_id = int(time.time())
    stop_event = asyncio.Event()
    dc_opt = _custom_dc_opt if _custom_dc_opt else {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(monitor_best_dc())
        loop.create_task(monitor_speed())
        try:
            loop.run_until_complete(_run(
                port=port, dc_opt=dc_opt, stop_event=stop_event, host="::" if _use_ipv6 else host,
                auth_required=_auth_creds is not None, auth_credentials=_auth_creds,
                udp_enabled=_udp_supported, use_compression=_compression_enabled
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally:
            save_daily_stats()
            loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": port}

def stop_proxy():
    global stop_event, dashboard_instance, zc_instance
    if stop_event: stop_event.set()
    if dashboard_instance: dashboard_instance.stop(); dashboard_instance = None
    if zc_instance: zc_instance.unregister_all_services(); zc_instance.close(); zc_instance = None
    return "Stopping"

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats.update({"is_running": proxy_thread is not None and proxy_thread.is_alive(), "port": _proxy_port, "best_dc": _current_best_dc, "speed_up": _speed_history_up, "speed_down": _speed_history_down})
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(CRASH_LOG, "a") as f: f.write(f"\n--- CRASH AT {datetime.now().isoformat()} ---\n{error_msg}\n")
    except: pass

def get_recent_logs(): return log_stream.getvalue()
def get_crash_logs():
    if os.path.exists(CRASH_LOG):
        with open(CRASH_LOG, "r") as f: return f.read()
    return "No crashes"

def clear_dns():
    try: _clear_dns_cache(); return True
    except: return False

def on_network_changed(is_wifi):
    global _is_wifi; _is_wifi = is_wifi
    return 6 if is_wifi else 2

def save_session_state():
    try:
        with open(SESSION_STATE_FILE, "w") as f: json.dump({"best_dc": _current_best_dc, "failover_count": _failover_count}, f)
    except: pass

def load_session_state():
    global _current_best_dc, _failover_count
    try:
        if os.path.exists(SESSION_STATE_FILE):
            with open(SESSION_STATE_FILE, "r") as f:
                state = json.load(f)
                _current_best_dc, _failover_count = state.get("best_dc", 2), state.get("failover_count", 0)
    except: pass
