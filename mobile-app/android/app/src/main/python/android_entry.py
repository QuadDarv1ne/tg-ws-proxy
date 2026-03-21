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
from datetime import date

from proxy.constants import DC_IP_MAP, WS_POOL_SIZE, WS_POOL_MAX_SIZE
from proxy.tg_ws_proxy import _run, get_stats, get_stats_summary, _measure_dc_ping, _clear_dns_cache
from proxy.mtproto_proxy import MTProtoProxy, generate_secret
from proxy.web_dashboard import WebDashboard

FILES_DIR = os.environ.get("HOME", ".")
STATS_FILE = os.path.join(FILES_DIR, "daily_stats.json")
CSV_EXPORT_FILE = os.path.join(FILES_DIR, "traffic_report.csv")

logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')
logger = logging.getLogger("python-proxy")

def export_stats_to_csv():
    """Task 10: Конвертация JSON статистики в CSV для Excel"""
    try:
        if not os.path.exists(STATS_FILE):
            return "No data to export"
            
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            
        with open(CSV_EXPORT_FILE, "w", newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Upload (Bytes)", "Download (Bytes)", "Last Update"])
            
            for day in sorted(data.keys()):
                writer.writerow([
                    day, 
                    data[day].get("up", 0), 
                    data[day].get("down", 0),
                    data[day].get("last_update", "")
                ])
        
        logger.info(f"Stats exported to CSV: {CSV_EXPORT_FILE}")
        return CSV_EXPORT_FILE
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return str(e)

def start_proxy(host="0.0.0.0", port=1080, auto_port=True):
    global stop_event, proxy_thread, _proxy_port
    _proxy_port = port
    if proxy_thread and proxy_thread.is_alive(): return {"status": "Already running"}
    
    stop_event = asyncio.Event()
    dc_opt = {dc_id: ip for dc_id, ip in DC_IP_MAP.items()}

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run(
                port=_proxy_port, dc_opt=dc_opt, stop_event=stop_event, host=host
            ))
        except Exception: write_crash_log(traceback.format_exc())
        finally: loop.close()

    proxy_thread = threading.Thread(target=run_loop, daemon=True)
    proxy_thread.start()
    return {"status": "Started", "port": _proxy_port}

def get_proxy_stats_dict():
    try:
        stats = get_stats()
        stats["is_running"] = proxy_thread is not None and proxy_thread.is_alive()
        stats["csv_available"] = os.path.exists(CSV_EXPORT_FILE)
        return stats
    except Exception as e: return {"error": str(e)}

def write_crash_log(error_msg):
    try:
        with open(os.path.join(FILES_DIR, "crash_log.txt"), "a") as f:
            f.write(f"\n--- CRASH {time.ctime()} ---\n{error_msg}\n")
    except: pass
